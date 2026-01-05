# Simple CubeSat Simulator - Design Document

## 1. Overview

Web ベースの 6U CubeSat シミュレータ。姿勢制御（MTQ + RW）のシミュレーションを Python バックエンドで行い、リアルタイムで WebSocket 経由でフロントエンドに送信し、3D 可視化する。

### 1.1 Key Features
- 6U CubeSat の 3D 可視化（Three.js）
- 地球と軌道の可視化（globe.gl）
- SSO (Sun-Synchronous Orbit) での軌道伝播
- 姿勢制御シミュレーション
  - B-dot デタンブリング制御
  - 3軸姿勢制御（RW）
  - RW アンローディング（MTQ）
- リアルタイムテレメトリ可視化
- 時系列データの DuckDB.wasm への保存

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | React + TypeScript | UI フレームワーク |
| Bundler | Vite | 高速な開発サーバー |
| 3D (Satellite) | Three.js + React Three Fiber | 衛星の 3D 表示 |
| 3D (Earth) | globe.gl | 地球と軌道の表示 |
| Charts | Plotly.js | 時系列グラフ |
| Client DB | DuckDB.wasm | テレメトリ保存・クエリ |
| Backend | Python + FastAPI | シミュレーションサーバー |
| WebSocket | FastAPI WebSockets | リアルタイム通信 |
| Python Env | uv | 依存関係管理 |
| Testing | pytest | TDD |

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Frontend (React + TypeScript)                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │ SatelliteView   │  │ GlobeView       │  │ TimeSeriesCharts        │  │
│  │ (Three.js)      │  │ (globe.gl)      │  │ (Plotly.js)             │  │
│  └────────┬────────┘  └────────┬────────┘  └────────────┬────────────┘  │
│           │                    │                        │               │
│           └──────────┬─────────┴────────────────────────┘               │
│                      │                                                   │
│  ┌───────────────────┴───────────────────────────────────────────────┐  │
│  │                    Telemetry Context + DuckDB.wasm                 │  │
│  └───────────────────────────────┬───────────────────────────────────┘  │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │ WebSocket
                                   │ (JSON, 10-50 Hz)
┌──────────────────────────────────┼──────────────────────────────────────┐
│                        Backend (Python + FastAPI)                        │
│  ┌───────────────────────────────┴───────────────────────────────────┐  │
│  │                      WebSocket Manager                             │  │
│  └───────────────────────────────┬───────────────────────────────────┘  │
│                                  │                                       │
│  ┌───────────────────────────────┴───────────────────────────────────┐  │
│  │                      Simulation Engine                             │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │  │
│  │  │ Dynamics    │  │ Actuators   │  │ Controllers │               │  │
│  │  │ - Attitude  │  │ - MTQ       │  │ - B-dot     │               │  │
│  │  │ - Orbit     │  │ - RW        │  │ - PD        │               │  │
│  │  │ - Env       │  │             │  │ - Unload    │               │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## 4. Directory Structure

```
simple-cubesat-sim/
├── DESIGN.md
├── README.md
├── pyproject.toml
├── uv.lock
│
├── backend/
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Configuration
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── simulation.py      # REST: /simulation/*
│   │   │   └── websocket.py       # WS: /ws/telemetry
│   │   └── schemas/
│   │       ├── __init__.py
│   │       ├── simulation.py
│   │       └── telemetry.py
│   │
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── engine.py              # Main simulation loop
│   │   ├── spacecraft.py          # 6U CubeSat model
│   │   └── time_manager.py        # Simulation time
│   │
│   ├── dynamics/
│   │   ├── __init__.py
│   │   ├── quaternion.py          # Quaternion operations
│   │   ├── attitude.py            # Euler equations + RK4
│   │   ├── orbit.py               # SGP4 propagation
│   │   └── environment.py         # IGRF magnetic field
│   │
│   ├── actuators/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── magnetorquer.py        # 3-axis MTQ
│   │   └── reaction_wheel.py      # 3-axis RW
│   │
│   ├── sensors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── magnetometer.py
│   │   └── gyroscope.py
│   │
│   ├── control/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── bdot.py                # B-dot detumbling
│   │   ├── attitude_controller.py # 3-axis PD control
│   │   └── rw_unloading.py        # MTQ momentum dump
│   │
│   └── utils/
│       ├── __init__.py
│       ├── frames.py              # Coordinate transforms
│       └── constants.py           # Physical constants
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_quaternion.py
│   │   ├── test_bdot.py
│   │   ├── test_attitude_controller.py
│   │   ├── test_rw_unloading.py
│   │   ├── test_magnetorquer.py
│   │   └── test_reaction_wheel.py
│   └── integration/
│       ├── __init__.py
│       ├── test_simulation_engine.py
│       └── test_detumbling_scenario.py
│
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── components/
        │   ├── layout/
        │   │   ├── Header.tsx
        │   │   ├── Sidebar.tsx
        │   │   └── MainLayout.tsx
        │   ├── visualization/
        │   │   ├── SatelliteView.tsx
        │   │   ├── GlobeView.tsx
        │   │   └── AttitudeIndicator.tsx
        │   ├── charts/
        │   │   ├── TimeSeriesChart.tsx
        │   │   ├── AngularVelocityChart.tsx
        │   │   ├── ReactionWheelChart.tsx
        │   │   └── QuaternionChart.tsx
        │   └── controls/
        │       ├── SimulationControls.tsx
        │       ├── TimeControls.tsx
        │       └── ModeSelector.tsx
        ├── hooks/
        │   ├── useWebSocket.ts
        │   ├── useTelemetry.ts
        │   ├── useDuckDB.ts
        │   └── useSimulationState.ts
        ├── services/
        │   ├── websocket.ts
        │   ├── api.ts
        │   └── telemetryStore.ts
        ├── types/
        │   ├── telemetry.ts
        │   ├── simulation.ts
        │   └── spacecraft.ts
        └── utils/
            ├── quaternion.ts
            └── constants.ts
```

