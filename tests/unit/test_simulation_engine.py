"""Unit tests for simulation engine.

TDD: Write tests first, then implement.

The simulation engine:
- Manages simulation time and state
- Runs the spacecraft simulation loop
- Provides telemetry data
- Supports start/stop/pause/reset
"""

import numpy as np
import pytest

from backend.simulation.engine import SimulationEngine, SimulationState


class TestSimulationEngineInitialization:
    """Tests for simulation engine initialization."""

    def test_default_initialization(self):
        """Engine should initialize with default parameters."""
        engine = SimulationEngine()

        assert engine.state == SimulationState.STOPPED
        assert engine.sim_time == 0.0
        assert engine.spacecraft is not None

    def test_custom_time_step(self):
        """Engine should accept custom time step."""
        engine = SimulationEngine(dt=0.05)

        assert engine.dt == 0.05

    def test_default_time_warp(self):
        """Default time warp should be 1.0 (real-time)."""
        engine = SimulationEngine()

        assert engine.time_warp == 1.0


class TestSimulationEngineState:
    """Tests for simulation state management."""

    def test_start_from_stopped(self):
        """Should be able to start from stopped state."""
        engine = SimulationEngine()

        engine.start()

        assert engine.state == SimulationState.RUNNING

    def test_pause_from_running(self):
        """Should be able to pause from running state."""
        engine = SimulationEngine()
        engine.start()

        engine.pause()

        assert engine.state == SimulationState.PAUSED

    def test_resume_from_paused(self):
        """Should be able to resume from paused state."""
        engine = SimulationEngine()
        engine.start()
        engine.pause()

        engine.start()

        assert engine.state == SimulationState.RUNNING

    def test_stop_from_running(self):
        """Should be able to stop from running state."""
        engine = SimulationEngine()
        engine.start()

        engine.stop()

        assert engine.state == SimulationState.STOPPED

    def test_reset_clears_time(self):
        """Reset should clear simulation time."""
        engine = SimulationEngine()
        engine.start()

        # Advance time manually
        engine.step()
        engine.step()

        engine.reset()

        assert engine.sim_time == 0.0
        assert engine.state == SimulationState.STOPPED


class TestSimulationEngineStep:
    """Tests for simulation stepping."""

    def test_step_advances_time(self):
        """Single step should advance simulation time."""
        engine = SimulationEngine(dt=0.1)
        engine.start()

        engine.step()

        assert np.isclose(engine.sim_time, 0.1)

    def test_multiple_steps(self):
        """Multiple steps should accumulate time."""
        engine = SimulationEngine(dt=0.1)
        engine.start()

        for _ in range(10):
            engine.step()

        assert np.isclose(engine.sim_time, 1.0)

    def test_step_updates_spacecraft(self):
        """Step should update spacecraft state."""
        engine = SimulationEngine(dt=0.1)
        engine.spacecraft.angular_velocity = np.array([0.0, 0.0, 0.1])
        engine.start()

        q_before = engine.spacecraft.quaternion.copy()
        engine.step()

        # Quaternion should have changed due to rotation
        assert not np.allclose(engine.spacecraft.quaternion, q_before)

    def test_step_does_nothing_when_stopped(self):
        """Step should not advance when stopped."""
        engine = SimulationEngine(dt=0.1)

        engine.step()  # Not started yet

        assert engine.sim_time == 0.0

    def test_step_does_nothing_when_paused(self):
        """Step should not advance when paused."""
        engine = SimulationEngine(dt=0.1)
        engine.start()
        engine.step()  # Advance to 0.1
        engine.pause()

        engine.step()  # Should not advance

        assert np.isclose(engine.sim_time, 0.1)


class TestSimulationEngineTelemetry:
    """Tests for telemetry generation."""

    def test_get_telemetry_returns_dict(self):
        """Should return telemetry as dictionary."""
        engine = SimulationEngine()

        telemetry = engine.get_telemetry()

        assert isinstance(telemetry, dict)

    def test_telemetry_contains_time(self):
        """Telemetry should contain simulation time."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        telemetry = engine.get_telemetry()

        assert "timestamp" in telemetry
        assert telemetry["timestamp"] > 0

    def test_telemetry_contains_attitude(self):
        """Telemetry should contain attitude data."""
        engine = SimulationEngine()

        telemetry = engine.get_telemetry()

        assert "attitude" in telemetry
        assert "quaternion" in telemetry["attitude"]
        assert "angularVelocity" in telemetry["attitude"]

    def test_telemetry_contains_actuators(self):
        """Telemetry should contain actuator data."""
        engine = SimulationEngine()

        telemetry = engine.get_telemetry()

        assert "actuators" in telemetry
        assert "reactionWheels" in telemetry["actuators"]
        assert "magnetorquers" in telemetry["actuators"]

    def test_telemetry_contains_control(self):
        """Telemetry should contain control mode."""
        engine = SimulationEngine()

        telemetry = engine.get_telemetry()

        assert "control" in telemetry
        assert "mode" in telemetry["control"]


class TestSimulationEngineTimeWarp:
    """Tests for time warp functionality."""

    def test_set_time_warp(self):
        """Should be able to set time warp."""
        engine = SimulationEngine()

        engine.set_time_warp(10.0)

        assert engine.time_warp == 10.0

    def test_time_warp_affects_effective_dt(self):
        """Time warp should scale effective time step."""
        engine = SimulationEngine(dt=0.1)
        engine.set_time_warp(5.0)
        engine.start()

        engine.step()

        # Effective dt = 0.1 * 5 = 0.5
        assert np.isclose(engine.sim_time, 0.5)

    def test_negative_time_warp_rejected(self):
        """Should reject negative time warp."""
        engine = SimulationEngine()

        with pytest.raises(ValueError):
            engine.set_time_warp(-1.0)

    def test_zero_time_warp_rejected(self):
        """Should reject zero time warp."""
        engine = SimulationEngine()

        with pytest.raises(ValueError):
            engine.set_time_warp(0.0)


class TestSimulationEngineControlMode:
    """Tests for control mode management."""

    def test_set_control_mode(self):
        """Should be able to set control mode."""
        engine = SimulationEngine()

        engine.set_control_mode("DETUMBLING")

        assert engine.spacecraft.control_mode == "DETUMBLING"

    def test_set_target_attitude(self):
        """Should be able to set target attitude."""
        from backend.dynamics.quaternion import from_axis_angle

        engine = SimulationEngine()
        target = from_axis_angle(np.array([0.0, 0.0, 1.0]), 0.5)

        engine.set_target_attitude(target)

        np.testing.assert_array_almost_equal(
            engine.spacecraft._target_quaternion, target
        )


class TestSimulationEngineMagneticField:
    """Tests for magnetic field model."""

    def test_magnetic_field_model(self):
        """Engine should have a magnetic field model."""
        engine = SimulationEngine()

        # Default should provide some field
        b_field = engine.get_magnetic_field()

        assert b_field is not None
        assert len(b_field) == 3
        assert np.linalg.norm(b_field) > 0  # Should be non-zero

    def test_magnetic_field_used_in_step(self):
        """Magnetic field should be used in simulation step."""
        engine = SimulationEngine()
        engine.spacecraft.angular_velocity = np.array([0.1, 0.05, -0.08])
        engine.set_control_mode("DETUMBLING")
        engine.start()

        # Run for some steps
        initial_rate = np.linalg.norm(engine.spacecraft.angular_velocity)
        for _ in range(1000):
            engine.step()

        final_rate = np.linalg.norm(engine.spacecraft.angular_velocity)

        # Detumbling should reduce angular velocity
        assert final_rate < initial_rate
