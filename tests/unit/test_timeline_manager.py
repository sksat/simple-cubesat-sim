"""Tests for timeline manager."""

import pytest
from backend.timeline.timeline_manager import TimelineManager
from backend.prediction.models import TimelineActionType


class TestTimelineManager:
    """Tests for TimelineManager class."""

    def test_add_action_creates_id(self):
        """Added action should have unique ID."""
        manager = TimelineManager()
        action = manager.add_action(
            time=100.0,
            action_type=TimelineActionType.CONTROL_MODE,
            params={"mode": "POINTING"},
            current_sim_time=0.0,
        )
        assert action.id is not None
        assert len(action.id) == 36  # UUID format

    def test_add_action_with_string_type(self):
        """Should accept string action type."""
        manager = TimelineManager()
        action = manager.add_action(
            time=100.0,
            action_type="control_mode",
            params={"mode": "POINTING"},
            current_sim_time=0.0,
        )
        assert action.action_type == TimelineActionType.CONTROL_MODE

    def test_add_action_in_past_raises(self):
        """Cannot schedule action in the past."""
        manager = TimelineManager()
        with pytest.raises(ValueError, match="Cannot schedule action in the past"):
            manager.add_action(
                time=50.0,
                action_type=TimelineActionType.CONTROL_MODE,
                params={"mode": "POINTING"},
                current_sim_time=100.0,
            )

    def test_actions_sorted_by_time(self):
        """Actions should be ordered by execution time."""
        manager = TimelineManager()

        # Add out of order
        manager.add_action(
            time=300.0,
            action_type=TimelineActionType.CONTROL_MODE,
            params={"mode": "IDLE"},
            current_sim_time=0.0,
        )
        manager.add_action(
            time=100.0,
            action_type=TimelineActionType.POINTING_MODE,
            params={"mode": "SUN"},
            current_sim_time=0.0,
        )
        manager.add_action(
            time=200.0,
            action_type=TimelineActionType.IMAGING_TARGET,
            params={"latitude": 35.0, "longitude": 139.0},
            current_sim_time=0.0,
        )

        pending = manager.get_pending_actions()
        times = [a.time for a in pending]
        assert times == [100.0, 200.0, 300.0]

    def test_get_due_actions_returns_correct(self):
        """Should return all actions due at or before given time."""
        manager = TimelineManager()

        manager.add_action(
            time=100.0,
            action_type=TimelineActionType.CONTROL_MODE,
            params={},
            current_sim_time=0.0,
        )
        manager.add_action(
            time=200.0,
            action_type=TimelineActionType.CONTROL_MODE,
            params={},
            current_sim_time=0.0,
        )
        manager.add_action(
            time=300.0,
            action_type=TimelineActionType.CONTROL_MODE,
            params={},
            current_sim_time=0.0,
        )

        # At t=150, only first action is due
        due = manager.get_due_actions(150.0)
        assert len(due) == 1
        assert due[0].time == 100.0

        # At t=250, first two actions are due
        due = manager.get_due_actions(250.0)
        assert len(due) == 2

        # At t=300, all three are due (exact match counts)
        due = manager.get_due_actions(300.0)
        assert len(due) == 3

    def test_mark_executed_sets_flag(self):
        """Marking action executed should set flag."""
        manager = TimelineManager()
        action = manager.add_action(
            time=100.0,
            action_type=TimelineActionType.CONTROL_MODE,
            params={},
            current_sim_time=0.0,
        )

        assert not action.executed
        manager.mark_executed(action.id)
        assert action.executed

    def test_executed_actions_not_returned_as_due(self):
        """Executed actions should not be returned as due."""
        manager = TimelineManager()
        action = manager.add_action(
            time=100.0,
            action_type=TimelineActionType.CONTROL_MODE,
            params={},
            current_sim_time=0.0,
        )

        # Before execution
        due = manager.get_due_actions(150.0)
        assert len(due) == 1

        # After execution
        manager.mark_executed(action.id)
        due = manager.get_due_actions(150.0)
        assert len(due) == 0

    def test_remove_action_by_id(self):
        """Should be able to remove action by ID."""
        manager = TimelineManager()
        action = manager.add_action(
            time=100.0,
            action_type=TimelineActionType.CONTROL_MODE,
            params={},
            current_sim_time=0.0,
        )

        assert manager.action_count == 1
        result = manager.remove_action(action.id)
        assert result is True
        assert manager.action_count == 0

    def test_remove_nonexistent_action(self):
        """Removing nonexistent action returns False."""
        manager = TimelineManager()
        result = manager.remove_action("nonexistent-id")
        assert result is False

    def test_clear_removes_all(self):
        """Clear should remove all actions."""
        manager = TimelineManager()

        for i in range(5):
            manager.add_action(
                time=100.0 + i * 100,
                action_type=TimelineActionType.CONTROL_MODE,
                params={},
                current_sim_time=0.0,
            )

        assert manager.action_count == 5
        manager.clear()
        assert manager.action_count == 0

    def test_to_dict_list_excludes_executed(self):
        """to_dict_list should only return pending actions."""
        manager = TimelineManager()

        action1 = manager.add_action(
            time=100.0,
            action_type=TimelineActionType.CONTROL_MODE,
            params={},
            current_sim_time=0.0,
        )
        manager.add_action(
            time=200.0,
            action_type=TimelineActionType.CONTROL_MODE,
            params={},
            current_sim_time=0.0,
        )

        manager.mark_executed(action1.id)

        dict_list = manager.to_dict_list()
        assert len(dict_list) == 1
        assert dict_list[0]["time"] == 200.0

    def test_action_to_dict_format(self):
        """Action dict should have correct format."""
        manager = TimelineManager()
        action = manager.add_action(
            time=100.0,
            action_type=TimelineActionType.POINTING_MODE,
            params={"mode": "SUN"},
            current_sim_time=50.0,
        )

        d = action.to_dict()
        assert d["id"] == action.id
        assert d["time"] == 100.0
        assert d["actionType"] == "pointing_mode"
        assert d["params"] == {"mode": "SUN"}
        assert d["executed"] is False
        assert d["createdAt"] == 50.0

    def test_executed_history(self):
        """Should track executed action history."""
        manager = TimelineManager()
        action = manager.add_action(
            time=100.0,
            action_type=TimelineActionType.CONTROL_MODE,
            params={},
            current_sim_time=0.0,
        )

        manager.mark_executed(action.id)
        history = manager.get_executed_history()
        assert len(history) == 1
        assert history[0]["id"] == action.id
