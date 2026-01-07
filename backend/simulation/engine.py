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
from backend.utils.coordinates import dcm_eci_to_ecef_fast_np
from backend.prediction.contact_predictor import ContactPredictor
from backend.prediction.models import ContactWindow, TimelineActionType
from backend.timeline.timeline_manager import TimelineManager
from backend.hardware.pico_rw_controller import PicoRWController


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

        # Cached values from step() for fast get_telemetry()
        self._cached_sun_dir_eci: Optional[NDArray[np.float64]] = None
        self._cached_dcm_eci_to_ecef: Optional[NDArray[np.float64]] = None

        # Attitude target calculator
        self._attitude_target_calc = AttitudeTargetCalculator(sun_pointing_config())
        self._pointing_mode: PointingMode = "MANUAL"
        self._ground_station = MAKINOHARA
        self._imaging_target: Optional[ImagingTarget] = None
        self._ground_station_visible = False

        # Timeline and contact prediction
        self._timeline = TimelineManager()
        self._contact_predictor: Optional[ContactPredictor] = None
        self._cached_next_contact: Optional[ContactWindow] = None
        self._contact_prediction_valid_until: float = 0.0

        # Hardware interface (optional - Pico RW controller)
        # Auto-detect and connect if available (disabled during tests)
        self._pico_rw: Optional[PicoRWController] = None
        if not self._is_running_tests():
            try:
                max_rw_speed = config.spacecraft.reaction_wheel.max_speed
                self._pico_rw = PicoRWController(max_rw_speed=max_rw_speed)
                if self._pico_rw.connect():
                    print(f"Pico RW controller connected (max speed: {max_rw_speed:.1f} rad/s)")
                else:
                    # Silently ignore if not found
                    self._pico_rw = None
            except Exception:
                # Silently ignore initialization errors
                self._pico_rw = None

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

    def _is_running_tests(self) -> bool:
        """Check if code is running under pytest.

        Returns:
            True if pytest is detected in sys.modules
        """
        import sys
        return "pytest" in sys.modules

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
        # Clear timeline and contact prediction cache
        self._timeline.clear()
        self._cached_next_contact = None
        self._contact_prediction_valid_until = 0.0

    def step(self) -> None:
        """Advance simulation by one time step.

        Only advances if the simulation is running.
        Uses sub-stepping for high time warp to maintain physics accuracy.
        """
        if self.state != SimulationState.RUNNING:
            return

        # Process timeline actions BEFORE physics step
        self._process_timeline()

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

        # Get fast ECI-to-ECEF transform (GMST-based, ~1000x faster than Astropy)
        dcm_eci_to_ecef = dcm_eci_to_ecef_fast_np(self.get_absolute_time())

        # Cache for get_telemetry()
        self._cached_sun_dir_eci = sun_dir_eci
        self._cached_dcm_eci_to_ecef = dcm_eci_to_ecef

        # Calculate target quaternion for 3Axis mode
        if self.spacecraft.control_mode == "3Axis" and self._pointing_mode != "MANUAL":
            self._update_target_attitude(sat_pos_eci, sun_dir_eci, dcm_eci_to_ecef)

        # Ground station visibility (fast calculation)
        sat_pos_eci_m = sat_pos_eci * 1000.0  # km to m
        self._ground_station_visible = is_ground_station_visible(
            sat_pos_eci_m, dcm_eci_to_ecef, self._ground_station
        )

        # Proactively update contact prediction cache (lazy - only if expired)
        # This ensures get_telemetry() doesn't trigger slow prediction
        self._update_contact_cache_if_needed()

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

        # Update hardware visualization (Pico RW controller)
        if self._pico_rw is not None:
            rw_speed = self.spacecraft.reaction_wheel.get_speed()
            self._pico_rw.set_speed(rw_speed)  # Send all 3 axes

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
        mode: Literal["Idle", "Detumbling", "3Axis"],
    ) -> None:
        """Set spacecraft control mode.

        Args:
            mode: Control mode ("Idle", "Detumbling", "3Axis")
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

    def set_pointing_config(
        self,
        main_target: str,
        main_body_axis: list[float],
        sub_target: str,
        sub_body_axis: list[float],
    ) -> None:
        """Set detailed pointing configuration with main/sub axis.

        Args:
            main_target: Target direction for main axis (SUN, EARTH_CENTER, etc.)
            main_body_axis: Body axis for main target [x, y, z]
            sub_target: Target direction for sub axis
            sub_body_axis: Body axis for sub target [x, y, z]

        Raises:
            ValueError: If target direction is invalid
        """
        # Convert string to TargetDirection enum
        try:
            main_dir = TargetDirection[main_target]
            sub_dir = TargetDirection[sub_target]
        except KeyError as e:
            raise ValueError(f"Invalid target direction: {e}")

        # Create pointing configuration
        config = PointingConfig(
            main_target=main_dir,
            sub_target=sub_dir,
            main_body_axis=np.array(main_body_axis, dtype=np.float64),
            sub_body_axis=np.array(sub_body_axis, dtype=np.float64),
            ground_station=self._ground_station,
            imaging_target=self._imaging_target,
        )
        self._attitude_target_calc.set_config(config)

        # Set mode to MANUAL to indicate custom configuration
        self._pointing_mode = "MANUAL"

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
                    "actualTorque": self.spacecraft.reaction_wheel.get_actual_torque().tolist(),
                    "momentum": self.spacecraft.reaction_wheel.get_momentum().tolist(),
                },
                "magnetorquers": {
                    "dipoleMoment": self.spacecraft.magnetorquer.get_dipole().tolist(),
                    "power": self.spacecraft.magnetorquer.get_power(),
                },
            },

            "control": {
                "mode": self.spacecraft.control_mode,
                "isUnloading": sc_state.get("is_unloading", False),
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
                "sunDirectionECI": self._get_sun_direction_for_body_frame(),
                "isIlluminated": self._is_illuminated,
            },

            "orbit": self.get_orbit_position(),

            "power": sc_state["power"],

            "timeline": {
                "nextContact": self._get_next_contact_dict(),
                "actions": self._timeline.to_dict_list(),
            },
        }

    def _get_sun_direction(self) -> list[float]:
        """Get current sun direction in Three.js scene coordinates.

        Uses cached values from step() for performance.
        Falls back to slow Astropy calculation if cache is empty.

        Returns:
            [x, y, z] unit vector pointing toward the Sun
        """
        if self._cached_sun_dir_eci is not None and self._cached_dcm_eci_to_ecef is not None:
            # Fast path: use cached values
            # Transform ECI to ECEF
            sun_ecef = self._cached_dcm_eci_to_ecef @ self._cached_sun_dir_eci
            # ECEF to Three.js: Scene X = ECEF X, Scene Y = ECEF Z, Scene Z = ECEF Y
            return [float(sun_ecef[0]), float(sun_ecef[2]), float(sun_ecef[1])]
        else:
            # Slow fallback: use Astropy (only before first step)
            from astropy.time import Time
            from backend.utils.coordinates import get_sun_direction_threejs
            sim_time = Time(self.get_absolute_time())
            sun_dir = get_sun_direction_threejs(sim_time)
            return list(sun_dir)

    def _get_sun_direction_for_body_frame(self) -> list[float]:
        """Get current sun direction in ECI (inertial) frame for body frame transformation.

        This is used by the frontend to transform sun direction to body frame using quaternion.

        Returns:
            [x, y, z] unit vector pointing toward the Sun in ECI frame
        """
        if self._cached_sun_dir_eci is not None:
            # Use cached ECI direction
            return [float(self._cached_sun_dir_eci[0]), float(self._cached_sun_dir_eci[1]), float(self._cached_sun_dir_eci[2])]
        else:
            # Fallback: compute directly
            sun_eci = self._get_sun_direction_eci()
            return [float(sun_eci[0]), float(sun_eci[1]), float(sun_eci[2])]

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
        dcm_eci_to_ecef: NDArray[np.float64],
    ) -> None:
        """Update target attitude based on current pointing mode.

        Args:
            sat_pos_eci_km: Satellite position in ECI (km)
            sun_dir_eci: Sun direction unit vector in ECI
            dcm_eci_to_ecef: Pre-computed ECI to ECEF rotation matrix
        """
        try:
            sat_pos_eci_m = sat_pos_eci_km * 1000.0  # km to m
            sat_vel_eci_km_s = self._get_satellite_velocity_eci()
            sat_vel_eci_m_s = sat_vel_eci_km_s * 1000.0  # km/s to m/s

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

    # ==================== Timeline Methods ====================

    def _process_timeline(self) -> None:
        """Execute due timeline actions. Called at start of step()."""
        due_actions = self._timeline.get_due_actions(self.sim_time)

        for action in due_actions:
            self._execute_action(action)
            self._timeline.mark_executed(action.id)

    def _execute_action(self, action) -> None:
        """Execute a single timeline action.

        Args:
            action: TimelineAction to execute
        """
        if action.action_type == TimelineActionType.CONTROL_MODE:
            mode = action.params.get("mode", "Idle")
            self.set_control_mode(mode)
        elif action.action_type == TimelineActionType.POINTING_MODE:
            mode = action.params.get("mode", "MANUAL")
            self.set_pointing_mode(mode)
        elif action.action_type == TimelineActionType.IMAGING_TARGET:
            lat = action.params.get("latitude", 0.0)
            lon = action.params.get("longitude", 0.0)
            alt = action.params.get("altitude", 0.0)
            self.set_imaging_target(lat, lon, alt)

    def add_timeline_action(
        self,
        time: float,
        action_type: str,
        params: dict,
    ) -> dict:
        """Add a scheduled action to the timeline.

        Args:
            time: Execution time (simulation seconds)
            action_type: Type of action ("control_mode", "pointing_mode", "imaging_target")
            params: Action parameters

        Returns:
            Created action as dict

        Raises:
            ValueError: If time is in the past
        """
        action = self._timeline.add_action(
            time=time,
            action_type=action_type,
            params=params,
            current_sim_time=self.sim_time,
        )
        return action.to_dict()

    def remove_timeline_action(self, action_id: str) -> bool:
        """Remove a scheduled action.

        Args:
            action_id: The action ID to remove

        Returns:
            True if action was found and removed
        """
        return self._timeline.remove_action(action_id)

    def get_pending_actions(self) -> list[dict]:
        """Get all pending timeline actions.

        Returns:
            List of pending actions as dicts
        """
        return self._timeline.to_dict_list()

    # ==================== Contact Prediction Methods ====================

    def get_next_contact(self, force_refresh: bool = False) -> Optional[ContactWindow]:
        """Get next contact window (uses cache if valid).

        Args:
            force_refresh: Force re-prediction even if cache is valid

        Returns:
            Next ContactWindow or None if no contact predicted
        """
        if self._contact_predictor is None:
            self._contact_predictor = ContactPredictor(
                orbit_propagator=self._orbit_propagator,
                ground_station=self._ground_station,
                sim_epoch=self._sim_epoch,
            )

        # Invalidate cache if needed
        # Note: _contact_prediction_valid_until == 0 means never predicted
        cache_expired = self.sim_time > self._contact_prediction_valid_until
        never_predicted = self._contact_prediction_valid_until == 0.0

        if force_refresh or never_predicted or cache_expired:
            self._cached_next_contact = self._contact_predictor.predict_next_contact(
                self.sim_time
            )
            if self._cached_next_contact:
                # Cache valid until contact ends
                self._contact_prediction_valid_until = self._cached_next_contact.end_time
            else:
                # Re-predict in 5 minutes if no contact found
                self._contact_prediction_valid_until = self.sim_time + 300

        return self._cached_next_contact

    def _get_next_contact_dict(self) -> Optional[dict]:
        """Get next contact as dict for telemetry.

        Returns:
            Contact window as dict, or None
        """
        contact = self.get_next_contact()
        if contact:
            return contact.to_dict()
        return None

    def refresh_contact_prediction(self) -> Optional[dict]:
        """Force refresh contact prediction and return result.

        Returns:
            New contact prediction as dict, or None
        """
        contact = self.get_next_contact(force_refresh=True)
        if contact:
            return contact.to_dict()
        return None

    def _update_contact_cache_if_needed(self) -> None:
        """Update contact prediction cache if expired.

        Called during step() to ensure get_telemetry() is fast.
        Only does prediction if cache is expired.
        """
        # Check if cache needs updating
        if (
            self._cached_next_contact is None
            or self.sim_time > self._contact_prediction_valid_until
        ):
            # Cache expired, trigger update
            self.get_next_contact()

    # ==================== Imaging Preset Methods ====================

    def get_ground_track_at_time(self, target_time: float) -> dict:
        """Get satellite ground track position at a specific simulation time.

        Args:
            target_time: Simulation time in seconds

        Returns:
            Dict with latitude, longitude, altitude
        """
        orbit_state = self._orbit_propagator.propagate(target_time, self._sim_epoch)
        return {
            "latitude": float(orbit_state.latitude),
            "longitude": float(orbit_state.longitude),
            "altitude": float(orbit_state.altitude),
            "time": target_time,
        }

    def calculate_imaging_preset(
        self,
        offset_seconds: float = 300.0,
    ) -> Optional[dict]:
        """Calculate imaging target based on next contact + offset.

        This is useful for planning imaging operations during a contact window.
        The imaging target is set to where the satellite will be at AOS + offset.

        Args:
            offset_seconds: Time offset from contact AOS in seconds (default 5 min)

        Returns:
            Dict with imaging target info, or None if no contact predicted
        """
        contact = self.get_next_contact()
        if contact is None:
            return None

        # Calculate target time (AOS + offset)
        target_time = contact.start_time + offset_seconds

        # Ensure target time is within contact window (with some margin)
        if target_time > contact.end_time + 60:
            # Target time is after contact, use mid-contact instead
            target_time = (contact.start_time + contact.end_time) / 2

        # Get ground track at target time
        ground_track = self.get_ground_track_at_time(target_time)

        return {
            "latitude": ground_track["latitude"],
            "longitude": ground_track["longitude"],
            "altitude": 0.0,  # Target on ground
            "targetTime": target_time,
            "contactStartTime": contact.start_time,
            "offsetSeconds": offset_seconds,
        }

    def set_imaging_preset(
        self,
        offset_seconds: float = 300.0,
        schedule_action: bool = False,
    ) -> Optional[dict]:
        """Set imaging target to satellite ground track at contact + offset.

        Args:
            offset_seconds: Time offset from contact AOS in seconds
            schedule_action: If True, also schedule timeline actions for the imaging

        Returns:
            Dict with imaging preset info, or None if no contact predicted
        """
        preset = self.calculate_imaging_preset(offset_seconds)
        if preset is None:
            return None

        # Set the imaging target
        self.set_imaging_target(
            lat_deg=preset["latitude"],
            lon_deg=preset["longitude"],
            alt_m=preset["altitude"],
        )

        # Optionally schedule timeline actions
        if schedule_action:
            target_time = preset["targetTime"]

            # Schedule pointing mode change to IMAGING_TARGET before imaging time
            # (30 seconds before to allow attitude settling)
            pointing_time = max(self.sim_time + 1, target_time - 30)
            try:
                self.add_timeline_action(
                    time=pointing_time,
                    action_type="pointing_mode",
                    params={"mode": "IMAGING_TARGET"},
                )
            except ValueError:
                pass  # Time already passed

        return preset
