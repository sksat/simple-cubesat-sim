/**
 * Compact satellite status display overlay.
 *
 * Shows real-time satellite state: mode, communication, power, and attitude error.
 */

import type { Telemetry } from '../types/telemetry';

interface StatusOverlayProps {
  telemetry: Telemetry | null;
}

function formatDuration(seconds: number): string {
  if (seconds < 0) return '0s';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.round(seconds % 60);
    return `${mins}m ${secs}s`;
  }
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

export function StatusOverlay({ telemetry }: StatusOverlayProps) {
  if (!telemetry) {
    return (
      <div className="status-overlay">
        <div>No telemetry</div>
      </div>
    );
  }

  const { control, power, environment, timeline, timestamp, absoluteTime, state } = telemetry;

  // Format time display
  const elapsedTime = `T+${timestamp.toFixed(1)}s`;
  const utcTime = new Date(absoluteTime).toISOString().replace('T', ' ').slice(0, 19);

  // Unloading status
  const isUnloading = control.isUnloading ?? false;

  // Format mode display
  const modeDisplay = control.mode === '3Axis'
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

  // Contact countdown calculation
  const nextContact = timeline?.nextContact ?? null;
  let contactCountdown: { label: string; time: number; isActive: boolean } | null = null;
  if (nextContact) {
    const timeToAos = nextContact.startTime - timestamp;
    const timeToLos = nextContact.endTime - timestamp;
    if (timeToAos <= 0 && timeToLos > 0) {
      contactCountdown = { label: 'LOS', time: timeToLos, isActive: true };
    } else if (timeToAos > 0) {
      contactCountdown = { label: 'AOS', time: timeToAos, isActive: false };
    }
  }

  return (
    <div className="status-overlay">
      <div>{elapsedTime}  {utcTime} UTC  [{state}]</div>
      <div>
        MODE: {modeDisplay}
        {isUnloading && <span className="unloading-indicator"> 🔄 Unloading</span>}
      </div>
      <div>
        COMM: GS {commStatus}
        {contactCountdown && (
          <span className={contactCountdown.isActive ? 'contact-active' : 'contact-pending'}>
            {' '}[{contactCountdown.label} {formatDuration(contactCountdown.time)}]
          </span>
        )}
        {'  '}PWR: {socPercent}% {powerIcon}{netPower}W {eclipseIcon}
      </div>
      <div>ERR: Att {attError}° Rate {rateError}°/s</div>
    </div>
  );
}
