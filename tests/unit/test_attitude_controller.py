"""Unit tests for 3-axis attitude controller.

TDD: Write tests first, then implement.

Quaternion-based PD attitude controller:
    T = -Kp * q_err_vec - Kd * ω

where:
    T: commanded torque (Nm)
    Kp: proportional gain matrix
    Kd: derivative gain matrix
    q_err_vec: vector part of quaternion error
    ω: angular velocity (rad/s)
"""

import numpy as np
import pytest

from backend.control.attitude_controller import AttitudeController
from backend.dynamics.quaternion import from_axis_angle, from_euler, multiply, normalize


class TestAttitudeControllerBasic:
    """Basic functionality tests for attitude controller."""

    def test_zero_error_produces_zero_torque(self):
        """At target attitude with zero rate, torque should be zero."""
        controller = AttitudeController(kp=0.1, kd=0.5)

        q_current = np.array([0.0, 0.0, 0.0, 1.0])
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.0, 0.0, 0.0])

        torque = controller.compute(q_current, q_target, omega)

        np.testing.assert_array_almost_equal(torque, [0.0, 0.0, 0.0])

    def test_attitude_error_produces_torque(self):
        """Attitude error should produce non-zero torque."""
        controller = AttitudeController(kp=0.1, kd=0.5)

        q_current = from_axis_angle(np.array([0.0, 0.0, 1.0]), 0.1)  # 0.1 rad around Z
        q_target = np.array([0.0, 0.0, 0.0, 1.0])  # Identity
        omega = np.array([0.0, 0.0, 0.0])

        torque = controller.compute(q_current, q_target, omega)

        # Should produce torque around Z to correct the error
        assert np.linalg.norm(torque) > 0

    def test_rate_error_produces_damping_torque(self):
        """Non-zero angular velocity should produce damping torque."""
        controller = AttitudeController(kp=0.1, kd=0.5)

        q_current = np.array([0.0, 0.0, 0.0, 1.0])
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.0, 0.0, 0.1])  # Rotating around Z

        torque = controller.compute(q_current, q_target, omega)

        # Damping torque should oppose angular velocity
        assert torque[2] < 0  # Negative torque to oppose positive omega_z


class TestAttitudeControllerQuaternionError:
    """Tests for quaternion error computation."""

    def test_quaternion_error_calculation(self):
        """Verify quaternion error q_err = q_target^-1 * q_current."""
        controller = AttitudeController(kp=0.1, kd=0.5)

        # 30 degree rotation around Z
        angle = np.pi / 6
        q_current = from_axis_angle(np.array([0.0, 0.0, 1.0]), angle)
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.0, 0.0, 0.0])

        q_err = controller.compute_error(q_current, q_target)

        # For rotation around Z, error vector should be in Z direction
        assert np.abs(q_err[2]) > np.abs(q_err[0])
        assert np.abs(q_err[2]) > np.abs(q_err[1])

    def test_short_rotation_path_selected(self):
        """Controller should use shortest rotation path (quaternion sign)."""
        controller = AttitudeController(kp=0.1, kd=0.5)

        # Create quaternion and its negative (represent same rotation)
        q_current = from_axis_angle(np.array([0.0, 0.0, 1.0]), 0.5)
        q_current_neg = -q_current
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.0, 0.0, 0.0])

        torque1 = controller.compute(q_current, q_target, omega)
        torque2 = controller.compute(q_current_neg, q_target, omega)

        # Both should produce similar torque (shortest path)
        np.testing.assert_array_almost_equal(torque1, torque2, decimal=5)

    def test_large_rotation_uses_shortest_path(self):
        """For rotations > 180 deg, should go the short way."""
        controller = AttitudeController(kp=0.1, kd=0.5)

        # 270 degree rotation (should go -90 instead)
        angle = 3 * np.pi / 2  # 270 deg
        q_current = from_axis_angle(np.array([0.0, 0.0, 1.0]), angle)
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.0, 0.0, 0.0])

        q_err = controller.compute_error(q_current, q_target)

        # Error should correspond to -90 deg, not +270 deg
        # For -90 deg around Z: q_err ≈ [0, 0, -sin(45°), cos(45°)]
        # The w component should be positive (shortest path)
        assert q_err[3] >= 0


