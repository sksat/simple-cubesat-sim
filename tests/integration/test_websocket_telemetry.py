"""Integration tests for WebSocket telemetry.

These tests verify that the full telemetry pipeline works correctly,
including JSON serialization of all data types.
"""

import json
import pytest
from backend.simulation.engine import SimulationEngine
from backend.api.routes.websocket import _step_and_get_telemetry


class TestTelemetryJSONSerialization:
    """Tests for JSON serialization of telemetry data.

    These tests catch issues like numpy.bool_ not being JSON serializable.
    """

    def test_telemetry_is_json_serializable(self):
        """All telemetry data must be JSON serializable.

        This catches numpy types that aren't directly serializable:
        - numpy.bool_ -> must be Python bool
        - numpy.float64 -> must be Python float
        - numpy.int64 -> must be Python int
        - numpy.ndarray -> must be Python list
        """
        engine = SimulationEngine()
        engine.start()

        # Run a few steps to populate all telemetry fields
        for _ in range(5):
            engine.step()

        telemetry = engine.get_telemetry()

        # This should not raise TypeError
        try:
            json_str = json.dumps(telemetry)
            # Verify it can be parsed back
            parsed = json.loads(json_str)
            assert parsed is not None
        except TypeError as e:
            pytest.fail(f"Telemetry is not JSON serializable: {e}")

    def test_step_and_get_telemetry_is_json_serializable(self):
        """The WebSocket helper function must return JSON-serializable data."""
        engine = SimulationEngine()
        engine.start()

        # This is what the WebSocket handler calls
        telemetry = _step_and_get_telemetry(engine)

        try:
            json_str = json.dumps(telemetry)
            parsed = json.loads(json_str)
            assert parsed["type"] == "telemetry"
        except TypeError as e:
            pytest.fail(f"WebSocket telemetry is not JSON serializable: {e}")

    def test_ground_station_visible_is_python_bool(self):
        """groundStationVisible must be a Python bool, not numpy.bool_."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        telemetry = engine.get_telemetry()
        visible = telemetry["control"]["groundStationVisible"]

        # Check it's a Python bool, not numpy.bool_
        assert type(visible) is bool, f"Expected bool, got {type(visible)}"

    def test_is_illuminated_is_python_bool(self):
        """isIlluminated must be a Python bool, not numpy.bool_."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        telemetry = engine.get_telemetry()
        illuminated = telemetry["environment"]["isIlluminated"]

        assert type(illuminated) is bool, f"Expected bool, got {type(illuminated)}"

    def test_telemetry_numeric_types_are_native(self):
        """All numeric values in telemetry must be native Python types."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        telemetry = engine.get_telemetry()

        # Check some key numeric fields
        assert type(telemetry["timestamp"]) is float
        assert type(telemetry["timeWarp"]) is float

        # Check nested numeric fields are lists of floats
        quaternion = telemetry["attitude"]["quaternion"]
        assert isinstance(quaternion, list)
        for val in quaternion:
            assert type(val) is float, f"Quaternion value should be float, got {type(val)}"

    def test_all_control_modes_produce_serializable_telemetry(self):
        """All control modes must produce JSON-serializable telemetry."""
        for mode in ["Idle", "Detumbling", "3Axis"]:
            engine = SimulationEngine()
            engine.set_control_mode(mode)
            engine.start()

            for _ in range(3):
                engine.step()

            telemetry = engine.get_telemetry()

            try:
                json.dumps(telemetry)
            except TypeError as e:
                pytest.fail(f"Telemetry not serializable in {mode} mode: {e}")

    def test_all_pointing_modes_produce_serializable_telemetry(self):
        """All pointing modes must produce JSON-serializable telemetry."""
        for pointing_mode in ["MANUAL", "SUN", "NADIR", "GROUND_STATION"]:
            engine = SimulationEngine()
            engine.set_control_mode("3Axis")
            engine.set_pointing_mode(pointing_mode)
            engine.start()

            for _ in range(3):
                engine.step()

            telemetry = engine.get_telemetry()

            try:
                json.dumps(telemetry)
            except TypeError as e:
                pytest.fail(
                    f"Telemetry not serializable in POINTING/{pointing_mode} mode: {e}"
                )
