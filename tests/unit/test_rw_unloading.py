"""Unit tests for reaction wheel momentum unloading controller.

TDD: Write tests first, then implement.

RW unloading uses magnetorquers to dump accumulated wheel momentum.
Control law:
    m = k * (B × H_rw) / |B|^2

where:
    m: MTQ dipole moment command (Am^2)
    k: unloading gain
    B: magnetic field in body frame (T)
    H_rw: total RW momentum vector (Nms)

The MTQ torque T_mtq = m × B absorbs RW momentum while minimizing
attitude disturbance.
"""

import numpy as np
import pytest

from backend.control.rw_unloading import RWUnloadingController


class TestRWUnloadingBasic:
    """Basic functionality tests for RW unloading controller."""

    def test_zero_momentum_produces_zero_dipole(self):
        """No RW momentum should produce zero MTQ command."""
        controller = RWUnloadingController(gain=1e4)

        h_rw = np.array([0.0, 0.0, 0.0])
        b_field = np.array([30e-6, 20e-6, 10e-6])

        dipole = controller.compute(h_rw, b_field)

        np.testing.assert_array_almost_equal(dipole, [0.0, 0.0, 0.0])

    def test_nonzero_momentum_produces_dipole(self):
        """Non-zero RW momentum should produce MTQ command."""
        controller = RWUnloadingController(gain=1e4)

        h_rw = np.array([0.001, 0.0, 0.0])  # 1 mNms
        b_field = np.array([30e-6, 20e-6, 10e-6])

        dipole = controller.compute(h_rw, b_field)

        assert np.linalg.norm(dipole) > 0

    def test_dipole_perpendicular_to_bfield(self):
        """Optimal dipole is perpendicular to B-field component."""
        controller = RWUnloadingController(gain=1e4, max_dipole=10.0)

        h_rw = np.array([0.01, 0.0, 0.0])
        b_field = np.array([0.0, 30e-6, 0.0])  # B along Y

        dipole = controller.compute(h_rw, b_field)

        # Dipole should be in XZ plane (perpendicular to B in Y)
        # For m = k * (B × H) / |B|^2, with B in Y and H in X:
        # B × H = Y × X = -Z, so dipole should be in -Z direction
        assert np.abs(dipole[1]) < np.abs(dipole[2]) + np.abs(dipole[0])


class TestRWUnloadingPhysics:
    """Tests for physical correctness of unloading."""

    def test_mtq_torque_acts_on_unloadable_component(self):
        """MTQ torque should act on the unloadable component of H_rw.

        The control law m = k * (B × H) / |B|² produces torque:
            T = m × B = k * (B × H) × B / |B|²

        Using vector triple product: (a×b)×c = b(a·c) - a(b·c)
            T = k * [H - (H·B̂)B̂]  (component of H perpendicular to B)

        This torque is in the direction of the unloadable momentum component,
        which the attitude controller then counteracts using RW.
        """
        controller = RWUnloadingController(gain=1e4, max_dipole=10.0)

        h_rw = np.array([0.01, 0.005, -0.003])
        b_field = np.array([30e-6, 20e-6, 10e-6])

        dipole = controller.compute(h_rw, b_field)
        torque_mtq = np.cross(dipole, b_field)

        # Get unloadable component (perpendicular to B)
        h_unloadable = controller.get_unloadable_momentum(h_rw, b_field)

        # Torque should be aligned with unloadable momentum direction
        if np.linalg.norm(h_unloadable) > 1e-10 and np.linalg.norm(torque_mtq) > 1e-15:
            cos_angle = np.dot(torque_mtq, h_unloadable) / (
                np.linalg.norm(torque_mtq) * np.linalg.norm(h_unloadable)
            )
            assert cos_angle > 0.9, f"Torque should align with unloadable H, cos={cos_angle}"

    def test_unloading_reduces_momentum_over_time(self):
        """Simulation should show RW momentum decreasing."""
        from backend.actuators.magnetorquer import Magnetorquer
        from backend.actuators.reaction_wheel import ReactionWheel

        controller = RWUnloadingController(gain=5e4, max_dipole=0.2)
        mtq = Magnetorquer(max_dipole=0.2)
        rw = ReactionWheel(inertia=1e-4, max_speed=628.3, max_torque=0.001)

        # Spacecraft inertia
        I_sc = np.diag([0.05, 0.05, 0.02])

        # Initial: RW has stored momentum
        # Spin up the wheel first
        for _ in range(100):
            rw.command_torque(np.array([0.0005, 0.0003, 0.0004]))
            rw.update(0.1)

        initial_momentum = np.linalg.norm(rw.get_momentum())
        assert initial_momentum > 0, "Should have initial momentum"

        # Now unload using MTQ
        omega_sc = np.array([0.0, 0.0, 0.0])
        b_field = np.array([30e-6, 20e-6, 10e-6])

        dt = 0.1
        duration = 60.0  # 1 minute
        num_steps = int(duration / dt)

        for _ in range(num_steps):
            h_rw = rw.get_momentum()

            # Unloading control
            dipole_cmd = controller.compute(h_rw, b_field)
            mtq.command(dipole_cmd)

            # MTQ torque on spacecraft
            torque_mtq = mtq.compute_torque(b_field)

            # The MTQ torque affects both spacecraft and RW momentum balance
            # For unloading: RW absorbs some torque to maintain attitude
            # Simplified: just apply small opposing torque to RW
            # In reality, attitude controller would coordinate this

            # Update spacecraft
            omega_dot = np.linalg.solve(I_sc, torque_mtq)
            omega_sc = omega_sc + omega_dot * dt

            # RW absorbs momentum to counter spacecraft rotation
            # This is simplified - in real system would use attitude control
            rw.command_torque(-torque_mtq * 0.1)  # Partial absorption
            rw.update(dt)

        final_momentum = np.linalg.norm(rw.get_momentum())

        # Momentum should have decreased (at least somewhat)
        assert final_momentum < initial_momentum, (
            f"Momentum should decrease: {initial_momentum:.6f} -> {final_momentum:.6f}"
        )


