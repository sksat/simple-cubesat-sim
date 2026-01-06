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
from backend.power import is_in_eclipse
from backend.control.attitude_target import (
    AttitudeTargetCalculator,
    PointingConfig,
    sun_pointing_config,
    nadir_pointing_config,
    ground_station_pointing_config,
    imaging_target_pointing_config,
)
from backend.control.target_direction import (
    TargetDirection,
    GroundStation,
    ImagingTarget,
    MAKINOHARA,
    is_ground_station_visible,
)


# Pointing mode types
PointingMode = Literal[
    "MANUAL",       # Use manually set quaternion
    "SUN",          # Sun pointing (+Z toward sun)
    "NADIR",        # Nadir pointing (-Z toward Earth)
    "GROUND_STATION",  # Point toward ground station
    "IMAGING_TARGET",  # Point toward imaging target
]


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

        # Eclipse status (updated each step)
        self._is_illuminated = True

        # Attitude target calculator
        self._attitude_target_calc = AttitudeTargetCalculator(sun_pointing_config())
        self._pointing_mode: PointingMode = "MANUAL"
        self._ground_station = MAKINOHARA
        self._imaging_target: Optional[ImagingTarget] = None
        self._ground_station_visible = False

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

        # Get sun direction in ECI and eclipse status (constant during this macro step)
        sun_dir_eci = self._get_sun_direction_eci()
        sat_pos_eci = self._get_satellite_position_eci()
        illuminated = not is_in_eclipse(sat_pos_eci, sun_dir_eci)
        self._is_illuminated = illuminated

        # Calculate target quaternion for POINTING mode
        # Note: This is expensive due to Astropy transforms, so only do when needed
        if self.spacecraft.control_mode == "POINTING" and self._pointing_mode != "MANUAL":
            self._update_target_attitude(sat_pos_eci, sun_dir_eci)

        # Ground station visibility is calculated in get_telemetry() on demand
        # to avoid expensive coordinate transforms every step

        # Sub-step if effective_dt is too large
        remaining_dt = effective_dt
        while remaining_dt > 0:
            physics_dt = min(remaining_dt, max_physics_dt)

            # Step spacecraft
            self.spacecraft.step(
                dt=physics_dt,
                magnetic_field_inertial=b_field_inertial,
                sun_direction_inertial=sun_dir_eci,
                is_illuminated=illuminated,
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

    def set_pointing_mode(self, mode: PointingMode) -> None:
        """Set pointing mode for automatic target calculation.

        Args:
            mode: Pointing mode (MANUAL, SUN, NADIR, GROUND_STATION, IMAGING_TARGET)
        """
        self._pointing_mode = mode

        # Update attitude target calculator config
        if mode == "SUN":
            self._attitude_target_calc.set_config(sun_pointing_config())
        elif mode == "NADIR":
            self._attitude_target_calc.set_config(nadir_pointing_config())
        elif mode == "GROUND_STATION":
            self._attitude_target_calc.set_config(
                ground_station_pointing_config(self._ground_station)
            )
        elif mode == "IMAGING_TARGET" and self._imaging_target is not None:
            self._attitude_target_calc.set_config(
                imaging_target_pointing_config(self._imaging_target)
            )

    @property
    def pointing_mode(self) -> PointingMode:
        """Get current pointing mode."""
        return self._pointing_mode

    def set_imaging_target(self, lat_deg: float, lon_deg: float, alt_m: float = 0.0) -> None:
        """Set imaging target location.

        Args:
            lat_deg: Latitude in degrees
            lon_deg: Longitude in degrees
            alt_m: Altitude in meters (default 0)
        """
        self._imaging_target = ImagingTarget(lat_deg, lon_deg, alt_m)
        if self._pointing_mode == "IMAGING_TARGET":
            self._attitude_target_calc.set_config(
                imaging_target_pointing_config(self._imaging_target)
            )

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
                "pointingMode": self._pointing_mode,
                "targetQuaternion": sc_state["target_quaternion"].tolist(),
                "error": {
                    "attitude": self.spacecraft.get_attitude_error(),
                    "rate": float(np.linalg.norm(omega)),
                },
                "groundStationVisible": self._ground_station_visible,
            },

            "environment": {
                "magneticField": self._magnetic_field_inertial.tolist(),
                "sunDirection": self._get_sun_direction(),
                "isIlluminated": self._is_illuminated,
            },

            "orbit": self.get_orbit_position(),

            "power": sc_state["power"],
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

    def _get_sun_direction_eci(self) -> NDArray[np.float64]:
        """Get current sun direction in ECI (inertial) frame.

        Returns:
            Unit vector pointing toward the Sun in ECI frame
        """
        from astropy.time import Time
        from astropy.coordinates import get_sun

        sim_time = Time(self.get_absolute_time())
        sun_gcrs = get_sun(sim_time)

        # Get direction vector (already in GCRS which is approximately ECI)
        cart = sun_gcrs.cartesian
        x = float(cart.x.value)  # type: ignore[union-attr]
        y = float(cart.y.value)  # type: ignore[union-attr]
        z = float(cart.z.value)  # type: ignore[union-attr]

        # Normalize to unit vector
        r = (x**2 + y**2 + z**2) ** 0.5
        return np.array([x / r, y / r, z / r])

    def _get_satellite_position_eci(self) -> NDArray[np.float64]:
        """Get current satellite position in ECI frame.

        Returns:
            Position vector in ECI frame (km)
        """
        # Get position from orbit propagator
        orbit_state = self._orbit_propagator.propagate(self.sim_time, self._sim_epoch)

        # The orbit propagator returns ECI position
        return np.array([
            orbit_state.position_eci[0],
            orbit_state.position_eci[1],
            orbit_state.position_eci[2],
        ])

    def _get_satellite_velocity_eci(self) -> NDArray[np.float64]:
        """Get current satellite velocity in ECI frame.

        Returns:
            Velocity vector in ECI frame (km/s)
        """
        orbit_state = self._orbit_propagator.propagate(self.sim_time, self._sim_epoch)
        return np.array([
            orbit_state.velocity_eci[0],
            orbit_state.velocity_eci[1],
            orbit_state.velocity_eci[2],
        ])

    def _get_dcm_eci_to_ecef(self) -> NDArray[np.float64]:
        """Get DCM from ECI to ECEF at current simulation time.

        Returns:
            3x3 rotation matrix
        """
        from astropy.time import Time
        from astropy.coordinates import GCRS, ITRS
        import astropy.units as u

        sim_time = Time(self.get_absolute_time())

        # Create basis vectors in GCRS and transform to ITRS
        # This gives us the rotation matrix
        gcrs_x = GCRS(ra=0*u.deg, dec=0*u.deg, distance=1*u.AU, obstime=sim_time)
        gcrs_y = GCRS(ra=90*u.deg, dec=0*u.deg, distance=1*u.AU, obstime=sim_time)
        gcrs_z = GCRS(ra=0*u.deg, dec=90*u.deg, distance=1*u.AU, obstime=sim_time)

        itrs_x = gcrs_x.transform_to(ITRS(obstime=sim_time))
        itrs_y = gcrs_y.transform_to(ITRS(obstime=sim_time))
        itrs_z = gcrs_z.transform_to(ITRS(obstime=sim_time))

        # Build DCM from transformed basis vectors
        # Type ignores for Astropy's complex typing
        dcm = np.array([
            [itrs_x.cartesian.x.value, itrs_y.cartesian.x.value, itrs_z.cartesian.x.value],  # type: ignore[union-attr]
            [itrs_x.cartesian.y.value, itrs_y.cartesian.y.value, itrs_z.cartesian.y.value],  # type: ignore[union-attr]
            [itrs_x.cartesian.z.value, itrs_y.cartesian.z.value, itrs_z.cartesian.z.value],  # type: ignore[union-attr]
        ])
        return dcm

    def _update_target_attitude(
        self,
        sat_pos_eci_km: NDArray[np.float64],
        sun_dir_eci: NDArray[np.float64],
    ) -> None:
        """Update target attitude based on current pointing mode.

        Args:
            sat_pos_eci_km: Satellite position in ECI (km)
            sun_dir_eci: Sun direction unit vector in ECI
        """
        try:
            sat_pos_eci_m = sat_pos_eci_km * 1000.0  # km to m
            sat_vel_eci_km_s = self._get_satellite_velocity_eci()
            sat_vel_eci_m_s = sat_vel_eci_km_s * 1000.0  # km/s to m/s

            # Only compute expensive ECI-to-ECEF transform when needed
            # (for ground station or imaging target pointing)
            if self._pointing_mode in ["GROUND_STATION", "IMAGING_TARGET"]:
                dcm_eci_to_ecef = self._get_dcm_eci_to_ecef()
            else:
                # For SUN, NADIR, VELOCITY modes, we don't need ECEF transform
                dcm_eci_to_ecef = np.eye(3)

            target_q = self._attitude_target_calc.calculate(
                sat_pos_eci_m=sat_pos_eci_m,
                sat_vel_eci_m_s=sat_vel_eci_m_s,
                sun_dir_eci=sun_dir_eci,
                dcm_eci_to_ecef=dcm_eci_to_ecef,
            )

            self.spacecraft.set_target_attitude(target_q)
        except ValueError:
            # If calculation fails (e.g., parallel vectors), keep previous target
            pass
