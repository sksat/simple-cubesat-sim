"""Quaternion operations for attitude representation.

Convention: quaternion = [x, y, z, w] (scalar-last, Hamilton convention)

The quaternion q = [x, y, z, w] represents the rotation:
    q = cos(theta/2) + sin(theta/2) * (xi + yj + zk)
    where (x, y, z) is the unit rotation axis and theta is the rotation angle.
"""

import numpy as np
from numpy.typing import NDArray


def normalize(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Normalize quaternion to unit length.

    Args:
        q: Quaternion [x, y, z, w]

    Returns:
        Unit quaternion. Returns identity [0, 0, 0, 1] if input is zero.
    """
    norm = np.linalg.norm(q)
    if norm < 1e-15:
        return np.array([0.0, 0.0, 0.0, 1.0])
    return q / norm


def conjugate(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Compute quaternion conjugate.

    For q = [x, y, z, w], conj(q) = [-x, -y, -z, w]

    Args:
        q: Quaternion [x, y, z, w]

    Returns:
        Conjugate quaternion
    """
    return np.array([-q[0], -q[1], -q[2], q[3]])


def multiply(q1: NDArray[np.float64], q2: NDArray[np.float64]) -> NDArray[np.float64]:
    """Multiply two quaternions (Hamilton product).

    q1 * q2 represents rotation q2 followed by q1.

    Args:
        q1: First quaternion [x, y, z, w]
        q2: Second quaternion [x, y, z, w]

    Returns:
        Product quaternion [x, y, z, w]
    """
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2

    return np.array([
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
    ])


def from_axis_angle(axis: NDArray[np.float64], angle: float) -> NDArray[np.float64]:
    """Create quaternion from axis-angle representation.

    Args:
        axis: Rotation axis (unit vector or will be normalized)
        angle: Rotation angle in radians

    Returns:
        Unit quaternion [x, y, z, w]
    """
    axis_norm = np.linalg.norm(axis)
    if axis_norm < 1e-15:
        return np.array([0.0, 0.0, 0.0, 1.0])

    axis = axis / axis_norm
    half_angle = angle / 2
    sin_half = np.sin(half_angle)
    cos_half = np.cos(half_angle)

    return np.array([
        axis[0] * sin_half,
        axis[1] * sin_half,
        axis[2] * sin_half,
        cos_half,
    ])


def rotate_vector(q: NDArray[np.float64], v: NDArray[np.float64]) -> NDArray[np.float64]:
    """Rotate a vector by a quaternion.

    Computes v' = q * v * conj(q) where v is treated as a pure quaternion [vx, vy, vz, 0].

    Args:
        q: Unit quaternion [x, y, z, w]
        v: 3D vector to rotate

    Returns:
        Rotated 3D vector
    """
    # Pure quaternion from vector
    v_quat = np.array([v[0], v[1], v[2], 0.0])

    # q * v * conj(q)
    result = multiply(multiply(q, v_quat), conjugate(q))

    return result[:3]


def to_rotation_matrix(q: NDArray[np.float64]) -> NDArray[np.float64]:
    """Convert quaternion to 3x3 rotation matrix.

    Args:
        q: Unit quaternion [x, y, z, w]

    Returns:
        3x3 rotation matrix
    """
    x, y, z, w = q

    # Precompute common terms
    xx = x * x
    yy = y * y
    zz = z * z
    xy = x * y
    xz = x * z
    yz = y * z
    wx = w * x
    wy = w * y
    wz = w * z

    return np.array([
        [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)],
        [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)],
        [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)],
    ])


def from_euler(roll: float, pitch: float, yaw: float) -> NDArray[np.float64]:
    """Create quaternion from Euler angles (ZYX convention).

    Rotation order: first roll (X), then pitch (Y), then yaw (Z).
    This is the aerospace convention (intrinsic ZYX = extrinsic XYZ).

    Args:
        roll: Rotation about X axis (radians)
        pitch: Rotation about Y axis (radians)
        yaw: Rotation about Z axis (radians)

    Returns:
        Unit quaternion [x, y, z, w]
    """
    cr = np.cos(roll / 2)
    sr = np.sin(roll / 2)
    cp = np.cos(pitch / 2)
    sp = np.sin(pitch / 2)
    cy = np.cos(yaw / 2)
    sy = np.sin(yaw / 2)

    return np.array([
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
        cr * cp * cy + sr * sp * sy,
    ])


