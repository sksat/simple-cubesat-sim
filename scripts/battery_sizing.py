#!/usr/bin/env python3
"""Battery sizing validation for 600km SSO.

Simulates multiple orbits to verify battery can sustain operations
through eclipse periods.
"""

import argparse
import numpy as np
from dataclasses import dataclass


@dataclass
class OrbitParams:
    """Orbital parameters for analysis."""
    altitude_km: float = 600.0
    inclination_deg: float = 97.8  # SSO for 600km
    period_min: float = 96.7  # Approximate period for 600km
    eclipse_fraction: float = 0.36  # ~35% of orbit in eclipse for SSO


@dataclass
class PowerParams:
    """Power system parameters."""
    panel_max_power: float = 5.0  # W per panel
    num_panels: int = 2
    panel_efficiency: float = 1.0  # Average cos(theta) factor
    battery_capacity_wh: float = 20.0
    battery_initial_soc: float = 0.8
    charge_efficiency: float = 0.9
    base_consumption: float = 2.0  # W
    mtq_power: float = 0.5  # W average
    rw_power: float = 0.5  # W average


def simulate_power_budget(
    orbit: OrbitParams,
    power: PowerParams,
    num_orbits: int = 10,
    time_step: float = 10.0,  # seconds
    verbose: bool = False,
) -> dict:
    """Simulate power budget over multiple orbits.

    Args:
        orbit: Orbital parameters
        power: Power system parameters
        num_orbits: Number of orbits to simulate
        time_step: Simulation time step (seconds)
        verbose: Print detailed output

    Returns:
        Dictionary with simulation results
    """
    period_s = orbit.period_min * 60.0
    eclipse_duration = period_s * orbit.eclipse_fraction
    sunlit_duration = period_s - eclipse_duration

    # Initialize battery
    energy_wh = power.battery_capacity_wh * power.battery_initial_soc

    # Track statistics
    min_soc = 1.0
    max_soc = 0.0
    soc_history = []
    time_history = []

    total_time = num_orbits * period_s
    current_time = 0.0

    while current_time < total_time:
        # Determine if in eclipse (simplified model)
        orbit_phase = (current_time % period_s) / period_s

        # Eclipse in middle of orbit (simplified)
        eclipse_start = 0.5 - orbit.eclipse_fraction / 2
        eclipse_end = 0.5 + orbit.eclipse_fraction / 2
        in_eclipse = eclipse_start <= orbit_phase <= eclipse_end

        # Calculate power
        if in_eclipse:
            generation = 0.0
        else:
            generation = power.panel_max_power * power.num_panels * power.panel_efficiency

        consumption = power.base_consumption + power.mtq_power + power.rw_power

        # Update battery
        dt_hours = time_step / 3600.0
        energy_in = generation * dt_hours * power.charge_efficiency
        energy_out = consumption * dt_hours
        energy_wh += energy_in - energy_out
        energy_wh = max(0.0, min(power.battery_capacity_wh, energy_wh))

        # Track SOC
        soc = energy_wh / power.battery_capacity_wh
        min_soc = min(min_soc, soc)
        max_soc = max(max_soc, soc)

        if len(soc_history) == 0 or current_time - time_history[-1] >= 60.0:
            soc_history.append(soc)
            time_history.append(current_time / 3600.0)  # hours

        current_time += time_step

    # Calculate energy balance per orbit
    sunlit_energy_in = (
        power.panel_max_power * power.num_panels * power.panel_efficiency
        * (sunlit_duration / 3600.0) * power.charge_efficiency
    )
    total_energy_out = (
        (power.base_consumption + power.mtq_power + power.rw_power)
        * (period_s / 3600.0)
    )

    net_energy_per_orbit = sunlit_energy_in - total_energy_out

    return {
        "min_soc": min_soc,
        "max_soc": max_soc,
        "final_soc": soc,
        "soc_history": soc_history,
        "time_history": time_history,
        "sunlit_energy_wh": sunlit_energy_in,
        "consumed_energy_wh": total_energy_out,
        "net_energy_per_orbit_wh": net_energy_per_orbit,
        "sustainable": net_energy_per_orbit >= 0,
        "eclipse_duration_min": eclipse_duration / 60.0,
        "sunlit_duration_min": sunlit_duration / 60.0,
    }


