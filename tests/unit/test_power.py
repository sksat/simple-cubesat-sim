"""Tests for power system module."""

import numpy as np
import pytest

from backend.power.solar_panel import SolarPanel
from backend.power.battery import Battery


class TestSolarPanel:
    """Tests for SolarPanel class."""

    def test_max_power_when_perpendicular(self):
        """Maximum power when sun is perpendicular to panel."""
        panel = SolarPanel(max_power=10.0, normal_body=[0, 0, 1])
        # Sun direction aligned with panel normal
        sun_direction_body = np.array([0, 0, 1])
        power = panel.calculate_power(sun_direction_body, is_illuminated=True)
        assert power == pytest.approx(10.0)

    def test_zero_power_when_parallel(self):
        """Zero power when sun is parallel to panel (90 deg)."""
        panel = SolarPanel(max_power=10.0, normal_body=[0, 0, 1])
        # Sun direction perpendicular to panel normal
        sun_direction_body = np.array([1, 0, 0])
        power = panel.calculate_power(sun_direction_body, is_illuminated=True)
        assert power == pytest.approx(0.0)

    def test_zero_power_in_eclipse(self):
        """Zero power when in eclipse."""
        panel = SolarPanel(max_power=10.0, normal_body=[0, 0, 1])
        sun_direction_body = np.array([0, 0, 1])
        power = panel.calculate_power(sun_direction_body, is_illuminated=False)
        assert power == pytest.approx(0.0)

    def test_cosine_falloff(self):
        """Power falls off with cosine of angle."""
        panel = SolarPanel(max_power=10.0, normal_body=[0, 0, 1])
        # 45 degree angle
        sun_direction_body = np.array([1, 0, 1])
        sun_direction_body = sun_direction_body / np.linalg.norm(sun_direction_body)
        power = panel.calculate_power(sun_direction_body, is_illuminated=True)
        expected = 10.0 * np.cos(np.pi / 4)
        assert power == pytest.approx(expected)

    def test_no_negative_power_from_backside(self):
        """No power when sun is behind panel."""
        panel = SolarPanel(max_power=10.0, normal_body=[0, 0, 1])
        # Sun direction opposite to panel normal
        sun_direction_body = np.array([0, 0, -1])
        power = panel.calculate_power(sun_direction_body, is_illuminated=True)
        assert power == pytest.approx(0.0)

    def test_double_sided_panel(self):
        """Double-sided panel generates power from both sides."""
        panel = SolarPanel(max_power=10.0, normal_body=[0, 0, 1], double_sided=True)

        # Sun from +Z
        power_front = panel.calculate_power(np.array([0, 0, 1]), is_illuminated=True)
        assert power_front == pytest.approx(10.0)

        # Sun from -Z
        power_back = panel.calculate_power(np.array([0, 0, -1]), is_illuminated=True)
        assert power_back == pytest.approx(10.0)


class TestBattery:
    """Tests for Battery class."""

    def test_initial_soc(self):
        """Battery starts at specified SOC."""
        battery = Battery(capacity_wh=10.0, initial_soc=0.5)
        assert battery.soc == pytest.approx(0.5)
        assert battery.energy_wh == pytest.approx(5.0)

    def test_default_soc_is_full(self):
        """Default SOC is 100%."""
        battery = Battery(capacity_wh=10.0)
        assert battery.soc == pytest.approx(1.0)

    def test_charge_increases_soc(self):
        """Charging increases SOC."""
        battery = Battery(capacity_wh=10.0, initial_soc=0.5)
        battery.update(dt=1.0, power_in=5.0, power_out=0.0)
        # With 90% efficiency, 5W * 1s * 0.9 = 4.5 Wh added
        # But we're using Wh, so 5W for 1s = 5/3600 Wh = 0.00139 Wh
        # Actually 5W * 1s = 5 J = 5/3600 Wh
        expected_energy = 5.0 + (5.0 * 1.0 / 3600.0 * 0.9)
        assert battery.energy_wh == pytest.approx(expected_energy, rel=1e-3)

    def test_discharge_decreases_soc(self):
        """Discharging decreases SOC."""
        battery = Battery(capacity_wh=10.0, initial_soc=0.5)
        initial_energy = battery.energy_wh
        battery.update(dt=1.0, power_in=0.0, power_out=5.0)
        # 5W * 1s = 5/3600 Wh consumed
        expected_energy = initial_energy - (5.0 * 1.0 / 3600.0)
        assert battery.energy_wh == pytest.approx(expected_energy, rel=1e-3)

    def test_soc_clamps_to_one(self):
        """SOC cannot exceed 1.0."""
        battery = Battery(capacity_wh=10.0, initial_soc=0.99)
        # Charge a lot
        battery.update(dt=3600.0, power_in=100.0, power_out=0.0)
        assert battery.soc == pytest.approx(1.0)

    def test_soc_clamps_to_zero(self):
        """SOC cannot go below 0.0."""
        battery = Battery(capacity_wh=10.0, initial_soc=0.01)
        # Discharge a lot
        battery.update(dt=3600.0, power_in=0.0, power_out=100.0)
        assert battery.soc == pytest.approx(0.0)

    def test_charge_efficiency(self):
        """Charging has efficiency loss."""
        battery = Battery(capacity_wh=10.0, initial_soc=0.0, charge_efficiency=0.9)
        # Charge with 10W for 1 hour
        battery.update(dt=3600.0, power_in=10.0, power_out=0.0)
        # Should store 10 * 0.9 = 9 Wh, so SOC = 0.9
        assert battery.soc == pytest.approx(0.9)

    def test_net_power_calculation(self):
        """Net power is correctly calculated."""
        battery = Battery(capacity_wh=10.0, initial_soc=0.5)
        battery.update(dt=1.0, power_in=10.0, power_out=5.0)
        # Charging: 10 * 0.9 = 9W effective
        # Net = 9 - 5 = 4W charging


