"""B-dot detumbling controller.

B-dot control is used for magnetic detumbling after satellite deployment.
It uses magnetorquers to dissipate rotational kinetic energy by
generating torque that opposes angular velocity.

Control Law:
    m = -k * dB/dt

where:
    m: commanded dipole moment (Am^2)
    k: control gain
    dB/dt: time derivative of magnetic field in body frame (T/s)

Physical Principle:
    Torque T = m × B
    When m ∝ -dB/dt, the resulting torque opposes angular velocity,
    which dissipates rotational kinetic energy.

Note:
    dB/dt ≈ -ω × B (for slowly varying B in inertial frame)
    So m ∝ -dB/dt ∝ ω × B, leading to T ∝ (ω × B) × B
    This always has a component opposing ω.
"""

import numpy as np
from numpy.typing import NDArray


class BdotController:
    """B-dot detumbling controller.

    Attributes:
        gain: Control gain k (Am^2 / (T/s))
        max_dipole: Maximum dipole moment per axis (Am^2)
    """

    def __init__(self, gain: float, max_dipole: float = 0.2):
        """Initialize B-dot controller.

        Args:
            gain: Control gain k. Typical values: 1e5 to 1e7
            max_dipole: Maximum dipole moment per axis (Am^2).
                       Typical for 6U CubeSat: 0.2 Am^2

        Raises:
            ValueError: If gain is not positive
        """
        if gain <= 0:
            raise ValueError("gain must be positive")
        self.gain = gain
        self.max_dipole = max_dipole

    def compute(self, b_dot: NDArray[np.float64]) -> NDArray[np.float64]:
        """Compute dipole moment command from dB/dt.

        Args:
            b_dot: Time derivative of magnetic field in body frame (T/s)

        Returns:
            Commanded dipole moment (Am^2)
        """
        # Safety check for invalid inputs
        if not np.all(np.isfinite(b_dot)):
            return np.array([0.0, 0.0, 0.0])

        # Control law: m = -k * dB/dt
        dipole = -self.gain * b_dot

        # Apply saturation limits (per-axis clipping)
        dipole = np.clip(dipole, -self.max_dipole, self.max_dipole)

        return dipole

    def compute_bdot(
        self,
        b_prev: NDArray[np.float64],
        b_curr: NDArray[np.float64],
        dt: float,
    ) -> NDArray[np.float64]:
        """Compute dB/dt from two magnetometer measurements.

        Args:
            b_prev: Previous magnetic field measurement (T)
            b_curr: Current magnetic field measurement (T)
            dt: Time between measurements (s)

        Returns:
            Estimated dB/dt (T/s)
        """
        return (b_curr - b_prev) / dt

    def update(
        self,
        b_prev: NDArray[np.float64],
        b_curr: NDArray[np.float64],
        dt: float,
    ) -> NDArray[np.float64]:
        """Full control update: compute dB/dt and dipole command.

        Args:
            b_prev: Previous magnetic field measurement (T)
            b_curr: Current magnetic field measurement (T)
            dt: Time between measurements (s)

        Returns:
            Commanded dipole moment (Am^2)
        """
        b_dot = self.compute_bdot(b_prev, b_curr, dt)
        return self.compute(b_dot)

    @staticmethod
    def compute_torque(
        dipole: NDArray[np.float64],
        b_field: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Compute torque from dipole moment and magnetic field.

        T = m × B

        Args:
            dipole: Dipole moment vector (Am^2)
            b_field: Magnetic field vector (T)

        Returns:
            Torque vector (Nm)
        """
        return np.cross(dipole, b_field)
