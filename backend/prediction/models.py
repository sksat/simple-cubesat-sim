"""Data models for contact prediction and timeline actions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass
class ContactWindow:
    """Predicted contact window with ground station.

    Represents a pass over a ground station with visibility information.
    Times are in simulation seconds from epoch.
    """

    ground_station_name: str
    start_time: float  # AOS time (simulation seconds)
    end_time: float  # LOS time (simulation seconds)
    max_elevation: float  # Maximum elevation angle (degrees)
    max_elevation_time: float  # Time of max elevation (simulation seconds)
    aos_azimuth: float = 0.0  # Azimuth at AOS (degrees, optional)
    los_azimuth: float = 0.0  # Azimuth at LOS (degrees, optional)

    def duration(self) -> float:
        """Get contact duration in seconds."""
        return self.end_time - self.start_time

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "groundStationName": self.ground_station_name,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "maxElevation": self.max_elevation,
            "maxElevationTime": self.max_elevation_time,
            "aosAzimuth": self.aos_azimuth,
            "losAzimuth": self.los_azimuth,
            "duration": self.duration(),
        }


class TimelineActionType(str, Enum):
    """Types of schedulable actions."""

    CONTROL_MODE = "control_mode"
    POINTING_MODE = "pointing_mode"
    IMAGING_TARGET = "imaging_target"


@dataclass
class TimelineAction:
    """Scheduled action in the timeline.

    Actions are executed when simulation time reaches the scheduled time.

    Params by action type:
    - CONTROL_MODE: {"mode": "IDLE"|"DETUMBLING"|"POINTING"|"UNLOADING"}
    - POINTING_MODE: {"mode": "MANUAL"|"SUN"|"NADIR"|"GROUND_STATION"|"IMAGING_TARGET"}
    - IMAGING_TARGET: {"latitude": float, "longitude": float, "altitude": float (optional)}
    """

    id: str  # Unique identifier (UUID)
    time: float  # Execution time (simulation seconds)
    action_type: TimelineActionType
    params: dict[str, Any] = field(default_factory=dict)
    executed: bool = False
    created_at: float = 0.0  # When the action was created (sim time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "id": self.id,
            "time": self.time,
            "actionType": self.action_type.value,
            "params": self.params,
            "executed": self.executed,
            "createdAt": self.created_at,
        }
