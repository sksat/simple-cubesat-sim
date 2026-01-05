"""Unit tests for B-dot detumbling controller.

TDD: Write tests first, then implement.

B-dot control law: m = -k * dB/dt
where:
    m: commanded dipole moment (Am^2)
    k: control gain
    dB/dt: time derivative of magnetic field in body frame (T/s)
"""

import numpy as np
import pytest

from backend.control.bdot import BdotController


class TestBdotControllerBasic:
    """Basic functionality tests for B-dot controller."""

    def test_zero_bdot_produces_zero_dipole(self):
        """When dB/dt = 0, commanded dipole moment should be zero."""
        controller = BdotController(gain=1e6)
        b_dot = np.array([0.0, 0.0, 0.0])
        dipole = controller.compute(b_dot)
        np.testing.assert_array_almost_equal(dipole, [0.0, 0.0, 0.0])

    def test_positive_bdot_produces_negative_dipole(self):
        """B-dot control law: m = -k * dB/dt."""
        # Use high max_dipole to avoid saturation in this test
        controller = BdotController(gain=1e6, max_dipole=10.0)
        b_dot = np.array([1e-6, 0.0, 0.0])  # 1 μT/s
        dipole = controller.compute(b_dot)
        assert dipole[0] < 0  # Should be negative
        assert np.isclose(dipole[0], -1.0)  # k * b_dot = 1e6 * 1e-6 = 1

    def test_negative_bdot_produces_positive_dipole(self):
        """Negative dB/dt should produce positive dipole."""
        controller = BdotController(gain=1e6)
        b_dot = np.array([-1e-6, 0.0, 0.0])
        dipole = controller.compute(b_dot)
        assert dipole[0] > 0

    def test_dipole_proportional_to_bdot_magnitude(self):
        """Dipole magnitude scales linearly with |dB/dt| (below saturation)."""
        # Use high max_dipole to avoid saturation
        controller = BdotController(gain=1e6, max_dipole=10.0)
        b_dot_1 = np.array([1e-6, 0.0, 0.0])
        b_dot_2 = np.array([2e-6, 0.0, 0.0])
        dipole_1 = controller.compute(b_dot_1)
        dipole_2 = controller.compute(b_dot_2)
        np.testing.assert_array_almost_equal(dipole_2, 2 * dipole_1)


class TestBdotControllerGain:
    """Tests for gain behavior."""

    def test_higher_gain_produces_larger_dipole(self):
        """Increasing k should increase |m| proportionally (below saturation)."""
        b_dot = np.array([1e-8, 1e-8, 0.0])  # Small b_dot to avoid saturation

        controller_low = BdotController(gain=1e5, max_dipole=10.0)
        controller_high = BdotController(gain=1e6, max_dipole=10.0)

        dipole_low = controller_low.compute(b_dot)
        dipole_high = controller_high.compute(b_dot)

        ratio = np.linalg.norm(dipole_high) / np.linalg.norm(dipole_low)
        assert np.isclose(ratio, 10.0)

    def test_negative_gain_rejected(self):
        """Controller should reject negative gain values."""
        with pytest.raises(ValueError, match="gain"):
            BdotController(gain=-1.0)

    def test_zero_gain_rejected(self):
        """Controller should reject zero gain."""
        with pytest.raises(ValueError, match="gain"):
            BdotController(gain=0.0)


