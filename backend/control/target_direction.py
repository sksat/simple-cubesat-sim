"""Target direction types for attitude control.

Defines direction types for main/sub axis pointing.
"""

from enum import Enum, auto
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray


class TargetDirection(Enum):
    """Target direction types for attitude pointing."""

    SUN = auto()  # Sun direction
    EARTH_CENTER = auto()  # Nadir (toward Earth center)
    GROUND_STATION = auto()  # Toward ground station
    IMAGING_TARGET = auto()  # Toward imaging target on Earth surface
    VELOCITY = auto()  # Satellite velocity direction
    ORBIT_NORMAL = auto()  # Orbit normal (r × v)


@dataclass
class GroundStation:
    """Ground station definition."""

    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float = 0.0
    min_elevation_deg: float = 5.0

    @property
    def latitude_rad(self) -> float:
        return np.deg2rad(self.latitude_deg)

    @property
    def longitude_rad(self) -> float:
        return np.deg2rad(self.longitude_deg)


# Predefined ground stations
MAKINOHARA = GroundStation(
    name="Makinohara",
    latitude_deg=34.74,
    longitude_deg=138.22,
    altitude_m=0.0,
    min_elevation_deg=5.0,
)


@dataclass
class ImagingTarget:
    """Imaging target on Earth surface."""

    latitude_deg: float
    longitude_deg: float
    altitude_m: float = 0.0

    @property
    def latitude_rad(self) -> float:
        return np.deg2rad(self.latitude_deg)

    @property
    def longitude_rad(self) -> float:
        return np.deg2rad(self.longitude_deg)


def lla_to_ecef(lat_rad: float, lon_rad: float, alt_m: float) -> NDArray[np.float64]:
    """Convert geodetic coordinates to ECEF.

    Args:
        lat_rad: Latitude in radians
        lon_rad: Longitude in radians
        alt_m: Altitude in meters

    Returns:
        ECEF position in meters [x, y, z]
    """
    # WGS84 parameters
    a = 6378137.0  # semi-major axis (m)
    f = 1 / 298.257223563  # flattening
    e2 = 2 * f - f * f  # eccentricity squared

    sin_lat = np.sin(lat_rad)
    cos_lat = np.cos(lat_rad)
    sin_lon = np.sin(lon_rad)
    cos_lon = np.cos(lon_rad)

    # Radius of curvature in prime vertical
    N = a / np.sqrt(1 - e2 * sin_lat * sin_lat)

    x = (N + alt_m) * cos_lat * cos_lon
    y = (N + alt_m) * cos_lat * sin_lon
    z = (N * (1 - e2) + alt_m) * sin_lat

    return np.array([x, y, z])


def calculate_target_direction_eci(
    direction: TargetDirection,
    sat_pos_eci_m: NDArray[np.float64],
    sat_vel_eci_m_s: NDArray[np.float64],
    sun_dir_eci: NDArray[np.float64],
    dcm_eci_to_ecef: NDArray[np.float64],
    ground_station: GroundStation | None = None,
    imaging_target: ImagingTarget | None = None,
) -> NDArray[np.float64]:
    """Calculate target direction unit vector in ECI frame.

    Args:
        direction: Target direction type
        sat_pos_eci_m: Satellite position in ECI (meters)
        sat_vel_eci_m_s: Satellite velocity in ECI (m/s)
        sun_dir_eci: Sun direction unit vector in ECI
        dcm_eci_to_ecef: DCM from ECI to ECEF
        ground_station: Ground station for GROUND_STATION direction
        imaging_target: Target for IMAGING_TARGET direction

    Returns:
        Unit vector in ECI pointing toward target

    Raises:
        ValueError: If required parameters are missing
    """
    if direction == TargetDirection.SUN:
        return sun_dir_eci / np.linalg.norm(sun_dir_eci)

    elif direction == TargetDirection.EARTH_CENTER:
        # Nadir: opposite of position vector
        nadir = -sat_pos_eci_m
        return nadir / np.linalg.norm(nadir)

    elif direction == TargetDirection.VELOCITY:
        return sat_vel_eci_m_s / np.linalg.norm(sat_vel_eci_m_s)

    elif direction == TargetDirection.ORBIT_NORMAL:
        # r × v
        orbit_normal = np.cross(sat_pos_eci_m, sat_vel_eci_m_s)
        return orbit_normal / np.linalg.norm(orbit_normal)

    elif direction == TargetDirection.GROUND_STATION:
        if ground_station is None:
            raise ValueError("Ground station required for GROUND_STATION direction")

        return _calculate_surface_target_direction(
            sat_pos_eci_m,
            dcm_eci_to_ecef,
            ground_station.latitude_rad,
            ground_station.longitude_rad,
            ground_station.altitude_m,
        )

    elif direction == TargetDirection.IMAGING_TARGET:
        if imaging_target is None:
            raise ValueError("Imaging target required for IMAGING_TARGET direction")

        return _calculate_surface_target_direction(
            sat_pos_eci_m,
            dcm_eci_to_ecef,
            imaging_target.latitude_rad,
            imaging_target.longitude_rad,
            imaging_target.altitude_m,
        )

    else:
        raise ValueError(f"Unknown target direction: {direction}")


