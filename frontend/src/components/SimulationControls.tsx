/**
 * Simulation control panel component.
 * Includes mode selection and axis configuration for 3Axis mode.
 */

import { useState } from 'react';
import type {
  ControlMode,
  PointingMode,
  Telemetry,
  SimulationState,
  ImagingTarget,
  TargetDirection,
  BodyAxis,
  PointingConfig,
} from '../types/telemetry';
import { TLESettings } from './TLESettings';
import { telemetryWS } from '../services/websocket';

interface ControlModeOptions {
  pointingMode?: PointingMode;
  targetQuaternion?: [number, number, number, number];
  imagingTarget?: ImagingTarget;
}

interface TelemetryState {
  telemetry: Telemetry | null;
  isConnected: boolean;
  simulationState: SimulationState;
  start: () => void;
  stop: () => void;
  pause: () => void;
  reset: () => void;
  setControlMode: (mode: ControlMode, options?: ControlModeOptions) => void;
  setTimeWarp: (timeWarp: number) => void;
}

interface SimulationControlsProps {
  telemetryState: TelemetryState;
}

// Body axis options
const BODY_AXES: { label: string; value: BodyAxis }[] = [
  { label: '+X', value: [1, 0, 0] },
  { label: '-X', value: [-1, 0, 0] },
  { label: '+Y', value: [0, 1, 0] },
  { label: '-Y', value: [0, -1, 0] },
  { label: '+Z', value: [0, 0, 1] },
  { label: '-Z', value: [0, 0, -1] },
];

// Target direction options
const TARGET_DIRECTIONS: { label: string; value: TargetDirection }[] = [
  { label: 'Sun', value: 'SUN' },
  { label: 'Nadir', value: 'EARTH_CENTER' },
  { label: 'Ground Station', value: 'GROUND_STATION' },
  { label: 'Imaging Target', value: 'IMAGING_TARGET' },
  { label: 'Velocity', value: 'VELOCITY' },
  { label: 'Orbit Normal', value: 'ORBIT_NORMAL' },
];

// Preset configurations
const PRESETS: { name: string; config: PointingConfig }[] = [
  {
    name: 'SUN',
    config: {
      mainTarget: 'SUN',
      mainBodyAxis: [0, 0, 1],  // +Z
      subTarget: 'EARTH_CENTER',
      subBodyAxis: [1, 0, 0],  // +X
    },
  },
  {
    name: 'NADIR',
    config: {
      mainTarget: 'EARTH_CENTER',
      mainBodyAxis: [0, 0, -1],  // -Z
      subTarget: 'VELOCITY',
      subBodyAxis: [1, 0, 0],  // +X
    },
  },
  {
    name: 'GS',
    config: {
      mainTarget: 'GROUND_STATION',
      mainBodyAxis: [0, 0, -1],  // -Z
      subTarget: 'VELOCITY',
      subBodyAxis: [1, 0, 0],  // +X
    },
  },
  {
    name: 'IMG',
    config: {
      mainTarget: 'IMAGING_TARGET',
      mainBodyAxis: [0, 0, -1],  // -Z
      subTarget: 'VELOCITY',
      subBodyAxis: [1, 0, 0],  // +X
    },
  },
];

function bodyAxisToString(axis: BodyAxis): string {
  const match = BODY_AXES.find(a =>
    a.value[0] === axis[0] && a.value[1] === axis[1] && a.value[2] === axis[2]
  );
  return match?.label || 'Unknown';
}

