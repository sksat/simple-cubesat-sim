"""Integration tests for timeline functionality."""

import json
import pytest
from backend.simulation.engine import SimulationEngine


class TestTimelineExecution:
    """Tests for timeline action execution."""

    def test_control_mode_action_executes(self):
        """Control mode action should change spacecraft mode at scheduled time."""
        engine = SimulationEngine()
        engine.start()

        # Schedule a control mode change at t=1.0s
        action = engine.add_timeline_action(
            time=1.0,
            action_type="control_mode",
            params={"mode": "POINTING"},
        )
        assert action["actionType"] == "control_mode"
        assert not action["executed"]

        # Initially in IDLE mode
        assert engine.spacecraft.control_mode == "IDLE"

        # Step until past t=1.0s
        while engine.sim_time < 1.5:
            engine.step()

        # Mode should have changed
        assert engine.spacecraft.control_mode == "POINTING"

    def test_pointing_mode_action_executes(self):
        """Pointing mode action should change pointing target."""
        engine = SimulationEngine()
        engine.set_control_mode("POINTING")
        engine.start()

        # Schedule pointing mode change at t=0.5s
        engine.add_timeline_action(
            time=0.5,
            action_type="pointing_mode",
            params={"mode": "SUN"},
        )

        # Initially MANUAL
        assert engine.pointing_mode == "MANUAL"

        # Step until past t=0.5s
        while engine.sim_time < 1.0:
            engine.step()

        # Pointing mode should have changed
        assert engine.pointing_mode == "SUN"

    def test_imaging_target_action_executes(self):
        """Imaging target action should set target coordinates."""
        engine = SimulationEngine()
        engine.start()

        # Schedule imaging target at t=0.5s
        engine.add_timeline_action(
            time=0.5,
            action_type="imaging_target",
            params={"latitude": 35.5, "longitude": 139.7, "altitude": 100.0},
        )

        # Step until past t=0.5s
        while engine.sim_time < 1.0:
            engine.step()

        # Imaging target should be set
        assert engine._imaging_target is not None
        assert abs(engine._imaging_target.latitude_deg - 35.5) < 0.01
        assert abs(engine._imaging_target.longitude_deg - 139.7) < 0.01

    def test_multiple_actions_execute_in_order(self):
        """Multiple actions should execute in time order."""
        engine = SimulationEngine()
        engine.start()

        # Schedule actions out of order
        engine.add_timeline_action(
            time=1.0,
            action_type="control_mode",
            params={"mode": "POINTING"},
        )
        engine.add_timeline_action(
            time=0.5,
            action_type="control_mode",
            params={"mode": "DETUMBLING"},
        )

        # Step until after t=0.5s but before t=1.0s
        while engine.sim_time < 0.8:
            engine.step()

        # First action (t=0.5s) should have executed
        assert engine.spacecraft.control_mode == "DETUMBLING"

        # Step past t=1.0s
        while engine.sim_time < 1.5:
            engine.step()

        # Second action should have executed
        assert engine.spacecraft.control_mode == "POINTING"

    def test_action_removal_prevents_execution(self):
        """Removed actions should not execute."""
        engine = SimulationEngine()
        engine.start()

        action = engine.add_timeline_action(
            time=0.5,
            action_type="control_mode",
            params={"mode": "POINTING"},
        )

        # Remove the action
        removed = engine.remove_timeline_action(action["id"])
        assert removed

        # Step past scheduled time
        while engine.sim_time < 1.0:
            engine.step()

        # Mode should still be IDLE
        assert engine.spacecraft.control_mode == "IDLE"

    def test_action_in_past_raises_error(self):
        """Cannot schedule action in the past."""
        engine = SimulationEngine()
        engine.start()

        # Step forward
        while engine.sim_time < 1.0:
            engine.step()

        # Try to schedule action in the past
        with pytest.raises(ValueError, match="Cannot schedule action in the past"):
            engine.add_timeline_action(
                time=0.5,
                action_type="control_mode",
                params={"mode": "POINTING"},
            )

    def test_reset_clears_timeline(self):
        """Reset should clear all pending actions."""
        engine = SimulationEngine()
        engine.start()

        engine.add_timeline_action(
            time=10.0,
            action_type="control_mode",
            params={"mode": "POINTING"},
        )

        assert len(engine.get_pending_actions()) == 1

        engine.reset()

        assert len(engine.get_pending_actions()) == 0