def _calculate_surface_target_direction(
    sat_pos_eci_m: NDArray[np.float64],
    dcm_eci_to_ecef: NDArray[np.float64],
    lat_rad: float,
    lon_rad: float,
    alt_m: float,
) -> NDArray[np.float64]:
    """Calculate direction from satellite to a point on Earth surface.

    Args:
        sat_pos_eci_m: Satellite position in ECI (meters)
        dcm_eci_to_ecef: DCM from ECI to ECEF
        lat_rad: Target latitude (radians)
        lon_rad: Target longitude (radians)
        alt_m: Target altitude (meters)

    Returns:
        Unit vector in ECI pointing from satellite to target
    """
    # Target position in ECEF
    target_ecef_m = lla_to_ecef(lat_rad, lon_rad, alt_m)

    # Convert to ECI: pos_eci = dcm_ecef_to_eci @ pos_ecef
    dcm_ecef_to_eci = dcm_eci_to_ecef.T
    target_eci_m = dcm_ecef_to_eci @ target_ecef_m

    # Direction from satellite to target
    direction = target_eci_m - sat_pos_eci_m
    return direction / np.linalg.norm(direction)


def calculate_elevation_angle(
    sat_pos_eci_m: NDArray[np.float64],
    dcm_eci_to_ecef: NDArray[np.float64],
    ground_station: GroundStation,
) -> float:
    """Calculate elevation angle of satellite from ground station.

    Args:
        sat_pos_eci_m: Satellite position in ECI (meters)
        dcm_eci_to_ecef: DCM from ECI to ECEF
        ground_station: Ground station

    Returns:
        Elevation angle in degrees (negative if below horizon)
    """
    # Ground station position in ECEF
    gs_ecef_m = lla_to_ecef(
        ground_station.latitude_rad,
        ground_station.longitude_rad,
        ground_station.altitude_m,
    )

    # Satellite position in ECEF
    sat_ecef_m = dcm_eci_to_ecef @ sat_pos_eci_m

    # Vector from ground station to satellite in ECEF
    to_sat_ecef = sat_ecef_m - gs_ecef_m

    # Local vertical at ground station (unit vector pointing up)
    # For a point on Earth's surface, this is approximately the position vector normalized
    local_up = gs_ecef_m / np.linalg.norm(gs_ecef_m)

    # Elevation angle: arcsin of dot product with local vertical
    to_sat_norm = to_sat_ecef / np.linalg.norm(to_sat_ecef)
    sin_elev = np.dot(to_sat_norm, local_up)
    elev_rad = np.arcsin(np.clip(sin_elev, -1.0, 1.0))

    return np.rad2deg(elev_rad)


def is_ground_station_visible(
    sat_pos_eci_m: NDArray[np.float64],
    dcm_eci_to_ecef: NDArray[np.float64],
    ground_station: GroundStation,
) -> bool:
    """Check if satellite is visible from ground station.

    Args:
        sat_pos_eci_m: Satellite position in ECI (meters)
        dcm_eci_to_ecef: DCM from ECI to ECEF
        ground_station: Ground station

    Returns:
        True if elevation angle exceeds minimum
    """
    elev = calculate_elevation_angle(sat_pos_eci_m, dcm_eci_to_ecef, ground_station)
    # Convert numpy.bool_ to Python bool for JSON serialization
    return bool(elev >= ground_station.min_elevation_deg)