## 5. Spacecraft Model (6U CubeSat)

### 5.1 Physical Parameters

```python
# 6U CubeSat dimensions: 10cm x 20cm x 30cm
MASS = 12.0  # kg (typical 6U mass)

# Inertia tensor (principal axes, kg*m^2)
INERTIA = np.diag([
    0.05,   # Ixx (around smallest dimension)
    0.05,   # Iyy
    0.02    # Izz (around longest dimension)
])
```

### 5.2 Actuators

#### Magnetorquer (MTQ)
- 3-axis configuration
- Max dipole moment: 0.2 Am^2 per axis
- Torque: T = m × B (cross product with magnetic field)

#### Reaction Wheel (RW)
- 3-axis configuration
- Max angular momentum: 0.01 Nms per axis
- Max torque: 0.001 Nm per axis
- Max speed: 6000 RPM

### 5.3 Sensors

#### Magnetometer
- 3-axis measurement
- Noise: 100 nT (1σ)
- Bias: configurable

#### Gyroscope
- 3-axis angular velocity
- Noise: 0.01 deg/s (1σ)
- Bias drift: 0.1 deg/hr

## 6. Control Algorithms

### 6.1 B-dot Detumbling Control

デタンブリング制御は、衛星放出直後の高角速度状態から低角速度状態へ減速するために使用。

```
Control Law:
    m = -k * dB/dt

where:
    m: commanded dipole moment (Am^2)
    k: control gain
    dB/dt: time derivative of magnetic field in body frame (T/s)

Physical Principle:
    T = m × B
    When m ∝ -dB/dt, the resulting torque opposes angular velocity,
    dissipating rotational kinetic energy.
```

**Implementation Notes:**
- dB/dt は磁力計の時間差分から計算
- ゲイン k は典型的に 1e5 ~ 1e7 の範囲
- MTQ 飽和を考慮した出力制限が必要

### 6.2 3-Axis Attitude Control (PD)

RW を使用した姿勢制御。クォータニオンエラーフィードバック方式。

```
Control Law:
    T_cmd = -Kp * q_err_vec - Kd * omega

where:
    T_cmd: commanded torque to reaction wheels (Nm)
    Kp: proportional gain matrix
    Kd: derivative gain matrix
    q_err_vec: vector part of quaternion error (q_target^-1 * q_current)
    omega: angular velocity in body frame (rad/s)

Quaternion Error:
    q_err = q_target^-1 ⊗ q_current
    If q_err.w < 0, negate q_err (shortest path)
```

**Typical Gains:**
- Kp: 0.01 ~ 0.1 (depends on inertia)
- Kd: 0.1 ~ 1.0 (critical damping)

### 6.3 RW Momentum Unloading

RW に蓄積された角運動量を MTQ を使って放出。

```
Control Law:
    m = k * (B × H_rw) / |B|^2

where:
    m: commanded dipole moment (Am^2)
    k: unloading gain
    B: magnetic field vector (T)
    H_rw: total RW momentum vector (Nms)

Physical Principle:
    MTQ torque T_mtq = m × B is used to absorb RW momentum
    while minimizing attitude disturbance.
```