class TestAttitudeControllerGains:
    """Tests for gain behavior."""

    def test_higher_kp_produces_larger_proportional_torque(self):
        """Increasing Kp should increase proportional response."""
        q_current = from_axis_angle(np.array([0.0, 0.0, 1.0]), 0.1)
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.0, 0.0, 0.0])

        # Use high max_torque to avoid saturation
        controller_low = AttitudeController(kp=0.05, kd=0.5, max_torque=1.0)
        controller_high = AttitudeController(kp=0.2, kd=0.5, max_torque=1.0)

        torque_low = controller_low.compute(q_current, q_target, omega)
        torque_high = controller_high.compute(q_current, q_target, omega)

        # Higher Kp should give larger torque
        assert np.linalg.norm(torque_high) > np.linalg.norm(torque_low)

    def test_higher_kd_produces_more_damping(self):
        """Increasing Kd should increase damping response."""
        q_current = np.array([0.0, 0.0, 0.0, 1.0])
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.0, 0.0, 0.1])

        # Use high max_torque to avoid saturation
        controller_low = AttitudeController(kp=0.1, kd=0.2, max_torque=1.0)
        controller_high = AttitudeController(kp=0.1, kd=1.0, max_torque=1.0)

        torque_low = controller_low.compute(q_current, q_target, omega)
        torque_high = controller_high.compute(q_current, q_target, omega)

        # Higher Kd should give larger damping torque
        assert np.abs(torque_high[2]) > np.abs(torque_low[2])

    def test_negative_gains_rejected(self):
        """Controller should reject negative gains."""
        with pytest.raises(ValueError, match="gain"):
            AttitudeController(kp=-0.1, kd=0.5)

        with pytest.raises(ValueError, match="gain"):
            AttitudeController(kp=0.1, kd=-0.5)


class TestAttitudeControllerDirection:
    """Tests for control torque direction."""

    def test_proportional_term_direction(self):
        """Proportional torque should drive attitude toward target."""
        controller = AttitudeController(kp=0.1, kd=0.0)  # No damping

        # Current attitude rotated 10 deg around Z from target
        q_current = from_axis_angle(np.array([0.0, 0.0, 1.0]), 0.175)  # ~10 deg
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.0, 0.0, 0.0])

        torque = controller.compute(q_current, q_target, omega)

        # Torque should be negative Z to rotate back toward target
        assert torque[2] < 0

    def test_derivative_term_opposes_velocity(self):
        """Derivative torque should oppose angular velocity."""
        controller = AttitudeController(kp=0.0, kd=0.5)  # No proportional

        q_current = np.array([0.0, 0.0, 0.0, 1.0])
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.05, -0.03, 0.08])

        torque = controller.compute(q_current, q_target, omega)

        # Each torque component should oppose corresponding omega
        assert torque[0] * omega[0] < 0
        assert torque[1] * omega[1] < 0
        assert torque[2] * omega[2] < 0


