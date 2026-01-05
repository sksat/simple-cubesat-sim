"""3-axis attitude controller using quaternion error feedback.

This controller uses a PD (Proportional-Derivative) control law
with quaternion error feedback for 3-axis attitude control.

Control Law:
    T = -Kp * q_err_vec - Kd * ω

where:
    T: commanded torque (Nm)
    Kp: proportional gain (Nm/rad, scalar or 3x3 matrix)
    Kd: derivative gain (Nms/rad, scalar or 3x3 matrix)
    q_err_vec: vector part [x, y, z] of quaternion error
    ω: angular velocity in body frame (rad/s)

Quaternion Error:
    q_err = q_target^(-1) ⊗ q_current

    For small errors, q_err_vec ≈ sin(θ/2) * axis ≈ θ/2 * axis
    So -Kp * q_err_vec produces torque toward the target.

Shortest Path:
    If q_err.w < 0, we negate q_err to ensure shortest rotation path.
"""

import numpy as np
from numpy.typing import NDArray

from backend.dynamics.quaternion import conjugate, multiply, normalize


class AttitudeController:
    """PD attitude controller with quaternion error feedback.

    Attributes:
        kp: Proportional gain
        kd: Derivative gain
        max_torque: Maximum torque per axis (Nm)
    """

    def __init__(
        self,
        kp: float = 0.01,
        kd: float = 0.1,
        max_torque: float = 0.001,
    ):
        """Initialize attitude controller.

        Args:
            kp: Proportional gain (Nm). Typical range: 0.001 to 0.1
            kd: Derivative gain (Nms). Typical range: 0.01 to 1.0
            max_torque: Maximum torque per axis (Nm)

        Raises:
            ValueError: If gains are negative
        """
        if kp < 0:
            raise ValueError("kp gain must be non-negative")
        if kd < 0:
            raise ValueError("kd gain must be non-negative")

        self.kp = kp
        self.kd = kd
        self.max_torque = max_torque
        self._target = np.array([0.0, 0.0, 0.0, 1.0])  # Identity quaternion

    def compute_error(
        self,
        q_current: NDArray[np.float64],
        q_target: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Compute quaternion error.

        q_err = q_target^(-1) ⊗ q_current

        Args:
            q_current: Current attitude quaternion [x, y, z, w]
            q_target: Target attitude quaternion [x, y, z, w]

        Returns:
            Error quaternion [x, y, z, w] with w >= 0 (shortest path)
        """
        # q_err = conj(q_target) * q_current
        q_target_inv = conjugate(q_target)
        q_err = multiply(q_target_inv, q_current)

        # Ensure shortest path by making w positive
        if q_err[3] < 0:
            q_err = -q_err

        return q_err

    def compute(
        self,
        q_current: NDArray[np.float64],
        q_target: NDArray[np.float64],
        omega: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Compute control torque.

        T = -Kp * q_err_vec - Kd * ω

        Args:
            q_current: Current attitude quaternion [x, y, z, w]
            q_target: Target attitude quaternion [x, y, z, w]
            omega: Angular velocity in body frame (rad/s)

        Returns:
            Commanded torque [Tx, Ty, Tz] (Nm)
        """
        # Compute quaternion error
        q_err = self.compute_error(q_current, q_target)

        # Extract vector part (proportional to rotation axis * sin(θ/2))
        q_err_vec = q_err[:3]

        # PD control law
        # Proportional term: drives attitude toward target
        # Derivative term: damps angular velocity
        torque = -self.kp * q_err_vec - self.kd * omega

        # Apply saturation limits
        torque = np.clip(torque, -self.max_torque, self.max_torque)

        return torque

    def get_error_angle(
        self,
        q_current: NDArray[np.float64],
        q_target: NDArray[np.float64],
    ) -> float:
        """Get attitude error as angle in degrees.

        Args:
            q_current: Current attitude quaternion
            q_target: Target attitude quaternion

        Returns:
            Error angle in degrees
        """
        q_err = self.compute_error(q_current, q_target)

        # For unit quaternion, angle = 2 * arccos(|w|)
        # Since we ensure w >= 0, we can use w directly
        w = np.clip(q_err[3], -1.0, 1.0)
        angle_rad = 2.0 * np.arccos(np.abs(w))

        return np.degrees(angle_rad)

    def set_target(self, q_target: NDArray[np.float64]) -> None:
        """Set target attitude.

        Args:
            q_target: Target attitude quaternion [x, y, z, w]
        """
        self._target = normalize(q_target)

    def get_target(self) -> NDArray[np.float64]:
        """Get current target attitude.

        Returns:
            Target quaternion [x, y, z, w]
        """
        return self._target.copy()
