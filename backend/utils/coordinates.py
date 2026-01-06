"""Coordinate transformation utilities using Astropy.

Design Philosophy:
- Use trusted libraries (Astropy) for all coordinate transformations
- Avoid custom coordinate transformation code
- Backend computes all coordinates, frontend only renders

Coordinate Frames:
- ECEF (ITRS): Earth-Centered Earth-Fixed, used for 3D visualization
- Geodetic: lat/lon/alt, human-readable display
- ECI (GCRS): Earth-Centered Inertial, for attitude/orbit dynamics
"""

from astropy import units as u
from astropy.coordinates import EarthLocation, get_sun, ITRS
from astropy.time import Time
from astropy.utils.iers import conf as iers_conf

# Use built-in IERS data to avoid network downloads and timeouts
iers_conf.auto_download = False


def geodetic_to_ecef(
    lat_deg: float,
    lon_deg: float,
    alt_km: float,
) -> tuple[float, float, float]:
    """Convert geodetic coordinates to ECEF using Astropy.

    Args:
        lat_deg: Latitude in degrees (-90 to 90)
        lon_deg: Longitude in degrees (-180 to 180)
        alt_km: Altitude above WGS84 ellipsoid in km

    Returns:
        (x, y, z) position in ECEF frame, in km

    Note:
        ECEF coordinate system:
        - X axis: points from Earth center to (lat=0, lon=0)
        - Y axis: points from Earth center to (lat=0, lon=90E)
        - Z axis: points from Earth center to North Pole
    """
    location = EarthLocation(
        lat=lat_deg * u.deg,
        lon=lon_deg * u.deg,
        height=alt_km * u.km,
    )

    # Get geocentric (ECEF) coordinates
    x = location.x.to(u.km).value
    y = location.y.to(u.km).value
    z = location.z.to(u.km).value

    return (float(x), float(y), float(z))


def ecef_to_threejs(
    x_ecef: float,
    y_ecef: float,
    z_ecef: float,
    earth_radius_km: float = 6371.0,
) -> tuple[float, float, float]:
    """Convert ECEF coordinates to Three.js scene coordinates.

    Three.js scene convention (matching Earth texture alignment):
    - Scene X: ECEF X (toward lat=0, lon=0)
    - Scene Y: ECEF Z (toward North Pole, "up" in scene)
    - Scene Z: ECEF Y (toward lat=0, lon=90E)
    - Earth radius = 1.0 in scene units

    Args:
        x_ecef: X coordinate in ECEF (km)
        y_ecef: Y coordinate in ECEF (km)
        z_ecef: Z coordinate in ECEF (km)
        earth_radius_km: Earth radius for normalization (default: 6371 km)

    Returns:
        (x, y, z) position in Three.js scene coordinates (normalized)
    """
    # Normalize to Earth radius = 1
    scale = 1.0 / earth_radius_km

    # ECEF to Three.js mapping
    # Scene Y is "up" (North Pole), so ECEF Z -> Scene Y
    scene_x = x_ecef * scale
    scene_y = z_ecef * scale  # ECEF Z (North) -> Scene Y (up)
    scene_z = y_ecef * scale  # ECEF Y (East) -> Scene Z

    return (scene_x, scene_y, scene_z)


def geodetic_to_threejs(
    lat_deg: float,
    lon_deg: float,
    alt_km: float,
    earth_radius_km: float = 6371.0,
) -> tuple[float, float, float]:
    """Convert geodetic coordinates directly to Three.js scene coordinates.

    Combines geodetic_to_ecef and ecef_to_threejs for convenience.

    Args:
        lat_deg: Latitude in degrees (-90 to 90)
        lon_deg: Longitude in degrees (-180 to 180)
        alt_km: Altitude above WGS84 ellipsoid in km
        earth_radius_km: Earth radius for normalization (default: 6371 km)

    Returns:
        (x, y, z) position in Three.js scene coordinates (normalized)
    """
    x_ecef, y_ecef, z_ecef = geodetic_to_ecef(lat_deg, lon_deg, alt_km)
    return ecef_to_threejs(x_ecef, y_ecef, z_ecef, earth_radius_km)


