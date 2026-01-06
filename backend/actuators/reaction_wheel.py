"""Reaction Wheel (RW) actuator model.

Reaction wheels store angular momentum and provide torque for fine attitude control.
They work by conservation of angular momentum: spinning up the wheel causes the
spacecraft to rotate in the opposite direction.

Dynamics:
    T_spacecraft = -T_wheel = -I_wheel * dω_wheel/dt
    H_wheel = I_wheel * ω_wheel

Typical 6U CubeSat reaction wheel specs:
    - Wheel inertia: ~3e-6 kg*m^2
    - Max speed: 8000-10000 RPM (~900 rad/s)
    - Max torque: 1-5 mNm
    - Max momentum: ~3 mNms
"""

import numpy as np
from numpy.typing import NDArray


class ReactionWheel:
    """3-axis reaction wheel assembly model.

    Models three orthogonal reaction wheels as a single unit.

    Attributes:
        inertia: Wheel moment of inertia (kg*m^2)
        max_speed: Maximum wheel speed (rad/s)
        max_torque: Maximum torque output (Nm)
        base_power: Base power consumption when spinning (W)
    """

    def __init__(
        self,
        inertia: float = 3.33e-6,
        max_speed: float = 900.0,  # ~8600 RPM
        max_torque: float = 0.004,  # 4 mNm
        base_power: float = 0.5,
    ):
        """Initialize reaction wheel assembly.

        Args:
            inertia: Wheel moment of inertia per axis (kg*m^2)
            max_speed: Maximum wheel speed per axis (rad/s)
            max_torque: Maximum torque per axis (Nm)
            base_power: Base power consumption (W)
        """
        self.inertia = inertia
        self.max_speed = max_speed
        self.max_torque = max_torque
        self.base_power = base_power

        self._speed = np.zeros(3)  # Wheel angular velocity (rad/s)
        self._commanded_torque = np.zeros(3)  # Current torque command (Nm)

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

        Integrates wheel dynamics: α = T / I, ω += α * dt

        Args:
            dt: Time step (s)
        """
        # Compute angular acceleration
        alpha = self._commanded_torque / self.inertia

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

    def get_torque_on_spacecraft(self) -> NDArray[np.float64]:
        """Get reaction torque applied to spacecraft.

        T_spacecraft = -T_wheel (Newton's third law)

        Returns:
            Torque on spacecraft [Tx, Ty, Tz] (Nm)
        """
        return -self._commanded_torque

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
            Dictionary containing speed, momentum, and torque
        """
        return {
            "speed": self._speed.copy(),
            "momentum": self.get_momentum(),
            "torque": self._commanded_torque.copy(),
            "power": self.get_power(),
        }

    def reset(self) -> None:
        """Reset to zero speed and zero torque command."""
        self._speed = np.zeros(3)
        self._commanded_torque = np.zeros(3)
