"""Simulation engine for CubeSat simulator.

Manages simulation time, state, and provides telemetry.
"""

import numpy as np
from numpy.typing import NDArray
from enum import Enum, auto
from typing import Optional, Literal

from backend.simulation.spacecraft import Spacecraft


class SimulationState(Enum):
    """Simulation state enumeration."""
    STOPPED = auto()
    RUNNING = auto()
    PAUSED = auto()


class SimulationEngine:
    """Main simulation engine.

    Manages the simulation loop, time advancement, and telemetry generation.

    Attributes:
        dt: Base time step (seconds)
        time_warp: Time scaling factor (1.0 = real-time)
        sim_time: Current simulation time (seconds)
        state: Current simulation state
        spacecraft: The spacecraft being simulated
    """

    def __init__(
        self,
        dt: float = 0.1,
        time_warp: float = 1.0,
    ):
        """Initialize simulation engine.

        Args:
            dt: Base time step in seconds
            time_warp: Time scaling factor (1.0 = real-time)
        """
        self.dt = dt
        self._time_warp = time_warp
        self.sim_time = 0.0
        self.state = SimulationState.STOPPED

        # Initial tumbling state (typical post-deployment)
        # About 100 deg/s tumble rate for visible B-dot detumbling effect
        # Convergence expected over multiple orbits (1 orbit ≈ 90 min at 600km)
        initial_omega = np.array([1.0, 1.2, -0.8])  # rad/s (~57-69 deg/s per axis, |ω|≈100 deg/s)

        # Create spacecraft with initial tumbling
        self.spacecraft = Spacecraft(angular_velocity=initial_omega)

        # Magnetic field model (simplified - constant inertial field)
        # In a full implementation, this would use IGRF or similar
        self._magnetic_field_inertial = np.array([30e-6, 20e-6, 10e-6])  # T

    @property
    def time_warp(self) -> float:
        """Get current time warp factor."""
        return self._time_warp

    def set_time_warp(self, time_warp: float) -> None:
        """Set time warp factor.

        Args:
            time_warp: Time scaling factor (must be positive)

        Raises:
            ValueError: If time_warp is not positive
        """
        if time_warp <= 0:
            raise ValueError("time_warp must be positive")
        self._time_warp = time_warp

    def start(self) -> None:
        """Start or resume simulation."""
        self.state = SimulationState.RUNNING

    def pause(self) -> None:
        """Pause simulation."""
        if self.state == SimulationState.RUNNING:
            self.state = SimulationState.PAUSED

    def stop(self) -> None:
        """Stop simulation."""
        self.state = SimulationState.STOPPED

    def reset(self) -> None:
        """Reset simulation to initial state."""
        self.sim_time = 0.0
        self.state = SimulationState.STOPPED
        self.spacecraft.reset()

    def step(self) -> None:
        """Advance simulation by one time step.

        Only advances if the simulation is running.
        Uses sub-stepping for high time warp to maintain physics accuracy.
        """
        if self.state != SimulationState.RUNNING:
            return

        # Calculate effective time step
        effective_dt = self.dt * self._time_warp

        # Maximum physics dt to maintain accuracy (especially for B-dot)
        max_physics_dt = 0.1  # seconds

        # Get magnetic field (constant during this macro step)
        b_field_inertial = self.get_magnetic_field()

        # Sub-step if effective_dt is too large
        remaining_dt = effective_dt
        while remaining_dt > 0:
            physics_dt = min(remaining_dt, max_physics_dt)

            # Step spacecraft
            self.spacecraft.step(
                dt=physics_dt,
                magnetic_field_inertial=b_field_inertial,
            )

            remaining_dt -= physics_dt

        # Update simulation time
        self.sim_time += effective_dt

    def get_magnetic_field(self) -> NDArray[np.float64]:
        """Get current magnetic field in inertial frame.

        Returns:
            Magnetic field vector in inertial frame (T)
        """
        # For now, return a constant field
        # In a full implementation, this would:
        # 1. Get spacecraft position from orbit propagator
        # 2. Calculate magnetic field using IGRF model
        return self._magnetic_field_inertial.copy()

    def set_control_mode(
        self,
        mode: Literal["IDLE", "DETUMBLING", "POINTING", "UNLOADING"],
    ) -> None:
        """Set spacecraft control mode.

        Args:
            mode: Control mode
        """
        self.spacecraft.set_control_mode(mode)

    def set_target_attitude(self, quaternion: NDArray[np.float64]) -> None:
        """Set target attitude for pointing mode.

        Args:
            quaternion: Target quaternion [x, y, z, w]
        """
        self.spacecraft.set_target_attitude(quaternion)

    def get_telemetry(self) -> dict:
        """Get current telemetry data.

        Returns:
            Dictionary containing all telemetry data
        """
        sc_state = self.spacecraft.get_state()

        # Convert angular velocity to list for JSON serialization
        omega = self.spacecraft.angular_velocity

        # Calculate Euler angles from quaternion
        from backend.dynamics.quaternion import to_euler
        euler = to_euler(self.spacecraft.quaternion)

        return {
            "timestamp": self.sim_time,
            "state": self.state.name,
            "timeWarp": self._time_warp,

            "attitude": {
                "quaternion": self.spacecraft.quaternion.tolist(),
                "angularVelocity": omega.tolist(),
                "eulerAngles": np.degrees(euler).tolist(),
            },

            "actuators": {
                "reactionWheels": {
                    "speed": self.spacecraft.reaction_wheel.get_speed().tolist(),
                    "torque": self.spacecraft.reaction_wheel.get_commanded_torque().tolist(),
                    "momentum": self.spacecraft.reaction_wheel.get_momentum().tolist(),
                },
                "magnetorquers": {
                    "dipoleMoment": self.spacecraft.magnetorquer.get_dipole().tolist(),
                    "power": self.spacecraft.magnetorquer.get_power(),
                },
            },

            "control": {
                "mode": self.spacecraft.control_mode,
                "targetQuaternion": sc_state["target_quaternion"].tolist(),
                "error": {
                    "attitude": self.spacecraft.get_attitude_error(),
                    "rate": float(np.linalg.norm(omega)),
                },
            },

            "environment": {
                "magneticField": self._magnetic_field_inertial.tolist(),
            },
        }