class TestAttitudeControllerConvergence:
    """Tests for attitude convergence."""

    def test_attitude_converges_to_target(self):
        """Closed-loop simulation should converge to target attitude.

        Note: Controller outputs torque needed for spacecraft.
        RW command_torque() is wheel torque, so we negate: rw.command_torque(-T_sc)
        """
        from backend.actuators.reaction_wheel import ReactionWheel

        controller = AttitudeController(kp=0.01, kd=0.1, max_torque=0.001)
        rw = ReactionWheel(inertia=1e-4, max_speed=628.3, max_torque=0.001)

        # Spacecraft inertia
        I_sc = np.diag([0.05, 0.05, 0.02])

        # Initial attitude: 20 deg rotation around X
        q = from_axis_angle(np.array([1.0, 0.0, 0.0]), 0.35)  # ~20 deg
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.0, 0.0, 0.0])

        dt = 0.01
        duration = 60.0  # 60 seconds
        num_steps = int(duration / dt)

        initial_error = np.linalg.norm(controller.compute_error(q, q_target)[:3])

        for _ in range(num_steps):
            # Control: output is spacecraft torque
            torque_sc = controller.compute(q, q_target, omega)
            # RW command is negated (wheel torque = -spacecraft torque)
            rw.command_torque(-torque_sc)
            rw.update(dt)

            # Spacecraft dynamics (torque from RW is opposite of wheel torque)
            torque_on_sc = rw.get_torque_on_spacecraft()
            omega_dot = np.linalg.solve(I_sc, torque_on_sc)
            omega = omega + omega_dot * dt

            # Quaternion integration
            omega_quat = np.array([omega[0], omega[1], omega[2], 0.0])
            q_dot = 0.5 * multiply(q, omega_quat)
            q = normalize(q + q_dot * dt)

        final_error = np.linalg.norm(controller.compute_error(q, q_target)[:3])

        # Error should have decreased significantly
        assert final_error < initial_error * 0.3, (
            f"Failed to converge: {initial_error:.4f} -> {final_error:.4f}"
        )

    def test_rate_damps_to_zero(self):
        """Angular velocity should damp to near-zero."""
        from backend.actuators.reaction_wheel import ReactionWheel

        controller = AttitudeController(kp=0.01, kd=0.1, max_torque=0.001)
        rw = ReactionWheel(inertia=1e-4, max_speed=628.3, max_torque=0.001)

        I_sc = np.diag([0.05, 0.05, 0.02])

        q = np.array([0.0, 0.0, 0.0, 1.0])
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.05, 0.03, -0.04])  # Initial rotation

        initial_rate = np.linalg.norm(omega)

        dt = 0.01
        duration = 30.0
        num_steps = int(duration / dt)

        for _ in range(num_steps):
            torque_sc = controller.compute(q, q_target, omega)
            rw.command_torque(-torque_sc)  # Negate for RW
            rw.update(dt)

            torque_on_sc = rw.get_torque_on_spacecraft()
            omega_dot = np.linalg.solve(I_sc, torque_on_sc)
            omega = omega + omega_dot * dt

            omega_quat = np.array([omega[0], omega[1], omega[2], 0.0])
            q_dot = 0.5 * multiply(q, omega_quat)
            q = normalize(q + q_dot * dt)

        final_rate = np.linalg.norm(omega)

        # Rate should be much smaller
        assert final_rate < initial_rate * 0.2, (
            f"Failed to damp: {initial_rate:.4f} -> {final_rate:.4f} rad/s"
        )


class TestAttitudeControllerSaturation:
    """Tests for torque saturation."""

    def test_output_respects_max_torque(self):
        """Output torque should be limited to max_torque."""
        max_torque = 0.001
        controller = AttitudeController(kp=1.0, kd=1.0, max_torque=max_torque)

        # Large error to saturate output
        q_current = from_axis_angle(np.array([1.0, 1.0, 1.0]), 1.0)
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.5, 0.5, 0.5])

        torque = controller.compute(q_current, q_target, omega)

        # Each component should be within limits
        assert np.all(np.abs(torque) <= max_torque + 1e-10)

    def test_large_error_saturates(self):
        """Large attitude error should saturate torque."""
        max_torque = 0.001
        controller = AttitudeController(kp=0.1, kd=0.5, max_torque=max_torque)

        # 90 degree rotation - large error
        q_current = from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 2)
        q_target = np.array([0.0, 0.0, 0.0, 1.0])
        omega = np.array([0.0, 0.0, 0.0])

        torque = controller.compute(q_current, q_target, omega)

        # Should be saturated at max
        assert np.isclose(np.abs(torque[2]), max_torque) or np.abs(torque[2]) < max_torque


class TestAttitudeControllerState:
    """Tests for state management."""

    def test_get_error_angle(self):
        """Should return error angle in degrees."""
        controller = AttitudeController(kp=0.1, kd=0.5)

        # 30 degree rotation
        q_current = from_axis_angle(np.array([0.0, 0.0, 1.0]), np.pi / 6)
        q_target = np.array([0.0, 0.0, 0.0, 1.0])

        error_deg = controller.get_error_angle(q_current, q_target)

        assert np.isclose(error_deg, 30.0, atol=1.0)

    def test_set_target(self):
        """Should be able to set target attitude."""
        controller = AttitudeController(kp=0.1, kd=0.5)

        new_target = from_axis_angle(np.array([1.0, 0.0, 0.0]), 0.5)
        controller.set_target(new_target)

        assert np.allclose(controller.get_target(), new_target)
