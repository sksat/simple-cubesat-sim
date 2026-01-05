"""Unit tests for quaternion operations.

TDD: Write tests first, then implement.
Convention: quaternion = [x, y, z, w] (scalar-last)
"""

import numpy as np
import pytest
from hypothesis import given, strategies as st

from backend.dynamics.quaternion import (
    conjugate,
    from_axis_angle,
    from_euler,
    multiply,
    normalize,
    rotate_vector,
    to_euler,
    to_rotation_matrix,
)


class TestQuaternionNormalize:
    """Tests for quaternion normalization."""

    def test_identity_quaternion_unchanged(self):
        """Identity quaternion [0, 0, 0, 1] should remain unchanged."""
        q = np.array([0.0, 0.0, 0.0, 1.0])
        result = normalize(q)
        np.testing.assert_array_almost_equal(result, q)

    def test_normalized_has_unit_norm(self):
        """Any quaternion when normalized should have |q| = 1."""
        q = np.array([1.0, 2.0, 3.0, 4.0])
        result = normalize(q)
        assert np.isclose(np.linalg.norm(result), 1.0)

    def test_zero_quaternion_returns_identity(self):
        """Zero quaternion should return identity to avoid NaN."""
        q = np.array([0.0, 0.0, 0.0, 0.0])
        result = normalize(q)
        np.testing.assert_array_almost_equal(result, [0.0, 0.0, 0.0, 1.0])

    @given(
        st.lists(
            st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False),
            min_size=4,
            max_size=4,
        )
    )
    def test_normalized_always_unit_norm(self, q_list):
        """Property: normalized quaternion always has unit norm."""
        q = np.array(q_list)
        result = normalize(q)
        assert np.isclose(np.linalg.norm(result), 1.0, atol=1e-10)


class TestQuaternionMultiply:
    """Tests for quaternion multiplication."""

    def test_identity_multiplication(self):
        """Multiplying by identity should return the same quaternion."""
        q = np.array([0.1, 0.2, 0.3, 0.9])
        q = normalize(q)
        identity = np.array([0.0, 0.0, 0.0, 1.0])
        result = multiply(q, identity)
        np.testing.assert_array_almost_equal(result, q)

    def test_multiply_by_conjugate_gives_identity(self):
        """q * conj(q) should give identity (for unit quaternion)."""
        q = normalize(np.array([1.0, 2.0, 3.0, 4.0]))
        q_conj = conjugate(q)
        result = multiply(q, q_conj)
        np.testing.assert_array_almost_equal(result, [0.0, 0.0, 0.0, 1.0], decimal=10)

    def test_multiplication_order_matters(self):
        """Quaternion multiplication is not commutative."""
        q1 = normalize(np.array([1.0, 0.0, 0.0, 1.0]))
        q2 = normalize(np.array([0.0, 1.0, 0.0, 1.0]))
        result1 = multiply(q1, q2)
        result2 = multiply(q2, q1)
        assert not np.allclose(result1, result2)


class TestQuaternionConjugate:
    """Tests for quaternion conjugate."""

    def test_conjugate_negates_vector_part(self):
        """Conjugate should negate x, y, z but keep w."""
        q = np.array([1.0, 2.0, 3.0, 4.0])
        result = conjugate(q)
        expected = np.array([-1.0, -2.0, -3.0, 4.0])
        np.testing.assert_array_almost_equal(result, expected)

    def test_double_conjugate_is_identity(self):
        """conj(conj(q)) = q."""
        q = np.array([1.0, 2.0, 3.0, 4.0])
        result = conjugate(conjugate(q))
        np.testing.assert_array_almost_equal(result, q)


class TestQuaternionFromAxisAngle:
    """Tests for axis-angle to quaternion conversion."""

    def test_zero_rotation(self):
        """Zero rotation should give identity quaternion."""
        axis = np.array([1.0, 0.0, 0.0])
        angle = 0.0
        result = from_axis_angle(axis, angle)
        np.testing.assert_array_almost_equal(result, [0.0, 0.0, 0.0, 1.0])

    def test_90_degree_rotation_about_z(self):
        """90 degree rotation about Z axis."""
        axis = np.array([0.0, 0.0, 1.0])
        angle = np.pi / 2
        result = from_axis_angle(axis, angle)
        expected = np.array([0.0, 0.0, np.sin(np.pi / 4), np.cos(np.pi / 4)])
        np.testing.assert_array_almost_equal(result, expected)

    def test_180_degree_rotation(self):
        """180 degree rotation about X axis."""
        axis = np.array([1.0, 0.0, 0.0])
        angle = np.pi
        result = from_axis_angle(axis, angle)
        expected = np.array([1.0, 0.0, 0.0, 0.0])
        np.testing.assert_array_almost_equal(result, expected)


