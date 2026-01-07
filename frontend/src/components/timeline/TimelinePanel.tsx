/**
 * Timeline panel component showing contact predictions and scheduled actions.
 */

import { useState } from 'react';
import type { Telemetry, ContactWindow, TimelineAction, TimelineActionType } from '../../types/telemetry';
import './TimelinePanel.css';

interface TimelinePanelProps {
  telemetry: Telemetry | null;
  isConnected: boolean;
  onAddAction: (
    time: number,
    actionType: TimelineActionType,
    params: Record<string, unknown>
  ) => void;
  onRemoveAction: (actionId: string) => void;
  onRefreshContact: () => void;
  onSetImagingPreset?: (offsetSeconds: number, scheduleAction: boolean) => void;
}

/**
 * Format duration in seconds to human-readable string.
 */
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

/**
 * Format action type for display.
 */
function formatActionType(actionType: TimelineActionType): string {
  switch (actionType) {
    case 'control_mode':
      return 'Control Mode';
    case 'pointing_mode':
      return 'Pointing Mode';
    case 'imaging_target':
      return 'Imaging Target';
    default:
      return actionType;
  }
}

/**
 * Format action params for display.
 */
function formatParams(actionType: TimelineActionType, params: Record<string, unknown>): string {
  if (actionType === 'control_mode' || actionType === 'pointing_mode') {
    return String(params.mode || '');
  }
  if (actionType === 'imaging_target') {
    const lat = Number(params.latitude || 0).toFixed(2);
    const lon = Number(params.longitude || 0).toFixed(2);
    return `${lat}, ${lon}`;
  }
  return JSON.stringify(params);
}

// ==================== Contact Display ====================

interface ContactDisplayProps {
  contact: ContactWindow | null;
  currentTime: number;
  onRefresh: () => void;
}

function ContactDisplay({ contact, currentTime, onRefresh }: ContactDisplayProps) {
  if (!contact) {
    return (
      <div className="contact-display no-contact">
        <div className="contact-header">
          <span className="contact-title">Next Contact</span>
          <button onClick={onRefresh} className="refresh-btn" title="Refresh prediction">
            Refresh
          </button>
        </div>
        <p className="no-contact-text">No upcoming contact predicted</p>
      </div>
    );
  }

  const timeToAos = contact.startTime - currentTime;
  const timeToLos = contact.endTime - currentTime;
  const isInContact = timeToAos <= 0 && timeToLos > 0;

  return (
    <div className={`contact-display ${isInContact ? 'in-contact' : ''}`}>
      <div className="contact-header">
        <span className="contact-title">{contact.groundStationName}</span>
        <button onClick={onRefresh} className="refresh-btn" title="Refresh prediction">
          Refresh
        </button>
      </div>
      <div className="contact-info">
        {isInContact ? (
          <p className="contact-status active">IN CONTACT - LOS in {formatDuration(timeToLos)}</p>
        ) : (
          <p className="contact-status pending">AOS in {formatDuration(timeToAos)}</p>
        )}
        <div className="contact-details">
          <span>Max El: {contact.maxElevation.toFixed(1)}</span>
          <span>Duration: {formatDuration(contact.duration)}</span>
        </div>
      </div>
    </div>
  );
}

// ==================== Action List ====================

interface ActionListProps {
  actions: TimelineAction[];
  currentTime: number;
  onRemove: (actionId: string) => void;
}

