"""Unit tests for reaction wheel model.

TDD: Write tests first, then implement.

Reaction wheel stores angular momentum and provides torque for attitude control.
Conservation of angular momentum: L_spacecraft + L_wheel = const
Torque from wheel: T = -dL_wheel/dt = -I_wheel * dω_wheel/dt
"""

import numpy as np
import pytest

from backend.actuators.reaction_wheel import ReactionWheel


class TestReactionWheelBasic:
    """Basic functionality tests for reaction wheel."""

    def test_initial_state_is_zero(self):
        """Initial wheel speed should be zero."""
        rw = ReactionWheel(
            inertia=1e-4,  # kg*m^2
            max_speed=6000 * 2 * np.pi / 60,  # 6000 RPM in rad/s
            max_torque=0.001,  # 1 mNm
        )
        np.testing.assert_array_almost_equal(rw.get_speed(), [0.0, 0.0, 0.0])

    def test_command_torque(self):
        """Command torque should affect wheel acceleration."""
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        # Command positive torque on X axis
        rw.command_torque(np.array([0.0005, 0.0, 0.0]))
        torque = rw.get_commanded_torque()
        assert torque[0] > 0

    def test_update_changes_speed(self):
        """Updating with torque command should change wheel speed."""
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        # Command torque and update
        rw.command_torque(np.array([0.0005, 0.0, 0.0]))
        initial_speed = rw.get_speed().copy()
        rw.update(dt=0.01)  # 10 ms
        final_speed = rw.get_speed()

        # Speed should have increased (positive torque -> positive acceleration)
        assert final_speed[0] > initial_speed[0]


class TestReactionWheelDynamics:
    """Tests for wheel dynamics."""

    def test_acceleration_from_torque(self):
        """Wheel acceleration should follow α = T / I."""
        inertia = 1e-4
        rw = ReactionWheel(
            inertia=inertia,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.01,
        )

        torque = 0.001  # 1 mNm
        rw.command_torque(np.array([torque, 0.0, 0.0]))
        rw.update(dt=1.0)  # 1 second

        # ω = α * t = (T/I) * t
        expected_speed = torque / inertia * 1.0
        assert np.isclose(rw.get_speed()[0], expected_speed, rtol=0.01)

    def test_momentum_storage(self):
        """Wheel should store angular momentum."""
        inertia = 1e-4
        rw = ReactionWheel(
            inertia=inertia,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.01,
        )

        # Spin up the wheel
        rw.command_torque(np.array([0.001, 0.0, 0.0]))
        for _ in range(100):
            rw.update(dt=0.1)

        momentum = rw.get_momentum()
        speed = rw.get_speed()

        # H = I * ω
        expected_momentum = inertia * speed
        np.testing.assert_array_almost_equal(momentum, expected_momentum)

    def test_reaction_torque_on_spacecraft(self):
        """Reaction torque on spacecraft is opposite to wheel torque."""
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        # Command torque on wheel
        wheel_torque = np.array([0.0005, 0.0, 0.0])
        rw.command_torque(wheel_torque)

        # Reaction on spacecraft should be opposite
        spacecraft_torque = rw.get_torque_on_spacecraft()
        np.testing.assert_array_almost_equal(spacecraft_torque, -wheel_torque)


class TestReactionWheelSaturation:
    """Tests for saturation limits."""

    def test_torque_saturation_positive(self):
        """Torque command exceeding max should be saturated."""
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        rw.command_torque(np.array([0.01, 0.0, 0.0]))  # 10x max
        torque = rw.get_commanded_torque()
        assert torque[0] == 0.001

    def test_torque_saturation_negative(self):
        """Negative torque exceeding max should be saturated."""
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        rw.command_torque(np.array([-0.01, 0.0, 0.0]))
        torque = rw.get_commanded_torque()
        assert torque[0] == -0.001

    def test_speed_saturation(self):
        """Wheel speed should not exceed max speed."""
        max_speed = 6000 * 2 * np.pi / 60  # ~628 rad/s
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=max_speed,
            max_torque=0.001,
        )

        # Command torque for a long time to reach saturation
        rw.command_torque(np.array([0.001, 0.0, 0.0]))
        for _ in range(10000):
            rw.update(dt=0.1)

        speed = rw.get_speed()
        assert np.abs(speed[0]) <= max_speed + 1e-10

    def test_momentum_limit(self):
        """Momentum should not exceed max (I * ω_max)."""
        inertia = 1e-4
        max_speed = 6000 * 2 * np.pi / 60
        max_momentum = inertia * max_speed

        rw = ReactionWheel(
            inertia=inertia,
            max_speed=max_speed,
            max_torque=0.001,
        )

        # Spin up to saturation
        rw.command_torque(np.array([0.001, 0.0, 0.0]))
        for _ in range(10000):
            rw.update(dt=0.1)

        momentum_mag = np.linalg.norm(rw.get_momentum())
        assert momentum_mag <= np.sqrt(3) * max_momentum + 1e-10


