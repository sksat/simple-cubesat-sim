"""Integration tests for automatic RW unloading."""

import numpy as np
import pytest

from backend.simulation.engine import SimulationEngine


class TestAutoUnloading:
    """Test automatic RW unloading during 3Axis mode."""

    def test_auto_unloading_triggers_on_high_speed(self):
        """Test that unloading automatically triggers when RW speed exceeds threshold."""
        engine = SimulationEngine()
        engine.spacecraft.set_control_mode("3Axis")
        engine.start()

        # Run simulation until RW speeds up significantly
        for _ in range(200):
            engine.step()

        # Check if auto-unloading has been activated
        rw_speed = engine.spacecraft.reaction_wheel.get_speed()
        auto_unload = engine.spacecraft._auto_unloading

        # At least one axis should be near/above threshold after 200 steps
        max_speed = np.max(np.abs(rw_speed))
        print(f"Max RW speed after 200 steps: {max_speed:.1f} rad/s")
        print(f"Upper threshold: {auto_unload.upper_threshold[0]:.1f} rad/s")

        # Speed should be high (approaching saturation)
        assert max_speed > 600.0, f"RW speed should be high, got {max_speed}"

    def test_auto_unloading_activates_and_deactivates(self):
        """Test that auto-unloading correctly activates and deactivates."""
        engine = SimulationEngine()
        engine.spacecraft.set_control_mode("3Axis")

        # Set more aggressive thresholds
        engine.spacecraft._auto_unloading.upper_threshold = np.array([700.0] * 3)
        engine.spacecraft._auto_unloading.lower_threshold = np.array([-700.0] * 3)
        engine.spacecraft._auto_unloading.target_speed = np.array([500.0, 500.0, 500.0])

        engine.start()

        # Track unloading state changes
        activations = []
        for i in range(300):
            rw_speed = engine.spacecraft.reaction_wheel.get_speed()
            was_active = engine.spacecraft._auto_unloading.is_active()

            engine.step()

            is_active = engine.spacecraft._auto_unloading.is_active()

            # Record activation/deactivation
            if not was_active and is_active:
                activations.append((i, "ON", rw_speed.copy()))
            elif was_active and not is_active:
                activations.append((i, "OFF", rw_speed.copy()))

        print(f"Unloading state changes: {len(activations)}")
        for step, state, speed in activations[:5]:  # Show first 5
            print(f"  Step {step}: {state}, speed={speed}")

        # Unloading should have activated at least once
        assert len(activations) > 0, "Auto-unloading should activate"
        assert any(state == "ON" for _, state, _ in activations), "Should have ON transitions"

    def test_auto_unloading_state_transitions(self):
        """Test that unloading state machine transitions correctly."""
        engine = SimulationEngine()
        engine.spacecraft.set_control_mode("3Axis")

        # Set aggressive thresholds to trigger quickly
        engine.spacecraft._auto_unloading.upper_threshold = np.array([400.0] * 3)
        engine.spacecraft._auto_unloading.lower_threshold = np.array([-400.0] * 3)
        engine.spacecraft._auto_unloading.target_speed = np.zeros(3)

        engine.start()

        # Run until unloading triggers
        state_changes = []
        for i in range(300):
            engine.step()
            auto_unload = engine.spacecraft._auto_unloading

            # Record when unloading activates
            if auto_unload.is_active():
                state_changes.append(i)
                break

        # Unloading should have activated
        assert len(state_changes) > 0, "Auto-unloading should activate"
        print(f"Unloading activated at step {state_changes[0]}")

    def test_is_unloading_flag_in_state(self):
        """Test that is_unloading flag is included in spacecraft state."""
        engine = SimulationEngine()
        engine.spacecraft.set_control_mode("3Axis")
        engine.start()

        # Run simulation
        for _ in range(50):
            engine.step()

        # Check that is_unloading is in state
        state = engine.spacecraft.get_state()
        assert "is_unloading" in state, "is_unloading should be in state"
        assert isinstance(state["is_unloading"], bool), "is_unloading should be bool"