function ActionList({ actions, currentTime, onRemove }: ActionListProps) {
  if (actions.length === 0) {
    return <p className="no-actions">No scheduled actions</p>;
  }

  return (
    <div className="action-list">
      {actions.map(action => {
        const timeUntil = action.time - currentTime;
        return (
          <div key={action.id} className="action-item">
            <div className="action-info">
              <span className="action-type">{formatActionType(action.actionType)}</span>
              <span className="action-params">{formatParams(action.actionType, action.params)}</span>
            </div>
            <div className="action-timing">
              <span className="action-time">T+{formatDuration(timeUntil)}</span>
              <button
                onClick={() => onRemove(action.id)}
                className="remove-btn"
                title="Remove action"
              >
                x
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ==================== Add Action Form ====================

interface AddActionFormProps {
  currentTime: number;
  nextContact: ContactWindow | null;
  onAdd: (
    time: number,
    actionType: TimelineActionType,
    params: Record<string, unknown>
  ) => void;
  onCancel: () => void;
}

function AddActionForm({ currentTime, nextContact, onAdd, onCancel }: AddActionFormProps) {
  const [actionType, setActionType] = useState<TimelineActionType>('control_mode');
  const [timeOffset, setTimeOffset] = useState(60);
  const [useContactRelative, setUseContactRelative] = useState(false);
  const [contactOffset, setContactOffset] = useState(0);
  const [mode, setMode] = useState('3Axis');
  const [latitude, setLatitude] = useState(35.0);
  const [longitude, setLongitude] = useState(139.0);

  const calculatedTime = useContactRelative && nextContact
    ? nextContact.startTime + contactOffset
    : currentTime + timeOffset;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    let params: Record<string, unknown> = {};
    if (actionType === 'control_mode' || actionType === 'pointing_mode') {
      params = { mode };
    } else if (actionType === 'imaging_target') {
      params = { latitude, longitude, altitude: 0 };
    }

    onAdd(calculatedTime, actionType, params);
  };

  return (
    <form className="add-action-form" onSubmit={handleSubmit}>
      <div className="form-row">
        <label>Type:</label>
        <select
          value={actionType}
          onChange={e => setActionType(e.target.value as TimelineActionType)}
        >
          <option value="control_mode">Control Mode</option>
          <option value="pointing_mode">Pointing Mode</option>
          <option value="imaging_target">Imaging Target</option>
        </select>
      </div>

      <div className="form-row">
        <label>
          <input
            type="checkbox"
            checked={useContactRelative}
            onChange={e => setUseContactRelative(e.target.checked)}
            disabled={!nextContact}
          />
          Relative to AOS
        </label>
      </div>

      <div className="form-row">
        <label>Offset (s):</label>
        <input
          type="number"
          value={useContactRelative ? contactOffset : timeOffset}
          onChange={e => {
            const val = Number(e.target.value);
            if (useContactRelative) {
              setContactOffset(val);
            } else {
              setTimeOffset(val);
            }
          }}
        />
      </div>

      <div className="form-row">
        <span className="time-preview">T+{calculatedTime.toFixed(0)}s</span>
      </div>

      {(actionType === 'control_mode') && (
        <div className="form-row">
          <label>Mode:</label>
          <select value={mode} onChange={e => setMode(e.target.value)}>
            <option value="Idle">Idle</option>
            <option value="Detumbling">Detumbling</option>
            <option value="3Axis">3Axis</option>
          </select>
        </div>
      )}

      {(actionType === 'pointing_mode') && (
        <div className="form-row">
          <label>Mode:</label>
          <select value={mode} onChange={e => setMode(e.target.value)}>
            <option value="MANUAL">Manual</option>
            <option value="SUN">Sun</option>
            <option value="NADIR">Nadir</option>
            <option value="GROUND_STATION">Ground Station</option>
            <option value="IMAGING_TARGET">Imaging Target</option>
          </select>
        </div>
      )}

      {(actionType === 'imaging_target') && (
        <>
          <div className="form-row">
            <label>Lat:</label>
            <input
              type="number"
              step="0.01"
              value={latitude}
              onChange={e => setLatitude(Number(e.target.value))}
            />
          </div>
          <div className="form-row">
            <label>Lon:</label>
            <input
              type="number"
              step="0.01"
              value={longitude}
              onChange={e => setLongitude(Number(e.target.value))}
            />
          </div>
        </>
      )}

      <div className="form-buttons">
        <button type="submit">Add</button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

// ==================== Main Panel ====================

export function TimelinePanel({
  telemetry,
  isConnected,
  onAddAction,
  onRemoveAction,
  onRefreshContact,
  onSetImagingPreset,
}: TimelinePanelProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [presetOffset, setPresetOffset] = useState(300); // 5 minutes default

  const timeline = telemetry?.timeline;
  const nextContact = timeline?.nextContact ?? null;
  const actions = timeline?.actions ?? [];
  const currentTime = telemetry?.timestamp ?? 0;

  return (
    <div className="timeline-panel">
      <h3>Timeline</h3>

      <ContactDisplay
        contact={nextContact}
        currentTime={currentTime}
        onRefresh={onRefreshContact}
      />

      {onSetImagingPreset && nextContact && (
        <div className="imaging-preset-section">
          <div className="preset-row">
            <label>Imaging at AOS +</label>
            <input
              type="number"
              value={presetOffset}
              onChange={e => setPresetOffset(Number(e.target.value))}
              min={0}
              step={60}
              className="preset-offset"
            />
            <span>s</span>
            <button
              onClick={() => onSetImagingPreset(presetOffset, true)}
              disabled={!isConnected}
              className="preset-btn"
              title="Set imaging target to ground track at this time"
            >
              Set Preset
            </button>
          </div>
        </div>
      )}

      <div className="actions-section">
        <div className="actions-header">
          <span>Scheduled Actions</span>
          <button
            onClick={() => setShowAddForm(true)}
            disabled={!isConnected || showAddForm}
            className="add-btn"
          >
            + Add
          </button>
        </div>

        {showAddForm ? (
          <AddActionForm
            currentTime={currentTime}
            nextContact={nextContact}
            onAdd={(time, type, params) => {
              onAddAction(time, type, params);
              setShowAddForm(false);
            }}
            onCancel={() => setShowAddForm(false)}
          />
        ) : (
          <ActionList
            actions={actions}
            currentTime={currentTime}
            onRemove={onRemoveAction}
          />
        )}
      </div>
    </div>
  );
}
