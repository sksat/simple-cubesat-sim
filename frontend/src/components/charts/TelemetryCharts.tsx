/**
 * Telemetry charts component using Plotly.js.
 *
 * Shows angular velocity and reaction wheel speed over time.
 */

import { useState, useMemo } from 'react';
import Plot from 'react-plotly.js';
import type { Data, Layout } from 'plotly.js';

interface TelemetryHistoryPoint {
  timestamp: number;
  angularVelocity: [number, number, number];
  eulerAngles: [number, number, number];
  rwSpeed: [number, number, number];
  rwTorque: [number, number, number];
  rwActualTorque: [number, number, number];
  rwMomentum: [number, number, number];
  mtqDipole: [number, number, number];
  attitudeError: number;
}

interface TelemetryChartsProps {
  history: TelemetryHistoryPoint[];
}

const CHART_COLORS = {
  x: '#ff6b6b',  // Red
  y: '#51cf66',  // Green
  z: '#339af0',  // Blue
  norm: '#ffd43b', // Yellow for norm
};

// Time range options in seconds
const TIME_RANGES = [
  { label: '30s', value: 30 },
  { label: '1m', value: 60 },
  { label: '5m', value: 300 },
  { label: '10m', value: 600 },
  { label: '30m', value: 1800 },
  { label: '1h', value: 3600 },
  { label: 'All', value: Infinity },
];

const DARK_LAYOUT: Partial<Layout> = {
  paper_bgcolor: 'transparent',
  plot_bgcolor: 'rgba(10, 10, 26, 0.8)',
  font: { color: '#ccc', size: 10 },
  margin: { l: 50, r: 20, t: 30, b: 40 },
  legend: {
    orientation: 'h',
    y: 1.15,
    font: { size: 9 },
  },
  xaxis: {
    gridcolor: '#333',
    zerolinecolor: '#555',
    title: { text: 'Time (s)', font: { size: 10 } },
  },
  yaxis: {
    gridcolor: '#333',
    zerolinecolor: '#555',
  },
};