**Implementation Notes:**
- アンローディングは姿勢制御と並行して動作可能
- B-field と H_rw の方向関係により効率が変化
- 地磁気の強い領域（高緯度）でより効果的

## 7. Orbit Model

### 7.1 Sun-Synchronous Orbit (SSO)

```
Typical Parameters:
    Altitude: 500-600 km
    Inclination: ~97.4° (for 550 km)
    Period: ~95 minutes
    LTAN: 10:30 (typical for Earth observation)
```

### 7.2 Propagation

SGP4 または簡易 Kepler 伝播を使用。

```python
# TLE example for SSO
TLE_LINE1 = "1 99999U 24001A   24001.00000000  .00000000  00000-0  00000-0 0    09"
TLE_LINE2 = "2 99999  97.4000 000.0000 0001000   0.0000   0.0000 15.00000000    07"
```

### 7.3 Magnetic Field Model

IGRF (International Geomagnetic Reference Field) を使用。

```
Field Strength (typical LEO):
    |B| ≈ 25-65 μT
    Varies with latitude and altitude
```

## 8. WebSocket Protocol

### 8.1 Message Types

#### Server → Client

```typescript
// Telemetry (10-50 Hz)
interface TelemetryMessage {
  type: "telemetry";
  timestamp: number;         // Simulation time (s)
  wallTime: number;          // Wall-clock time (ms)

  attitude: {
    quaternion: [number, number, number, number];  // [x, y, z, w]
    angularVelocity: [number, number, number];     // rad/s, body frame
    eulerAngles: [number, number, number];         // deg [roll, pitch, yaw]
  };

  orbit: {
    position: [number, number, number];   // ECI, km
    velocity: [number, number, number];   // ECI, km/s
    latitude: number;                     // deg
    longitude: number;                    // deg
    altitude: number;                     // km
  };

  actuators: {
    reactionWheels: {
      speed: [number, number, number];     // rad/s
      torque: [number, number, number];    // Nm
      momentum: [number, number, number];  // Nms
    };
    magnetorquers: {
      dipoleMoment: [number, number, number];  // Am^2
      power: number;                           // W
    };
  };

  sensors: {
    magnetometer: {
      field: [number, number, number];  // T, body frame
    };
    gyroscope: {
      angularVelocity: [number, number, number];  // rad/s (with noise)
    };
  };

  environment: {
    magneticField: [number, number, number];  // T, ECI
    sunVector: [number, number, number];      // unit vector, ECI
    eclipse: boolean;
  };

  control: {
    mode: "DETUMBLING" | "POINTING" | "UNLOADING" | "IDLE";
    targetQuaternion?: [number, number, number, number];
    error?: {
      attitude: number;   // deg
      rate: number;       // rad/s
    };
  };
}

// Status Update
interface StatusMessage {
  type: "status";
  state: "RUNNING" | "PAUSED" | "STOPPED" | "ERROR";
  simTime: number;
  timeWarp: number;
  message?: string;
}
```

#### Client → Server

```typescript
// Control Command
interface ControlCommand {
  type: "command";
  command: "START" | "STOP" | "PAUSE" | "RESET";
}

// Mode Change
interface ModeChangeCommand {
  type: "mode";
  mode: "DETUMBLING" | "POINTING" | "UNLOADING" | "IDLE";
  params?: {
    targetQuaternion?: [number, number, number, number];
    gains?: Record<string, number>;
  };
}

// Configuration
interface ConfigCommand {
  type: "config";
  timeWarp?: number;
  telemetryRate?: number;  // Hz
}
```

### 8.2 REST API

```
GET  /api/simulation/state          # Current state
POST /api/simulation/start          # Start
POST /api/simulation/stop           # Stop
POST /api/simulation/reset          # Reset
PUT  /api/simulation/config         # Update config
GET  /api/spacecraft/config         # Spacecraft params
```

## 9. Testing Strategy

### 9.1 TDD Approach

全ての制御アルゴリズムは TDD で開発する。

```
Red-Green-Refactor Cycle:
1. Write failing test
2. Implement minimal code to pass
3. Refactor for clarity
```

### 9.2 Test Categories

| Category | Purpose | Coverage Target |
|----------|---------|-----------------|
| Unit | Individual functions | >90% |
| Component | Module with mocks | >80% |
| Integration | Subsystem interactions | Key scenarios |
| Property-based | Invariants | Math operations |

### 9.3 Key Test Cases

