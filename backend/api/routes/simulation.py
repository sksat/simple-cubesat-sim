"""REST API endpoints for simulation control."""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.api.routes.websocket import get_engine


router = APIRouter(prefix="/api/simulation", tags=["simulation"])


class SimulationConfig(BaseModel):
    """Simulation configuration."""
    timeWarp: Optional[float] = Field(None, gt=0, description="Time warp factor")


class TargetAttitude(BaseModel):
    """Target attitude for pointing mode."""
    quaternion: list[float] = Field(..., min_length=4, max_length=4)


class ControlModeRequest(BaseModel):
    """Control mode change request."""
    mode: str
    targetQuaternion: Optional[list[float]] = None


class TLERequest(BaseModel):
    """TLE set request."""
    # TLE lines are typically 69 characters but can vary slightly
    line1: str = Field(..., min_length=60, max_length=80)
    line2: str = Field(..., min_length=60, max_length=80)


@router.get("/state")
async def get_state():
    """Get current simulation state."""
    engine = get_engine()
    return {
        "state": engine.state.name,
        "simTime": engine.sim_time,
        "timeWarp": engine.time_warp,
        "controlMode": engine.spacecraft.control_mode,
    }


@router.post("/start")
async def start_simulation():
    """Start the simulation."""
    engine = get_engine()
    engine.start()
    return {"status": "ok", "state": engine.state.name}


@router.post("/stop")
async def stop_simulation():
    """Stop the simulation."""
    engine = get_engine()
    engine.stop()
    return {"status": "ok", "state": engine.state.name}


@router.post("/pause")
async def pause_simulation():
    """Pause the simulation."""
    engine = get_engine()
    engine.pause()
    return {"status": "ok", "state": engine.state.name}


@router.post("/reset")
async def reset_simulation():
    """Reset the simulation to initial state."""
    engine = get_engine()
    engine.reset()
    return {"status": "ok", "state": engine.state.name}


@router.put("/config")
async def update_config(config: SimulationConfig):
    """Update simulation configuration."""
    engine = get_engine()

    if config.timeWarp is not None:
        try:
            engine.set_time_warp(config.timeWarp)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "ok",
        "timeWarp": engine.time_warp,
    }


@router.put("/control-mode")
async def set_control_mode(request: ControlModeRequest):
    """Set spacecraft control mode."""
    engine = get_engine()

    if request.mode not in ["IDLE", "DETUMBLING", "POINTING", "UNLOADING"]:
        raise HTTPException(status_code=400, detail=f"Unknown mode: {request.mode}")

    engine.set_control_mode(request.mode)

    if request.targetQuaternion is not None:
        import numpy as np
        engine.set_target_attitude(np.array(request.targetQuaternion))

    return {
        "status": "ok",
        "mode": engine.spacecraft.control_mode,
    }


@router.get("/telemetry")
async def get_telemetry():
    """Get current telemetry snapshot."""
    engine = get_engine()
    return engine.get_telemetry()


@router.get("/tle")
async def get_tle():
    """Get current TLE data."""
    engine = get_engine()
    return engine.get_tle()


@router.put("/tle")
async def set_tle(request: TLERequest):
    """Set TLE for orbit propagation."""
    engine = get_engine()

    try:
        engine.set_tle(request.line1, request.line2)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "status": "ok",
        **engine.get_tle(),
    }
