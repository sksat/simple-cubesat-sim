"""Simulation engine for CubeSat simulator.

Manages simulation time, state, and provides telemetry.
"""

import numpy as np
from numpy.typing import NDArray
from enum import Enum, auto
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal

from backend.config import Config, get_config
from backend.simulation.spacecraft import Spacecraft
from backend.dynamics.orbit import OrbitPropagator


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

        # SGP4 orbit propagator
        self._orbit_propagator = OrbitPropagator()
        self._sim_epoch = datetime.now(timezone.utc)

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

    def get_absolute_time(self) -> datetime:
        """Get current absolute simulation time.

        Returns:
            Absolute UTC datetime corresponding to current simulation time
        """
        return self._sim_epoch + timedelta(seconds=self.sim_time)

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

    def set_tle(self, line1: str, line2: str) -> None:
        """Set TLE for orbit propagation.

        Args:
            line1: First line of TLE
            line2: Second line of TLE

        Raises:
            ValueError: If TLE is invalid
        """
        self._orbit_propagator.set_tle(line1, line2)
        # Reset simulation epoch when TLE changes
        self._sim_epoch = datetime.now(timezone.utc)

    def get_tle(self) -> dict:
        """Get current TLE data.

        Returns:
            Dictionary with TLE lines and orbital parameters
        """
        return {
            "line1": self._orbit_propagator.tle_line1,
            "line2": self._orbit_propagator.tle_line2,
            "inclination": self._orbit_propagator.inclination,
            "period": self._orbit_propagator.period,
        }

    def get_orbit_position(self) -> dict:
        """Calculate current orbit position using SGP4.

        Returns:
            Dictionary with latitude, longitude, altitude, and orbit parameters
        """
        # Propagate orbit using SGP4
        orbit_state = self._orbit_propagator.propagate(self.sim_time, self._sim_epoch)

        latitude = orbit_state.latitude
        longitude = orbit_state.longitude
        altitude = orbit_state.altitude

        # Get orbital parameters from propagator
        inclination = self._orbit_propagator.inclination
        period = self._orbit_propagator.period

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
            "absoluteTime": self.get_absolute_time().isoformat(),
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
                "sunDirection": self._get_sun_direction(),
            },

            "orbit": self.get_orbit_position(),
        }

    def _get_sun_direction(self) -> list[float]:
        """Get current sun direction in Three.js scene coordinates.

        Uses simulation absolute time for accurate sun position.

        Returns:
            [x, y, z] unit vector pointing toward the Sun
        """
        from astropy.time import Time
        from backend.utils.coordinates import get_sun_direction_threejs

        # Use simulation absolute time for sun position calculation
        sim_time = Time(self.get_absolute_time())
        sun_dir = get_sun_direction_threejs(sim_time)
        return list(sun_dir)