class TestRWUnloadingSaturation:
    """Tests for saturation limits."""

    def test_dipole_respects_max_limit(self):
        """Output dipole should not exceed max_dipole."""
        max_dipole = 0.2
        controller = RWUnloadingController(gain=1e8, max_dipole=max_dipole)

        # Large momentum to potentially saturate
        h_rw = np.array([1.0, 0.5, 0.3])
        b_field = np.array([30e-6, 20e-6, 10e-6])

        dipole = controller.compute(h_rw, b_field)

        assert np.all(np.abs(dipole) <= max_dipole + 1e-10)

    def test_small_bfield_handled_safely(self):
        """Small B-field should not cause numerical issues."""
        controller = RWUnloadingController(gain=1e4)

        h_rw = np.array([0.01, 0.0, 0.0])
        b_field = np.array([1e-9, 1e-9, 1e-9])  # Very small B-field

        dipole = controller.compute(h_rw, b_field)

        # Should not produce NaN or Inf
        assert np.all(np.isfinite(dipole))

    def test_zero_bfield_returns_zero_dipole(self):
        """Zero B-field should return zero dipole (can't unload)."""
        controller = RWUnloadingController(gain=1e4)

        h_rw = np.array([0.01, 0.005, 0.003])
        b_field = np.array([0.0, 0.0, 0.0])

        dipole = controller.compute(h_rw, b_field)

        np.testing.assert_array_almost_equal(dipole, [0.0, 0.0, 0.0])


class TestRWUnloadingGains:
    """Tests for gain behavior."""

    def test_higher_gain_produces_larger_dipole(self):
        """Increasing gain should increase dipole (below saturation)."""
        # Use very small momentum and low gains to stay below saturation
        h_rw = np.array([1e-7, 0.0, 0.0])
        b_field = np.array([30e-6, 20e-6, 10e-6])

        controller_low = RWUnloadingController(gain=1e2, max_dipole=10.0)
        controller_high = RWUnloadingController(gain=1e3, max_dipole=10.0)

        dipole_low = controller_low.compute(h_rw, b_field)
        dipole_high = controller_high.compute(h_rw, b_field)

        assert np.linalg.norm(dipole_high) > np.linalg.norm(dipole_low)

    def test_negative_gain_rejected(self):
        """Should reject negative gain."""
        with pytest.raises(ValueError, match="gain"):
            RWUnloadingController(gain=-1.0)


class TestRWUnloadingCoordination:
    """Tests for coordination with attitude control."""

    def test_control_law_produces_correct_direction(self):
        """Verify the control law produces dipole in correct direction.

        m = k * (B × H) / |B|²

        For B along Z and H along X:
        B × H = [0,0,Z] × [X,0,0] = [0*0-Z*0, Z*X-0*0, 0*0-0*X] = [0, ZX, 0]
        So dipole should be in +Y direction for positive Z and X.
        """
        controller = RWUnloadingController(gain=1e4, max_dipole=100.0)

        h_rw = np.array([0.01, 0.0, 0.0])  # H along X
        b_field = np.array([0.0, 0.0, 30e-6])  # B along Z

        dipole = controller.compute(h_rw, b_field)

        # B × H = [0,0,Z] × [X,0,0] = [0, Z*X, 0] = +Y
        # So dipole should be positive Y
        assert dipole[1] > 0, f"Dipole Y should be positive, got {dipole[1]}"
        assert np.abs(dipole[0]) < np.abs(dipole[1]), "Dipole should be primarily in Y"
        assert np.abs(dipole[2]) < np.abs(dipole[1]), "Dipole should be primarily in Y"
