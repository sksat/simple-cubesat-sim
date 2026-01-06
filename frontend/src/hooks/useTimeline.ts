/**
 * React hook for timeline management.
 */

import { useCallback } from 'react';
import type { TimelineActionType } from '../types/telemetry';
import { telemetryWS } from '../services/websocket';

interface UseTimelineResult {
  /** Add a scheduled action to the timeline */
  addAction: (
    time: number,
    actionType: TimelineActionType,
    params: Record<string, unknown>
  ) => void;
  /** Remove a scheduled action */
  removeAction: (actionId: string) => void;
  /** Force refresh contact prediction */
  refreshContact: () => void;
  /** Add a control mode change action */
  addControlModeAction: (time: number, mode: string) => void;
  /** Add a pointing mode change action */
  addPointingModeAction: (time: number, mode: string) => void;
  /** Add an imaging target action */
  addImagingTargetAction: (
    time: number,
    latitude: number,
    longitude: number,
    altitude?: number
  ) => void;
  /** Set imaging target from contact + offset (imaging preset) */
  setImagingPreset: (offsetSeconds?: number, scheduleAction?: boolean) => void;
}

/**
 * Hook for managing timeline actions.
 *
 * Provides methods to add/remove scheduled actions and refresh contact prediction.
 * Timeline state is included in the telemetry updates.
 */
export function useTimeline(): UseTimelineResult {
  const addAction = useCallback(
    (
      time: number,
      actionType: TimelineActionType,
      params: Record<string, unknown>
    ) => {
      telemetryWS.addTimelineAction(time, actionType, params);
    },
    []
  );

  const removeAction = useCallback((actionId: string) => {
    telemetryWS.removeTimelineAction(actionId);
  }, []);

  const refreshContact = useCallback(() => {
    telemetryWS.refreshContactPrediction();
  }, []);

  // Convenience methods for common action types

  const addControlModeAction = useCallback((time: number, mode: string) => {
    telemetryWS.addTimelineAction(time, 'control_mode', { mode });
  }, []);

  const addPointingModeAction = useCallback((time: number, mode: string) => {
    telemetryWS.addTimelineAction(time, 'pointing_mode', { mode });
  }, []);

  const addImagingTargetAction = useCallback(
    (time: number, latitude: number, longitude: number, altitude: number = 0) => {
      telemetryWS.addTimelineAction(time, 'imaging_target', {
        latitude,
        longitude,
        altitude,
      });
    },
    []
  );

  const setImagingPreset = useCallback(
    (offsetSeconds: number = 300, scheduleAction: boolean = false) => {
      telemetryWS.setImagingPreset(offsetSeconds, scheduleAction);
    },
    []
  );

  return {
    addAction,
    removeAction,
    refreshContact,
    addControlModeAction,
    addPointingModeAction,
    addImagingTargetAction,
    setImagingPreset,
  };
}
