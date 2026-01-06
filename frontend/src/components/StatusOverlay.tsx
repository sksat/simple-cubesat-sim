/**
 * Compact satellite status display overlay.
 *
 * Shows real-time satellite state: mode, communication, power, and attitude error.
 */

import type { Telemetry } from '../types/telemetry';

interface StatusOverlayProps {
  telemetry: Telemetry | null;
}

export function StatusOverlay({ telemetry }: StatusOverlayProps) {
  if (!telemetry) {
    return (
      <div className="status-overlay">
        <div>No telemetry</div>
      </div>
    );
  }

  const { control, power, environment } = telemetry;

  // Format mode display
  const modeDisplay = control.mode === 'POINTING'
    ? `${control.mode} (${control.pointingMode})`
    : control.mode;

  // Communication status
  const commStatus = control.groundStationVisible ? '✓' : '✗';

  // Power display
  const socPercent = power ? (power.soc * 100).toFixed(0) : '?';
  const netPower = power ? power.netPower.toFixed(1) : '?';
  const powerIcon = power && power.netPower >= 0 ? '⚡' : '🔋';
  const eclipseIcon = environment.isIlluminated ? '☀️' : '🌑';

  // Attitude error
  const attError = control.error.attitude.toFixed(1);
  const rateError = (control.error.rate * 180 / Math.PI).toFixed(2);

  return (
    <div className="status-overlay">
      <div>MODE: {modeDisplay}</div>
      <div>
        COMM: GS {commStatus}  PWR: {socPercent}% {powerIcon}{netPower}W {eclipseIcon}
      </div>
      <div>ERR: Att {attError}° Rate {rateError}°/s</div>
    </div>
  );
}
