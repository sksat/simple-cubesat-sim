"""Simulation engine for CubeSat simulator.

Manages simulation time, state, and provides telemetry.
"""

import numpy as np
from numpy.typing import NDArray
from enum import Enum, auto
from typing import Optional, Literal

from backend.config import Config, get_config
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
        dt: Optional[float] = None,
        time_warp: Optional[float] = None,
        config: Optional[Config] = None,
    ):
        """Initialize simulation engine.

        Args:
            dt: Base time step in seconds (overrides config)
            time_warp: Time scaling factor (overrides config)
            config: Configuration object (uses global config if None)
        """
        if config is None:
            config = get_config()

        sim_cfg = config.simulation

        self.dt = dt if dt is not None else sim_cfg.dt
        self._time_warp = time_warp if time_warp is not None else sim_cfg.time_warp
        self.sim_time = 0.0
        self.state = SimulationState.STOPPED

        # Initial tumbling state from config
        initial_omega = np.array(sim_cfg.initial_angular_velocity)

        # Create spacecraft with initial tumbling
        self.spacecraft = Spacecraft(angular_velocity=initial_omega, config=config)

        # Magnetic field from config (simplified - constant inertial field)
        self._magnetic_field_inertial = np.array(sim_cfg.magnetic_field)

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

    def get_orbit_position(self) -> dict:
        """Calculate current orbit position (simplified circular orbit).

        Returns:
            Dictionary with latitude, longitude, altitude, and orbit parameters
        """
        config = get_config()
        orbit = config.simulation.orbit

        # Orbital parameters
        period = orbit.period
        inclination = orbit.inclination
        inclination_rad = np.radians(inclination)
        altitude = orbit.altitude
        initial_lon = orbit.initial_longitude

        # Mean anomaly (angle along orbit from ascending node)
        mean_anomaly = (2 * np.pi * self.sim_time / period) % (2 * np.pi)

        # Latitude oscillates between +/- inclination
        # For SSO (retrograde), inclination > 90°, so we use sin(180° - i)
        effective_inc = inclination_rad if inclination_rad <= np.pi / 2 else np.pi - inclination_rad
        latitude = np.degrees(np.arcsin(np.sin(effective_inc) * np.sin(mean_anomaly)))

        # Longitude calculation for ground track
        # Earth rotates 360°/86400s = 0.00417°/s eastward
        earth_rotation_rate = 360.0 / 86400.0  # deg/s

        # Orbital longitude progression
        if abs(np.cos(mean_anomaly)) > 1e-10:
            orbit_lon = np.degrees(
                np.arctan2(
                    np.cos(inclination_rad) * np.sin(mean_anomaly),
                    np.cos(mean_anomaly)
                )
            )
        else:
            orbit_lon = 90.0 if np.sin(mean_anomaly) > 0 else -90.0

        # Ground track longitude (subtract Earth rotation)
        longitude = initial_lon + orbit_lon - earth_rotation_rate * self.sim_time

        # Normalize to [-180, 180]
        longitude = ((longitude + 180) % 360) - 180

        # Calculate ECEF and Three.js coordinates using Astropy
        from backend.utils.coordinates import geodetic_to_ecef, geodetic_to_threejs

        ecef = geodetic_to_ecef(latitude, longitude, altitude)
        threejs = geodetic_to_threejs(latitude, longitude, altitude)

        return {
            "latitude": float(latitude),
            "longitude": float(longitude),
            "altitude": float(altitude),
            "inclination": float(inclination),
            "period": float(period),
            "positionECEF": list(ecef),
            "positionThreeJS": list(threejs),
        }

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

            "orbit": self.get_orbit_position(),
        }
