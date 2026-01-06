"""Integration tests for custom pointing configuration."""

import numpy as np
import pytest

from backend.simulation.engine import SimulationEngine
from backend.control.target_direction import TargetDirection


class TestPointingConfig:
    """Test custom pointing configuration via main/sub axis."""

    def test_set_pointing_config_basic(self):
        """Test setting a custom pointing configuration."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        # Set custom config: +X → Sun, +Y → Nadir
        engine.set_pointing_config(
            main_target="SUN",
            main_body_axis=[1, 0, 0],
            sub_target="EARTH_CENTER",
            sub_body_axis=[0, 1, 0],
        )

        # Should switch to MANUAL mode (custom config)
        assert engine.pointing_mode == "MANUAL"

        # Verify config was set in attitude target calculator
        config = engine._attitude_target_calc.config
        assert config.main_target == TargetDirection.SUN
        assert np.allclose(config.main_body_axis, [1, 0, 0])
        assert config.sub_target == TargetDirection.EARTH_CENTER
        assert np.allclose(config.sub_body_axis, [0, 1, 0])

    def test_set_pointing_config_velocity(self):
        """Test pointing configuration with velocity target."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        # Set config: -Z → Nadir, +X → Velocity
        engine.set_pointing_config(
            main_target="EARTH_CENTER",
            main_body_axis=[0, 0, -1],
            sub_target="VELOCITY",
            sub_body_axis=[1, 0, 0],
        )

        config = engine._attitude_target_calc.config
        assert config.main_target == TargetDirection.EARTH_CENTER
        assert config.sub_target == TargetDirection.VELOCITY

    def test_set_pointing_config_orbit_normal(self):
        """Test pointing configuration with orbit normal target."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        # Set config: +Y → Orbit Normal, +Z → Velocity
        engine.set_pointing_config(
            main_target="ORBIT_NORMAL",
            main_body_axis=[0, 1, 0],
            sub_target="VELOCITY",
            sub_body_axis=[0, 0, 1],
        )

        config = engine._attitude_target_calc.config
        assert config.main_target == TargetDirection.ORBIT_NORMAL
        assert config.sub_target == TargetDirection.VELOCITY

    def test_set_pointing_config_invalid_target(self):
        """Test error on invalid target direction."""
        engine = SimulationEngine()

        with pytest.raises(ValueError, match="Invalid target direction"):
            engine.set_pointing_config(
                main_target="INVALID_TARGET",
                main_body_axis=[0, 0, 1],
                sub_target="SUN",
                sub_body_axis=[1, 0, 0],
            )

    def test_set_pointing_config_normalizes_axes(self):
        """Test that body axes are normalized."""
        engine = SimulationEngine()

        # Set config with non-unit vectors
        engine.set_pointing_config(
            main_target="SUN",
            main_body_axis=[2, 0, 0],  # Not unit length
            sub_target="EARTH_CENTER",
            sub_body_axis=[0, 3, 0],  # Not unit length
        )

        # Axes should be normalized
        config = engine._attitude_target_calc.config
        assert np.allclose(np.linalg.norm(config.main_body_axis), 1.0)
        assert np.allclose(np.linalg.norm(config.sub_body_axis), 1.0)
        assert np.allclose(config.main_body_axis, [1, 0, 0])
        assert np.allclose(config.sub_body_axis, [0, 1, 0])

    def test_set_pointing_config_with_ground_station(self):
        """Test pointing config using ground station target."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        # Set config with ground station
        engine.set_pointing_config(
            main_target="GROUND_STATION",
            main_body_axis=[0, 0, -1],
            sub_target="VELOCITY",
            sub_body_axis=[1, 0, 0],
        )

        config = engine._attitude_target_calc.config
        assert config.main_target == TargetDirection.GROUND_STATION
        assert config.ground_station is not None

    def test_set_pointing_config_with_imaging_target(self):
        """Test pointing config using imaging target."""
        engine = SimulationEngine()
        engine.set_imaging_target(lat_deg=35.0, lon_deg=139.0)
        engine.start()
        engine.step()

        # Set config with imaging target
        engine.set_pointing_config(
            main_target="IMAGING_TARGET",
            main_body_axis=[0, 0, -1],
            sub_target="EARTH_CENTER",
            sub_body_axis=[1, 0, 0],
        )

        config = engine._attitude_target_calc.config
        assert config.main_target == TargetDirection.IMAGING_TARGET
        assert config.imaging_target is not None
        assert config.imaging_target.latitude_deg == 35.0

    def test_pointing_config_with_control_mode(self):
        """Test that custom config works with POINTING control mode."""
        engine = SimulationEngine()
        engine.set_control_mode("POINTING")

        # Set custom config (+X → Sun, +Y → Nadir)
        engine.set_pointing_config(
            main_target="SUN",
            main_body_axis=[1, 0, 0],
            sub_target="EARTH_CENTER",
            sub_body_axis=[0, 1, 0],
        )

        engine.start()
        # Run a few steps to let control settle
        for _ in range(10):
            engine.step()

        # Should be in MANUAL mode (custom config)
        assert engine.pointing_mode == "MANUAL"

        # Verify configuration is still set
        config = engine._attitude_target_calc.config
        assert config.main_target == TargetDirection.SUN
        assert np.allclose(config.main_body_axis, [1, 0, 0])
