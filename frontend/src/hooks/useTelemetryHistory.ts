/**
 * Hook for storing telemetry history for charting.
 *
 * Uses a simple ring buffer to store recent telemetry data.
 */

import { useState, useCallback, useRef } from 'react';
import type { Telemetry } from '../types/telemetry';

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

interface UseTelemetryHistoryResult {
  history: TelemetryHistoryPoint[];
  addTelemetry: (telemetry: Telemetry) => void;
  clear: () => void;
}

const MAX_HISTORY_SIZE = 36000; // ~1 hour at 10Hz

export function useTelemetryHistory(): UseTelemetryHistoryResult {
  const [history, setHistory] = useState<TelemetryHistoryPoint[]>([]);
  const lastTimestampRef = useRef<number>(-1);

  const addTelemetry = useCallback((telemetry: Telemetry) => {
    // Skip duplicate timestamps
    if (telemetry.timestamp === lastTimestampRef.current) {
      return;
    }
    lastTimestampRef.current = telemetry.timestamp;

    const point: TelemetryHistoryPoint = {
      timestamp: telemetry.timestamp,
      angularVelocity: telemetry.attitude.angularVelocity,
      eulerAngles: telemetry.attitude.eulerAngles,
      rwSpeed: telemetry.actuators.reactionWheels.speed,
      rwTorque: telemetry.actuators.reactionWheels.torque,
      rwActualTorque: telemetry.actuators.reactionWheels.actualTorque,
      rwMomentum: telemetry.actuators.reactionWheels.momentum,
      mtqDipole: telemetry.actuators.magnetorquers.dipoleMoment,
      attitudeError: telemetry.control.error.attitude,
    };

    setHistory(prev => {
      const newHistory = [...prev, point];
      // Trim to max size (ring buffer behavior)
      if (newHistory.length > MAX_HISTORY_SIZE) {
        return newHistory.slice(-MAX_HISTORY_SIZE);
      }
      return newHistory;
    });
  }, []);

  const clear = useCallback(() => {
    setHistory([]);
    lastTimestampRef.current = -1;
  }, []);

  return { history, addTelemetry, clear };
}