class TestBdotControllerSaturation:
    """Tests for saturation limits."""

    def test_dipole_respects_saturation_limits(self):
        """Output dipole should not exceed magnetorquer limits."""
        max_dipole = 0.2  # Am^2 (typical for CubeSat)
        controller = BdotController(gain=1e8, max_dipole=max_dipole)

        # Large b_dot that would exceed limits without saturation
        b_dot = np.array([1e-4, 1e-4, 1e-4])
        dipole = controller.compute(b_dot)

        # Check each component is within limits
        assert np.all(np.abs(dipole) <= max_dipole + 1e-10)

    def test_large_bdot_saturates_correctly(self):
        """Verify saturation behavior for large rate inputs."""
        max_dipole = 0.2
        controller = BdotController(gain=1e8, max_dipole=max_dipole)

        # Very large b_dot
        b_dot = np.array([1e-3, 0.0, 0.0])
        dipole = controller.compute(b_dot)

        # Should be saturated at max
        assert np.isclose(np.abs(dipole[0]), max_dipole)

    def test_no_saturation_when_below_limit(self):
        """Below saturation limit, output should follow control law exactly."""
        max_dipole = 0.2
        controller = BdotController(gain=1e5, max_dipole=max_dipole)

        # Small b_dot that won't saturate
        b_dot = np.array([1e-7, 0.0, 0.0])
        dipole = controller.compute(b_dot)

        # Should equal -k * b_dot exactly
        expected = -1e5 * b_dot
        np.testing.assert_array_almost_equal(dipole, expected)


class TestBdotControllerEdgeCases:
    """Tests for edge cases and numerical stability."""

    def test_nan_input_returns_zero(self):
        """NaN inputs should return zero dipole for safety."""
        controller = BdotController(gain=1e6)
        b_dot = np.array([np.nan, 0.0, 0.0])
        dipole = controller.compute(b_dot)
        np.testing.assert_array_almost_equal(dipole, [0.0, 0.0, 0.0])

    def test_inf_input_returns_zero(self):
        """Infinite inputs should return zero dipole for safety."""
        controller = BdotController(gain=1e6)
        b_dot = np.array([np.inf, 0.0, 0.0])
        dipole = controller.compute(b_dot)
        np.testing.assert_array_almost_equal(dipole, [0.0, 0.0, 0.0])

    def test_very_small_bdot_numerical_stability(self):
        """Controller remains stable with near-zero inputs."""
        controller = BdotController(gain=1e6)
        b_dot = np.array([1e-15, 1e-15, 1e-15])
        dipole = controller.compute(b_dot)
        # Should not produce NaN or overflow
        assert np.all(np.isfinite(dipole))


class TestBdotControllerWithMeasurement:
    """Tests for B-dot calculation from magnetometer measurements."""

    def test_compute_bdot_from_measurements(self):
        """Compute dB/dt from two magnetometer readings."""
        controller = BdotController(gain=1e6)

        b_prev = np.array([30e-6, 0.0, 0.0])  # 30 μT
        b_curr = np.array([30.1e-6, 0.0, 0.0])  # Increased by 0.1 μT
        dt = 0.1  # 100 ms

        b_dot = controller.compute_bdot(b_prev, b_curr, dt)

        expected_bdot = (b_curr - b_prev) / dt  # 1e-6 T/s
        np.testing.assert_array_almost_equal(b_dot, expected_bdot)

    def test_compute_and_control(self):
        """Full pipeline: measure B, compute dB/dt, compute dipole."""
        controller = BdotController(gain=1e6)

        b_prev = np.array([30e-6, 20e-6, 10e-6])
        b_curr = np.array([30.1e-6, 20e-6, 10e-6])  # Only X changed
        dt = 0.1

        dipole = controller.update(b_prev, b_curr, dt)

        # dB/dt = [1e-6, 0, 0] T/s
        # m = -k * dB/dt = [-1, 0, 0] Am^2
        assert dipole[0] < 0
        assert np.isclose(dipole[1], 0.0)
        assert np.isclose(dipole[2], 0.0)