def to_euler(q: NDArray[np.float64]) -> tuple[float, float, float]:
    """Convert quaternion to Euler angles (ZYX convention).

    Args:
        q: Unit quaternion [x, y, z, w]

    Returns:
        (roll, pitch, yaw) in radians
    """
    x, y, z, w = q

    # Roll (X-axis rotation)
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = np.arctan2(sinr_cosp, cosr_cosp)

    # Pitch (Y-axis rotation)
    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = np.copysign(np.pi / 2, sinp)  # Gimbal lock
    else:
        pitch = np.arcsin(sinp)

    # Yaw (Z-axis rotation)
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = np.arctan2(siny_cosp, cosy_cosp)

    return roll, pitch, yaw


def error(q_current: NDArray[np.float64], q_target: NDArray[np.float64]) -> NDArray[np.float64]:
    """Compute quaternion error for attitude control.

    Returns q_err such that q_current = q_err * q_target.
    The vector part of q_err is proportional to the rotation error.

    Args:
        q_current: Current attitude quaternion
        q_target: Target attitude quaternion

    Returns:
        Error quaternion [x, y, z, w]
    """
    # q_err = q_current * conj(q_target)
    q_err = multiply(q_current, conjugate(q_target))

    # Ensure shortest path (w should be positive)
    if q_err[3] < 0:
        q_err = -q_err

    return q_err


def from_dcm(dcm: NDArray[np.float64]) -> NDArray[np.float64]:
    """Convert rotation matrix (DCM) to quaternion.

    Uses Shepperd's method for numerical stability.

    Args:
        dcm: 3x3 rotation matrix

    Returns:
        Unit quaternion [x, y, z, w]
    """
    trace = dcm[0, 0] + dcm[1, 1] + dcm[2, 2]

    if trace > 0:
        s = 0.5 / np.sqrt(trace + 1.0)
        w = 0.25 / s
        x = (dcm[2, 1] - dcm[1, 2]) * s
        y = (dcm[0, 2] - dcm[2, 0]) * s
        z = (dcm[1, 0] - dcm[0, 1]) * s
    elif dcm[0, 0] > dcm[1, 1] and dcm[0, 0] > dcm[2, 2]:
        s = 2.0 * np.sqrt(1.0 + dcm[0, 0] - dcm[1, 1] - dcm[2, 2])
        w = (dcm[2, 1] - dcm[1, 2]) / s
        x = 0.25 * s
        y = (dcm[0, 1] + dcm[1, 0]) / s
        z = (dcm[0, 2] + dcm[2, 0]) / s
    elif dcm[1, 1] > dcm[2, 2]:
        s = 2.0 * np.sqrt(1.0 + dcm[1, 1] - dcm[0, 0] - dcm[2, 2])
        w = (dcm[0, 2] - dcm[2, 0]) / s
        x = (dcm[0, 1] + dcm[1, 0]) / s
        y = 0.25 * s
        z = (dcm[1, 2] + dcm[2, 1]) / s
    else:
        s = 2.0 * np.sqrt(1.0 + dcm[2, 2] - dcm[0, 0] - dcm[1, 1])
        w = (dcm[1, 0] - dcm[0, 1]) / s
        x = (dcm[0, 2] + dcm[2, 0]) / s
        y = (dcm[1, 2] + dcm[2, 1]) / s
        z = 0.25 * s

    q = np.array([x, y, z, w])

    # Ensure positive scalar part for consistency
    if w < 0:
        q = -q

    return normalize(q)


def make_dcm_from_two_vectors(
    v1: NDArray[np.float64],
    v2: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Create DCM from two direction vectors.

    Creates a coordinate frame where:
    - X axis is aligned with v1
    - Y axis is in the plane spanned by v1 and v2, orthogonal to X
    - Z axis = X × Y (right-handed)

    Args:
        v1: First direction vector (will be X axis after normalization)
        v2: Second direction vector (used to define XY plane)

    Returns:
        3x3 DCM where rows are the coordinate frame axes

    Raises:
        ValueError: If vectors are parallel or zero
    """
    # Normalize v1 -> X axis
    v1_norm = np.linalg.norm(v1)
    if v1_norm < 1e-10:
        raise ValueError("v1 is zero vector")
    x_axis = v1 / v1_norm

    # Make v2 orthogonal to v1 using Gram-Schmidt
    # v2' = v2 - (v2 · x) * x
    v2_proj = v2 - np.dot(v2, x_axis) * x_axis
    v2_norm = np.linalg.norm(v2_proj)
    if v2_norm < 1e-10:
        raise ValueError("v1 and v2 are parallel")
    y_axis = v2_proj / v2_norm

    # Z axis = X × Y
    z_axis = np.cross(x_axis, y_axis)

    # DCM rows are the axes
    return np.array([x_axis, y_axis, z_axis], dtype=np.float64)
