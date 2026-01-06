"""Eclipse detection for satellite illumination."""

import numpy as np
from numpy.typing import NDArray


# Earth radius in km
EARTH_RADIUS_KM = 6371.0


def is_in_eclipse(
    sat_pos_eci: NDArray[np.float64],
    sun_dir_eci: NDArray[np.float64],
) -> bool:
    """Check if satellite is in Earth's shadow.

    Uses simplified cylindrical shadow model (umbra only).

    Args:
        sat_pos_eci: Satellite position in ECI frame (km)
        sun_dir_eci: Unit vector toward Sun in ECI frame

    Returns:
        True if satellite is in eclipse (Earth's shadow)
    """
    # Normalize sun direction
    sun_dir = sun_dir_eci / np.linalg.norm(sun_dir_eci)

    # Project satellite position onto sun direction
    # Positive = satellite is on the sun side
    # Negative = satellite is on the shadow side
    proj_on_sun_axis = float(np.dot(sat_pos_eci, sun_dir))

    if proj_on_sun_axis >= 0:
        # Satellite is on the sun side of Earth - illuminated
        return False

    # Satellite is behind Earth relative to Sun
    # Check if it's within the shadow cylinder

    # Distance from satellite to sun-Earth axis
    # This is the perpendicular distance from the satellite to the Sun-Earth line
    perpendicular_component = sat_pos_eci - proj_on_sun_axis * sun_dir
    distance_from_axis = float(np.linalg.norm(perpendicular_component))

    # If within Earth's radius of the axis, it's in shadow
    return distance_from_axis < EARTH_RADIUS_KM
