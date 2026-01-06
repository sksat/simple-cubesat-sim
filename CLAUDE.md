# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development
```bash
# Start backend (runs on http://localhost:8000)
make backend
# or: PYTHONPATH=. uv run uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Start frontend (runs on http://localhost:5173)
make frontend
# or: cd frontend && npm run dev
```

### Testing
```bash
# Run all tests
uv run pytest

# Run single test file
uv run pytest tests/unit/test_bdot.py

# Run specific test
uv run pytest tests/unit/test_bdot.py::TestBdotController::test_control_law_sign -v

# Run with coverage
uv run pytest --cov=backend
```

### Linting
```bash
# Python
uv run ruff check backend tests
uv run pyright backend

# Frontend
cd frontend && npm run lint
```

## Architecture

### Backend (Python + FastAPI)
```
backend/
├── main.py                 # FastAPI entry point
├── api/routes/
│   ├── simulation.py       # REST endpoints
│   └── websocket.py        # WebSocket /ws/telemetry (10Hz telemetry)
├── simulation/
│   ├── engine.py           # Main simulation loop with sub-stepping
│   └── spacecraft.py       # 6U CubeSat model with RK4 integration
├── dynamics/
│   └── quaternion.py       # Quaternion ops (scalar-last [x,y,z,w])
├── actuators/
│   ├── magnetorquer.py     # MTQ: T = m × B
│   └── reaction_wheel.py   # RW: 3-axis momentum storage
└── control/
    ├── bdot.py             # B-dot detumbling: m = -k * dB/dt
    ├── attitude_controller.py  # PD control: T = -Kp*q_err - Kd*ω
    └── rw_unloading.py     # Momentum dump: m = k * (B × H_rw) / |B|²
```

### Frontend (React + TypeScript)
```
frontend/src/
├── services/websocket.ts   # WebSocket client (singleton)
├── hooks/
│   ├── useTelemetry.ts     # Telemetry subscription hook
│   └── useTelemetryHistory.ts  # History buffer for charts
└── components/
    ├── visualization/
    │   ├── SatelliteView.tsx   # Three.js satellite view
    │   └── CubeSatModel.tsx    # 6U model (X=1U, Y=2U, Z=3U)
    └── charts/
        └── TelemetryCharts.tsx # Plotly.js time-series
```

### Data Flow
1. `SimulationEngine.step()` runs in thread pool (non-blocking)
2. Sub-stepping maintains physics accuracy at high time warp (max 0.1s per sub-step)
3. WebSocket sends telemetry JSON at 10Hz to frontend
4. Frontend stores history in `useTelemetryHistory` (36000 points max)

## Key Conventions

### Quaternion Convention
- **Scalar-last**: `[x, y, z, w]` (Hamilton convention)
- `q = cos(θ/2) + sin(θ/2) * (xi + yj + zk)`
- Shortest path ensured by negating if `w < 0`

### Control Modes
| Mode | Actuator | Algorithm |
|------|----------|-----------|
| DETUMBLING | MTQ | B-dot: `m = -k * dB/dt` |
| POINTING | RW | PD: `T = -Kp*q_err - Kd*ω` |
| UNLOADING | MTQ + RW | `m = k * (B × H_rw) / |B|²` |

### 6U CubeSat Dimensions
- X axis: 1U (10cm)
- Y axis: 2U (20cm)
- Z axis: 3U (30cm) - longest dimension
- Solar panels: deployed from +Z end, parallel to +Z face

### Testing Approach
TDD for all control algorithms. Key test patterns:
- Zero input → zero output
- Sign/direction verification
- Saturation limits
- Energy/momentum conservation
- Convergence simulations

## WebSocket Protocol

### Server → Client (Telemetry)
```typescript
{
  type: "telemetry",
  timestamp: number,           // simulation time (s)
  attitude: {
    quaternion: [x, y, z, w],
    angularVelocity: [wx, wy, wz],  // rad/s
    eulerAngles: [roll, pitch, yaw] // deg
  },
  actuators: {
    reactionWheels: { speed, torque, momentum },
    magnetorquers: { dipoleMoment, power }
  },
  control: { mode, error: { attitude, rate } }
}
```

### Client → Server
```typescript
{ type: "command", command: "START" | "STOP" | "PAUSE" | "RESET" }
{ type: "mode", mode: "DETUMBLING" | "POINTING" | "UNLOADING" | "IDLE" }
{ type: "config", timeWarp: number }
```
