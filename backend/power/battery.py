"""Battery model for energy storage."""


class Battery:
    """Simple battery model with SOC tracking.

    Attributes:
        capacity_wh: Battery capacity in Watt-hours
        charge_efficiency: Charging efficiency (0-1)
        energy_wh: Current stored energy in Watt-hours
    """

    def __init__(
        self,
        capacity_wh: float,
        initial_soc: float = 1.0,
        charge_efficiency: float = 0.9,
    ):
        """Initialize battery.

        Args:
            capacity_wh: Battery capacity in Watt-hours
            initial_soc: Initial state of charge (0-1), default 1.0 (full)
            charge_efficiency: Charging efficiency, default 0.9 (90%)
        """
        self.capacity_wh = capacity_wh
        self.charge_efficiency = charge_efficiency
        self._energy_wh = capacity_wh * initial_soc

    @property
    def soc(self) -> float:
        """State of charge (0-1)."""
        return self._energy_wh / self.capacity_wh

    @property
    def energy_wh(self) -> float:
        """Current stored energy in Watt-hours."""
        return self._energy_wh

    def update(self, dt: float, power_in: float, power_out: float) -> None:
        """Update battery state.

        Args:
            dt: Time step in seconds
            power_in: Power input (charging) in Watts
            power_out: Power output (consumption) in Watts
        """
        # Convert power to energy (Wh)
        dt_hours = dt / 3600.0

        # Charging with efficiency loss
        energy_in = power_in * dt_hours * self.charge_efficiency

        # Discharging (no efficiency loss in simple model)
        energy_out = power_out * dt_hours

        # Update stored energy
        self._energy_wh += energy_in - energy_out

        # Clamp to valid range
        self._energy_wh = max(0.0, min(self.capacity_wh, self._energy_wh))

    def reset(self, soc: float = 1.0) -> None:
        """Reset battery to specified SOC.

        Args:
            soc: State of charge (0-1)
        """
        self._energy_wh = self.capacity_wh * max(0.0, min(1.0, soc))
