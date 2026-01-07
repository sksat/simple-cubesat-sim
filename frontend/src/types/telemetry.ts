/**
 * Telemetry data types for CubeSat simulator.
 */

export interface Attitude {
  quaternion: [number, number, number, number];
  angularVelocity: [number, number, number];
  eulerAngles: [number, number, number];
}

export interface ReactionWheelState {
  speed: [number, number, number];
  torque: [number, number, number];
  /** Actual motor torque output (after dynamics) */
  actualTorque: [number, number, number];
  momentum: [number, number, number];
}

export interface MagnetorquerState {
  dipoleMoment: [number, number, number];
  power: number;
}

export interface ActuatorState {
  reactionWheels: ReactionWheelState;
  magnetorquers: MagnetorquerState;
}

export type PointingMode = 'MANUAL' | 'SUN' | 'NADIR' | 'GROUND_STATION' | 'IMAGING_TARGET';

export type TargetDirection =
  | 'SUN'
  | 'EARTH_CENTER'
  | 'GROUND_STATION'
  | 'IMAGING_TARGET'
  | 'VELOCITY'
  | 'ORBIT_NORMAL';

export type BodyAxis =
  | [1, 0, 0]   // +X
  | [-1, 0, 0]  // -X
  | [0, 1, 0]   // +Y
  | [0, -1, 0]  // -Y
  | [0, 0, 1]   // +Z
  | [0, 0, -1]; // -Z

export interface PointingConfig {
  mainTarget: TargetDirection;
  mainBodyAxis: BodyAxis;
  subTarget: TargetDirection;
  subBodyAxis: BodyAxis;
}

export interface ControlState {
  mode: ControlMode;
  pointingMode: PointingMode;
  targetQuaternion: [number, number, number, number];
  error: {
    attitude: number;
    rate: number;
  };
  groundStationVisible: boolean;
}

export interface EnvironmentState {
  magneticField: [number, number, number];
  /** Sun direction vector in Three.js scene coordinates (unit vector) */
  sunDirection: [number, number, number];
  /** Sun direction vector in ECI (inertial) frame for body frame transformation */
  sunDirectionECI: [number, number, number];
  /** True if satellite is illuminated (not in eclipse) */
  isIlluminated: boolean;
}

export interface PowerState {
  /** Battery state of charge (0-1) */
  soc: number;
  /** Current battery energy (Wh) */
  batteryEnergy: number;
  /** Battery capacity (Wh) */
  batteryCapacity: number;
  /** Current power generation from solar panels (W) */
  powerGenerated: number;
  /** Current power consumption (W) */
  powerConsumed: number;
  /** Net power (positive = charging, negative = discharging) (W) */
  netPower: number;
}

// ==================== Timeline Types ====================

/** Ground station contact window */
export interface ContactWindow {
  groundStationName: string;
  /** AOS time in simulation seconds */
  startTime: number;
  /** LOS time in simulation seconds */
  endTime: number;
  /** Maximum elevation angle in degrees */
  maxElevation: number;
  /** Time of maximum elevation in simulation seconds */
  maxElevationTime: number;
  /** Azimuth at AOS in degrees */
  aosAzimuth: number;
  /** Azimuth at LOS in degrees */
  losAzimuth: number;
  /** Contact duration in seconds */
  duration: number;
}

/** Types of timeline actions */
export type TimelineActionType = 'control_mode' | 'pointing_mode' | 'imaging_target';

/** Scheduled timeline action */
export interface TimelineAction {
  id: string;
  /** Execution time in simulation seconds */
  time: number;
  actionType: TimelineActionType;
  params: Record<string, unknown>;
  executed: boolean;
  /** When the action was created (sim time) */
  createdAt: number;
}

/** Timeline state in telemetry */
export interface TimelineState {
  nextContact: ContactWindow | null;
  actions: TimelineAction[];
}

export interface OrbitState {
  latitude: number;
  longitude: number;
  altitude: number;
  inclination: number;
  period: number;
  /** ECEF position in km (computed by Astropy) */
  positionECEF: [number, number, number];
  /** Three.js scene coordinates (normalized, Earth radius = 1) */
  positionThreeJS: [number, number, number];
}

export interface Telemetry {
  type: 'telemetry';
  timestamp: number;
  /** Absolute simulation time as ISO8601 UTC string */
  absoluteTime: string;
  state: SimulationState;
  timeWarp: number;
  attitude: Attitude;
  actuators: ActuatorState;
  control: ControlState;
  environment: EnvironmentState;
  orbit?: OrbitState;
  power?: PowerState;
  timeline?: TimelineState;
}

export type SimulationState = 'STOPPED' | 'RUNNING' | 'PAUSED';
export type ControlMode = 'IDLE' | 'DETUMBLING' | 'POINTING' | 'UNLOADING';

export interface StatusMessage {
  type: 'status';
  state: SimulationState;
  simTime: number;
  timeWarp: number;
}

export interface ErrorMessage {
  type: 'error';
  message: string;
}

/** Imaging preset result */
export interface ImagingPreset {
  latitude: number;
  longitude: number;
  altitude: number;
  targetTime: number;
  contactStartTime: number;
  offsetSeconds: number;
}

/** Timeline event message from server */
export interface TimelineEventMessage {
  type: 'timeline_event';
  event: 'action_added' | 'action_removed' | 'contact_refreshed' | 'imaging_preset_set';
  action?: TimelineAction;
  actionId?: string;
  nextContact?: ContactWindow | null;
  preset?: ImagingPreset;
}

export type WebSocketMessage = Telemetry | StatusMessage | ErrorMessage | TimelineEventMessage;

// Commands
export interface CommandMessage {
  type: 'command';
  command: 'START' | 'STOP' | 'PAUSE' | 'RESET';
}

export interface ImagingTarget {
  latitude: number;
  longitude: number;
  altitude?: number;
}

export interface ModeChangeMessage {
  type: 'mode';
  mode: ControlMode;
  params?: {
    pointingMode?: PointingMode;
    targetQuaternion?: [number, number, number, number];
    imagingTarget?: ImagingTarget;
  };
}

export interface ConfigMessage {
  type: 'config';
  timeWarp?: number;
}

/** Timeline command from client */
export interface TimelineMessage {
  type: 'timeline';
  action: 'add' | 'remove' | 'refresh_contact' | 'imaging_preset';
  /** For add action */
  time?: number;
  actionType?: TimelineActionType;
  params?: Record<string, unknown>;
  /** For remove action */
  actionId?: string;
  /** For imaging_preset action */
  offsetSeconds?: number;
  scheduleAction?: boolean;
}

/** Pointing configuration message */
export interface PointingConfigMessage {
  type: 'pointing_config';
  mainTarget: TargetDirection;
  mainBodyAxis: BodyAxis;
  subTarget: TargetDirection;
  subBodyAxis: BodyAxis;
}

export type ClientMessage = CommandMessage | ModeChangeMessage | ConfigMessage | TimelineMessage | PointingConfigMessage;
