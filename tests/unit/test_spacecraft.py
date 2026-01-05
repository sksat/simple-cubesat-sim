"""Unit tests for 6U CubeSat spacecraft model.

TDD: Write tests first, then implement.

The spacecraft model integrates:
- Attitude state (quaternion, angular velocity)
- Actuators (MTQ, RW)
- Inertia tensor
- Dynamics propagation
"""

import numpy as np
import pytest

from backend.simulation.spacecraft import Spacecraft


class TestSpacecraftInitialization:
    """Tests for spacecraft initialization."""

    def test_default_initialization(self):
        """Spacecraft should initialize with default parameters."""
        sc = Spacecraft()

        # Default attitude: identity quaternion
        np.testing.assert_array_almost_equal(
            sc.quaternion, [0.0, 0.0, 0.0, 1.0]
        )

        # Default angular velocity: zero
        np.testing.assert_array_almost_equal(
            sc.angular_velocity, [0.0, 0.0, 0.0]
        )

    def test_custom_initialization(self):
        """Spacecraft should accept custom initial conditions."""
        q0 = np.array([0.0, 0.0, np.sin(0.1), np.cos(0.1)])
        omega0 = np.array([0.01, 0.02, 0.03])

        sc = Spacecraft(quaternion=q0, angular_velocity=omega0)

        np.testing.assert_array_almost_equal(sc.quaternion, q0)
        np.testing.assert_array_almost_equal(sc.angular_velocity, omega0)

    def test_inertia_tensor_default(self):
        """Default inertia should be 6U CubeSat typical values."""
        sc = Spacecraft()

        # 6U CubeSat typical inertia
        expected = np.diag([0.05, 0.05, 0.02])
        np.testing.assert_array_almost_equal(sc.inertia, expected)

    def test_custom_inertia(self):
        """Spacecraft should accept custom inertia tensor."""
        custom_inertia = np.diag([0.1, 0.08, 0.03])
        sc = Spacecraft(inertia=custom_inertia)

        np.testing.assert_array_almost_equal(sc.inertia, custom_inertia)


class TestSpacecraftActuators:
    """Tests for actuator integration."""

    def test_has_reaction_wheels(self):
        """Spacecraft should have reaction wheel assembly."""
        sc = Spacecraft()

        assert sc.reaction_wheel is not None
        assert hasattr(sc.reaction_wheel, "command_torque")
        assert hasattr(sc.reaction_wheel, "get_momentum")

    def test_has_magnetorquers(self):
        """Spacecraft should have magnetorquer assembly."""
        sc = Spacecraft()

        assert sc.magnetorquer is not None
        assert hasattr(sc.magnetorquer, "command")
        assert hasattr(sc.magnetorquer, "compute_torque")

    def test_rw_initial_state(self):
        """Reaction wheels should start at rest."""
        sc = Spacecraft()

        speed = sc.reaction_wheel.get_speed()
        np.testing.assert_array_almost_equal(speed, [0.0, 0.0, 0.0])

    def test_mtq_initial_state(self):
        """Magnetorquers should start with zero dipole."""
        sc = Spacecraft()

        dipole = sc.magnetorquer.get_dipole()
        np.testing.assert_array_almost_equal(dipole, [0.0, 0.0, 0.0])


class TestSpacecraftDynamics:
    """Tests for attitude dynamics propagation."""

    def test_step_with_zero_torque(self):
        """With zero torque and zero omega, state should not change."""
        sc = Spacecraft()

        q_before = sc.quaternion.copy()
        omega_before = sc.angular_velocity.copy()

        sc.step(dt=0.1)

        np.testing.assert_array_almost_equal(sc.quaternion, q_before)
        np.testing.assert_array_almost_equal(sc.angular_velocity, omega_before)

    def test_step_with_initial_rotation(self):
        """With initial angular velocity, attitude should change."""
        sc = Spacecraft(angular_velocity=np.array([0.0, 0.0, 0.1]))

        q_before = sc.quaternion.copy()

        sc.step(dt=1.0)

        # Quaternion should have changed
        assert not np.allclose(sc.quaternion, q_before)

    def test_rw_torque_affects_attitude(self):
        """Commanding RW torque should change spacecraft angular velocity.

        Use POINTING mode with target = current to allow RW to spin up
        while maintaining attitude. Then check momentum transfer.
        """
        sc = Spacecraft()

        # Set target to current attitude, then manually override RW
        # Actually, we'll use direct actuator access with step that
        # doesn't run control by using a helper method.

        # Better approach: command torque inside loop before control runs
        # We'll manually update RW and dynamics without control loop
        dt = 0.01
        for _ in range(100):
            # Command before step
            sc.reaction_wheel.command_torque(np.array([0.0, 0.0, 0.0005]))
            sc.reaction_wheel.update(dt)

            # Get torque on spacecraft
            torque = sc.reaction_wheel.get_torque_on_spacecraft()

            # Update angular velocity (simplified, no gyroscopic terms)
            omega_dot = sc.inertia_inv @ torque
            sc.angular_velocity = sc.angular_velocity + omega_dot * dt

        # Angular velocity should have changed (opposite to wheel)
        assert np.linalg.norm(sc.angular_velocity) > 0
        assert sc.angular_velocity[2] < 0  # Opposite to positive wheel torque

    def test_angular_momentum_conservation_isolated(self):
        """Total angular momentum should be conserved (no external torque).

        Use POINTING mode which uses only RW (internal torque).
        """
        from backend.dynamics.quaternion import from_axis_angle

        sc = Spacecraft(angular_velocity=np.array([0.0, 0.0, 0.1]))

        # Set target attitude different from current to generate RW torque
        target = from_axis_angle(np.array([0.0, 0.0, 1.0]), 0.5)
        sc.set_target_attitude(target)
        sc.set_control_mode("POINTING")

        # Initial total angular momentum
        L_initial = sc.get_total_angular_momentum()

        # Run for several steps
        for _ in range(200):
            sc.step(dt=0.01)

        # Final total angular momentum
        L_final = sc.get_total_angular_momentum()

        # Should be conserved (only internal RW torque, no MTQ)
        np.testing.assert_array_almost_equal(L_initial, L_final, decimal=5)

    def test_mtq_torque_affects_angular_momentum(self):
        """MTQ torque (external) should change total angular momentum.

        Manually apply MTQ torque to verify external torque changes momentum.
        """
        sc = Spacecraft()

        L_initial = sc.get_total_angular_momentum()

        # Magnetic field
        b_field = np.array([30e-6, 20e-6, 10e-6])
        dipole = np.array([0.1, 0.1, 0.0])

        # Manually apply MTQ torque (bypass control loop)
        dt = 0.01
        for _ in range(100):
            # Command MTQ
            sc.magnetorquer.command(dipole)

            # Calculate torque
            torque_mtq = sc.magnetorquer.compute_torque(b_field)

            # Update angular velocity
            omega_dot = sc.inertia_inv @ torque_mtq
            sc.angular_velocity = sc.angular_velocity + omega_dot * dt

        L_final = sc.get_total_angular_momentum()

        # Angular momentum should have changed (external torque)
        assert not np.allclose(L_initial, L_final)


