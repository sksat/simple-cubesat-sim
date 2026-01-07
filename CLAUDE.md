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
│   ├── simulation.py       # REST endpoints (TLE設定など)
│   └── websocket.py        # WebSocket /ws/telemetry (10Hz telemetry)
├── simulation/
│   ├── engine.py           # Main simulation loop with sub-stepping
│   └── spacecraft.py       # 6U CubeSat model with RK4 integration
├── dynamics/
│   ├── quaternion.py       # Quaternion ops (scalar-last [x,y,z,w])
│   └── orbit.py            # SGP4 orbit propagation (TLE-based)
├── utils/
│   └── coordinates.py      # Astropy coordinate transforms (ECEF, sun direction)
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
| Idle | None | No control |
| Detumbling | MTQ | B-dot: `m = -k * dB/dt` |
| 3Axis | RW + MTQ (auto) | PD control with auto-unloading |

**3Axis Mode Details:**
- Primary: RW for 3-axis attitude control (`T = -Kp*q_err - Kd*ω`)
- Secondary: Automatic MTQ unloading when RW speed exceeds threshold
- `isUnloading` flag in telemetry indicates unloading is active

### 6U CubeSat Dimensions
- X axis: 1U (10cm)
- Y axis: 2U (20cm)
- Z axis: 3U (30cm) - longest dimension
- Solar panels: deployed from +Z end, parallel to +Z face

### Testing Approach

**Backend (Python/pytest)**
TDD for all control algorithms. Key test patterns:
- Zero input → zero output
- Sign/direction verification
- Saturation limits
- Energy/momentum conservation
- Convergence simulations

**Frontend (Playwright)**
Browser-based E2E tests for visualization:
```bash
cd frontend && npm test        # Run all tests
cd frontend && npm run test:ui # Interactive UI mode
```
Key test patterns:
- Page loads without JavaScript errors
- Canvas renders with proper dimensions
- UI components are visible and interactive
- No WebGL/WebGPU errors in console

Use Playwright tests to verify viewer functionality before manual testing.
This catches rendering issues (WebGPU compatibility, Three.js errors) early.

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
  control: { mode, isUnloading, error: { attitude, rate } }
}
```

### Client → Server
```typescript
{ type: "command", command: "START" | "STOP" | "PAUSE" | "RESET" }
{ type: "mode", mode: "Idle" | "Detumbling" | "3Axis" }
{ type: "config", timeWarp: number }
```

## REST API

TLE設定など、一度きりの設定変更はREST APIを使用:
```
GET  /api/simulation/tle     # 現在のTLE取得
PUT  /api/simulation/tle     # TLE設定 (line1, line2)
```

**重要**: フロントエンドからREST APIを使う場合、Viteのプロキシ設定が必要:
```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

## Coordinate Systems

### 設計原則
座標変換は間違いやすい。自前実装を避け、**Astropy**を使用する。
- バックエンド(Python)で座標変換を完結
- フロントエンドには描画用座標を直接送信

### 座標系
| Frame | Description | Use Case |
|-------|-------------|----------|
| ECI (GCRS) | 慣性系 | 姿勢・軌道ダイナミクス |
| ECEF (ITRS) | 地球固定 | 3D可視化 |
| Three.js Scene | Y=North, X=lon0, Z=lon90E | フロントエンド描画 |

### ECEF → Three.js 変換
```
Three.js X = ECEF X / R_earth
Three.js Y = ECEF Z / R_earth  (北極方向)
Three.js Z = ECEF Y / R_earth
```

## SGP4 Orbit Propagation

TLE (Two-Line Element) を使用した軌道伝播:
- `backend/dynamics/orbit.py` - OrbitPropagator クラス
- sgp4ライブラリを使用
- TLEはフロントエンドからCelesTrakを直接取得可能

### TLE検証
- 行の長さ: 60-80文字 (厳密に69文字ではない)
- Line1は "1 " で開始
- Line2は "2 " で開始

## Development Lessons

### Frontend-Backend Communication

**WebSocket vs REST API**
- リアルタイム更新(テレメトリ、コマンド): WebSocket
- 一度きりの設定(TLE): REST API
- timeWarp変更はWebSocket経由で送信済み

**Viteプロキシ設定を忘れずに**
- `/api/*` へのリクエストはVite dev server (5173) に行く
- バックエンド (8000) への転送にはproxy設定が必須
- 404エラーが出たらまずproxy設定を確認

### Error Handling

**FastAPI Validation Errors**
FastAPIは422エラーで`detail`を**配列**で返す:
```typescript
// 正しいハンドリング
if (Array.isArray(errorData.detail)) {
  errorMessage = errorData.detail.map(e => e.msg).join(', ');
} else if (errorData.detail) {
  errorMessage = errorData.detail;
}
```

**Response Body消費問題**
Fetch APIのresponse bodyは一度しか読めない:
```typescript
// NG: body consumed twice
const json = await response.json();  // 失敗時
const text = await response.text();  // ここでエラー

// OK: textで読んでからparse
const text = await response.text();
const json = JSON.parse(text);
```

### External API (CelesTrak)

**CelesTrakはCORS許可**
- ブラウザから直接fetch可能
- レスポンスはプレーンテキスト (JSONではない)
- エラー時は "No GP data found" などのテキストが返る

**TLEフォーマット**
```
Line 0: 衛星名
Line 1: 1 NNNNN...
Line 2: 2 NNNNN...
```

### Three.js Shaders

**法線の座標系に注意**
- `normalMatrix * normal` → ビュー空間 (カメラ回転で変わる)
- `(modelMatrix * vec4(normal, 0.0)).xyz` → ワールド空間 (正しい)

昼夜境界など、カメラ非依存の計算にはワールド空間法線を使用。

### Camera Control

**軌道追従カメラ (LVLH-like frame)**
- Nadir: 地球中心方向 (下)
- Zenith: 反Nadir (上)
- Tangent: Nadir × 北極方向
- カメラオフセットを軌道座標系で保持し、衛星に追従