class TestBdotControllerTorque:
    """Tests for torque calculation from dipole and B-field."""

    def test_torque_perpendicular_to_bfield(self):
        """Generated torque T = m x B should be perpendicular to B."""
        controller = BdotController(gain=1e6)

        # Simple case: B along X, dipole along Y
        b_field = np.array([30e-6, 0.0, 0.0])
        dipole = np.array([0.0, 0.1, 0.0])

        torque = controller.compute_torque(dipole, b_field)

        # T should be along Z (m x B = Y x X = -Z)
        assert np.isclose(torque[0], 0.0, atol=1e-15)
        assert np.isclose(torque[1], 0.0, atol=1e-15)
        assert torque[2] != 0

    def test_torque_magnitude(self):
        """Torque magnitude should be |T| = |m| * |B| * sin(theta)."""
        controller = BdotController(gain=1e6)

        b_field = np.array([30e-6, 0.0, 0.0])  # 30 μT along X
        dipole = np.array([0.0, 0.1, 0.0])  # 0.1 Am^2 along Y

        torque = controller.compute_torque(dipole, b_field)

        # |T| = |m| * |B| = 0.1 * 30e-6 = 3e-6 Nm
        expected_magnitude = 0.1 * 30e-6
        assert np.isclose(np.linalg.norm(torque), expected_magnitude)

    def test_zero_torque_when_parallel(self):
        """Torque is zero when dipole and B-field are parallel."""
        controller = BdotController(gain=1e6)

        b_field = np.array([30e-6, 0.0, 0.0])
        dipole = np.array([0.1, 0.0, 0.0])  # Parallel to B

        torque = controller.compute_torque(dipole, b_field)

        np.testing.assert_array_almost_equal(torque, [0.0, 0.0, 0.0])


