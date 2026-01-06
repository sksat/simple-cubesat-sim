# Phase 4: UI Enhancement Implementation Plan

## Overview

Enhance the UI with satellite status display, reorganized view controls, and detailed 3-axis pointing configuration.

## Current State Analysis

### Backend
- Full main/sub axis support via `PointingConfig` class ([backend/control/attitude_target.py](backend/control/attitude_target.py))
- Simplified "presets" via `PointingMode` type (MANUAL, SUN, NADIR, GROUND_STATION, IMAGING_TARGET)
- Each preset maps to a predefined main/sub axis configuration
- Body axes: `[1,0,0]` = +X, `[0,1,0]` = +Y, `[0,0,1]` = +Z (and negatives)
- Target directions: `SUN, EARTH_CENTER, GROUND_STATION, IMAGING_TARGET, VELOCITY, ORBIT_NORMAL`

### Frontend
- Only exposes simplified PointingMode presets in dropdown
- Control selection in [SimulationControls.tsx](frontend/src/components/SimulationControls.tsx) sidebar
- View center toggle buttons in orbit overlay at top-left ([GlobeView.tsx:542-555](frontend/src/components/visualization/GlobeView.tsx#L542-L555))
- No UI for detailed main/sub axis configuration

## Tasks

### Task 1: Satellite Status Display

**Goal:** Add compact status overlay showing real-time satellite state

**Location:** Top-left in both attitude and orbit views

**Design:**
```
┌─────────────────────────────┐
│ MODE: POINTING (SUN)        │
│ COMM: GS ✓  PWR: 85% +2.5W  │
│ ERR: Att 2.3° Rate 0.15°/s  │
└─────────────────────────────┘
```

**Implementation:**

1. Create new component `frontend/src/components/StatusOverlay.tsx`:
   - Props: `telemetry: Telemetry | null`
   - Display format:
     - Line 1: `MODE: {controlMode} ({pointingMode})`
     - Line 2: `COMM: GS {visible ? '✓' : '✗'}  PWR: {soc}% {netPower >= 0 ? '⚡' : '🔋'}{netPower}W {eclipse ? '🌑' : '☀️'}`
     - Line 3: `ERR: Att {attError}° Rate {rateError}°/s`
   - Style: monospace, compact, semi-transparent background like attitude-overlay

2. Add to [SatelliteView.tsx](frontend/src/components/visualization/SatelliteView.tsx) (replace or modify existing attitude-overlay)

3. Add to [GlobeView.tsx](frontend/src/components/visualization/GlobeView.tsx) (modify orbit-overlay)

4. Add CSS to [App.css](frontend/src/App.css):
   ```css
   .status-overlay {
     position: absolute;
     top: 1rem;
     left: 1rem;
     background: rgba(0, 0, 0, 0.7);
     padding: 0.75rem 1rem;
     border-radius: 4px;
     font-family: monospace;
     font-size: 0.875rem;
     color: #fff;
     z-index: 10;
   }
   ```

**Files to modify:**
- `frontend/src/components/StatusOverlay.tsx` (new)
- `frontend/src/components/visualization/SatelliteView.tsx`
- `frontend/src/components/visualization/GlobeView.tsx`
- `frontend/src/App.css`

### Task 2: Move Center Button to Top-Right

**Goal:** Relocate view center toggle (Earth/Satellite) from orbit overlay to top-right

**Current:** View center toggle is in orbit overlay at top-left ([GlobeView.tsx:542-555](frontend/src/components/visualization/GlobeView.tsx#L542-L555))

**New:** Place next to Attitude/Orbit toggle at top-right (only visible in Orbit view)

**Design:**
```
Top-right corner:
┌────────────────────────────────┐
│ [Attitude] [Orbit] [Earth] [Sat] │
└────────────────────────────────┘
```

**Implementation:**

1. Modify [GlobeView.tsx](frontend/src/components/visualization/GlobeView.tsx):
   - Remove `view-center-toggle` from `OrbitOverlay` component (lines 542-555)
   - Pass `viewCenter` and `onViewCenterChange` as props to parent (App.tsx)
   - Keep orbit position/time info in overlay

2. Modify [App.tsx](frontend/src/App.tsx):
   - Add `viewCenter` state and handlers
   - Modify visualization section to show center toggle when `viewMode === 'orbit'`
   - Structure:
     ```tsx
     <div className="view-mode-toggle">
       <button onClick={() => setViewMode('attitude')}>Attitude</button>
       <button onClick={() => setViewMode('orbit')}>Orbit</button>
       {viewMode === 'orbit' && (
         <>
           <button onClick={() => setViewCenter('earth')}>Earth</button>
           <button onClick={() => setViewCenter('satellite')}>Satellite</button>
         </>
       )}
     </div>
     ```

3. CSS already exists in [App.css](frontend/src/App.css) (lines 254-285), no changes needed

**Files to modify:**
- `frontend/src/App.tsx`
- `frontend/src/components/visualization/GlobeView.tsx`

### Task 3: 3-Axis Control UI

**Goal:** Expose full main/sub axis configuration in UI

**Location:** New collapsible panel in sidebar (below TimelinePanel)

**Design:**
```
┌─────────────────────────────────┐
│ ▼ Pointing Configuration        │
│                                  │
│ Presets: [SUN] [NADIR] [GS] [IMG] │
│                                  │
│ Main Axis:                       │
│   Target:    [SUN ▼]             │
│   Body Axis: [+Z ▼]              │
│                                  │
│ Sub Axis:                        │
│   Target:    [NADIR ▼]           │
│   Body Axis: [+X ▼]              │
│                                  │
│ [Apply Configuration]            │
└─────────────────────────────────┘
```

**Implementation:**

1. **Backend changes:**

   a. Add new websocket handler in [backend/api/routes/websocket.py](backend/api/routes/websocket.py):
   ```python
   elif message_type == "pointing_config":
       main_target = message.get("mainTarget", "SUN")
       main_body_axis = message.get("mainBodyAxis", [0, 0, 1])
       sub_target = message.get("subTarget", "EARTH_CENTER")
       sub_body_axis = message.get("subBodyAxis", [1, 0, 0])

       engine.set_pointing_config(
           main_target=main_target,
           main_body_axis=main_body_axis,
           sub_target=sub_target,
           sub_body_axis=sub_body_axis,
       )
       await send_status(websocket, engine)
   ```

   b. Add method to [backend/simulation/engine.py](backend/simulation/engine.py):
   ```python
   def set_pointing_config(
       self,
       main_target: str,
       main_body_axis: list[float],
       sub_target: str,
       sub_body_axis: list[float],
   ) -> None:
       """Set detailed pointing configuration with main/sub axis."""
       from backend.control.target_direction import TargetDirection
       import numpy as np

       # Convert string to TargetDirection enum
       main_dir = TargetDirection[main_target]
       sub_dir = TargetDirection[sub_target]

       config = PointingConfig(
           main_target=main_dir,
           sub_target=sub_dir,
           main_body_axis=np.array(main_body_axis),
           sub_body_axis=np.array(sub_body_axis),
           ground_station=self._ground_station,
           imaging_target=self._imaging_target,
       )
       self._attitude_target_calc.set_config(config)
       self._pointing_mode = "MANUAL"  # Custom config
   ```

2. **Frontend changes:**

   a. Add types to [frontend/src/types/telemetry.ts](frontend/src/types/telemetry.ts):
   ```typescript
   export type TargetDirection =
     | 'SUN'
     | 'EARTH_CENTER'
     | 'GROUND_STATION'
     | 'IMAGING_TARGET'
     | 'VELOCITY'
     | 'ORBIT_NORMAL';

   export type BodyAxis =
     | [1, 0, 0]   // +X
     | [-1, 0, 0]  // -X
     | [0, 1, 0]   // +Y
     | [0, -1, 0]  // -Y
     | [0, 0, 1]   // +Z
     | [0, 0, -1]; // -Z

   export interface PointingConfig {
     mainTarget: TargetDirection;
     mainBodyAxis: BodyAxis;
     subTarget: TargetDirection;
     subBodyAxis: BodyAxis;
   }
   ```

   b. Add to websocket service [frontend/src/services/websocket.ts](frontend/src/services/websocket.ts):
   ```typescript
   setPointingConfig(config: PointingConfig): void {
     this.send({
       type: 'pointing_config',
       mainTarget: config.mainTarget,
       mainBodyAxis: config.mainBodyAxis,
       subTarget: config.subTarget,
       subBodyAxis: config.subBodyAxis,
     });
   }
   ```

   c. Create [frontend/src/components/PointingConfigPanel.tsx](frontend/src/components/PointingConfigPanel.tsx):
   - State: `mainTarget`, `mainBodyAxis`, `subTarget`, `subBodyAxis`
   - Preset buttons that set predefined configs
   - Dropdowns for custom config
   - Apply button calls `websocketService.setPointingConfig()`

   d. Create [frontend/src/components/PointingConfigPanel.css](frontend/src/components/PointingConfigPanel.css):
   - Similar styling to TimelinePanel
   - Compact form layout

   e. Modify [frontend/src/App.tsx](frontend/src/App.tsx):
   - Import and add `<PointingConfigPanel />` to sidebar
   - Pass `isConnected` prop

**Files to modify:**
- `backend/api/routes/websocket.py`
- `backend/simulation/engine.py`
- `frontend/src/types/telemetry.ts`
- `frontend/src/services/websocket.ts`
- `frontend/src/components/PointingConfigPanel.tsx` (new)
- `frontend/src/components/PointingConfigPanel.css` (new)
- `frontend/src/App.tsx`

**Test files:**
- `tests/integration/test_pointing_config.py` (new) - test custom pointing configs via websocket

## Implementation Order

1. **Task 1: Status Overlay** (simplest, no protocol changes)
   - Create StatusOverlay component
   - Integrate into views
   - Test display with existing telemetry

2. **Task 2: Move Center Button** (UI reorganization, no backend changes)
   - Refactor GlobeView/App.tsx
   - Test both view modes

3. **Task 3: 3-Axis Control UI** (most complex, new protocol)
   - Backend: Add websocket handler and engine method
   - Frontend: Add types, websocket method, component
   - Integration test
   - Test preset buttons work correctly

## Questions for User

1. Should the status overlay be always visible or toggle-able?
2. Should the PointingConfigPanel be collapsed by default?
3. Any specific text/icons for the status overlay display?
