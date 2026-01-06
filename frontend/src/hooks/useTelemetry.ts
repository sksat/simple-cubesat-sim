/**
 * React hook for telemetry subscription.
 */

import { useState, useEffect, useCallback } from 'react';
import type {
  Telemetry,
  SimulationState,
  ControlMode,
  PointingMode,
  ImagingTarget,
} from '../types/telemetry';
import { telemetryWS } from '../services/websocket';

interface ControlModeOptions {
  pointingMode?: PointingMode;
  targetQuaternion?: [number, number, number, number];
  imagingTarget?: ImagingTarget;
}

interface UseTelemetryResult {
  telemetry: Telemetry | null;
  isConnected: boolean;
  simulationState: SimulationState;
  connect: () => void;
  disconnect: () => void;
  start: () => void;
  stop: () => void;
  pause: () => void;
  reset: () => void;
  setControlMode: (mode: ControlMode, options?: ControlModeOptions) => void;
  setTimeWarp: (timeWarp: number) => void;
}

export function useTelemetry(): UseTelemetryResult {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [simulationState, setSimulationState] = useState<SimulationState>('STOPPED');

  useEffect(() => {
    // Subscribe to telemetry updates
    const unsubscribeTelemetry = telemetryWS.onTelemetry((data) => {
      setTelemetry(data);
      setSimulationState(data.state);
    });

    // Subscribe to connection events
    const unsubscribeConnect = telemetryWS.onConnect(() => {
      setIsConnected(true);
    });

    const unsubscribeDisconnect = telemetryWS.onDisconnect(() => {
      setIsConnected(false);
    });

    // Subscribe to status updates
    const unsubscribeMessage = telemetryWS.onMessage((message) => {
      if (message.type === 'status') {
        setSimulationState(message.state);
      }
    });

    // Connect on mount
    telemetryWS.connect();

    // Cleanup on unmount
    return () => {
      unsubscribeTelemetry();
      unsubscribeConnect();
      unsubscribeDisconnect();
      unsubscribeMessage();
    };
  }, []);

  const connect = useCallback(() => {
    telemetryWS.connect();
  }, []);

  const disconnect = useCallback(() => {
    telemetryWS.disconnect();
  }, []);

  const start = useCallback(() => {
    telemetryWS.sendCommand('START');
  }, []);

  const stop = useCallback(() => {
    telemetryWS.sendCommand('STOP');
  }, []);

  const pause = useCallback(() => {
    telemetryWS.sendCommand('PAUSE');
  }, []);

  const reset = useCallback(() => {
    telemetryWS.sendCommand('RESET');
  }, []);

  const setControlMode = useCallback((
    mode: ControlMode,
    options?: ControlModeOptions
  ) => {
    telemetryWS.setControlMode(mode, options);
  }, []);

  const setTimeWarp = useCallback((timeWarp: number) => {
    telemetryWS.setTimeWarp(timeWarp);
  }, []);

  return {
    telemetry,
    isConnected,
    simulationState,
    connect,
    disconnect,
    start,
    stop,
    pause,
    reset,
    setControlMode,
    setTimeWarp,
  };
}
