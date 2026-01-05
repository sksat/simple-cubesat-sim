/**
 * Simulation control panel component.
 */

import type { ControlMode, Telemetry, SimulationState } from '../types/telemetry';

interface TelemetryState {
  telemetry: Telemetry | null;
  isConnected: boolean;
  simulationState: SimulationState;
  start: () => void;
  stop: () => void;
  pause: () => void;
  reset: () => void;
  setControlMode: (mode: ControlMode, targetQuaternion?: [number, number, number, number]) => void;
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
    setControlMode(e.target.value as ControlMode);
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

      {telemetry && (
        <div className="telemetry-display">
          <h3>Telemetry</h3>
          <div className="telemetry-section">
            <h4>Time</h4>
            <p>Simulation Time: {telemetry.timestamp.toFixed(1)}s</p>
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
            <p>Attitude Error: {telemetry.control.error.attitude.toFixed(2)}deg</p>
            <p>Rate: {(telemetry.control.error.rate * 180 / Math.PI).toFixed(2)}deg/s</p>
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
        </div>
      )}
    </div>
  );
}
