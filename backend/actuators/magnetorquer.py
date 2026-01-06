"""Magnetorquer (MTQ) actuator model.

Magnetorquers generate torque via interaction with Earth's magnetic field.
They consist of coils that generate a magnetic dipole moment when energized.

Torque generation:
    T = m × B

where:
    T: torque vector (Nm)
    m: dipole moment vector (Am^2)
    B: magnetic field vector in body frame (T)

Typical 6U CubeSat magnetorquer specs:
    - Max dipole moment: 0.2-0.4 Am^2 per axis
    - Power consumption: ~1W at max dipole
"""

import numpy as np
from numpy.typing import NDArray


class Magnetorquer:
    """3-axis magnetorquer model.

    Attributes:
        max_dipole: Maximum dipole moment per axis (Am^2)
        power_per_dipole: Power consumption coefficient (W/Am^2)^2
    """

    def __init__(self, max_dipole: float = 0.2, power_per_dipole: float = 25.0):
        """Initialize magnetorquer.

        Args:
            max_dipole: Maximum dipole moment per axis (Am^2)
            power_per_dipole: Power coefficient such that P = k * |m|^2 (W/(Am^2)^2)
                             Default: 25 gives ~1W at 0.2 Am^2
        """
        self.max_dipole = max_dipole
        self.power_per_dipole = power_per_dipole
        self._dipole = np.zeros(3)

    def command(self, dipole_cmd: NDArray[np.float64]) -> None:
        """Command dipole moment.

        Args:
            dipole_cmd: Desired dipole moment [mx, my, mz] (Am^2)
        """
        # Apply saturation limits per axis
        self._dipole = np.clip(dipole_cmd, -self.max_dipole, self.max_dipole)

    def get_dipole(self) -> NDArray[np.float64]:
        """Get current dipole moment.

        Returns:
            Dipole moment vector [mx, my, mz] (Am^2)
        """
        return self._dipole.copy()

    def compute_torque(self, b_field: NDArray[np.float64]) -> NDArray[np.float64]:
        """Compute torque from current dipole and magnetic field.

        T = m × B

        Args:
            b_field: Magnetic field vector in body frame (T)

        Returns:
            Torque vector (Nm)
        """
        return np.cross(self._dipole, b_field)

    def get_power(self) -> float:
        """Get current power consumption.

        Power model: P = k * |m|^2

        Returns:
            Power consumption (W)
        """
        dipole_magnitude_sq = np.sum(self._dipole**2)
        return self.power_per_dipole * dipole_magnitude_sq

    def get_state(self) -> dict:
        """Get current state.

        Returns:
            Dictionary containing dipole and power
        """
        return {
            "dipole": self._dipole.copy(),
            "power": self.get_power(),
        }

    def reset(self) -> None:
        """Reset to zero dipole."""
        self._dipole = np.zeros(3)