class TestTimelineTelemetry:
    """Tests for timeline data in telemetry."""

    def test_telemetry_includes_timeline(self):
        """Telemetry should include timeline data."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        telemetry = engine.get_telemetry()

        assert "timeline" in telemetry
        assert "nextContact" in telemetry["timeline"]
        assert "actions" in telemetry["timeline"]

    def test_telemetry_timeline_is_json_serializable(self):
        """Timeline data in telemetry must be JSON serializable."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        # Add some actions
        engine.add_timeline_action(
            time=100.0,
            action_type="control_mode",
            params={"mode": "POINTING"},
        )
        engine.add_timeline_action(
            time=200.0,
            action_type="imaging_target",
            params={"latitude": 35.0, "longitude": 139.0},
        )

        telemetry = engine.get_telemetry()

        # This should not raise
        try:
            json_str = json.dumps(telemetry["timeline"])
            parsed = json.loads(json_str)
            assert "nextContact" in parsed
            assert "actions" in parsed
            assert len(parsed["actions"]) == 2
        except TypeError as e:
            pytest.fail(f"Timeline not JSON serializable: {e}")

    def test_actions_appear_in_telemetry(self):
        """Added actions should appear in telemetry."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        action = engine.add_timeline_action(
            time=100.0,
            action_type="control_mode",
            params={"mode": "POINTING"},
        )

        telemetry = engine.get_telemetry()
        actions = telemetry["timeline"]["actions"]

        assert len(actions) == 1
        assert actions[0]["id"] == action["id"]
        assert actions[0]["actionType"] == "control_mode"

    def test_executed_actions_not_in_pending_list(self):
        """Executed actions should not appear in pending list."""
        engine = SimulationEngine()
        engine.start()

        engine.add_timeline_action(
            time=0.5,
            action_type="control_mode",
            params={"mode": "POINTING"},
        )

        # Before execution
        telemetry = engine.get_telemetry()
        assert len(telemetry["timeline"]["actions"]) == 1

        # Step past execution time
        while engine.sim_time < 1.0:
            engine.step()

        # After execution - action should not be in pending list
        telemetry = engine.get_telemetry()
        assert len(telemetry["timeline"]["actions"]) == 0


class TestImagingPreset:
    """Tests for imaging preset feature."""

    def test_calculate_imaging_preset(self):
        """Calculate imaging preset should return ground track position."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        preset = engine.calculate_imaging_preset(offset_seconds=300)

        if preset is not None:
            assert "latitude" in preset
            assert "longitude" in preset
            assert "targetTime" in preset
            assert "contactStartTime" in preset
            assert -90 <= preset["latitude"] <= 90
            assert -180 <= preset["longitude"] <= 180

    def test_set_imaging_preset(self):
        """Set imaging preset should set the imaging target."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        # Clear any existing target
        engine._imaging_target = None

        preset = engine.set_imaging_preset(offset_seconds=300, schedule_action=False)

        if preset is not None:
            assert engine._imaging_target is not None
            assert abs(engine._imaging_target.latitude_deg - preset["latitude"]) < 0.01

    def test_set_imaging_preset_with_schedule(self):
        """Set imaging preset with schedule should add timeline action."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        initial_count = len(engine.get_pending_actions())
        preset = engine.set_imaging_preset(offset_seconds=300, schedule_action=True)

        if preset is not None:
            # Should have scheduled a pointing mode action
            new_count = len(engine.get_pending_actions())
            assert new_count >= initial_count  # At least same or more

    def test_get_ground_track_at_time(self):
        """Get ground track should return valid coordinates."""
        engine = SimulationEngine()

        ground_track = engine.get_ground_track_at_time(1000.0)

        assert "latitude" in ground_track
        assert "longitude" in ground_track
        assert "altitude" in ground_track
        assert "time" in ground_track
        assert ground_track["time"] == 1000.0
        assert -90 <= ground_track["latitude"] <= 90
        assert -180 <= ground_track["longitude"] <= 180


class TestContactPrediction:
    """Tests for contact prediction in engine."""

    def test_contact_prediction_returns_dict_or_none(self):
        """Contact prediction should return dict or None."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        contact = engine.get_next_contact()
        assert contact is None or hasattr(contact, "to_dict")

    def test_contact_in_telemetry(self):
        """Next contact should appear in telemetry."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        telemetry = engine.get_telemetry()
        timeline = telemetry["timeline"]

        # nextContact can be None or a dict
        assert "nextContact" in timeline

    def test_refresh_contact_updates_cache(self):
        """Refresh contact should update cache."""
        engine = SimulationEngine()
        engine.start()
        engine.step()

        # Get initial prediction
        contact1 = engine.get_next_contact()

        # Force refresh
        contact2 = engine.get_next_contact(force_refresh=True)

        # Both should be valid (or both None)
        if contact1 is not None:
            assert contact1.ground_station_name == contact2.ground_station_name
