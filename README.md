# Simple CubeSat Simulator

Web-based 6U CubeSat attitude control simulator.

## Features

- 3D satellite visualization (Three.js)
- Earth and orbit visualization (globe.gl)
- Real-time attitude control simulation
  - B-dot detumbling
  - 3-axis attitude control (Reaction Wheels)
  - RW momentum unloading (Magnetorquers)
- Time-series telemetry visualization (Plotly.js)
- Client-side data storage (DuckDB.wasm)

## Tech Stack

- **Frontend**: React + TypeScript + Vite
- **Backend**: Python + FastAPI + WebSockets
- **Visualization**: Three.js, globe.gl, Plotly.js
- **Database**: DuckDB.wasm

## Setup

### Backend (Python)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Run tests
uv run pytest

# Start backend server
uv run uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Hardware Visualization (Optional)

To visualize reaction wheel rotation with a physical motor using Raspberry Pi Pico:

1. Flash firmware to Pico:
   ```bash
   cd pico-rw-mock
   cargo run --release
   ```

2. Start backend (Pico will be auto-detected):
   ```bash
   uv run uvicorn backend.main:app --reload
   ```

Backend will automatically detect and use connected Pico device.
See [pico-rw-mock/README.md](pico-rw-mock/README.md) for hardware setup details.

## Development

This project follows TDD (Test-Driven Development) approach for control algorithms.

See [DESIGN.md](DESIGN.md) for detailed design documentation.
