"""Spacecraft and simulation configuration.

All physical parameters are defined here and can be overridden via config file.
"""

from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Optional


@dataclass
class ReactionWheelConfig:
    """Reaction wheel parameters."""
    inertia: float = 3.33e-6  # Rotor inertia [kg*m^2]
    max_speed: float = 900.0  # Max speed [rad/s] (~8600 RPM)
    max_torque: float = 0.004  # Max torque [Nm] (4 mNm)
    base_power: float = 0.5  # Base power [W]


@dataclass
class MagnetorquerConfig:
    """Magnetorquer parameters."""
    max_dipole: float = 0.32  # Max dipole moment [Am^2]
    power_per_dipole: float = 10.0  # Power coefficient [W/(Am^2)^2]


@dataclass
class SpacecraftConfig:
    """Spacecraft physical parameters."""
    # Inertia tensor diagonal [kg*m^2] (6U CubeSat: 10x20x30 cm, ~10kg)
    inertia_xx: float = 0.05
    inertia_yy: float = 0.05
    inertia_zz: float = 0.02

    # Actuators
    reaction_wheel: ReactionWheelConfig = field(default_factory=ReactionWheelConfig)
    magnetorquer: MagnetorquerConfig = field(default_factory=MagnetorquerConfig)


@dataclass
class ControlConfig:
    """Controller parameters."""
    # B-dot detumbling
    bdot_gain: float = 1e6

    # Attitude controller (PD)
    attitude_kp: float = 0.01
    attitude_kd: float = 0.1

    # RW unloading
    # Gain for m = k * (B × H) / |B|^2
    # With H~0.01 Nms, B~30e-6 T, want m~0.1 Am²:
    # k * 3e-7 / 9e-10 = k * 333 ≈ 0.1 → k ≈ 3e-4
    unloading_gain: float = 300.0  # Reduced from 1e4 to avoid MTQ saturation


@dataclass
class OrbitConfig:
    """Orbit parameters (simplified circular orbit)."""
    altitude: float = 600.0  # Altitude [km]
    inclination: float = 97.8  # Inclination [deg] (SSO at 600km)
    period: float = 96.7 * 60  # Orbital period [s] (~96.7 min for 600km)
    initial_longitude: float = 0.0  # Initial longitude [deg]


@dataclass
class SimulationConfig:
    """Simulation parameters."""
    dt: float = 0.1  # Base time step [s]
    time_warp: float = 5.0  # Default time warp
    telemetry_rate: float = 10.0  # Telemetry rate [Hz]

    # Initial conditions
    initial_angular_velocity: list[float] = field(
        default_factory=lambda: [0.2, 0.3, -0.24]  # ~24 deg/s tumble
    )

    # Environment (simplified constant magnetic field in inertial frame [T])
    magnetic_field: list[float] = field(
        default_factory=lambda: [30e-6, 20e-6, 10e-6]
    )

    # Orbit parameters
    orbit: OrbitConfig = field(default_factory=OrbitConfig)


@dataclass
class Config:
    """Root configuration."""
    spacecraft: SpacecraftConfig = field(default_factory=SpacecraftConfig)
    control: ControlConfig = field(default_factory=ControlConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)


def load_config(path: Optional[Path] = None) -> Config:
    """Load configuration from JSON file or return defaults.

    Args:
        path: Path to config JSON file. If None, returns defaults.

    Returns:
        Configuration object
    """
    if path is None or not path.exists():
        return Config()

    with open(path) as f:
        data = json.load(f)

    # Build config from nested dict
    config = Config()

    if "spacecraft" in data:
        sc = data["spacecraft"]
        config.spacecraft.inertia_xx = sc.get("inertia_xx", config.spacecraft.inertia_xx)
        config.spacecraft.inertia_yy = sc.get("inertia_yy", config.spacecraft.inertia_yy)
        config.spacecraft.inertia_zz = sc.get("inertia_zz", config.spacecraft.inertia_zz)

        if "reaction_wheel" in sc:
            rw = sc["reaction_wheel"]
            config.spacecraft.reaction_wheel.inertia = rw.get(
                "inertia", config.spacecraft.reaction_wheel.inertia
            )
            config.spacecraft.reaction_wheel.max_speed = rw.get(
                "max_speed", config.spacecraft.reaction_wheel.max_speed
            )
            config.spacecraft.reaction_wheel.max_torque = rw.get(
                "max_torque", config.spacecraft.reaction_wheel.max_torque
            )

        if "magnetorquer" in sc:
            mtq = sc["magnetorquer"]
            config.spacecraft.magnetorquer.max_dipole = mtq.get(
                "max_dipole", config.spacecraft.magnetorquer.max_dipole
            )

    if "control" in data:
        ctrl = data["control"]
        config.control.bdot_gain = ctrl.get("bdot_gain", config.control.bdot_gain)
        config.control.attitude_kp = ctrl.get("attitude_kp", config.control.attitude_kp)
        config.control.attitude_kd = ctrl.get("attitude_kd", config.control.attitude_kd)
        config.control.unloading_gain = ctrl.get(
            "unloading_gain", config.control.unloading_gain
        )

    if "simulation" in data:
        sim = data["simulation"]
        config.simulation.dt = sim.get("dt", config.simulation.dt)
        config.simulation.time_warp = sim.get("time_warp", config.simulation.time_warp)
        config.simulation.initial_angular_velocity = sim.get(
            "initial_angular_velocity", config.simulation.initial_angular_velocity
        )
        config.simulation.magnetic_field = sim.get(
            "magnetic_field", config.simulation.magnetic_field
        )

    return config


# Default config file path
CONFIG_FILE = Path(__file__).parent.parent / "config.json"

# Global state
_config: Optional[Config] = None
_config_mtime: float = 0.0
_on_config_change_callbacks: list = []


def get_config() -> Config:
    """Get global configuration instance.

    Auto-loads from config.json if it exists.
    """
    global _config, _config_mtime

    if _config is None:
        _config, _config_mtime = _load_config_with_mtime()

    return _config


def set_config(config: Config) -> None:
    """Set global configuration instance."""
    global _config
    _config = config


def reload_config() -> Config:
    """Force reload configuration from file."""
    global _config, _config_mtime
    _config, _config_mtime = _load_config_with_mtime()
    return _config


def check_config_changed() -> bool:
    """Check if config file has changed since last load.

    Returns:
        True if config file was modified and config was reloaded
    """
    global _config_mtime

    if not CONFIG_FILE.exists():
        return False

    current_mtime = CONFIG_FILE.stat().st_mtime
    if current_mtime > _config_mtime:
        reload_config()
        # Notify callbacks
        for callback in _on_config_change_callbacks:
            callback()
        return True

    return False


def on_config_change(callback) -> None:
    """Register a callback to be called when config changes."""
    _on_config_change_callbacks.append(callback)


def _load_config_with_mtime() -> tuple[Config, float]:
    """Load config and return with file mtime."""
    if CONFIG_FILE.exists():
        mtime = CONFIG_FILE.stat().st_mtime
        config = load_config(CONFIG_FILE)
        return config, mtime
    else:
        return Config(), 0.0
