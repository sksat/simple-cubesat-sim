/**
 * Hook for storing orbit position history for ground track visualization.
 */

import { useState, useCallback, useRef } from 'react';
import type { Telemetry } from '../types/telemetry';

export interface OrbitHistoryPoint {
  timestamp: number;
  latitude: number;
  longitude: number;
  altitude: number;
  /** Pre-computed Three.js coordinates from backend (Astropy) */
  positionThreeJS: [number, number, number];
}

interface UseOrbitHistoryResult {
  history: OrbitHistoryPoint[];
  addTelemetry: (telemetry: Telemetry) => void;
  clear: () => void;
}

// Store ~2 orbits worth of ground track (~190 min at 10Hz)
const MAX_ORBIT_HISTORY_SIZE = 114000;

// Minimum time between history points (seconds) to avoid too many points
const MIN_HISTORY_INTERVAL = 1.0;

export function useOrbitHistory(): UseOrbitHistoryResult {
  const [history, setHistory] = useState<OrbitHistoryPoint[]>([]);
  const lastTimestampRef = useRef<number>(-Infinity);

  const addTelemetry = useCallback((telemetry: Telemetry) => {
    if (!telemetry.orbit) {
      return;
    }

    // Skip if too close to previous point
    if (telemetry.timestamp - lastTimestampRef.current < MIN_HISTORY_INTERVAL) {
      return;
    }
    lastTimestampRef.current = telemetry.timestamp;

    const point: OrbitHistoryPoint = {
      timestamp: telemetry.timestamp,
      latitude: telemetry.orbit.latitude,
      longitude: telemetry.orbit.longitude,
      altitude: telemetry.orbit.altitude,
      positionThreeJS: telemetry.orbit.positionThreeJS,
    };

    setHistory(prev => {
      const newHistory = [...prev, point];
      if (newHistory.length > MAX_ORBIT_HISTORY_SIZE) {
        return newHistory.slice(-MAX_ORBIT_HISTORY_SIZE);
      }
      return newHistory;
    });
  }, []);

  const clear = useCallback(() => {
    setHistory([]);
    lastTimestampRef.current = -Infinity;
  }, []);

  return { history, addTelemetry, clear };
}
