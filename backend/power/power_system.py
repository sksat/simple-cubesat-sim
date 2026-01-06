"""Power system integrating solar panels and battery."""

import numpy as np
from numpy.typing import NDArray

from backend.power.solar_panel import SolarPanel
from backend.power.battery import Battery


class PowerSystem:
    """Integrated power system with solar panels and battery.

    The 6U CubeSat has:
    - Two solar panels deployed from +Z end
    - Panels have solar cells on both sides (double-sided)
    - Panel normal is in Z direction (body frame)

    Attributes:
        solar_panels: List of solar panels
        battery: Battery for energy storage
        base_consumption: Base power consumption (W)
    """

    def __init__(
        self,
        panel_max_power: float = 5.0,
        battery_capacity_wh: float = 20.0,
        battery_initial_soc: float = 0.8,
        base_consumption: float = 2.0,
    ):
        """Initialize power system.

        Args:
            panel_max_power: Max power per panel (W), default 5W
            battery_capacity_wh: Battery capacity (Wh), default 20Wh
            battery_initial_soc: Initial battery SOC (0-1), default 0.8
            base_consumption: Base power consumption (W), default 2W
        """
        # Two double-sided solar panels with normal in +Z direction
        # (panels are parallel to XY plane, cells on both Z faces)
        self.solar_panels = [
            SolarPanel(max_power=panel_max_power, normal_body=[0, 0, 1], double_sided=True),
            SolarPanel(max_power=panel_max_power, normal_body=[0, 0, 1], double_sided=True),
        ]

        self.battery = Battery(
            capacity_wh=battery_capacity_wh,
            initial_soc=battery_initial_soc,
        )

        self.base_consumption = base_consumption
        self._last_power_generated = 0.0
        self._last_power_consumed = 0.0

    def update(
        self,
        dt: float,
        sun_direction_body: NDArray[np.float64],
        is_illuminated: bool,
        additional_consumption: float = 0.0,
    ) -> None:
        """Update power system state.

        Args:
            dt: Time step (seconds)
            sun_direction_body: Unit vector toward sun in body frame
            is_illuminated: True if satellite is not in eclipse
            additional_consumption: Extra power consumption beyond base (W)
        """
        # Calculate total solar power generation
        total_generation = sum(
            panel.calculate_power(sun_direction_body, is_illuminated)
            for panel in self.solar_panels
        )

        # Calculate total consumption
        total_consumption = self.base_consumption + additional_consumption

        # Update battery
        self.battery.update(
            dt=dt,
            power_in=total_generation,
            power_out=total_consumption,
        )

        # Store for telemetry
        self._last_power_generated = total_generation
        self._last_power_consumed = total_consumption

    @property
    def soc(self) -> float:
        """Battery state of charge (0-1)."""
        return self.battery.soc

    @property
    def power_generated(self) -> float:
        """Last calculated power generation (W)."""
        return self._last_power_generated

    @property
    def power_consumed(self) -> float:
        """Last calculated power consumption (W)."""
        return self._last_power_consumed

    @property
    def net_power(self) -> float:
        """Net power (positive = charging)."""
        return self._last_power_generated * self.battery.charge_efficiency - self._last_power_consumed

    def reset(self, initial_soc: float = 0.8) -> None:
        """Reset power system.

        Args:
            initial_soc: Initial battery SOC (0-1)
        """
        self.battery.reset(initial_soc)
        self._last_power_generated = 0.0
        self._last_power_consumed = 0.0

    def get_state(self) -> dict:
        """Get power system state for telemetry.

        Returns:
            Dictionary with power system state
        """
        return {
            "soc": self.soc,
            "batteryEnergy": self.battery.energy_wh,
            "batteryCapacity": self.battery.capacity_wh,
            "powerGenerated": self._last_power_generated,
            "powerConsumed": self._last_power_consumed,
            "netPower": self.net_power,
        }
