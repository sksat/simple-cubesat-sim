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
        """Test different unloading gains and their effectiveness."""
        gains = [100.0, 300.0, 1000.0]
        results = []

        for gain in gains:
            engine = SimulationEngine()
            engine.spacecraft._unloading_controller.gain = gain
            engine.spacecraft.set_control_mode("POINTING")

            # Aggressive thresholds
            engine.spacecraft._auto_unloading.upper_threshold = np.array([750.0] * 3)
            engine.spacecraft._auto_unloading.target_speed = np.array([600.0] * 3)

            engine.start()

            # Run simulation
            mtq_saturation_count = 0
            max_dipole = engine.spacecraft.magnetorquer.max_dipole

            for _ in range(150):
                engine.step()
                mtq_dipole = engine.spacecraft.magnetorquer.get_dipole()
                if np.linalg.norm(mtq_dipole) > max_dipole * 0.95:
                    mtq_saturation_count += 1

            saturation_ratio = mtq_saturation_count / 150
            final_speed = engine.spacecraft.reaction_wheel.get_speed()

            results.append({
                'gain': gain,
                'saturation_ratio': saturation_ratio,
                'final_speed': final_speed,
            })

            print(f"Gain {gain:6.1f}: MTQ saturation={saturation_ratio:.1%}, "
                  f"final_speed={np.linalg.norm(final_speed):.1f}")

        # With 10% scaling, all gains should have low saturation
        for result in results:
            assert result['saturation_ratio'] < 0.5, \
                f"Gain {result['gain']}: saturation should be low"
