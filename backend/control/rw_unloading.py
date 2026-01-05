"""Reaction wheel momentum unloading controller.

RW momentum unloading uses magnetorquers (MTQ) to dump accumulated
angular momentum from the reaction wheels without causing large
attitude disturbances.

Control Law:
    m = k * (B × H_rw) / |B|^2

where:
    m: commanded MTQ dipole moment (Am^2)
    k: unloading gain
    B: magnetic field vector in body frame (T)
    H_rw: total RW momentum vector (Nms)

Physical Principle:
    The MTQ torque is T_mtq = m × B
    Substituting the control law:
        T_mtq = k * (B × H_rw) × B / |B|^2

    Using the vector triple product identity (a × b) × c = b(a·c) - a(b·c):
        T_mtq = k * [H_rw(B·B) - B(B·H_rw)] / |B|^2
              = k * [H_rw - B(B·H_rw)/|B|^2]
              = k * [H_rw - (H_rw·B̂)B̂]

    This is k times the component of H_rw perpendicular to B.
    The torque works to reduce this perpendicular component of H_rw.

Note:
    The component of H_rw parallel to B cannot be unloaded using MTQ
    because m × B = 0 when m is parallel to B. This is a fundamental
    limitation of magnetic attitude control.
"""

import numpy as np
from numpy.typing import NDArray


class RWUnloadingController:
    """Reaction wheel momentum unloading controller using magnetorquers.

    Attributes:
        gain: Unloading gain k
        max_dipole: Maximum dipole moment per axis (Am^2)
        min_bfield: Minimum B-field magnitude for safe operation (T)
    """

    def __init__(
        self,
        gain: float = 1e4,
        max_dipole: float = 0.2,
        min_bfield: float = 1e-8,
    ):
        """Initialize RW unloading controller.

        Args:
            gain: Unloading gain. Typical range: 1e3 to 1e5
            max_dipole: Maximum dipole moment per axis (Am^2)
            min_bfield: Minimum B-field magnitude for safe computation (T)

        Raises:
            ValueError: If gain is negative
        """
        if gain < 0:
            raise ValueError("gain must be non-negative")

        self.gain = gain
        self.max_dipole = max_dipole
        self.min_bfield = min_bfield

    def compute(
        self,
        h_rw: NDArray[np.float64],
        b_field: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Compute MTQ dipole command for momentum unloading.

        m = k * (B × H_rw) / |B|^2

        Args:
            h_rw: Total RW momentum vector (Nms)
            b_field: Magnetic field vector in body frame (T)

        Returns:
            Commanded MTQ dipole moment (Am^2)
        """
        # Check for zero or very small B-field
        b_mag_sq = np.dot(b_field, b_field)
        if b_mag_sq < self.min_bfield**2:
            return np.array([0.0, 0.0, 0.0])

        # Check for zero momentum
        if np.linalg.norm(h_rw) < 1e-15:
            return np.array([0.0, 0.0, 0.0])

        # Control law: m = k * (B × H_rw) / |B|^2
        b_cross_h = np.cross(b_field, h_rw)
        dipole = self.gain * b_cross_h / b_mag_sq

        # Apply saturation limits
        dipole = np.clip(dipole, -self.max_dipole, self.max_dipole)

        return dipole

    def compute_torque(
        self,
        h_rw: NDArray[np.float64],
        b_field: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Compute the resulting MTQ torque for unloading.

        T = m × B

        Args:
            h_rw: Total RW momentum vector (Nms)
            b_field: Magnetic field vector in body frame (T)

        Returns:
            MTQ torque vector (Nm)
        """
        dipole = self.compute(h_rw, b_field)
        return np.cross(dipole, b_field)

    def get_unloadable_momentum(
        self,
        h_rw: NDArray[np.float64],
        b_field: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Get the component of H_rw that can be unloaded.

        Only the component perpendicular to B can be unloaded.

        Args:
            h_rw: Total RW momentum vector (Nms)
            b_field: Magnetic field vector in body frame (T)

        Returns:
            Unloadable momentum component (Nms)
        """
        b_mag_sq = np.dot(b_field, b_field)
        if b_mag_sq < self.min_bfield**2:
            return np.array([0.0, 0.0, 0.0])

        # Component parallel to B (cannot be unloaded)
        h_parallel = np.dot(h_rw, b_field) / b_mag_sq * b_field

        # Component perpendicular to B (can be unloaded)
        h_perp = h_rw - h_parallel

        return h_perp
