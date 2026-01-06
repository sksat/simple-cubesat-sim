"""Orbit propagation using SGP4.

Uses TLE (Two-Line Element) sets to propagate satellite orbits.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from numpy.typing import NDArray
from sgp4.api import Satrec, jday


@dataclass
class OrbitState:
    """Orbit state at a given time."""
    position_eci: NDArray[np.float64]  # ECI position [km]
    velocity_eci: NDArray[np.float64]  # ECI velocity [km/s]
    latitude: float  # Geodetic latitude [deg]
    longitude: float  # Geodetic longitude [deg]
    altitude: float  # Altitude above WGS84 ellipsoid [km]


# Default TLE for ISS-like orbit (as fallback)
DEFAULT_TLE_LINE1 = "1 25544U 98067A   24001.00000000  .00016717  00000-0  10270-3 0  9003"
DEFAULT_TLE_LINE2 = "2 25544  51.6400   0.0000 0005000   0.0000   0.0000 15.50000000000000"


class OrbitPropagator:
    """SGP4-based orbit propagator.

    Propagates satellite orbits using TLE data and the SGP4/SDP4 algorithm.
    """

    def __init__(
        self,
        tle_line1: Optional[str] = None,
        tle_line2: Optional[str] = None,
    ):
        """Initialize orbit propagator.

        Args:
            tle_line1: First line of TLE (uses default if None)
            tle_line2: Second line of TLE (uses default if None)
        """
        self._tle_line1 = tle_line1 or DEFAULT_TLE_LINE1
        self._tle_line2 = tle_line2 or DEFAULT_TLE_LINE2
        self._satellite = Satrec.twoline2rv(self._tle_line1, self._tle_line2)

        # Cache TLE epoch for simulation time offset
        self._epoch_jd = self._satellite.jdsatepoch + self._satellite.jdsatepochF

    @property
    def tle_line1(self) -> str:
        """Get TLE line 1."""
        return self._tle_line1

    @property
    def tle_line2(self) -> str:
        """Get TLE line 2."""
        return self._tle_line2

    @property
    def inclination(self) -> float:
        """Get orbital inclination in degrees."""
        return np.degrees(self._satellite.inclo)

    @property
    def period(self) -> float:
        """Get orbital period in seconds."""
        # n0 is mean motion in radians/minute
        n0 = self._satellite.no_kozai  # rad/min
        if n0 > 0:
            return 2 * np.pi / n0 * 60  # seconds
        return 0.0

    def set_tle(self, line1: str, line2: str) -> None:
        """Set new TLE data.

        Args:
            line1: First line of TLE
            line2: Second line of TLE

        Raises:
            ValueError: If TLE parsing fails
        """
        try:
            satellite = Satrec.twoline2rv(line1, line2)
            # Test propagation to validate TLE
            jd, fr = jday(2024, 1, 1, 0, 0, 0)
            e, r, v = satellite.sgp4(jd, fr)
            if e != 0:
                raise ValueError(f"SGP4 error code: {e}")
        except Exception as e:
            raise ValueError(f"Invalid TLE: {e}")

        self._tle_line1 = line1
        self._tle_line2 = line2
        self._satellite = satellite
        self._epoch_jd = satellite.jdsatepoch + satellite.jdsatepochF

    def propagate(self, sim_time: float, epoch: Optional[datetime] = None) -> OrbitState:
        """Propagate orbit to given simulation time.

        Args:
            sim_time: Simulation time in seconds from start
            epoch: Epoch datetime for simulation start (uses now if None)

        Returns:
            OrbitState with position and velocity
        """
        # Default epoch is current time
        if epoch is None:
            epoch = datetime.now(timezone.utc)

        # Calculate Julian date for propagation
        total_seconds = sim_time
        target_time = epoch.replace(tzinfo=timezone.utc)
        target_time = datetime(
            target_time.year,
            target_time.month,
            target_time.day,
            target_time.hour,
            target_time.minute,
            target_time.second,
            target_time.microsecond,
            tzinfo=timezone.utc,
        )

        # Add simulation seconds
        from datetime import timedelta
        target_time = target_time + timedelta(seconds=total_seconds)

        # Convert to Julian date
        jd, fr = jday(
            target_time.year,
            target_time.month,
            target_time.day,
            target_time.hour,
            target_time.minute,
            target_time.second + target_time.microsecond / 1e6,
        )

        # Propagate with SGP4
        e, r, v = self._satellite.sgp4(jd, fr)

        if e != 0:
            # SGP4 error - return zeros
            return OrbitState(
                position_eci=np.zeros(3),
                velocity_eci=np.zeros(3),
                latitude=0.0,
                longitude=0.0,
                altitude=0.0,
            )

        position_eci = np.array(r)  # km
        velocity_eci = np.array(v)  # km/s

        # Convert ECI to geodetic (lat, lon, alt)
        lat, lon, alt = self._eci_to_geodetic(position_eci, jd, fr)

        return OrbitState(
            position_eci=position_eci,
            velocity_eci=velocity_eci,
            latitude=lat,
            longitude=lon,
            altitude=alt,
        )

    def _eci_to_geodetic(
        self,
        position_eci: NDArray[np.float64],
        jd: float,
        fr: float,
    ) -> tuple[float, float, float]:
        """Convert ECI position to geodetic coordinates.

        Args:
            position_eci: ECI position [km]
            jd: Julian date (integer part)
            fr: Julian date (fractional part)

        Returns:
            (latitude, longitude, altitude) in (deg, deg, km)
        """
        # Earth parameters (WGS84)
        a = 6378.137  # Equatorial radius [km]
        f = 1 / 298.257223563  # Flattening
        e2 = 2 * f - f * f  # Eccentricity squared

        x, y, z = position_eci

        # Calculate longitude in ECI frame
        lon_eci = np.degrees(np.arctan2(y, x))

        # Calculate GMST (Greenwich Mean Sidereal Time)
        # GMST at 0h UT1
        t_ut1 = (jd + fr - 2451545.0) / 36525.0
        gmst_sec = (
            67310.54841
            + (876600.0 * 3600 + 8640184.812866) * t_ut1
            + 0.093104 * t_ut1**2
            - 6.2e-6 * t_ut1**3
        )
        gmst_deg = (gmst_sec / 240.0) % 360.0  # Convert seconds to degrees

        # Longitude (subtract Earth rotation)
        longitude = lon_eci - gmst_deg
        # Normalize to [-180, 180]
        longitude = ((longitude + 180) % 360) - 180

        # Iterative calculation for latitude (geodetic from geocentric)
        p = np.sqrt(x**2 + y**2)
        lat = np.arctan2(z, p)  # Initial guess

        for _ in range(10):
            sin_lat = np.sin(lat)
            N = a / np.sqrt(1 - e2 * sin_lat**2)
            lat_new = np.arctan2(z + e2 * N * sin_lat, p)
            if abs(lat_new - lat) < 1e-12:
                break
            lat = lat_new

        latitude = np.degrees(lat)

        # Altitude
        sin_lat = np.sin(lat)
        cos_lat = np.cos(lat)
        N = a / np.sqrt(1 - e2 * sin_lat**2)

        if abs(cos_lat) > 1e-10:
            altitude = p / cos_lat - N
        else:
            altitude = abs(z) - N * (1 - e2)

        return latitude, longitude, altitude
