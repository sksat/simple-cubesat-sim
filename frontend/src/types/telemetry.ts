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

export type WebSocketMessage = Telemetry | StatusMessage | ErrorMessage;

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

export type ClientMessage = CommandMessage | ModeChangeMessage | ConfigMessage;