class TestQuaternionRotateVector:
    """Tests for rotating vectors with quaternions."""

    def test_identity_rotation(self):
        """Identity quaternion should not change the vector."""
        q = np.array([0.0, 0.0, 0.0, 1.0])
        v = np.array([1.0, 2.0, 3.0])
        result = rotate_vector(q, v)
        np.testing.assert_array_almost_equal(result, v)

    def test_90_degree_rotation_z_axis(self):
        """90 degree rotation about Z: [1,0,0] -> [0,1,0]."""
        q = from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 2)
        v = np.array([1.0, 0.0, 0.0])
        result = rotate_vector(q, v)
        expected = np.array([0.0, 1.0, 0.0])
        np.testing.assert_array_almost_equal(result, expected, decimal=10)

    def test_180_degree_rotation_z_axis(self):
        """180 degree rotation about Z: [1,0,0] -> [-1,0,0]."""
        q = from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi)
        v = np.array([1.0, 0.0, 0.0])
        result = rotate_vector(q, v)
        expected = np.array([-1.0, 0.0, 0.0])
        np.testing.assert_array_almost_equal(result, expected, decimal=10)

    def test_rotation_preserves_magnitude(self):
        """Rotation should preserve vector magnitude."""
        q = from_axis_angle(np.array([1.0, 1.0, 1.0]), np.pi / 3)
        v = np.array([1.0, 2.0, 3.0])
        result = rotate_vector(q, v)
        assert np.isclose(np.linalg.norm(result), np.linalg.norm(v))


class TestQuaternionToRotationMatrix:
    """Tests for quaternion to rotation matrix conversion."""

    def test_identity_gives_identity_matrix(self):
        """Identity quaternion should give 3x3 identity matrix."""
        q = np.array([0.0, 0.0, 0.0, 1.0])
        result = to_rotation_matrix(q)
        np.testing.assert_array_almost_equal(result, np.eye(3))

    def test_rotation_matrix_is_orthogonal(self):
        """Rotation matrix should be orthogonal: R @ R.T = I."""
        q = normalize(np.array([1.0, 2.0, 3.0, 4.0]))
        R = to_rotation_matrix(q)
        np.testing.assert_array_almost_equal(R @ R.T, np.eye(3))

    def test_rotation_matrix_has_determinant_one(self):
        """Rotation matrix should have det(R) = 1."""
        q = normalize(np.array([1.0, 2.0, 3.0, 4.0]))
        R = to_rotation_matrix(q)
        assert np.isclose(np.linalg.det(R), 1.0)


class TestEulerConversion:
    """Tests for Euler angle conversions (ZYX convention: yaw, pitch, roll)."""

    def test_zero_euler_gives_identity(self):
        """Zero Euler angles should give identity quaternion."""
        result = from_euler(0.0, 0.0, 0.0)
        np.testing.assert_array_almost_equal(result, [0.0, 0.0, 0.0, 1.0])

    def test_round_trip_conversion(self):
        """from_euler -> to_euler should return original angles."""
        roll, pitch, yaw = 0.3, 0.2, 0.5
        q = from_euler(roll, pitch, yaw)
        r2, p2, y2 = to_euler(q)
        assert np.isclose(roll, r2, atol=1e-10)
        assert np.isclose(pitch, p2, atol=1e-10)
        assert np.isclose(yaw, y2, atol=1e-10)

    def test_90_degree_yaw(self):
        """90 degree yaw rotation."""
        q = from_euler(0.0, 0.0, np.pi / 2)
        roll, pitch, yaw = to_euler(q)
        assert np.isclose(yaw, np.pi / 2, atol=1e-10)
        assert np.isclose(roll, 0.0, atol=1e-10)
        assert np.isclose(pitch, 0.0, atol=1e-10)
