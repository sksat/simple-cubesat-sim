"""Test RW unloading after saturation on individual axes."""

import numpy as np
import pytest

from backend.simulation.engine import SimulationEngine


class TestRWSaturationUnloading:
    """Test that RW unloading works when axes reach saturation."""

    def test_single_axis_saturation_and_unload(self):
        """Test unloading after a single RW axis saturates."""
        engine = SimulationEngine()
        engine.spacecraft.set_control_mode("POINTING")

        # Set aggressive threshold to trigger unloading quickly
        engine.spacecraft._auto_unloading.upper_threshold = np.array([800.0] * 3)
        engine.spacecraft._auto_unloading.lower_threshold = np.array([-800.0] * 3)
        engine.spacecraft._auto_unloading.target_speed = np.array([600.0] * 3)

        engine.start()

        # Run until RW saturates
        max_speed_reached = False
        for i in range(100):
            engine.step()
            rw_speed = engine.spacecraft.reaction_wheel.get_speed()
            max_speed = engine.spacecraft.reaction_wheel.max_speed

            if np.any(np.abs(rw_speed) >= max_speed * 0.99):
                max_speed_reached = True
                print(f"Step {i}: RW saturated, speed={rw_speed}")
                break

        assert max_speed_reached, "RW should reach saturation"

        # Continue running with unloading active
        initial_speed = engine.spacecraft.reaction_wheel.get_speed().copy()
        mtq_values = []

        for i in range(200):
            engine.step()
            rw_speed = engine.spacecraft.reaction_wheel.get_speed()
            mtq_dipole = engine.spacecraft.magnetorquer.get_dipole()
            mtq_values.append(np.linalg.norm(mtq_dipole))

            if i % 40 == 0:
                is_unloading = engine.spacecraft._auto_unloading.is_active()
                print(f"Step {i}: speed={rw_speed[0]:.1f}, "
                      f"|MTQ|={np.linalg.norm(mtq_dipole):.4f}, unload={is_unloading}")

        final_speed = engine.spacecraft.reaction_wheel.get_speed()

        print(f"\\nInitial speed: {initial_speed}")
        print(f"Final speed:   {final_speed}")
        print(f"MTQ usage: min={min(mtq_values):.4f}, max={max(mtq_values):.4f}, "
              f"mean={np.mean(mtq_values):.4f}")

        # Check that MTQ is not constantly saturated
        max_dipole = engine.spacecraft.magnetorquer.max_dipole
        saturated_ratio = sum(1 for m in mtq_values if m > max_dipole * 0.95) / len(mtq_values)
        print(f"MTQ saturation ratio: {saturated_ratio:.2%}")

        # MTQ should not be saturated all the time
        assert saturated_ratio < 0.8, f"MTQ saturated {saturated_ratio:.1%} of time (too high)"

    def test_three_axis_saturation_and_unload(self):
        """Test unloading behavior when all three axes are saturated."""
        engine = SimulationEngine()
        engine.spacecraft.set_control_mode("POINTING")

        # Very aggressive to reach saturation quickly
        engine.spacecraft._auto_unloading.upper_threshold = np.array([850.0] * 3)
        engine.spacecraft._auto_unloading.lower_threshold = np.array([-850.0] * 3)
        engine.spacecraft._auto_unloading.target_speed = np.array([700.0] * 3)

        engine.start()

        # Run until all RW axes saturate
        for i in range(50):
            engine.step()

        rw_speed = engine.spacecraft.reaction_wheel.get_speed()
        max_speed = engine.spacecraft.reaction_wheel.max_speed

        print(f"After 50 steps: RW speed = {rw_speed}")
        print(f"Max speed: {max_speed}")

        # Check how many axes are near saturation
        saturated_axes = np.sum(np.abs(rw_speed) > max_speed * 0.9)
        print(f"Saturated axes: {saturated_axes}/3")

        # At least one axis should be near saturation
        assert saturated_axes >= 1, "At least one RW axis should be near saturation"

        # Track MTQ and speed for extended period
        speed_history = []
        mtq_history = []

        for i in range(300):
            engine.step()
            rw_speed = engine.spacecraft.reaction_wheel.get_speed()
            mtq_dipole = engine.spacecraft.magnetorquer.get_dipole()

            speed_history.append(rw_speed.copy())
            mtq_history.append(mtq_dipole.copy())

            if i % 60 == 0:
                print(f"Step {i:3d}: speed={rw_speed}, |MTQ|={np.linalg.norm(mtq_dipole):.4f}")

        # Analyze results
        speeds = np.array(speed_history)
        mtqs = np.array(mtq_history)

        print(f"\\nSpeed stats (rad/s):")
        print(f"  Mean: {np.mean(np.abs(speeds), axis=0)}")
        print(f"  Max:  {np.max(np.abs(speeds), axis=0)}")

        print(f"\\nMTQ stats (Am²):")
        print(f"  Mean |m|: {np.mean(np.linalg.norm(mtqs, axis=1)):.4f}")
        print(f"  Max |m|:  {np.max(np.linalg.norm(mtqs, axis=1)):.4f}")

        # Check that MTQ is being used (unloading is active)
        mean_mtq = np.mean(np.linalg.norm(mtqs, axis=1))
        assert mean_mtq > 0.01, "MTQ should be active for unloading"

    def test_unloading_gain_effectiveness(self):
        """Test that torque-based unloading avoids MTQ saturation."""
        engine = SimulationEngine()
        engine.spacecraft.set_control_mode("POINTING")

        # Use default thresholds (±720 rad/s)
        engine.start()

        # Run simulation and track MTQ saturation
        mtq_saturation_count = 0
        max_dipole = engine.spacecraft.magnetorquer.max_dipole

        for _ in range(200):
            engine.step()
            mtq_dipole = engine.spacecraft.magnetorquer.get_dipole()
            if np.linalg.norm(mtq_dipole) > max_dipole * 0.95:
                mtq_saturation_count += 1

        saturation_ratio = mtq_saturation_count / 200
        final_speed = engine.spacecraft.reaction_wheel.get_speed()

        print(f"MTQ saturation: {saturation_ratio:.1%}")
        print(f"Final RW speed: {final_speed}")
        print(f"Final RW speed norm: {np.linalg.norm(final_speed):.1f} rad/s")

        # Torque-based control should keep MTQ saturation low
        assert saturation_ratio < 0.5, \
            f"MTQ saturation ratio {saturation_ratio:.1%} is too high"

    def test_negative_saturation_recovery(self):
        """Test recovery when multiple axes saturate in negative direction."""
        engine = SimulationEngine()
        engine.spacecraft.set_control_mode("POINTING")

        # Set negative initial RW speeds (near saturation)
        engine.spacecraft.reaction_wheel._speed = np.array([-850.0, -850.0, 0.0])

        # Aggressive thresholds to trigger unloading immediately
        engine.spacecraft._auto_unloading.upper_threshold = np.array([800.0] * 3)
        engine.spacecraft._auto_unloading.lower_threshold = np.array([-800.0] * 3)
        engine.spacecraft._auto_unloading.target_speed = np.zeros(3)

        engine.start()

        # Record initial state
        initial_speed = engine.spacecraft.reaction_wheel.get_speed().copy()
        print(f"Initial RW speed: {initial_speed}")

        # Run simulation for recovery
        speed_history = []
        state_history = []
        mtq_history = []

        for i in range(500):
            engine.step()
            rw_speed = engine.spacecraft.reaction_wheel.get_speed()
            mtq_dipole = engine.spacecraft.magnetorquer.get_dipole()
            unload_state = [
                engine.spacecraft._auto_unloading.get_state_str(j) for j in range(3)
            ]

            speed_history.append(rw_speed.copy())
            state_history.append(unload_state)
            mtq_history.append(mtq_dipole.copy())

            if i % 100 == 0:
                print(f"Step {i:3d}: speed={rw_speed}, state={unload_state}, "
                      f"|MTQ|={np.linalg.norm(mtq_dipole):.4f}")

        final_speed = engine.spacecraft.reaction_wheel.get_speed()
        print(f"\nFinal RW speed: {final_speed}")

        # Check if X and Y axes recovered towards zero
        # They should have increased (become less negative)
        assert final_speed[0] > initial_speed[0] + 50.0, \
            f"X-axis should recover: initial={initial_speed[0]:.1f}, final={final_speed[0]:.1f}"
        assert final_speed[1] > initial_speed[1] + 50.0, \
            f"Y-axis should recover: initial={initial_speed[1]:.1f}, final={final_speed[1]:.1f}"

        # Analyze recovery rate
        speeds = np.array(speed_history)
        print(f"\nSpeed range over time:")
        print(f"  X: [{speeds[:, 0].min():.1f}, {speeds[:, 0].max():.1f}]")
        print(f"  Y: [{speeds[:, 1].min():.1f}, {speeds[:, 1].max():.1f}]")
        print(f"  Z: [{speeds[:, 2].min():.1f}, {speeds[:, 2].max():.1f}]")

    def test_natural_negative_saturation(self):
        """Test if system naturally recovers from negative saturation during POINTING."""
        engine = SimulationEngine()
        engine.spacecraft.set_control_mode("POINTING")

        # Use default thresholds (±720 rad/s)
        engine.start()

        # Run until some axes naturally reach negative speeds
        # Track when negative saturation occurs
        max_negative_steps = 1000
        negative_saturation_detected = False

        for i in range(max_negative_steps):
            engine.step()
            rw_speed = engine.spacecraft.reaction_wheel.get_speed()

            # Check if X or Y is below -800 rad/s
            if rw_speed[0] < -800.0 or rw_speed[1] < -800.0:
                negative_saturation_detected = True
                print(f"\nNegative saturation detected at step {i}:")
                print(f"  RW speed: {rw_speed}")
                break

        if not negative_saturation_detected:
            print(f"\nNo negative saturation after {max_negative_steps} steps")
            print(f"  Final RW speed: {engine.spacecraft.reaction_wheel.get_speed()}")
            # This is fine - not all scenarios will reach negative saturation
            return

        # Now track recovery for extended period
        recovery_start_speed = engine.spacecraft.reaction_wheel.get_speed().copy()
        print(f"Starting recovery from: {recovery_start_speed}")

        speed_history = []
        for i in range(1000):
            engine.step()
            rw_speed = engine.spacecraft.reaction_wheel.get_speed()
            speed_history.append(rw_speed.copy())

            if i % 200 == 0:
                state = [engine.spacecraft._auto_unloading.get_state_str(j) for j in range(3)]
                print(f"Recovery step {i:3d}: speed={rw_speed}, state={state}")

        final_speed = engine.spacecraft.reaction_wheel.get_speed()
        print(f"\nRecovery result:")
        print(f"  Start: {recovery_start_speed}")
        print(f"  End:   {final_speed}")
        print(f"  Delta: {final_speed - recovery_start_speed}")

        # Check if axes that were negative are recovering
        for axis in range(2):  # Check X and Y
            if recovery_start_speed[axis] < -800.0:
                # Speed should increase (become less negative) by at least some amount
                improvement = final_speed[axis] - recovery_start_speed[axis]
                print(f"  Axis {axis} improvement: {improvement:.1f} rad/s")
                # Allow for slow recovery - at least 20 rad/s improvement
                assert improvement > 20.0, \
                    f"Axis {axis} should improve from negative saturation"
