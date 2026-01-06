/**
 * WebSocket service for real-time telemetry communication.
 */

import type {
  Telemetry,
  ClientMessage,
  WebSocketMessage,
  ControlMode,
  PointingMode,
  ImagingTarget,
  TimelineActionType,
  PointingConfig,
} from '../types/telemetry';

type MessageHandler = (message: WebSocketMessage) => void;
type ConnectionHandler = () => void;
type ErrorHandler = (error: Event) => void;

export class TelemetryWebSocket {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private messageHandlers: Set<MessageHandler> = new Set();
  private connectHandlers: Set<ConnectionHandler> = new Set();
  private disconnectHandlers: Set<ConnectionHandler> = new Set();
  private errorHandlers: Set<ErrorHandler> = new Set();

  constructor(url: string = 'ws://localhost:8000/ws/telemetry') {
    this.url = url;
  }

  /**
   * Connect to the WebSocket server.
   */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.connectHandlers.forEach(handler => handler());
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.disconnectHandlers.forEach(handler => handler());
        this.attemptReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.errorHandlers.forEach(handler => handler(error));
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.messageHandlers.forEach(handler => handler(message));
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
    }
  }

  /**
   * Disconnect from the WebSocket server.
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Send a message to the server.
   */
  send(message: ClientMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected');
    }
  }

  /**
   * Send simulation control command.
   */
  sendCommand(command: 'START' | 'STOP' | 'PAUSE' | 'RESET'): void {
    this.send({ type: 'command', command });
  }

  /**
   * Set control mode with optional pointing configuration.
   */
  setControlMode(
    mode: ControlMode,
    options?: {
      pointingMode?: PointingMode;
      targetQuaternion?: [number, number, number, number];
      imagingTarget?: ImagingTarget;
    }
  ): void {
    const message: ClientMessage = {
      type: 'mode',
      mode,
      params: options,
    };
    this.send(message);
  }

  /**
   * Set time warp.
   */
  setTimeWarp(timeWarp: number): void {
    this.send({ type: 'config', timeWarp });
  }

  /**
   * Set detailed pointing configuration with main/sub axis.
   */
  setPointingConfig(config: PointingConfig): void {
    this.send({
      type: 'pointing_config',
      mainTarget: config.mainTarget,
      mainBodyAxis: config.mainBodyAxis,
      subTarget: config.subTarget,
      subBodyAxis: config.subBodyAxis,
    });
  }

  // ==================== Timeline Methods ====================

  /**
   * Add a scheduled action to the timeline.
   */
  addTimelineAction(
    time: number,
    actionType: TimelineActionType,
    params: Record<string, unknown>
  ): void {
    this.send({
      type: 'timeline',
      action: 'add',
      time,
      actionType,
      params,
    });
  }

  /**
   * Remove a scheduled action from the timeline.
   */
  removeTimelineAction(actionId: string): void {
    this.send({
      type: 'timeline',
      action: 'remove',
      actionId,
    });
  }

  /**
   * Force refresh contact prediction.
   */
  refreshContactPrediction(): void {
    this.send({
      type: 'timeline',
      action: 'refresh_contact',
    });
  }

  /**
   * Set imaging target from contact + offset.
   */
  setImagingPreset(offsetSeconds: number = 300, scheduleAction: boolean = false): void {
    this.send({
      type: 'timeline',
      action: 'imaging_preset',
      offsetSeconds,
      scheduleAction,
    });
  }

  /**
   * Subscribe to messages.
   */
  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  /**
   * Subscribe to telemetry updates only.
   */
  onTelemetry(handler: (telemetry: Telemetry) => void): () => void {
    const wrappedHandler: MessageHandler = (message) => {
      if (message.type === 'telemetry') {
        handler(message);
      }
    };
    return this.onMessage(wrappedHandler);
  }

  /**
   * Subscribe to connection events.
   */
  onConnect(handler: ConnectionHandler): () => void {
    this.connectHandlers.add(handler);
    return () => this.connectHandlers.delete(handler);
  }

  /**
   * Subscribe to disconnection events.
   */
  onDisconnect(handler: ConnectionHandler): () => void {
    this.disconnectHandlers.add(handler);
    return () => this.disconnectHandlers.delete(handler);
  }

  /**
   * Subscribe to error events.
   */
  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.add(handler);
    return () => this.errorHandlers.delete(handler);
  }

  /**
   * Check if connected.
   */
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Max reconnect attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

    setTimeout(() => {
      this.connect();
    }, delay);
  }
}

// Singleton instance
export const telemetryWS = new TelemetryWebSocket();