class TestBdotEnergyDissipation:
    """Tests for energy dissipation and angular velocity reduction."""

    def test_torque_opposes_angular_velocity(self):
        """B-dot torque should have a component opposing angular velocity.

        Physical principle:
        - In body frame, dB/dt ≈ -ω × B (for slowly varying B in inertial frame)
        - m = -k * dB/dt ≈ k * (ω × B)
        - T = m × B ≈ k * (ω × B) × B

        Using vector triple product: (a × b) × b = (a·b)b - (b·b)a
        So T ≈ k * [(ω·B)B - |B|²ω]

        The -|B|²ω term always opposes ω, causing deceleration.
        """
        controller = BdotController(gain=1e6, max_dipole=10.0)

        # Satellite spinning around Z-axis
        omega = np.array([0.0, 0.0, 0.1])  # 0.1 rad/s around Z

        # Magnetic field in body frame (assume mostly along X)
        b_field = np.array([30e-6, 10e-6, 5e-6])  # Typical LEO field

        # Compute dB/dt ≈ -ω × B (assuming B is constant in inertial frame)
        b_dot = -np.cross(omega, b_field)

        # Compute control dipole and torque
        dipole = controller.compute(b_dot)
        torque = controller.compute_torque(dipole, b_field)

        # Torque should have negative Z component (opposing omega_z)
        # Or more generally: T · ω < 0 (energy dissipation)
        power = np.dot(torque, omega)
        assert power < 0, f"Power should be negative (dissipating), got {power}"

    def test_energy_dissipation_various_orientations(self):
        """Energy dissipation works for various angular velocity orientations."""
        controller = BdotController(gain=1e6, max_dipole=10.0)
        b_field = np.array([30e-6, 10e-6, 5e-6])

        # Test various angular velocity directions
        omega_cases = [
            np.array([0.1, 0.0, 0.0]),
            np.array([0.0, 0.1, 0.0]),
            np.array([0.0, 0.0, 0.1]),
            np.array([0.05, 0.05, 0.05]),
            np.array([-0.1, 0.05, -0.03]),
        ]

        for omega in omega_cases:
            b_dot = -np.cross(omega, b_field)
            dipole = controller.compute(b_dot)
            torque = controller.compute_torque(dipole, b_field)
            power = np.dot(torque, omega)

            # Power should be negative (energy dissipation)
            assert power < 0, f"Failed for omega={omega}, power={power}"

    def test_angular_velocity_decreases_over_time(self):
        """Simulate one step and verify angular velocity magnitude decreases.

        Simple Euler integration: ω_new = ω + (T/I) * dt
        """
        controller = BdotController(gain=1e6, max_dipole=10.0)

        # 6U CubeSat inertia (simplified scalar for this test)
        inertia = 0.05  # kg*m^2 (typical for 6U)

        # Initial angular velocity
        omega = np.array([0.1, 0.05, 0.08])  # rad/s
        omega_initial_mag = np.linalg.norm(omega)

        # Magnetic field
        b_field = np.array([30e-6, 15e-6, 10e-6])

        # Simulate for a short duration
        dt = 0.1  # 100 ms step
        num_steps = 100

        for _ in range(num_steps):
            # B-dot in body frame (assuming B constant in inertial, which is
            # approximate but valid for short time scales)
            b_dot = -np.cross(omega, b_field)

            # Control
            dipole = controller.compute(b_dot)
            torque = controller.compute_torque(dipole, b_field)

            # Angular acceleration (T = I * alpha, so alpha = T / I)
            # Simplified: assuming scalar inertia for each axis
            alpha = torque / inertia

            # Euler integration
            omega = omega + alpha * dt

        omega_final_mag = np.linalg.norm(omega)

        # Angular velocity should have decreased
        assert omega_final_mag < omega_initial_mag, (
            f"Angular velocity should decrease: "
            f"{omega_initial_mag:.4f} -> {omega_final_mag:.4f}"
        )

    def test_detumbling_convergence(self):
        """Test that B-dot control converges to low angular velocity.

        This is a longer simulation to verify convergence behavior.
        Note: Real B-dot detumbling can take several orbits (~hours).
        For unit testing, we use higher gain and verify monotonic decrease.
        """
        controller = BdotController(gain=2e6, max_dipole=0.2)

        # 6U CubeSat inertia tensor (diagonal)
        inertia = np.diag([0.05, 0.05, 0.02])  # kg*m^2

        # Initial tumble rate
        omega = np.array([0.1, 0.15, -0.08])

        # Magnetic field (varies slightly to simulate orbit)
        b_field_base = np.array([30e-6, 20e-6, 10e-6])

        dt = 0.1  # 100 ms
        duration = 600.0  # 10 minutes
        num_steps = int(duration / dt)

        omega_history = [np.linalg.norm(omega)]

        for step in range(num_steps):
            # Add small variation to B-field to simulate orbital motion
            t = step * dt
            b_field = b_field_base * (1 + 0.1 * np.sin(2 * np.pi * t / 90))

            # B-dot in body frame
            b_dot = -np.cross(omega, b_field)

            # Control
            dipole = controller.compute(b_dot)
            torque = controller.compute_torque(dipole, b_field)

            # Angular acceleration: I * alpha = T, so alpha = I^-1 * T
            alpha = np.linalg.solve(inertia, torque)

            # Euler integration
            omega = omega + alpha * dt

            # Record history every 100 steps
            if step % 100 == 0:
                omega_history.append(np.linalg.norm(omega))

        # Final angular velocity should be significantly lower
        initial_rate = omega_history[0]
        final_rate = omega_history[-1]

        # Verify angular velocity decreased
        assert final_rate < initial_rate, (
            f"Angular velocity should decrease: {initial_rate:.4f} -> {final_rate:.4f} rad/s"
        )

        # Verify at least 15% reduction (MTQ torque is small, detumbling is slow)
        reduction_ratio = (initial_rate - final_rate) / initial_rate
        assert reduction_ratio > 0.15, (
            f"Failed to reduce sufficiently: {initial_rate:.4f} -> {final_rate:.4f} rad/s "
            f"(reduction: {reduction_ratio*100:.1f}%)"
        )

        # Verify monotonic decrease trend (averaged over windows)
        window_size = len(omega_history) // 4
        for i in range(3):
            start = i * window_size
            end = (i + 2) * window_size
            avg_early = np.mean(omega_history[start : start + window_size])
            avg_late = np.mean(omega_history[end - window_size : end])
            assert avg_late <= avg_early * 1.05, (  # Allow 5% margin for oscillations
                f"Not decreasing monotonically in window {i}"
            )