class TestPowerSystem:
    """Tests for integrated PowerSystem class."""

    def test_power_generation_in_sunlight(self):
        """Power is generated when illuminated."""
        from backend.power.power_system import PowerSystem

        system = PowerSystem(panel_max_power=5.0, battery_capacity_wh=20.0, battery_initial_soc=0.5)

        # Sun aligned with panel normal (+Z)
        sun_dir = np.array([0, 0, 1])
        system.update(dt=1.0, sun_direction_body=sun_dir, is_illuminated=True)

        # Two panels × 5W = 10W generated
        assert system.power_generated == pytest.approx(10.0)

    def test_no_power_in_eclipse(self):
        """No power generated in eclipse."""
        from backend.power.power_system import PowerSystem

        system = PowerSystem(panel_max_power=5.0)

        sun_dir = np.array([0, 0, 1])
        system.update(dt=1.0, sun_direction_body=sun_dir, is_illuminated=False)

        assert system.power_generated == pytest.approx(0.0)

    def test_base_consumption(self):
        """Base consumption is always applied."""
        from backend.power.power_system import PowerSystem

        system = PowerSystem(base_consumption=2.0)

        sun_dir = np.array([0, 0, 1])
        system.update(dt=1.0, sun_direction_body=sun_dir, is_illuminated=False)

        assert system.power_consumed == pytest.approx(2.0)

    def test_get_state(self):
        """get_state returns expected fields."""
        from backend.power.power_system import PowerSystem

        system = PowerSystem()
        state = system.get_state()

        assert "soc" in state
        assert "batteryEnergy" in state
        assert "powerGenerated" in state
        assert "powerConsumed" in state
        assert "netPower" in state


class TestEclipseDetection:
    """Tests for eclipse detection."""

    def test_satellite_in_sunlight(self):
        """Satellite in front of Earth relative to Sun is illuminated."""
        from backend.power.eclipse import is_in_eclipse

        # Satellite at +X (between Earth and Sun)
        sat_pos_eci = np.array([7000.0, 0.0, 0.0])  # 7000 km from Earth center
        sun_dir_eci = np.array([1.0, 0.0, 0.0])  # Sun in +X direction

        assert not is_in_eclipse(sat_pos_eci, sun_dir_eci)

    def test_satellite_in_shadow(self):
        """Satellite behind Earth relative to Sun is in eclipse."""
        from backend.power.eclipse import is_in_eclipse

        # Satellite at -X (Earth between satellite and Sun)
        sat_pos_eci = np.array([-7000.0, 0.0, 0.0])  # Behind Earth
        sun_dir_eci = np.array([1.0, 0.0, 0.0])  # Sun in +X direction

        assert is_in_eclipse(sat_pos_eci, sun_dir_eci)

    def test_satellite_on_edge(self):
        """Satellite at the edge of shadow."""
        from backend.power.eclipse import is_in_eclipse

        # Satellite at 90 degrees from sun direction (on the edge)
        sat_pos_eci = np.array([0.0, 7000.0, 0.0])
        sun_dir_eci = np.array([1.0, 0.0, 0.0])

        # At exact 90 degrees, should be illuminated (just barely)
        assert not is_in_eclipse(sat_pos_eci, sun_dir_eci)
