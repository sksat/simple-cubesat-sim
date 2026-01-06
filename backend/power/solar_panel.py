"""Solar panel model for power generation."""

import numpy as np
from numpy.typing import NDArray


class SolarPanel:
    """Solar panel power generation model.

    Calculates power output based on sun angle and illumination.

    Attributes:
        max_power: Maximum power output when sun is perpendicular (W)
        normal_body: Panel normal vector in body frame
        double_sided: Whether panel has cells on both sides
    """

    def __init__(
        self,
        max_power: float,
        normal_body: list[float] | NDArray[np.float64],
        double_sided: bool = False,
    ):
        """Initialize solar panel.

        Args:
            max_power: Maximum power output (W)
            normal_body: Panel normal vector in body frame (will be normalized)
            double_sided: If True, panel generates power from both sides
        """
        self.max_power = max_power
        normal = np.array(normal_body, dtype=np.float64)
        self.normal_body = normal / np.linalg.norm(normal)
        self.double_sided = double_sided

    def calculate_power(
        self,
        sun_direction_body: NDArray[np.float64],
        is_illuminated: bool,
    ) -> float:
        """Calculate power output.

        Args:
            sun_direction_body: Unit vector toward sun in body frame
            is_illuminated: True if satellite is not in eclipse

        Returns:
            Power output in Watts
        """
        if not is_illuminated:
            return 0.0

        # Calculate cosine of angle between panel normal and sun direction
        cos_angle = float(np.dot(self.normal_body, sun_direction_body))

        if self.double_sided:
            # Use absolute value for double-sided panels
            cos_angle = abs(cos_angle)
        else:
            # Single-sided: only positive angles (front face)
            cos_angle = max(0.0, cos_angle)

        return self.max_power * cos_angle
