/**
 * Pointing configuration panel for detailed 3-axis control.
 *
 * Allows users to configure main/sub axis pointing with preset buttons.
 */

import { useState } from 'react';
import type { TargetDirection, BodyAxis, PointingConfig } from '../types/telemetry';
import { telemetryWS } from '../services/websocket';
import './PointingConfigPanel.css';

interface PointingConfigPanelProps {
  isConnected: boolean;
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
  { label: 'Nadir (Earth Center)', value: 'EARTH_CENTER' },
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

export function PointingConfigPanel({ isConnected }: PointingConfigPanelProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [mainTarget, setMainTarget] = useState<TargetDirection>('SUN');
  const [mainBodyAxis, setMainBodyAxis] = useState<BodyAxis>([0, 0, 1]);
  const [subTarget, setSubTarget] = useState<TargetDirection>('EARTH_CENTER');
  const [subBodyAxis, setSubBodyAxis] = useState<BodyAxis>([1, 0, 0]);

  const handlePreset = (preset: PointingConfig) => {
    setMainTarget(preset.mainTarget);
    setMainBodyAxis(preset.mainBodyAxis);
    setSubTarget(preset.subTarget);
    setSubBodyAxis(preset.subBodyAxis);
    // Apply immediately
    telemetryWS.setPointingConfig(preset);
  };

  const handleApply = () => {
    const config: PointingConfig = {
      mainTarget,
      mainBodyAxis,
      subTarget,
      subBodyAxis,
    };
    telemetryWS.setPointingConfig(config);
  };

  return (
    <div className="pointing-config-panel">
      <div className="panel-header" onClick={() => setCollapsed(!collapsed)}>
        <span>{collapsed ? '▶' : '▼'}</span>
        <h3>Pointing Configuration</h3>
      </div>

      {!collapsed && (
        <div className="panel-content">
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

          <div className="axis-config">
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
              <label>Body Axis:</label>
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

          <div className="axis-config">
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
              <label>Body Axis:</label>
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
            onClick={handleApply}
            disabled={!isConnected}
          >
            Apply Configuration
          </button>
        </div>
      )}
    </div>
  );
}