#### B-dot Controller
- Zero dB/dt → zero dipole
- Positive dB/dt → negative dipole (control law)
- Saturation limits respected
- Energy dissipation direction

#### Attitude Controller
- Zero error → zero torque
- Quaternion error shortest path
- Asymptotic convergence
- Gain tuning effects

#### RW Unloading
- Momentum reduction over time
- MTQ saturation handling
- Attitude disturbance minimization

## 10. Dependencies

### Python (Backend)
```toml
[project]
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "websockets>=12.0",
    "numpy>=1.26.0",
    "scipy>=1.12.0",
    "sgp4>=2.23",
    "pydantic>=2.5.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "hypothesis>=6.98.0",
    "ruff>=0.2.0",
]
```

### JavaScript (Frontend)
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "three": "^0.161.0",
    "@react-three/fiber": "^8.15.0",
    "@react-three/drei": "^9.96.0",
    "globe.gl": "^2.27.0",
    "plotly.js": "^2.29.0",
    "react-plotly.js": "^2.6.0",
    "@duckdb/duckdb-wasm": "^1.28.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "@types/react": "^18.2.0"
  }
}
```

## 11. Implementation Status

### 11.1 Completed Components

| Phase | Component | Status | Tests |
|-------|-----------|--------|-------|
| Phase 1 | Project Setup | ✅ Done | - |
| Phase 1 | DESIGN.md | ✅ Done | - |
| Phase 1 | Python project (uv) | ✅ Done | - |
| Phase 1 | Frontend (React + Vite) | ✅ Done | - |
| Phase 2 | `quaternion.py` | ✅ Done | 22 |
| Phase 3 | `magnetorquer.py` | ✅ Done | 15 |
| Phase 3 | `reaction_wheel.py` | ✅ Done | 20 |
| Phase 4 | `bdot.py` | ✅ Done | 22 |
| Phase 4 | `attitude_controller.py` | ✅ Done | 17 |
| Phase 4 | `rw_unloading.py` | ✅ Done | 11 |
| Phase 5 | `spacecraft.py` | ✅ Done | 19 |
| Phase 5 | `engine.py` | ✅ Done | 26 |
| Phase 5 | FastAPI backend + WebSocket | ✅ Done | - |
| Phase 6 | Frontend WebSocket integration | ✅ Done | - |

**Total Tests: 152 (all passing)**

### 11.2 Test Coverage Highlights

#### B-dot Controller
- Basic control law verification
- Saturation limits
- **Energy dissipation simulation** (angular velocity reduction over time)
- Detumbling convergence test (10 minutes simulation)

#### Reaction Wheel
- Basic dynamics (speed, momentum, torque)
- **Angular momentum conservation** (L_total = I_sc * ω_sc + I_rw * ω_rw = const)
- **Spacecraft attitude change** (quaternion integration with RW torque)
- Saturation limits

#### Attitude Controller
- Quaternion error calculation (shortest path)
- PD control law verification
- **Closed-loop convergence** (attitude error reduction simulation)
- **Rate damping** (angular velocity reduction simulation)

#### RW Unloading
- Unloading control law verification
- Torque direction alignment
- **Momentum reduction simulation**

### 11.3 Git Commits

```
a45f410 Add frontend WebSocket integration and telemetry display
a4cc57d Add spacecraft model, simulation engine, and FastAPI backend
9c55436 Add RW momentum unloading controller with TDD
db54da4 Add 3-axis attitude controller with TDD
2a3fafa Add magnetorquer and reaction wheel models with TDD
e89f0fd Add B-dot detumbling controller with TDD
99a46cb Initial project setup with quaternion module (TDD)
```

### 11.4 Remaining Tasks

| Phase | Component | Status |
|-------|-----------|--------|
| Phase 2 | `attitude.py` (Euler equations + RK4) | ⏳ Pending (basic dynamics in spacecraft.py) |
| Phase 2 | `orbit.py` (SGP4) | ⏳ Pending |
| Phase 2 | `environment.py` (IGRF) | ⏳ Pending (using constant field) |
| Phase 3 | `magnetometer.py` | ⏳ Pending |
| Phase 3 | `gyroscope.py` | ⏳ Pending |
| Phase 7 | 3D visualization (Three.js + globe.gl) | ⏳ Pending |
| Phase 8 | Charts + DuckDB.wasm | ⏳ Pending |

## 12. Future Extensions

- Sun sensor model
- Star tracker model
- Orbit maneuvers (thrusters)
- Power system simulation
- Thermal model
- Ground station communication windows
- Multiple satellite simulation
