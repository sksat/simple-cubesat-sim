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

export interface ControlState {
  mode: ControlMode;
  targetQuaternion: [number, number, number, number];
  error: {
    attitude: number;
    rate: number;
  };
}

export interface EnvironmentState {
  magneticField: [number, number, number];
}

export interface Telemetry {
  type: 'telemetry';
  timestamp: number;
  state: SimulationState;
  timeWarp: number;
  attitude: Attitude;
  actuators: ActuatorState;
  control: ControlState;
  environment: EnvironmentState;
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

export interface ModeChangeMessage {
  type: 'mode';
  mode: ControlMode;
  params?: {
    targetQuaternion?: [number, number, number, number];
  };
}

export interface ConfigMessage {
  type: 'config';
  timeWarp?: number;
}

export type ClientMessage = CommandMessage | ModeChangeMessage | ConfigMessage;