def print_report(results: dict, orbit: OrbitParams, power: PowerParams) -> None:
    """Print analysis report."""
    print("=" * 60)
    print("Battery Sizing Analysis Report")
    print("=" * 60)
    print()
    print("Orbit Parameters:")
    print(f"  Altitude: {orbit.altitude_km} km")
    print(f"  Inclination: {orbit.inclination_deg}° (SSO)")
    print(f"  Period: {orbit.period_min:.1f} min")
    print(f"  Eclipse fraction: {orbit.eclipse_fraction * 100:.1f}%")
    print(f"  Eclipse duration: {results['eclipse_duration_min']:.1f} min")
    print(f"  Sunlit duration: {results['sunlit_duration_min']:.1f} min")
    print()
    print("Power System Parameters:")
    print(f"  Solar panels: {power.num_panels} x {power.panel_max_power}W")
    print(f"  Max generation: {power.num_panels * power.panel_max_power}W")
    print(f"  Battery capacity: {power.battery_capacity_wh} Wh")
    print(f"  Charge efficiency: {power.charge_efficiency * 100}%")
    print(f"  Base consumption: {power.base_consumption}W")
    print(f"  MTQ power: {power.mtq_power}W")
    print(f"  RW power: {power.rw_power}W")
    print(f"  Total consumption: {power.base_consumption + power.mtq_power + power.rw_power}W")
    print()
    print("Energy Balance (per orbit):")
    print(f"  Energy generated: {results['sunlit_energy_wh']:.2f} Wh")
    print(f"  Energy consumed: {results['consumed_energy_wh']:.2f} Wh")
    print(f"  Net energy: {results['net_energy_per_orbit_wh']:.2f} Wh")
    print()
    print("Simulation Results (10 orbits):")
    print(f"  Minimum SOC: {results['min_soc'] * 100:.1f}%")
    print(f"  Maximum SOC: {results['max_soc'] * 100:.1f}%")
    print(f"  Final SOC: {results['final_soc'] * 100:.1f}%")
    print()

    if results['sustainable']:
        print("✅ RESULT: Power budget is SUSTAINABLE")
    else:
        print("❌ RESULT: Power budget is NOT SUSTAINABLE")
        deficit_per_orbit = -results['net_energy_per_orbit_wh']
        orbits_until_empty = power.battery_capacity_wh * power.battery_initial_soc / deficit_per_orbit
        print(f"   Battery will deplete in ~{orbits_until_empty:.1f} orbits")

    print()
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Battery sizing validation for 600km SSO")
    parser.add_argument("--altitude", type=float, default=600.0, help="Orbit altitude (km)")
    parser.add_argument("--battery", type=float, default=20.0, help="Battery capacity (Wh)")
    parser.add_argument("--panel-power", type=float, default=5.0, help="Panel max power (W)")
    parser.add_argument("--num-panels", type=int, default=2, help="Number of panels")
    parser.add_argument("--base-power", type=float, default=2.0, help="Base consumption (W)")
    parser.add_argument("--orbits", type=int, default=10, help="Number of orbits to simulate")
    parser.add_argument("--plot", action="store_true", help="Plot SOC history")
    args = parser.parse_args()

    orbit = OrbitParams(altitude_km=args.altitude)
    power = PowerParams(
        panel_max_power=args.panel_power,
        num_panels=args.num_panels,
        battery_capacity_wh=args.battery,
        base_consumption=args.base_power,
    )

    results = simulate_power_budget(orbit, power, num_orbits=args.orbits)
    print_report(results, orbit, power)

    if args.plot:
        try:
            import matplotlib.pyplot as plt

            plt.figure(figsize=(12, 6))
            plt.plot(results['time_history'], [s * 100 for s in results['soc_history']])
            plt.xlabel('Time (hours)')
            plt.ylabel('Battery SOC (%)')
            plt.title('Battery State of Charge over Time')
            plt.grid(True)
            plt.ylim(0, 100)
            plt.axhline(y=20, color='r', linestyle='--', label='Critical SOC (20%)')
            plt.legend()
            plt.savefig('battery_soc.png', dpi=150)
            print(f"\nPlot saved to battery_soc.png")
        except ImportError:
            print("\nNote: matplotlib not installed, skipping plot")


if __name__ == "__main__":
    main()
