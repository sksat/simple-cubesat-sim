"""Reaction Wheel (RW) actuator model.

Reaction wheels store angular momentum and provide torque for fine attitude control.
They work by conservation of angular momentum: spinning up the wheel causes the
spacecraft to rotate in the opposite direction.

Dynamics:
    T_spacecraft = -T_wheel = -I_wheel * dω_wheel/dt
    H_wheel = I_wheel * ω_wheel

Motor Response Dynamics:
    Real motors cannot instantly produce commanded torque. A first-order lag
    models the electrical and mechanical response:
        T_actual(t+dt) = T_actual(t) + (T_cmd - T_actual) * (1 - exp(-dt/τ))

Typical 6U CubeSat reaction wheel specs:
    - Wheel inertia: ~3e-6 kg*m^2
    - Max speed: 6000-8000 RPM (~700 rad/s)
    - Max torque: 1-5 mNm
    - Max momentum: ~2-3 mNms
    - Torque time constant: 20-100 ms
"""

from typing import Optional

import numpy as np
from numpy.typing import NDArray


class ReactionWheel:
    """3-axis reaction wheel assembly model.

    Models three orthogonal reaction wheels as a single unit.
    Includes motor response dynamics via first-order lag.

    Attributes:
        inertia: Wheel moment of inertia (kg*m^2)
        max_speed: Maximum wheel speed (rad/s)
        max_torque: Maximum torque output (Nm)
        base_power: Base power consumption when spinning (W)
        torque_time_constant: Motor torque response time constant (s)
        torque_slew_rate: Optional torque rate limit (Nm/s)
    """

    def __init__(
        self,
        inertia: float = 3.33e-6,
        max_speed: float = 700.0,  # ~6700 RPM
        max_torque: float = 0.001,  # 1 mNm
        base_power: float = 0.5,
        torque_time_constant: float = 0.05,  # 50 ms
        torque_slew_rate: Optional[float] = None,
    ):
        """Initialize reaction wheel assembly.

        Args:
            inertia: Wheel moment of inertia per axis (kg*m^2)
            max_speed: Maximum wheel speed per axis (rad/s)
            max_torque: Maximum torque per axis (Nm)
            base_power: Base power consumption (W)
            torque_time_constant: First-order lag time constant (s).
                Set to 0 for instant response.
            torque_slew_rate: Optional torque rate limit (Nm/s).
                If None, no slew rate limit is applied.
        """
        self.inertia = inertia
        self.max_speed = max_speed
        self.max_torque = max_torque
        self.base_power = base_power
        self.torque_time_constant = torque_time_constant
        self.torque_slew_rate = torque_slew_rate

        self._speed = np.zeros(3)  # Wheel angular velocity (rad/s)
        self._commanded_torque = np.zeros(3)  # Current torque command (Nm)
        self._actual_torque = np.zeros(3)  # Actual motor torque output (Nm)

    def command_torque(self, torque_cmd: NDArray[np.float64]) -> None:
        """Command torque on wheels.

        Positive torque accelerates the wheel, causing negative torque on spacecraft.

        Args:
            torque_cmd: Desired wheel torque [Tx, Ty, Tz] (Nm)
        """
        # Apply saturation limits per axis
        self._commanded_torque = np.clip(torque_cmd, -self.max_torque, self.max_torque)

    def update(self, dt: float) -> None:
        """Update wheel state based on current torque command.

        Applies motor response dynamics (first-order lag) then integrates
        wheel dynamics: α = T_actual / I, ω += α * dt

        Args:
            dt: Time step (s)
        """
        # Apply first-order lag to torque response
        # T_actual += (T_cmd - T_actual) * (1 - exp(-dt/τ))
        if self.torque_time_constant > 0:
            alpha_filter = 1.0 - np.exp(-dt / self.torque_time_constant)
            new_actual_torque = (
                self._actual_torque
                + (self._commanded_torque - self._actual_torque) * alpha_filter
            )
        else:
            # No dynamics (instant response)
            new_actual_torque = self._commanded_torque.copy()

        # Optional: Apply slew rate limit
        if self.torque_slew_rate is not None:
            max_delta = self.torque_slew_rate * dt
            delta = new_actual_torque - self._actual_torque
            delta = np.clip(delta, -max_delta, max_delta)
            new_actual_torque = self._actual_torque + delta

        self._actual_torque = new_actual_torque

        # Compute angular acceleration using ACTUAL torque
        alpha = self._actual_torque / self.inertia

        # Integrate (Euler method)
        new_speed = self._speed + alpha * dt

        # Apply speed saturation
        self._speed = np.clip(new_speed, -self.max_speed, self.max_speed)

    def get_speed(self) -> NDArray[np.float64]:
        """Get current wheel speeds.

        Returns:
            Wheel angular velocity [ωx, ωy, ωz] (rad/s)
        """
        return self._speed.copy()

    def get_momentum(self) -> NDArray[np.float64]:
        """Get stored angular momentum.

        H = I * ω

        Returns:
            Angular momentum vector [Hx, Hy, Hz] (Nms)
        """
        return self.inertia * self._speed

    def get_commanded_torque(self) -> NDArray[np.float64]:
        """Get current commanded torque (after saturation).

        Returns:
            Commanded torque [Tx, Ty, Tz] (Nm)
        """
        return self._commanded_torque.copy()

    def get_actual_torque(self) -> NDArray[np.float64]:
        """Get actual motor torque output (after dynamics).

        This is the torque actually being produced by the motor,
        accounting for response dynamics (first-order lag).

        Returns:
            Actual torque [Tx, Ty, Tz] (Nm)
        """
        return self._actual_torque.copy()

    def get_torque_on_spacecraft(self) -> NDArray[np.float64]:
        """Get reaction torque applied to spacecraft.

        T_spacecraft = -T_wheel (Newton's third law)
        Uses actual torque (after motor dynamics), not commanded.

        Returns:
            Torque on spacecraft [Tx, Ty, Tz] (Nm)
        """
        return -self._actual_torque

    def get_power(self) -> float:
        """Get current power consumption.

        Simple model: P = P_base + k * |T|^2

        Returns:
            Power consumption (W)
        """
        torque_power = np.sum(self._commanded_torque**2) * 1000  # Scale factor
        return self.base_power + torque_power

    def get_state(self) -> dict:
        """Get current state.

        Returns:
            Dictionary containing speed, momentum, torque, and actualTorque
        """
        return {
            "speed": self._speed.copy(),
            "momentum": self.get_momentum(),
            "torque": self._commanded_torque.copy(),
            "actualTorque": self._actual_torque.copy(),
            "power": self.get_power(),
        }

    def reset(self) -> None:
        """Reset to zero speed and zero torque command."""
        self._speed = np.zeros(3)
        self._commanded_torque = np.zeros(3)
        self._actual_torque = np.zeros(3)
