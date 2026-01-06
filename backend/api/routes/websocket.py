"""WebSocket endpoint for real-time telemetry."""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.config import check_config_changed, get_config
from backend.simulation.engine import SimulationEngine


router = APIRouter()

# Global simulation engine instance
_engine: Optional[SimulationEngine] = None

# Config check interval (seconds)
CONFIG_CHECK_INTERVAL = 1.0


def get_engine() -> SimulationEngine:
    """Get or create simulation engine instance."""
    global _engine
    if _engine is None:
        _engine = SimulationEngine()
    return _engine


def reset_engine() -> SimulationEngine:
    """Reset engine with new config."""
    global _engine
    _engine = SimulationEngine(config=get_config())
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

    # Create separate tasks for sending and receiving
    send_task = asyncio.create_task(
        send_telemetry_loop(websocket, engine, telemetry_interval)
    )
    receive_task = asyncio.create_task(
        receive_message_loop(websocket, engine)
    )

    try:
        # Wait for either task to complete (usually due to disconnect)
        done, pending = await asyncio.wait(
            [send_task, receive_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel pending tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception:
        pass
    finally:
        # Ensure both tasks are cancelled
        send_task.cancel()
        receive_task.cancel()
        manager.disconnect(websocket)


def _step_and_get_telemetry(engine: SimulationEngine) -> dict:
    """Step simulation and get telemetry in a single call.

    This runs in thread pool to avoid blocking.
    """
    engine.step()
    telemetry = engine.get_telemetry()
    telemetry["type"] = "telemetry"
    return telemetry


async def send_telemetry_loop(
    websocket: WebSocket,
    engine: SimulationEngine,
    interval: float,
) -> None:
    """Background task to send telemetry at regular intervals.

    Uses asyncio.to_thread() to run simulation step in thread pool,
    preventing blocking of the async event loop during heavy computation.
    Also checks for config file changes periodically.
    """
    loop = asyncio.get_event_loop()
    last_config_check = loop.time()

    try:
        while True:
            loop_start = loop.time()

            # Check for config changes periodically (also in thread pool)
            if loop_start - last_config_check >= CONFIG_CHECK_INTERVAL:
                last_config_check = loop_start
                config_changed = await asyncio.to_thread(check_config_changed)
                if config_changed:
                    # Config changed - reset engine and notify client
                    engine = reset_engine()
                    await websocket.send_json({
                        "type": "config_reload",
                        "message": "Configuration reloaded, simulation reset",
                    })

            # Step simulation and get telemetry in thread pool
            telemetry = await asyncio.to_thread(_step_and_get_telemetry, engine)
            await websocket.send_json(telemetry)

            # Calculate remaining time to maintain consistent interval
            elapsed = loop.time() - loop_start
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
    except Exception as e:
        import logging
        logging.error(f"Telemetry loop error: {e}", exc_info=True)


async def receive_message_loop(
    websocket: WebSocket,
    engine: SimulationEngine,
) -> None:
    """Background task to receive and handle messages."""
    try:
        while True:
            data = await websocket.receive_text()
            await handle_message(data, engine, websocket)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        import logging
        logging.error(f"Receive loop error: {e}", exc_info=True)


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
        elif msg_type == "timeline":
            await handle_timeline(message, engine, websocket)
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

        # Handle pointing mode configuration
        if "pointingMode" in params:
            pointing_mode = params["pointingMode"]
            if pointing_mode in ["MANUAL", "SUN", "NADIR", "GROUND_STATION", "IMAGING_TARGET"]:
                engine.set_pointing_mode(pointing_mode)

        # Handle target quaternion for manual pointing mode
        if "targetQuaternion" in params:
            import numpy as np
            target = np.array(params["targetQuaternion"])
            engine.set_target_attitude(target)

        # Handle imaging target
        if "imagingTarget" in params:
            target = params["imagingTarget"]
            engine.set_imaging_target(
                lat_deg=target.get("latitude", 0),
                lon_deg=target.get("longitude", 0),
                alt_m=target.get("altitude", 0),
            )
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


async def handle_timeline(
    message: dict,
    engine: SimulationEngine,
    websocket: WebSocket,
) -> None:
    """Handle timeline-related messages.

    Message formats:
        Add action:
            {"type": "timeline", "action": "add", "time": 1234.5,
             "actionType": "control_mode", "params": {"mode": "POINTING"}}
        Remove action:
            {"type": "timeline", "action": "remove", "actionId": "uuid"}
        Refresh contact:
            {"type": "timeline", "action": "refresh_contact"}
    """
    action = message.get("action")

    if action == "add":
        try:
            result = engine.add_timeline_action(
                time=message["time"],
                action_type=message["actionType"],
                params=message.get("params", {}),
            )
            await websocket.send_json({
                "type": "timeline_event",
                "event": "action_added",
                "action": result,
            })
        except ValueError as e:
            await send_error(websocket, str(e))
        except KeyError as e:
            await send_error(websocket, f"Missing required field: {e}")

    elif action == "remove":
        action_id = message.get("actionId")
        if not action_id:
            await send_error(websocket, "Missing actionId")
            return

        if engine.remove_timeline_action(action_id):
            await websocket.send_json({
                "type": "timeline_event",
                "event": "action_removed",
                "actionId": action_id,
            })
        else:
            await send_error(websocket, "Action not found")

    elif action == "refresh_contact":
        contact = engine.refresh_contact_prediction()
        await websocket.send_json({
            "type": "timeline_event",
            "event": "contact_refreshed",
            "nextContact": contact,
        })

    elif action == "imaging_preset":
        offset = message.get("offsetSeconds", 300.0)
        schedule = message.get("scheduleAction", False)
        result = engine.set_imaging_preset(
            offset_seconds=offset,
            schedule_action=schedule,
        )
        if result:
            await websocket.send_json({
                "type": "timeline_event",
                "event": "imaging_preset_set",
                "preset": result,
            })
        else:
            await send_error(websocket, "No contact predicted for imaging preset")

    else:
        await send_error(websocket, f"Unknown timeline action: {action}")


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
