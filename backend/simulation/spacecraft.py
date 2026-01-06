"""6U CubeSat spacecraft model.

Integrates attitude dynamics, actuators, and control algorithms.
"""

import numpy as np
from numpy.typing import NDArray
from typing import Optional, Literal

from backend.actuators.magnetorquer import Magnetorquer
from backend.actuators.reaction_wheel import ReactionWheel
from backend.config import Config, get_config
from backend.control.bdot import BdotController
from backend.control.attitude_controller import AttitudeController
from backend.control.rw_unloading import RWUnloadingController
from backend.control.auto_unloading import AutoUnloadingController
from backend.dynamics.quaternion import multiply, normalize, rotate_vector, conjugate
from backend.power import PowerSystem


ControlMode = Literal["IDLE", "DETUMBLING", "POINTING", "UNLOADING"]


class Spacecraft:
    """6U CubeSat spacecraft model.

    Attributes:
        quaternion: Attitude quaternion [x, y, z, w]
        angular_velocity: Angular velocity in body frame (rad/s)
        inertia: Inertia tensor (kg*m^2)
        reaction_wheel: Reaction wheel assembly
        magnetorquer: Magnetorquer assembly
    """

    def __init__(
        self,
        quaternion: Optional[NDArray[np.float64]] = None,
        angular_velocity: Optional[NDArray[np.float64]] = None,
        inertia: Optional[NDArray[np.float64]] = None,
        config: Optional[Config] = None,
    ):
        """Initialize spacecraft.

        Args:
            quaternion: Initial attitude quaternion [x, y, z, w]
            angular_velocity: Initial angular velocity (rad/s)
            inertia: Inertia tensor (overrides config if provided)
            config: Configuration object (uses global config if None)
        """
        if config is None:
            config = get_config()

        sc_cfg = config.spacecraft
        ctrl_cfg = config.control

        # Store initial conditions for reset
        self._initial_quaternion = (
            quaternion.copy() if quaternion is not None
            else np.array([0.0, 0.0, 0.0, 1.0])
        )
        self._initial_angular_velocity = (
            angular_velocity.copy() if angular_velocity is not None
            else np.array([0.0, 0.0, 0.0])
        )

        # Current state
        self.quaternion = self._initial_quaternion.copy()
        self.angular_velocity = self._initial_angular_velocity.copy()

        # Inertia tensor (override or from config)
        if inertia is not None:
            self.inertia = inertia.copy()
        else:
            self.inertia = np.diag([sc_cfg.inertia_xx, sc_cfg.inertia_yy, sc_cfg.inertia_zz])
        self.inertia_inv = np.linalg.inv(self.inertia)

        # Actuators from config
        rw_cfg = sc_cfg.reaction_wheel
        mtq_cfg = sc_cfg.magnetorquer

        self.reaction_wheel = ReactionWheel(
            inertia=rw_cfg.inertia,
            max_speed=rw_cfg.max_speed,
            max_torque=rw_cfg.max_torque,
        )
        self.magnetorquer = Magnetorquer(max_dipole=mtq_cfg.max_dipole)

        # Controllers from config
        self._bdot_controller = BdotController(
            gain=ctrl_cfg.bdot_gain, max_dipole=mtq_cfg.max_dipole
        )
        self._attitude_controller = AttitudeController(
            kp=ctrl_cfg.attitude_kp, kd=ctrl_cfg.attitude_kd, max_torque=rw_cfg.max_torque
        )
        self._unloading_controller = RWUnloadingController(
            gain=ctrl_cfg.unloading_gain, max_dipole=mtq_cfg.max_dipole
        )

        # Automatic unloading controller
        # Uses 80% of max_speed as thresholds
        max_speed = rw_cfg.max_speed
        self._auto_unloading = AutoUnloadingController(
            upper_threshold=np.array([0.8 * max_speed] * 3),
            lower_threshold=np.array([-0.8 * max_speed] * 3),
            target_speed=np.zeros(3),
            control_gain=-1e-3,  # Negative gain to oppose speed (stronger)
        )

        # Control mode
        self._control_mode: ControlMode = "IDLE"
        self._target_quaternion = np.array([0.0, 0.0, 0.0, 1.0])

        # Previous magnetic field for B-dot calculation
        self._prev_b_field: Optional[NDArray[np.float64]] = None

        # Power system
        self.power_system = PowerSystem()

    @property
    def control_mode(self) -> ControlMode:
        """Get current control mode."""
        return self._control_mode

    def set_control_mode(self, mode: ControlMode) -> None:
        """Set control mode.

        Args:
            mode: Control mode ("IDLE", "DETUMBLING", "POINTING", "UNLOADING")
        """
        self._control_mode = mode

    def set_target_attitude(self, quaternion: NDArray[np.float64]) -> None:
        """Set target attitude for pointing mode.

        Args:
            quaternion: Target quaternion [x, y, z, w]
        """
        self._target_quaternion = normalize(quaternion)

    def get_attitude_error(self) -> float:
        """Get attitude error in degrees.

        Returns:
            Error angle in degrees
        """
        return self._attitude_controller.get_error_angle(
            self.quaternion, self._target_quaternion
        )

    def get_total_angular_momentum(self) -> NDArray[np.float64]:
        """Get total angular momentum (spacecraft + RW).

        L_total = I_sc * omega_sc + H_rw

        Returns:
            Total angular momentum vector (Nms)
        """
        L_sc = self.inertia @ self.angular_velocity
        H_rw = self.reaction_wheel.get_momentum()
        return L_sc + H_rw

    def step(
        self,
        dt: float,
        magnetic_field: Optional[NDArray[np.float64]] = None,
        magnetic_field_inertial: Optional[NDArray[np.float64]] = None,
        sun_direction_inertial: Optional[NDArray[np.float64]] = None,
        is_illuminated: bool = True,
    ) -> None:
        """Advance simulation by one time step.

        Args:
            dt: Time step (seconds)
            magnetic_field: Magnetic field in body frame (T) - deprecated
            magnetic_field_inertial: Magnetic field in inertial frame (T)
            sun_direction_inertial: Sun direction unit vector in inertial frame
            is_illuminated: True if satellite is not in eclipse

        If magnetic_field_inertial is provided, it will be transformed to
        body frame using the current attitude. This is the preferred method
        as it correctly computes B-dot for detumbling.
        """
        # Transform inertial field to body frame, or use provided body field
        if magnetic_field_inertial is not None:
            # Transform from inertial to body: v_body = q_conj * v_inertial * q
            # Using rotate_vector with conjugate quaternion
            q_conj = conjugate(self.quaternion)
            magnetic_field = rotate_vector(q_conj, magnetic_field_inertial)
        elif magnetic_field is None:
            magnetic_field = np.array([0.0, 0.0, 0.0])

        # Run control algorithm based on mode
        self._run_control(dt, magnetic_field)

        # Update actuators
        self.reaction_wheel.update(dt)

        # Calculate total external torque
        torque_mtq = self.magnetorquer.compute_torque(magnetic_field)
        torque_rw = self.reaction_wheel.get_torque_on_spacecraft()
        total_torque = torque_mtq + torque_rw

        # RK4 integration for attitude dynamics
        self._integrate_rk4(dt, total_torque)

        # Store magnetic field for next step
        self._prev_b_field = magnetic_field.copy()

        # Update power system
        if sun_direction_inertial is not None:
            # Transform sun direction to body frame
            q_conj = conjugate(self.quaternion)
            sun_direction_body = rotate_vector(q_conj, sun_direction_inertial)
        else:
            # Default: sun in +Z body direction
            sun_direction_body = np.array([0.0, 0.0, 1.0])

        # Calculate additional power consumption based on control mode
        additional_power = 0.0
        if self._control_mode in ("DETUMBLING", "UNLOADING"):
            additional_power += self.magnetorquer.get_power()
        if self._control_mode in ("POINTING", "UNLOADING"):
            additional_power += 0.5  # RW power consumption estimate

        self.power_system.update(
            dt=dt,
            sun_direction_body=sun_direction_body,
            is_illuminated=is_illuminated,
            additional_consumption=additional_power,
        )

    def _integrate_rk4(
        self,
        dt: float,
        torque: NDArray[np.float64],
    ) -> None:
        """Integrate attitude dynamics using RK4 method.

        Integrates both Euler equation (angular velocity) and
        quaternion kinematics simultaneously.

        Args:
            dt: Time step (seconds)
            torque: External torque vector (Nm)
        """
        def omega_dot(omega: NDArray[np.float64]) -> NDArray[np.float64]:
            """Compute angular acceleration from Euler equation."""
            omega_cross_I_omega = np.cross(omega, self.inertia @ omega)
            return self.inertia_inv @ (torque - omega_cross_I_omega)

        def q_dot(q: NDArray[np.float64], omega: NDArray[np.float64]) -> NDArray[np.float64]:
            """Compute quaternion derivative from kinematics."""
            omega_quat = np.array([omega[0], omega[1], omega[2], 0.0])
            return 0.5 * multiply(q, omega_quat)

        # Current state
        omega0 = self.angular_velocity
        q0 = self.quaternion

        # RK4 for angular velocity
        k1_omega = omega_dot(omega0)
        k1_q = q_dot(q0, omega0)

        omega1 = omega0 + 0.5 * dt * k1_omega
        q1 = normalize(q0 + 0.5 * dt * k1_q)
        k2_omega = omega_dot(omega1)
        k2_q = q_dot(q1, omega1)

        omega2 = omega0 + 0.5 * dt * k2_omega
        q2 = normalize(q0 + 0.5 * dt * k2_q)
        k3_omega = omega_dot(omega2)
        k3_q = q_dot(q2, omega2)

        omega3 = omega0 + dt * k3_omega
        q3 = normalize(q0 + dt * k3_q)
        k4_omega = omega_dot(omega3)
        k4_q = q_dot(q3, omega3)

        # Update state
        self.angular_velocity = omega0 + (dt / 6.0) * (k1_omega + 2*k2_omega + 2*k3_omega + k4_omega)
        self.quaternion = normalize(q0 + (dt / 6.0) * (k1_q + 2*k2_q + 2*k3_q + k4_q))

    def _run_control(
        self,
        dt: float,
        magnetic_field: NDArray[np.float64],
    ) -> None:
        """Run control algorithm based on current mode.

        Args:
            dt: Time step (seconds)
            magnetic_field: Magnetic field in body frame (T)
        """
        if self._control_mode == "IDLE":
            # No control commands
            self.magnetorquer.command(np.array([0.0, 0.0, 0.0]))
            self.reaction_wheel.command_torque(np.array([0.0, 0.0, 0.0]))

        elif self._control_mode == "DETUMBLING":
            # B-dot control using MTQ
            if self._prev_b_field is not None:
                b_dot = (magnetic_field - self._prev_b_field) / dt
                dipole = self._bdot_controller.compute(b_dot)
                self.magnetorquer.command(dipole)

            # Zero RW torque
            self.reaction_wheel.command_torque(np.array([0.0, 0.0, 0.0]))

        elif self._control_mode == "POINTING":
            # Attitude control using RW
            torque = self._attitude_controller.compute(
                self.quaternion, self._target_quaternion, self.angular_velocity
            )
            # Controller outputs spacecraft torque, RW needs negative
            self.reaction_wheel.command_torque(-torque)

            # Automatic unloading (c2a-aobc style)
            # Check if any RW needs unloading and apply MTQ if needed
            rw_speed = self.reaction_wheel.get_speed()
            self._auto_unloading.update_state(rw_speed)

            if self._auto_unloading.is_active():
                # Use momentum-based unloading (more effective than torque-based)
                # Only unload axes that need it (selective unloading)
                h_rw = self.reaction_wheel.get_momentum()

                # Zero out momentum for axes not needing unloading
                h_unload = np.zeros(3)
                for i in range(3):
                    from backend.control.auto_unloading import UnloadingState
                    if self._auto_unloading.state[i] != UnloadingState.OFF:
                        h_unload[i] = h_rw[i]

                # Apply standard unloading law to selected momentum
                dipole = self._unloading_controller.compute(h_unload, magnetic_field)
                self.magnetorquer.command(dipole)
            else:
                # No unloading needed
                self.magnetorquer.command(np.array([0.0, 0.0, 0.0]))

        elif self._control_mode == "UNLOADING":
            # RW momentum unloading using MTQ
            h_rw = self.reaction_wheel.get_momentum()
            dipole = self._unloading_controller.compute(h_rw, magnetic_field)
            self.magnetorquer.command(dipole)

            # Also run attitude control
            torque = self._attitude_controller.compute(
                self.quaternion, self._target_quaternion, self.angular_velocity
            )
            self.reaction_wheel.command_torque(-torque)

    def get_state(self) -> dict:
        """Get complete spacecraft state.

        Returns:
            State dictionary
        """
        return {
            "quaternion": self.quaternion.copy(),
            "angular_velocity": self.angular_velocity.copy(),
            "reaction_wheel": self.reaction_wheel.get_state(),
            "magnetorquer": self.magnetorquer.get_state(),
            "control_mode": self._control_mode,
            "target_quaternion": self._target_quaternion.copy(),
            "power": self.power_system.get_state(),
        }

    def reset(self) -> None:
        """Reset spacecraft to initial state."""
        self.quaternion = self._initial_quaternion.copy()
        self.angular_velocity = self._initial_angular_velocity.copy()
        self.reaction_wheel.reset()
        self.magnetorquer.reset()
        self.power_system.reset()
        self._control_mode = "IDLE"
        self._prev_b_field = None