class TestSpacecraftState:
    """Tests for state access and management."""

    def test_get_state(self):
        """Should return complete state dictionary."""
        sc = Spacecraft()

        state = sc.get_state()

        assert "quaternion" in state
        assert "angular_velocity" in state
        assert "reaction_wheel" in state
        assert "magnetorquer" in state

    def test_reset(self):
        """Reset should restore initial state."""
        q0 = np.array([0.0, 0.0, 0.0, 1.0])
        omega0 = np.array([0.0, 0.0, 0.0])

        sc = Spacecraft(quaternion=q0, angular_velocity=omega0)

        # Modify state
        sc.reaction_wheel.command_torque(np.array([0.001, 0.0, 0.0]))
        for _ in range(100):
            sc.step(dt=0.01)

        # Reset
        sc.reset()

        np.testing.assert_array_almost_equal(sc.quaternion, q0)
        np.testing.assert_array_almost_equal(sc.angular_velocity, omega0)

    def test_quaternion_stays_normalized(self):
        """Quaternion should remain normalized after steps."""
        sc = Spacecraft(angular_velocity=np.array([0.1, 0.05, -0.08]))

        for _ in range(1000):
            sc.step(dt=0.01)

        norm = np.linalg.norm(sc.quaternion)
        assert np.isclose(norm, 1.0, atol=1e-6)


class TestSpacecraftControlModes:
    """Tests for control mode integration."""

    def test_detumbling_mode(self):
        """Detumbling mode should reduce angular velocity.

        Uses inertial magnetic field so that B-dot is properly computed
        as the spacecraft rotates (body-frame field changes).
        """
        sc = Spacecraft(angular_velocity=np.array([0.1, 0.05, -0.08]))

        initial_rate = np.linalg.norm(sc.angular_velocity)

        # Enable detumbling mode
        sc.set_control_mode("DETUMBLING")

        # Simulate with inertial magnetic field (body field changes as we rotate)
        b_field_inertial = np.array([30e-6, 20e-6, 10e-6])
        for _ in range(3000):  # 5 minutes at 10 Hz
            sc.step(dt=0.1, magnetic_field_inertial=b_field_inertial)

        final_rate = np.linalg.norm(sc.angular_velocity)

        # Should have reduced
        assert final_rate < initial_rate

    def test_pointing_mode(self):
        """Pointing mode should converge to target attitude."""
        from backend.dynamics.quaternion import from_axis_angle

        sc = Spacecraft()

        # Set target attitude (10 deg rotation around Z)
        target = from_axis_angle(np.array([0.0, 0.0, 1.0]), np.radians(10))
        sc.set_target_attitude(target)

        # Enable pointing mode
        sc.set_control_mode("POINTING")

        # Initial error
        initial_error = sc.get_attitude_error()

        # Simulate
        for _ in range(6000):  # 60 seconds at 100 Hz
            sc.step(dt=0.01)

        final_error = sc.get_attitude_error()

        # Error should have reduced
        assert final_error < initial_error * 0.5

    def test_idle_mode(self):
        """Idle mode should not command actuators."""
        sc = Spacecraft(angular_velocity=np.array([0.01, 0.0, 0.0]))

        sc.set_control_mode("IDLE")

        # Step
        sc.step(dt=0.1, magnetic_field=np.array([30e-6, 20e-6, 10e-6]))

        # MTQ should be zero
        np.testing.assert_array_almost_equal(
            sc.magnetorquer.get_dipole(), [0.0, 0.0, 0.0]
        )

        # RW should have zero commanded torque
        np.testing.assert_array_almost_equal(
            sc.reaction_wheel.get_commanded_torque(), [0.0, 0.0, 0.0]
        )