export function TelemetryCharts({ history }: TelemetryChartsProps) {
  const [timeRange, setTimeRange] = useState<number>(300); // Default 5 minutes

  // Filter history based on time range
  const filteredHistory = useMemo(() => {
    if (history.length === 0) return [];
    if (timeRange === Infinity) return history;

    const latestTime = history[history.length - 1].timestamp;
    const cutoffTime = latestTime - timeRange;
    return history.filter(h => h.timestamp >= cutoffTime);
  }, [history, timeRange]);

  if (history.length === 0) {
    return (
      <div className="telemetry-charts-empty">
        <p>No telemetry data yet. Start the simulation to see charts.</p>
      </div>
    );
  }

  const timestamps = filteredHistory.map(h => h.timestamp);

  // Angular velocity data (convert to deg/s for readability)
  const omegaX = filteredHistory.map(h => h.angularVelocity[0] * 180 / Math.PI);
  const omegaY = filteredHistory.map(h => h.angularVelocity[1] * 180 / Math.PI);
  const omegaZ = filteredHistory.map(h => h.angularVelocity[2] * 180 / Math.PI);
  const omegaNorm = filteredHistory.map(h => {
    const [x, y, z] = h.angularVelocity;
    return Math.sqrt(x * x + y * y + z * z) * 180 / Math.PI;
  });

  const angularVelocityData: Data[] = [
    { x: timestamps, y: omegaX, name: 'ωx', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.x, width: 1 } },
    { x: timestamps, y: omegaY, name: 'ωy', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.y, width: 1 } },
    { x: timestamps, y: omegaZ, name: 'ωz', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.z, width: 1 } },
    { x: timestamps, y: omegaNorm, name: '|ω|', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.norm, width: 2 } },
  ];

  const angularVelocityLayout: Partial<Layout> = {
    ...DARK_LAYOUT,
    title: { text: 'Angular Velocity', font: { size: 12 } },
    yaxis: { ...DARK_LAYOUT.yaxis, title: { text: 'deg/s', font: { size: 10 } } },
  };

  // Reaction wheel speed (convert to RPM)
  const rwX = filteredHistory.map(h => h.rwSpeed[0] * 60 / (2 * Math.PI));
  const rwY = filteredHistory.map(h => h.rwSpeed[1] * 60 / (2 * Math.PI));
  const rwZ = filteredHistory.map(h => h.rwSpeed[2] * 60 / (2 * Math.PI));

  const rwSpeedData: Data[] = [
    { x: timestamps, y: rwX, name: 'RW-X', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.x, width: 1 } },
    { x: timestamps, y: rwY, name: 'RW-Y', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.y, width: 1 } },
    { x: timestamps, y: rwZ, name: 'RW-Z', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.z, width: 1 } },
  ];

  // RW max speed: 700 rad/s = 6684.51 RPM
  const RW_MAX_RPM = 700 * 60 / (2 * Math.PI);

  const rwSpeedLayout: Partial<Layout> = {
    ...DARK_LAYOUT,
    title: { text: 'Reaction Wheel Speed', font: { size: 12 } },
    yaxis: {
      ...DARK_LAYOUT.yaxis,
      title: { text: 'RPM', font: { size: 10 } },
      range: [-7000, 7000],  // Fixed range with margin above max speed (700 rad/s)
    },
    shapes: [
      {
        type: 'line',
        x0: timestamps[0],
        x1: timestamps[timestamps.length - 1],
        y0: RW_MAX_RPM,
        y1: RW_MAX_RPM,
        line: { color: '#888', width: 1, dash: 'dash' },
      },
      {
        type: 'line',
        x0: timestamps[0],
        x1: timestamps[timestamps.length - 1],
        y0: -RW_MAX_RPM,
        y1: -RW_MAX_RPM,
        line: { color: '#888', width: 1, dash: 'dash' },
      },
    ],
  };

  // RW Torque comparison (convert to mNm for readability)
  const torqueCmdX = filteredHistory.map(h => h.rwTorque[0] * 1000);
  const torqueCmdY = filteredHistory.map(h => h.rwTorque[1] * 1000);
  const torqueCmdZ = filteredHistory.map(h => h.rwTorque[2] * 1000);
  const torqueActX = filteredHistory.map(h => h.rwActualTorque[0] * 1000);
  const torqueActY = filteredHistory.map(h => h.rwActualTorque[1] * 1000);
  const torqueActZ = filteredHistory.map(h => h.rwActualTorque[2] * 1000);

  const rwTorqueData: Data[] = [
    // Commanded torque (dashed)
    { x: timestamps, y: torqueCmdX, name: 'Cmd-X', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.x, width: 1, dash: 'dot' }, legendgroup: 'x' },
    { x: timestamps, y: torqueCmdY, name: 'Cmd-Y', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.y, width: 1, dash: 'dot' }, legendgroup: 'y' },
    { x: timestamps, y: torqueCmdZ, name: 'Cmd-Z', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.z, width: 1, dash: 'dot' }, legendgroup: 'z' },
    // Actual torque (solid)
    { x: timestamps, y: torqueActX, name: 'Act-X', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.x, width: 1.5 }, legendgroup: 'x' },
    { x: timestamps, y: torqueActY, name: 'Act-Y', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.y, width: 1.5 }, legendgroup: 'y' },
    { x: timestamps, y: torqueActZ, name: 'Act-Z', type: 'scatter', mode: 'lines', line: { color: CHART_COLORS.z, width: 1.5 }, legendgroup: 'z' },
  ];

  const rwTorqueLayout: Partial<Layout> = {
    ...DARK_LAYOUT,
    title: { text: 'RW Torque (Cmd vs Actual)', font: { size: 12 } },
    yaxis: {
      ...DARK_LAYOUT.yaxis,
      title: { text: 'mNm', font: { size: 10 } },
    },
    legend: {
      ...DARK_LAYOUT.legend,
      tracegroupgap: 0,
    },
  };

  return (
    <div className="telemetry-charts-wrapper">
      <div className="charts-toolbar">
        <label>Time Range:</label>
        <select
          value={timeRange}
          onChange={(e) => setTimeRange(Number(e.target.value))}
        >
          {TIME_RANGES.map(({ label, value }) => (
            <option key={label} value={value}>{label}</option>
          ))}
        </select>
      </div>
      <div className="telemetry-charts">
        <div className="chart-container">
          <Plot
            data={angularVelocityData}
            layout={angularVelocityLayout}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
            useResizeHandler
          />
        </div>
        <div className="chart-container">
          <Plot
            data={rwSpeedData}
            layout={rwSpeedLayout}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
            useResizeHandler
          />
        </div>
        <div className="chart-container">
          <Plot
            data={rwTorqueData}
            layout={rwTorqueLayout}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: '100%', height: '100%' }}
            useResizeHandler
          />
        </div>
      </div>
    </div>
  );
}
