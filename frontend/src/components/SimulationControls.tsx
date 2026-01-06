/**
 * Simulation control panel component.
 */

import type { ControlMode, PointingMode, Telemetry, SimulationState, ImagingTarget } from '../types/telemetry';
import { TLESettings } from './TLESettings';

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

  const handleModeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const mode = e.target.value as ControlMode;
    // Keep current pointing mode when switching to POINTING
    if (mode === 'POINTING' && telemetry?.control.pointingMode) {
      setControlMode(mode, { pointingMode: telemetry.control.pointingMode });
    } else {
      setControlMode(mode);
    }
  };

  const handlePointingModeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const pointingMode = e.target.value as PointingMode;
    setControlMode('POINTING', { pointingMode });
  };

  const handleTimeWarpChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setTimeWarp(parseFloat(e.target.value));
  };

  const statusClass = isConnected ? 'connected' : 'disconnected';

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
          value={telemetry?.control.mode || 'IDLE'}
          onChange={handleModeChange}
          disabled={!isConnected}
        >
          <option value="IDLE">Idle</option>
          <option value="DETUMBLING">Detumbling</option>
          <option value="POINTING">Pointing</option>
          <option value="UNLOADING">Unloading</option>
        </select>
      </div>

      {telemetry?.control.mode === 'POINTING' && (
        <div className="pointing-mode">
          <label>Pointing Target:</label>
          <select
            value={telemetry?.control.pointingMode || 'MANUAL'}
            onChange={handlePointingModeChange}
            disabled={!isConnected}
          >
            <option value="MANUAL">Manual</option>
            <option value="SUN">Sun (+Z)</option>
            <option value="NADIR">Nadir (-Z)</option>
            <option value="GROUND_STATION">Ground Station</option>
            <option value="IMAGING_TARGET">Imaging Target</option>
          </select>
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
            {telemetry.control.mode === 'POINTING' && (
              <p>Target: {telemetry.control.pointingMode}</p>
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
