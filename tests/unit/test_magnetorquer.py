"""Unit tests for magnetorquer model.

TDD: Write tests first, then implement.

Magnetorquer generates torque via interaction with Earth's magnetic field:
    T = m × B
where:
    T: torque (Nm)
    m: dipole moment (Am^2)
    B: magnetic field (T)
"""

import numpy as np
import pytest

from backend.actuators.magnetorquer import Magnetorquer


class TestMagnetorquerBasic:
    """Basic functionality tests for magnetorquer."""

    def test_zero_command_produces_zero_dipole(self):
        """Zero command should produce zero dipole moment."""
        mtq = Magnetorquer(max_dipole=0.2)
        mtq.command(np.array([0.0, 0.0, 0.0]))
        np.testing.assert_array_almost_equal(mtq.get_dipole(), [0.0, 0.0, 0.0])

    def test_command_sets_dipole(self):
        """Command should set the dipole moment."""
        mtq = Magnetorquer(max_dipole=0.2)
        cmd = np.array([0.1, -0.05, 0.08])
        mtq.command(cmd)
        np.testing.assert_array_almost_equal(mtq.get_dipole(), cmd)

    def test_default_state_is_zero(self):
        """Initial state should be zero dipole."""
        mtq = Magnetorquer(max_dipole=0.2)
        np.testing.assert_array_almost_equal(mtq.get_dipole(), [0.0, 0.0, 0.0])


class TestMagnetorquerSaturation:
    """Tests for saturation limits."""

    def test_positive_saturation(self):
        """Command exceeding max should be saturated."""
        mtq = Magnetorquer(max_dipole=0.2)
        mtq.command(np.array([0.5, 0.0, 0.0]))
        assert mtq.get_dipole()[0] == 0.2

    def test_negative_saturation(self):
        """Negative command exceeding max should be saturated."""
        mtq = Magnetorquer(max_dipole=0.2)
        mtq.command(np.array([-0.5, 0.0, 0.0]))
        assert mtq.get_dipole()[0] == -0.2

    def test_per_axis_saturation(self):
        """Each axis should be saturated independently."""
        mtq = Magnetorquer(max_dipole=0.2)
        mtq.command(np.array([0.5, -0.5, 0.1]))
        dipole = mtq.get_dipole()
        assert dipole[0] == 0.2
        assert dipole[1] == -0.2
        assert np.isclose(dipole[2], 0.1)


class TestMagnetorquerTorque:
    """Tests for torque computation."""

    def test_torque_cross_product(self):
        """Torque should be T = m × B."""
        mtq = Magnetorquer(max_dipole=0.2)
        mtq.command(np.array([0.1, 0.0, 0.0]))  # Dipole along X
        b_field = np.array([0.0, 30e-6, 0.0])  # B along Y

        torque = mtq.compute_torque(b_field)

        # m × B = X × Y = Z
        expected = np.array([0.0, 0.0, 0.1 * 30e-6])
        np.testing.assert_array_almost_equal(torque, expected)

    def test_zero_torque_when_parallel(self):
        """Torque is zero when dipole and B-field are parallel."""
        mtq = Magnetorquer(max_dipole=0.2)
        mtq.command(np.array([0.1, 0.0, 0.0]))
        b_field = np.array([30e-6, 0.0, 0.0])  # Parallel to dipole

        torque = mtq.compute_torque(b_field)

        np.testing.assert_array_almost_equal(torque, [0.0, 0.0, 0.0])

    def test_torque_magnitude(self):
        """Torque magnitude should be |T| = |m| * |B| * sin(theta)."""
        mtq = Magnetorquer(max_dipole=0.2)
        mtq.command(np.array([0.1, 0.0, 0.0]))
        b_field = np.array([0.0, 30e-6, 0.0])  # Perpendicular

        torque = mtq.compute_torque(b_field)

        expected_mag = 0.1 * 30e-6  # |m| * |B| * sin(90°)
        assert np.isclose(np.linalg.norm(torque), expected_mag)


class TestMagnetorquerPower:
    """Tests for power consumption model."""

    def test_zero_dipole_zero_power(self):
        """Zero dipole should consume zero power."""
        mtq = Magnetorquer(max_dipole=0.2, power_per_dipole=1.0)
        mtq.command(np.array([0.0, 0.0, 0.0]))
        assert mtq.get_power() == 0.0

    def test_power_proportional_to_dipole_squared(self):
        """Power should scale with dipole magnitude squared (P = k * m^2)."""
        mtq = Magnetorquer(max_dipole=0.2, power_per_dipole=10.0)

        mtq.command(np.array([0.1, 0.0, 0.0]))
        power1 = mtq.get_power()

        mtq.command(np.array([0.2, 0.0, 0.0]))
        power2 = mtq.get_power()

        # Power ratio should be 4 (0.2^2 / 0.1^2)
        assert np.isclose(power2 / power1, 4.0)


class TestMagnetorquer3Axis:
    """Tests for 3-axis magnetorquer system."""

    def test_independent_axis_control(self):
        """Each axis should be controllable independently."""
        mtq = Magnetorquer(max_dipole=0.2)

        # Command only X axis
        mtq.command(np.array([0.1, 0.0, 0.0]))
        dipole = mtq.get_dipole()
        assert dipole[0] != 0
        assert dipole[1] == 0
        assert dipole[2] == 0

        # Command only Y axis
        mtq.command(np.array([0.0, 0.15, 0.0]))
        dipole = mtq.get_dipole()
        assert dipole[0] == 0
        assert dipole[1] != 0
        assert dipole[2] == 0

    def test_combined_axis_torque(self):
        """Combined axis dipole should produce correct torque."""
        mtq = Magnetorquer(max_dipole=0.2)
        mtq.command(np.array([0.1, 0.1, 0.0]))
        b_field = np.array([0.0, 0.0, 30e-6])

        torque = mtq.compute_torque(b_field)

        # m × B with m in XY plane and B along Z
        expected = np.cross([0.1, 0.1, 0.0], [0.0, 0.0, 30e-6])
        np.testing.assert_array_almost_equal(torque, expected)


class TestMagnetorquerState:
    """Tests for state management."""

    def test_get_state_returns_dict(self):
        """get_state should return a dictionary with all state info."""
        mtq = Magnetorquer(max_dipole=0.2)
        mtq.command(np.array([0.1, 0.05, -0.08]))

        state = mtq.get_state()

        assert "dipole" in state
        assert "power" in state
        assert len(state["dipole"]) == 3

    def test_reset_clears_state(self):
        """reset should clear the dipole command."""
        mtq = Magnetorquer(max_dipole=0.2)
        mtq.command(np.array([0.1, 0.1, 0.1]))
        mtq.reset()

        np.testing.assert_array_almost_equal(mtq.get_dipole(), [0.0, 0.0, 0.0])
