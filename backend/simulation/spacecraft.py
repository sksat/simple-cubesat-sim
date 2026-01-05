"""6U CubeSat spacecraft model.

Integrates attitude dynamics, actuators, and control algorithms.
"""

import numpy as np
from numpy.typing import NDArray
from typing import Optional, Literal

from backend.actuators.magnetorquer import Magnetorquer
from backend.actuators.reaction_wheel import ReactionWheel
from backend.control.bdot import BdotController
from backend.control.attitude_controller import AttitudeController
from backend.control.rw_unloading import RWUnloadingController
from backend.dynamics.quaternion import multiply, normalize, rotate_vector, conjugate


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
        rw_inertia: float = 1e-4,
        rw_max_speed: float = 628.3,  # ~6000 RPM
        rw_max_torque: float = 0.001,
        mtq_max_dipole: float = 0.2,
    ):
        """Initialize spacecraft.

        Args:
            quaternion: Initial attitude quaternion [x, y, z, w]
            angular_velocity: Initial angular velocity (rad/s)
            inertia: Inertia tensor (kg*m^2)
            rw_inertia: Reaction wheel inertia per axis
            rw_max_speed: RW maximum speed (rad/s)
            rw_max_torque: RW maximum torque (Nm)
            mtq_max_dipole: MTQ maximum dipole moment (Am^2)
        """
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

        # Inertia tensor (default: 6U CubeSat)
        if inertia is not None:
            self.inertia = inertia.copy()
        else:
            self.inertia = np.diag([0.05, 0.05, 0.02])

        self.inertia_inv = np.linalg.inv(self.inertia)

        # Actuators
        self.reaction_wheel = ReactionWheel(
            inertia=rw_inertia,
            max_speed=rw_max_speed,
            max_torque=rw_max_torque,
        )
        self.magnetorquer = Magnetorquer(max_dipole=mtq_max_dipole)

        # Controllers
        self._bdot_controller = BdotController(gain=1e6, max_dipole=mtq_max_dipole)
        self._attitude_controller = AttitudeController(
            kp=0.01, kd=0.1, max_torque=rw_max_torque
        )
        self._unloading_controller = RWUnloadingController(
            gain=1e4, max_dipole=mtq_max_dipole
        )

        # Control mode
        self._control_mode: ControlMode = "IDLE"
        self._target_quaternion = np.array([0.0, 0.0, 0.0, 1.0])

        # Previous magnetic field for B-dot calculation
        self._prev_b_field: Optional[NDArray[np.float64]] = None

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
    ) -> None:
        """Advance simulation by one time step.

        Args:
            dt: Time step (seconds)
            magnetic_field: Magnetic field in body frame (T) - deprecated
            magnetic_field_inertial: Magnetic field in inertial frame (T)

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

        # Euler's equation: I * omega_dot = T - omega x (I * omega)
        # For simplicity, using basic Euler integration
        omega_cross_I_omega = np.cross(
            self.angular_velocity, self.inertia @ self.angular_velocity
        )
        omega_dot = self.inertia_inv @ (total_torque - omega_cross_I_omega)
        self.angular_velocity = self.angular_velocity + omega_dot * dt

        # Quaternion kinematic equation: q_dot = 0.5 * q * [omega, 0]
        omega_quat = np.array([
            self.angular_velocity[0],
            self.angular_velocity[1],
            self.angular_velocity[2],
            0.0
        ])
        q_dot = 0.5 * multiply(self.quaternion, omega_quat)
        self.quaternion = normalize(self.quaternion + q_dot * dt)

        # Store magnetic field for next step
        self._prev_b_field = magnetic_field.copy()

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

            # Zero MTQ
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
        }

    def reset(self) -> None:
        """Reset spacecraft to initial state."""
        self.quaternion = self._initial_quaternion.copy()
        self.angular_velocity = self._initial_angular_velocity.copy()
        self.reaction_wheel.reset()
        self.magnetorquer.reset()
        self._control_mode = "IDLE"
        self._prev_b_field = None