class TestReactionWheel3Axis:
    """Tests for 3-axis reaction wheel system."""

    def test_independent_axis_control(self):
        """Each axis should be controllable independently."""
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        # Command only X axis
        rw.command_torque(np.array([0.0005, 0.0, 0.0]))
        rw.update(dt=0.1)

        speed = rw.get_speed()
        assert speed[0] != 0
        assert speed[1] == 0
        assert speed[2] == 0

    def test_combined_axis_momentum(self):
        """Combined axis operation should work correctly."""
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        # Command all axes
        rw.command_torque(np.array([0.0005, 0.0003, -0.0004]))
        rw.update(dt=1.0)

        speed = rw.get_speed()
        assert speed[0] > 0
        assert speed[1] > 0
        assert speed[2] < 0


class TestReactionWheelState:
    """Tests for state management."""

    def test_get_state_returns_dict(self):
        """get_state should return a dictionary with all state info."""
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )
        rw.command_torque(np.array([0.0005, 0.0, 0.0]))
        rw.update(dt=0.1)

        state = rw.get_state()

        assert "speed" in state
        assert "momentum" in state
        assert "torque" in state
        assert len(state["speed"]) == 3

    def test_reset_clears_state(self):
        """reset should clear wheel speed."""
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        # Spin up
        rw.command_torque(np.array([0.0005, 0.0005, 0.0005]))
        for _ in range(100):
            rw.update(dt=0.1)

        # Reset
        rw.reset()

        np.testing.assert_array_almost_equal(rw.get_speed(), [0.0, 0.0, 0.0])
        np.testing.assert_array_almost_equal(rw.get_momentum(), [0.0, 0.0, 0.0])


class TestReactionWheelPower:
    """Tests for power consumption."""

    def test_zero_torque_base_power(self):
        """Zero torque command should consume only base power (if spinning)."""
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
            base_power=0.5,  # 0.5 W base power
        )

        rw.command_torque(np.array([0.0, 0.0, 0.0]))
        power = rw.get_power()

        # Should be base power or zero depending on implementation
        assert power >= 0

    def test_torque_increases_power(self):
        """Commanding torque should increase power consumption."""
        rw = ReactionWheel(
            inertia=1e-4,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
            base_power=0.5,
        )

        rw.command_torque(np.array([0.0, 0.0, 0.0]))
        power_idle = rw.get_power()

        rw.command_torque(np.array([0.001, 0.0, 0.0]))
        power_active = rw.get_power()

        assert power_active >= power_idle


