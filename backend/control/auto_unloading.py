"""Automatic RW momentum unloading controller.

Automatically monitors RW speeds and performs unloading when thresholds
are exceeded, without requiring manual mode switching.
"""

import numpy as np
from numpy.typing import NDArray
from enum import Enum


class UnloadingState(Enum):
    """Unloading state for each RW axis."""

    OFF = 0  # No unloading needed
    ON_INCREASE = 1  # Unloading to increase speed (speed < lower_threshold)
    ON_DECREASE = 2  # Unloading to decrease speed (speed > upper_threshold)


class AutoUnloadingController:
    """Automatic RW unloading controller with threshold-based state machine.

    Monitors each RW axis independently and triggers unloading when speed
    exceeds thresholds. Works continuously during POINTING mode.

    Attributes:
        upper_threshold: Upper speed threshold for each axis (rad/s)
        lower_threshold: Lower speed threshold for each axis (rad/s)
        target_speed: Target speed for unloading (rad/s)
        control_gain: P-gain for speed error (Nm/(rad/s))
        min_torque: Minimum torque output (Nm)
    """

    def __init__(
        self,
        upper_threshold: NDArray[np.float64] | None = None,
        lower_threshold: NDArray[np.float64] | None = None,
        target_speed: NDArray[np.float64] | None = None,
        control_gain: float = -1e-4,  # Negative gain to oppose speed
        min_torque: float = 1e-6,
    ):
        """Initialize automatic unloading controller.

        Args:
            upper_threshold: Upper speed threshold per axis (rad/s)
                            If None, uses ±0.8 * max_speed
            lower_threshold: Lower speed threshold per axis (rad/s)
                            If None, uses ±0.8 * max_speed
            target_speed: Target speed for unloading (rad/s)
                         If None, uses 0.0 for all axes
            control_gain: Proportional gain (Nm/(rad/s)), should be negative
            min_torque: Minimum torque magnitude (Nm)
        """
        # Default thresholds: ±720 rad/s (±6880 RPM) for 900 rad/s max
        if upper_threshold is None:
            upper_threshold = np.array([720.0, 720.0, 720.0])
        if lower_threshold is None:
            lower_threshold = np.array([-720.0, -720.0, -720.0])
        if target_speed is None:
            target_speed = np.array([0.0, 0.0, 0.0])

        self.upper_threshold = upper_threshold.copy()
        self.lower_threshold = lower_threshold.copy()
        self.target_speed = target_speed.copy()
        self.control_gain = control_gain
        self.min_torque = min_torque

        # State for each axis
        self.state = np.array([UnloadingState.OFF] * 3)
        self.num_unloading = 0

    def update_state(self, rw_speed: NDArray[np.float64]) -> None:
        """Update unloading state based on current RW speeds.

        Args:
            rw_speed: Current RW angular velocity [ωx, ωy, ωz] (rad/s)
        """
        self.num_unloading = 0

        for i in range(3):
            if self.state[i] == UnloadingState.OFF:
                # Check if unloading needed
                if rw_speed[i] > self.upper_threshold[i]:
                    self.state[i] = UnloadingState.ON_DECREASE
                elif rw_speed[i] < self.lower_threshold[i]:
                    self.state[i] = UnloadingState.ON_INCREASE

            elif self.state[i] == UnloadingState.ON_INCREASE:
                # Check if target reached
                if rw_speed[i] >= self.target_speed[i]:
                    self.state[i] = UnloadingState.OFF

            elif self.state[i] == UnloadingState.ON_DECREASE:
                # Check if target reached
                if rw_speed[i] <= self.target_speed[i]:
                    self.state[i] = UnloadingState.OFF

            # Count active unloading axes
            if self.state[i] != UnloadingState.OFF:
                self.num_unloading += 1

    def compute_torque(self, rw_speed: NDArray[np.float64]) -> NDArray[np.float64]:
        """Compute unloading torque based on current state.

        Torque = control_gain * (speed - target_speed) for each axis needing unloading.

        Args:
            rw_speed: Current RW angular velocity [ωx, ωy, ωz] (rad/s)

        Returns:
            Unloading torque command [Tx, Ty, Tz] (Nm)
        """
        torque = np.zeros(3)

        for i in range(3):
            if self.state[i] != UnloadingState.OFF:
                # Compute torque from speed error
                speed_error = rw_speed[i] - self.target_speed[i]
                axis_torque = self.control_gain * speed_error

                # Apply minimum torque threshold
                if abs(axis_torque) < self.min_torque:
                    axis_torque = np.sign(axis_torque) * self.min_torque

                torque[i] = axis_torque

        return torque

    def is_active(self) -> bool:
        """Check if any axis is currently unloading.

        Returns:
            True if at least one axis is unloading
        """
        return self.num_unloading > 0

    def get_state_str(self, axis: int) -> str:
        """Get human-readable state string for an axis.

        Args:
            axis: Axis index (0=X, 1=Y, 2=Z)

        Returns:
            State string
        """
        state_map = {
            UnloadingState.OFF: "OFF",
            UnloadingState.ON_INCREASE: "INCREASE",
            UnloadingState.ON_DECREASE: "DECREASE",
        }
        return state_map.get(self.state[axis], "UNKNOWN")

    def reset(self) -> None:
        """Reset all axes to OFF state."""
        self.state = np.array([UnloadingState.OFF] * 3)
        self.num_unloading = 0
