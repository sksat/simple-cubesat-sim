"""Timeline manager for scheduled action execution."""

from bisect import insort
from typing import Any
from uuid import uuid4

from backend.prediction.models import TimelineAction, TimelineActionType


class TimelineManager:
    """Manages scheduled actions and their execution.

    Actions are stored sorted by execution time for efficient retrieval.
    The manager handles adding, removing, and executing actions at the
    appropriate simulation time.
    """

    def __init__(self) -> None:
        """Initialize empty timeline."""
        self._actions: list[TimelineAction] = []
        self._executed_history: list[TimelineAction] = []
        self._max_history: int = 100  # Keep last N executed actions

    def add_action(
        self,
        time: float,
        action_type: TimelineActionType | str,
        params: dict[str, Any],
        current_sim_time: float,
    ) -> TimelineAction:
        """Add a new scheduled action.

        Args:
            time: Execution time (simulation seconds)
            action_type: Type of action (enum or string)
            params: Action parameters
            current_sim_time: Current simulation time (for created_at)

        Returns:
            Created TimelineAction

        Raises:
            ValueError: If time is in the past
        """
        if time < current_sim_time:
            raise ValueError(
                f"Cannot schedule action in the past "
                f"(action time {time:.1f}s < current time {current_sim_time:.1f}s)"
            )

        # Convert string to enum if needed
        if isinstance(action_type, str):
            action_type = TimelineActionType(action_type)

        action = TimelineAction(
            id=str(uuid4()),
            time=time,
            action_type=action_type,
            params=params,
            executed=False,
            created_at=current_sim_time,
        )

        # Insert sorted by time
        insort(self._actions, action, key=lambda a: a.time)
        return action

    def remove_action(self, action_id: str) -> bool:
        """Remove an action by ID.

        Args:
            action_id: The action ID to remove

        Returns:
            True if action was found and removed, False otherwise
        """
        for i, action in enumerate(self._actions):
            if action.id == action_id:
                del self._actions[i]
                return True
        return False

    def get_pending_actions(self) -> list[TimelineAction]:
        """Get all pending (unexecuted) actions."""
        return [a for a in self._actions if not a.executed]

    def get_due_actions(self, sim_time: float) -> list[TimelineAction]:
        """Get actions that should execute at or before sim_time.

        Args:
            sim_time: Current simulation time

        Returns:
            List of due actions in execution order
        """
        due = []
        for action in self._actions:
            if action.executed:
                continue
            if action.time <= sim_time:
                due.append(action)
            else:
                break  # List is sorted, no more due actions
        return due

    def mark_executed(self, action_id: str) -> None:
        """Mark an action as executed.

        Args:
            action_id: The action ID to mark executed
        """
        for action in self._actions:
            if action.id == action_id:
                action.executed = True
                self._executed_history.append(action)
                # Trim history if needed
                if len(self._executed_history) > self._max_history:
                    self._executed_history = self._executed_history[-self._max_history :]
                break

    def clear(self) -> None:
        """Clear all actions (used on simulation reset)."""
        self._actions.clear()
        self._executed_history.clear()

    def to_dict_list(self) -> list[dict[str, Any]]:
        """Serialize all actions for telemetry.

        Returns only pending actions (not yet executed).
        """
        return [a.to_dict() for a in self._actions if not a.executed]

    def get_executed_history(self) -> list[dict[str, Any]]:
        """Get recently executed actions."""
        return [a.to_dict() for a in self._executed_history]

    @property
    def action_count(self) -> int:
        """Get total number of pending actions."""
        return len([a for a in self._actions if not a.executed])