class TestReactionWheelAttitudeChange:
    """Tests for spacecraft attitude change from RW actuation.

    These tests verify that conservation of angular momentum causes
    spacecraft rotation when wheel speed changes.

    Total angular momentum: L_total = I_sc * ω_sc + I_rw * ω_rw = const
    """

    def test_rw_torque_causes_spacecraft_rotation(self):
        """RW torque should cause opposite rotation of spacecraft.

        When wheel accelerates, spacecraft rotates in opposite direction.
        """
        rw = ReactionWheel(
            inertia=1e-4,  # Wheel inertia
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        # Spacecraft inertia (6U CubeSat)
        I_sc = np.diag([0.05, 0.05, 0.02])

        # Initial conditions: spacecraft at rest
        omega_sc = np.array([0.0, 0.0, 0.0])

        # Command torque on wheel (accelerate wheel around Z axis)
        rw.command_torque(np.array([0.0, 0.0, 0.0005]))

        # Simulate for some time
        dt = 0.01
        duration = 1.0
        num_steps = int(duration / dt)

        for _ in range(num_steps):
            rw.update(dt)

            # Get reaction torque on spacecraft
            torque_on_sc = rw.get_torque_on_spacecraft()

            # Update spacecraft angular velocity (ω_dot = I^-1 * T)
            omega_dot = np.linalg.solve(I_sc, torque_on_sc)
            omega_sc = omega_sc + omega_dot * dt

        # Spacecraft should be rotating in opposite direction to wheel
        wheel_speed = rw.get_speed()
        assert wheel_speed[2] > 0  # Wheel spinning positive Z
        assert omega_sc[2] < 0  # Spacecraft rotating negative Z

    def test_angular_momentum_conservation(self):
        """Total angular momentum should be conserved.

        L_total = I_sc * ω_sc + I_rw * ω_rw = const
        """
        I_rw = 1e-4
        rw = ReactionWheel(
            inertia=I_rw,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        # Spacecraft inertia
        I_sc = np.diag([0.05, 0.05, 0.02])

        # Initial: spacecraft rotating, wheel at rest
        omega_sc = np.array([0.0, 0.0, 0.1])  # 0.1 rad/s around Z
        omega_rw_initial = rw.get_speed()

        # Initial total angular momentum
        L_initial = I_sc @ omega_sc + I_rw * omega_rw_initial

        # Apply wheel torque
        rw.command_torque(np.array([0.0, 0.0, 0.0008]))

        dt = 0.01
        duration = 2.0
        num_steps = int(duration / dt)

        for _ in range(num_steps):
            rw.update(dt)
            torque_on_sc = rw.get_torque_on_spacecraft()
            omega_dot = np.linalg.solve(I_sc, torque_on_sc)
            omega_sc = omega_sc + omega_dot * dt

        # Final total angular momentum
        omega_rw_final = rw.get_speed()
        L_final = I_sc @ omega_sc + I_rw * omega_rw_final

        # Angular momentum should be conserved
        np.testing.assert_array_almost_equal(L_initial, L_final, decimal=6)

    def test_rw_can_stop_spacecraft_rotation(self):
        """RW can absorb spacecraft angular momentum to stop rotation."""
        I_rw = 1e-4
        rw = ReactionWheel(
            inertia=I_rw,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        I_sc = np.diag([0.05, 0.05, 0.02])

        # Spacecraft initially rotating around X
        omega_sc = np.array([0.05, 0.0, 0.0])  # 0.05 rad/s
        initial_rate = np.linalg.norm(omega_sc)

        # Control loop: simple proportional control to stop rotation
        dt = 0.01
        duration = 5.0  # 5 seconds
        num_steps = int(duration / dt)

        Kp = 0.02  # Proportional gain

        for _ in range(num_steps):
            # Simple control: torque proportional to angular velocity
            torque_cmd = Kp * omega_sc
            # Clamp to max torque
            torque_cmd = np.clip(torque_cmd, -0.001, 0.001)

            rw.command_torque(torque_cmd)
            rw.update(dt)

            torque_on_sc = rw.get_torque_on_spacecraft()
            omega_dot = np.linalg.solve(I_sc, torque_on_sc)
            omega_sc = omega_sc + omega_dot * dt

        final_rate = np.linalg.norm(omega_sc)

        # Spacecraft should have slowed down significantly
        assert final_rate < initial_rate * 0.5, (
            f"Failed to slow down: {initial_rate:.4f} -> {final_rate:.4f} rad/s"
        )

    def test_attitude_change_from_rw(self):
        """Verify actual attitude (quaternion) changes from RW actuation."""
        from backend.dynamics.quaternion import multiply, normalize

        I_rw = 1e-4
        rw = ReactionWheel(
            inertia=I_rw,
            max_speed=6000 * 2 * np.pi / 60,
            max_torque=0.001,
        )

        I_sc = np.diag([0.05, 0.05, 0.02])

        # Initial attitude: identity quaternion
        q = np.array([0.0, 0.0, 0.0, 1.0])
        omega_sc = np.array([0.0, 0.0, 0.0])

        # Command torque to rotate around Z
        rw.command_torque(np.array([0.0, 0.0, 0.0005]))

        dt = 0.01
        duration = 2.0
        num_steps = int(duration / dt)

        for _ in range(num_steps):
            rw.update(dt)
            torque_on_sc = rw.get_torque_on_spacecraft()
            omega_dot = np.linalg.solve(I_sc, torque_on_sc)
            omega_sc = omega_sc + omega_dot * dt

            # Update quaternion: q_dot = 0.5 * q * [ω, 0]
            omega_quat = np.array([omega_sc[0], omega_sc[1], omega_sc[2], 0.0])
            q_dot = 0.5 * multiply(q, omega_quat)
            q = normalize(q + q_dot * dt)

        # Quaternion should have changed from identity
        # Check that we've rotated around Z (q[2] should be non-zero)
        assert not np.allclose(q, [0.0, 0.0, 0.0, 1.0]), "Attitude should have changed"

        # The rotation should be primarily around Z axis
        # For small rotations: q ≈ [0, 0, sin(θ/2), cos(θ/2)]
        assert np.abs(q[2]) > 0.01, "Should have rotated around Z axis"