export function SimulationControls({ telemetryState }: SimulationControlsProps) {
  const {
    telemetry,
    isConnected,
    simulationState,
    start,
    stop,
    pause,
    reset,
    setControlMode,
    setTimeWarp,
  } = telemetryState;

  // Axis configuration state
  const [mainTarget, setMainTarget] = useState<TargetDirection>('SUN');
  const [mainBodyAxis, setMainBodyAxis] = useState<BodyAxis>([0, 0, 1]);
  const [subTarget, setSubTarget] = useState<TargetDirection>('EARTH_CENTER');
  const [subBodyAxis, setSubBodyAxis] = useState<BodyAxis>([1, 0, 0]);

  const handleModeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const mode = e.target.value as ControlMode;
    // Keep current pointing mode when switching to 3Axis
    if (mode === '3Axis' && telemetry?.control.pointingMode) {
      setControlMode(mode, { pointingMode: telemetry.control.pointingMode });
    } else {
      setControlMode(mode);
    }
  };

  const handleTimeWarpChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setTimeWarp(parseFloat(e.target.value));
  };

  const handlePreset = (preset: PointingConfig) => {
    setMainTarget(preset.mainTarget);
    setMainBodyAxis(preset.mainBodyAxis);
    setSubTarget(preset.subTarget);
    setSubBodyAxis(preset.subBodyAxis);
    // Apply immediately
    telemetryWS.setPointingConfig(preset);
  };

  const handleApplyConfig = () => {
    const config: PointingConfig = {
      mainTarget,
      mainBodyAxis,
      subTarget,
      subBodyAxis,
    };
    telemetryWS.setPointingConfig(config);
  };

  const statusClass = isConnected ? 'connected' : 'disconnected';
  const is3AxisMode = telemetry?.control.mode === '3Axis';

  return (
    <div className="simulation-controls">
      <div className="connection-status">
        <span className={`status-indicator ${statusClass}`} />
        {isConnected ? 'Connected' : 'Disconnected'}
      </div>

      <div className="control-buttons">
        <button onClick={start} disabled={!isConnected || simulationState === 'RUNNING'}>
          Start
        </button>
        <button onClick={pause} disabled={!isConnected || simulationState !== 'RUNNING'}>
          Pause
        </button>
        <button onClick={stop} disabled={!isConnected || simulationState === 'STOPPED'}>
          Stop
        </button>
        <button onClick={reset} disabled={!isConnected}>
          Reset
        </button>
      </div>

      <div className="control-mode">
        <label>Control Mode:</label>
        <select
          value={telemetry?.control.mode || 'Idle'}
          onChange={handleModeChange}
          disabled={!isConnected}
        >
          <option value="Idle">Idle</option>
          <option value="Detumbling">Detumbling</option>
          <option value="3Axis">3Axis</option>
        </select>
      </div>

      {/* Axis Configuration - shown when 3Axis mode is selected */}
      {is3AxisMode && (
        <div className="axis-configuration">
          <div className="preset-buttons">
            {PRESETS.map(preset => (
              <button
                key={preset.name}
                onClick={() => handlePreset(preset.config)}
                disabled={!isConnected}
                className="preset-btn"
              >
                {preset.name}
              </button>
            ))}
          </div>

          <div className="axis-config-section">
            <h4>Main Axis</h4>
            <div className="config-row">
              <label>Target:</label>
              <select
                value={mainTarget}
                onChange={e => setMainTarget(e.target.value as TargetDirection)}
                disabled={!isConnected}
              >
                {TARGET_DIRECTIONS.map(dir => (
                  <option key={dir.value} value={dir.value}>
                    {dir.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="config-row">
              <label>Body:</label>
              <select
                value={bodyAxisToString(mainBodyAxis)}
                onChange={e => {
                  const selected = BODY_AXES.find(a => a.label === e.target.value);
                  if (selected) setMainBodyAxis(selected.value);
                }}
                disabled={!isConnected}
              >
                {BODY_AXES.map(axis => (
                  <option key={axis.label} value={axis.label}>
                    {axis.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="axis-config-section">
            <h4>Sub Axis</h4>
            <div className="config-row">
              <label>Target:</label>
              <select
                value={subTarget}
                onChange={e => setSubTarget(e.target.value as TargetDirection)}
                disabled={!isConnected}
              >
                {TARGET_DIRECTIONS.map(dir => (
                  <option key={dir.value} value={dir.value}>
                    {dir.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="config-row">
              <label>Body:</label>
              <select
                value={bodyAxisToString(subBodyAxis)}
                onChange={e => {
                  const selected = BODY_AXES.find(a => a.label === e.target.value);
                  if (selected) setSubBodyAxis(selected.value);
                }}
                disabled={!isConnected}
              >
                {BODY_AXES.map(axis => (
                  <option key={axis.label} value={axis.label}>
                    {axis.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            className="apply-btn"
            onClick={handleApplyConfig}
            disabled={!isConnected}
          >
            Apply
          </button>
        </div>
      )}

      <div className="time-warp">
        <label>Time Warp:</label>
        <select
          value={telemetry?.timeWarp || 1}
          onChange={handleTimeWarpChange}
          disabled={!isConnected}
        >
          <option value="0.1">0.1x</option>
          <option value="0.5">0.5x</option>
          <option value="1">1x</option>
          <option value="2">2x</option>
          <option value="5">5x</option>
          <option value="10">10x</option>
          <option value="50">50x</option>
          <option value="100">100x</option>
          <option value="1000">1000x</option>
        </select>
      </div>

      <TLESettings isConnected={isConnected} />

      {telemetry && (
        <div className="telemetry-display">
          <h3>Telemetry</h3>
          <div className="telemetry-section">
            <h4>Time</h4>
            <p>Elapsed: {telemetry.timestamp.toFixed(1)}s</p>
            <p>UTC: {new Date(telemetry.absoluteTime).toISOString().replace('T', ' ').slice(0, 19)}</p>
            <p>State: {telemetry.state}</p>
          </div>

          <div className="telemetry-section">
            <h4>Attitude</h4>
            <p>Euler (deg): [{telemetry.attitude.eulerAngles.map(a => a.toFixed(1)).join(', ')}]</p>
            <p>Angular Velocity (rad/s): [{telemetry.attitude.angularVelocity.map(v => v.toFixed(4)).join(', ')}]</p>
          </div>

          <div className="telemetry-section">
            <h4>Control</h4>
            <p>Mode: {telemetry.control.mode}</p>
            {telemetry.control.mode === '3Axis' && (
              <>
                <p>Unloading: {telemetry.control.isUnloading ? '🔄 Active' : 'Off'}</p>
              </>
            )}
            <p>Attitude Error: {telemetry.control.error.attitude.toFixed(2)}deg</p>
            <p>Rate: {(telemetry.control.error.rate * 180 / Math.PI).toFixed(2)}deg/s</p>
            <p>GS Visible: {telemetry.control.groundStationVisible ? '📡 Yes' : '❌ No'}</p>
          </div>

          <div className="telemetry-section">
            <h4>Reaction Wheels</h4>
            <p>Speed (RPM): [{telemetry.actuators.reactionWheels.speed.map(s => (s * 60 / (2 * Math.PI)).toFixed(0)).join(', ')}]</p>
            <p>Momentum (mNms): [{telemetry.actuators.reactionWheels.momentum.map(m => (m * 1000).toFixed(2)).join(', ')}]</p>
          </div>

          <div className="telemetry-section">
            <h4>Magnetorquers</h4>
            <p>Dipole (Am2): [{telemetry.actuators.magnetorquers.dipoleMoment.map(d => d.toFixed(3)).join(', ')}]</p>
            <p>Power: {telemetry.actuators.magnetorquers.power.toFixed(2)}W</p>
          </div>

          {telemetry.power && (
            <div className="telemetry-section">
              <h4>Power</h4>
              <p>Eclipse: {telemetry.environment.isIlluminated ? '☀️ Sun' : '🌑 Eclipse'}</p>
              <p>SOC: {(telemetry.power.soc * 100).toFixed(1)}%</p>
              <p>Battery: {telemetry.power.batteryEnergy.toFixed(2)} / {telemetry.power.batteryCapacity.toFixed(1)} Wh</p>
              <p>Generated: {telemetry.power.powerGenerated.toFixed(2)} W</p>
              <p>Consumed: {telemetry.power.powerConsumed.toFixed(2)} W</p>
              <p>Net: {telemetry.power.netPower >= 0 ? '+' : ''}{telemetry.power.netPower.toFixed(2)} W</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
