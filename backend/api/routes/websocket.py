"""WebSocket endpoint for real-time telemetry."""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.simulation.engine import SimulationEngine


router = APIRouter()

# Global simulation engine instance
_engine: Optional[SimulationEngine] = None


def get_engine() -> SimulationEngine:
    """Get or create simulation engine instance."""
    global _engine
    if _engine is None:
        _engine = SimulationEngine()
    return _engine


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        """Broadcast message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


@router.websocket("/ws/telemetry")
async def telemetry_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time telemetry.

    Sends telemetry data at a configurable rate.
    Receives control commands from client.
    """
    await manager.connect(websocket)
    engine = get_engine()

    # Telemetry rate (Hz)
    telemetry_rate = 10.0
    telemetry_interval = 1.0 / telemetry_rate

    try:
        # Start background task to send telemetry
        send_task = asyncio.create_task(
            send_telemetry_loop(websocket, engine, telemetry_interval)
        )

        # Handle incoming messages
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.1,
                )
                await handle_message(data, engine, websocket)
            except asyncio.TimeoutError:
                continue

    except WebSocketDisconnect:
        pass
    finally:
        send_task.cancel()
        manager.disconnect(websocket)


async def send_telemetry_loop(
    websocket: WebSocket,
    engine: SimulationEngine,
    interval: float,
) -> None:
    """Background task to send telemetry at regular intervals."""
    while True:
        try:
            # Step simulation if running
            engine.step()

            # Send telemetry
            telemetry = engine.get_telemetry()
            telemetry["type"] = "telemetry"
            await websocket.send_json(telemetry)

            await asyncio.sleep(interval)
        except Exception:
            break


async def handle_message(
    data: str,
    engine: SimulationEngine,
    websocket: WebSocket,
) -> None:
    """Handle incoming WebSocket message.

    Args:
        data: JSON message string
        engine: Simulation engine instance
        websocket: WebSocket connection
    """
    try:
        message = json.loads(data)
        msg_type = message.get("type")

        if msg_type == "command":
            await handle_command(message, engine, websocket)
        elif msg_type == "mode":
            await handle_mode_change(message, engine, websocket)
        elif msg_type == "config":
            await handle_config(message, engine, websocket)
        else:
            await send_error(websocket, f"Unknown message type: {msg_type}")

    except json.JSONDecodeError:
        await send_error(websocket, "Invalid JSON")
    except Exception as e:
        await send_error(websocket, str(e))


async def handle_command(
    message: dict,
    engine: SimulationEngine,
    websocket: WebSocket,
) -> None:
    """Handle control commands (START, STOP, PAUSE, RESET)."""
    command = message.get("command")

    if command == "START":
        engine.start()
    elif command == "STOP":
        engine.stop()
    elif command == "PAUSE":
        engine.pause()
    elif command == "RESET":
        engine.reset()
    else:
        await send_error(websocket, f"Unknown command: {command}")
        return

    await send_status(websocket, engine)


async def handle_mode_change(
    message: dict,
    engine: SimulationEngine,
    websocket: WebSocket,
) -> None:
    """Handle control mode change."""
    mode = message.get("mode")
    params = message.get("params", {})

    if mode in ["IDLE", "DETUMBLING", "POINTING", "UNLOADING"]:
        engine.set_control_mode(mode)

        # Handle target quaternion for pointing mode
        if "targetQuaternion" in params:
            import numpy as np
            target = np.array(params["targetQuaternion"])
            engine.set_target_attitude(target)
    else:
        await send_error(websocket, f"Unknown mode: {mode}")
        return

    await send_status(websocket, engine)


async def handle_config(
    message: dict,
    engine: SimulationEngine,
    websocket: WebSocket,
) -> None:
    """Handle configuration changes."""
    if "timeWarp" in message:
        try:
            engine.set_time_warp(message["timeWarp"])
        except ValueError as e:
            await send_error(websocket, str(e))
            return

    await send_status(websocket, engine)


async def send_status(websocket: WebSocket, engine: SimulationEngine) -> None:
    """Send status update to client."""
    status = {
        "type": "status",
        "state": engine.state.name,
        "simTime": engine.sim_time,
        "timeWarp": engine.time_warp,
    }
    await websocket.send_json(status)


async def send_error(websocket: WebSocket, message: str) -> None:
    """Send error message to client."""
    error = {
        "type": "error",
        "message": message,
    }
    await websocket.send_json(error)