def get_sun_direction_ecef(time: Time | None = None) -> tuple[float, float, float]:
    """Get the Sun direction vector in ECEF coordinates.

    Args:
        time: Astropy Time object. If None, uses current UTC time.

    Returns:
        (x, y, z) unit vector pointing toward the Sun in ECEF frame
    """
    if time is None:
        time = Time.now()

    # Get Sun position in geocentric coordinates (GCRS)
    sun_gcrs = get_sun(time)

    # Transform to ECEF (ITRS - International Terrestrial Reference System)
    sun_itrs = sun_gcrs.transform_to(ITRS(obstime=time))

    # Get Cartesian coordinates
    x = sun_itrs.cartesian.x.value
    y = sun_itrs.cartesian.y.value
    z = sun_itrs.cartesian.z.value

    # Normalize to unit vector
    r = (x**2 + y**2 + z**2) ** 0.5

    return (x / r, y / r, z / r)


def get_sun_direction_threejs(time: Time | None = None) -> tuple[float, float, float]:
    """Get the Sun direction vector in Three.js scene coordinates.

    Args:
        time: Astropy Time object. If None, uses current UTC time.

    Returns:
        (x, y, z) unit vector pointing toward the Sun in Three.js scene frame
    """
    x_ecef, y_ecef, z_ecef = get_sun_direction_ecef(time)

    # Convert to Three.js coordinates (same mapping as ecef_to_threejs but for unit vector)
    # Scene X = ECEF X, Scene Y = ECEF Z (North), Scene Z = ECEF Y (East)
    return (x_ecef, z_ecef, y_ecef)


# Constants
EARTH_RADIUS_KM = 6371.0


def gmst_from_datetime(dt) -> float:
    """Calculate Greenwich Mean Sidereal Time from datetime.

    Uses IAU 2000 formula for GMST.
    Much faster than Astropy coordinate transforms.

    Args:
        dt: Python datetime object (timezone-aware UTC)

    Returns:
        GMST in radians

    Note:
        This ignores precession/nutation but is accurate enough
        for ground station visibility calculations (~0.1° accuracy).
    """
    import math
    from datetime import datetime, timezone

    # Ensure UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # Calculate Julian Date
    # JD = 367*Y - INT(7*(Y+INT((M+9)/12))/4) + INT(275*M/9) + D + 1721013.5 + UT/24
    year = dt.year
    month = dt.month
    day = dt.day
    ut = dt.hour + dt.minute / 60.0 + dt.second / 3600.0 + dt.microsecond / 3600000000.0

    # Julian Date calculation (valid for dates from March 1900 to February 2100)
    if month <= 2:
        year -= 1
        month += 12

    a = int(year / 100)
    b = 2 - a + int(a / 4)

    jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + ut / 24.0 + b - 1524.5

    # Days since J2000.0 (JD 2451545.0)
    d = jd - 2451545.0

    # GMST formula (IAU 2000)
    # GMST in degrees = 280.46061837 + 360.98564736629 * d + ...
    # Higher order terms are very small, ignore for this application
    gmst_deg = 280.46061837 + 360.98564736629 * d

    # Normalize to 0-360
    gmst_deg = gmst_deg % 360.0
    if gmst_deg < 0:
        gmst_deg += 360.0

    return math.radians(gmst_deg)


def dcm_eci_to_ecef_fast(dt) -> tuple[tuple[float, float, float], ...]:
    """Calculate ECI to ECEF rotation matrix using GMST.

    This is a fast approximation that only accounts for Earth rotation.
    It ignores precession, nutation, and polar motion.
    Accurate to ~0.1° which is sufficient for ground station visibility.

    Args:
        dt: Python datetime object (timezone-aware UTC)

    Returns:
        3x3 rotation matrix as nested tuples ((r00, r01, r02), (r10, ...), ...)
    """
    import math

    gmst = gmst_from_datetime(dt)

    # ECI to ECEF is a rotation about Z by +GMST
    # At GMST, Greenwich (ECEF x-axis) is at RA=GMST in ECI
    # So RA=0 in ECI maps to longitude (360-GMST)° in ECEF
    c = math.cos(gmst)
    s = math.sin(gmst)

    # Standard Rz(theta) rotation matrix
    return (
        (c, s, 0.0),
        (-s, c, 0.0),
        (0.0, 0.0, 1.0),
    )


def dcm_eci_to_ecef_fast_np(dt):
    """Calculate ECI to ECEF rotation matrix using GMST (numpy version).

    Same as dcm_eci_to_ecef_fast but returns numpy array.

    Args:
        dt: Python datetime object (timezone-aware UTC)

    Returns:
        3x3 numpy rotation matrix
    """
    import numpy as np

    dcm = dcm_eci_to_ecef_fast(dt)
    return np.array(dcm, dtype=np.float64)
