import { useEffect, useState } from 'react'
import { SimulationControls } from './components/SimulationControls'
import { SatelliteView } from './components/visualization/SatelliteView'
import { GlobeView } from './components/visualization/GlobeView'
import { TelemetryCharts } from './components/charts/TelemetryCharts'
import { useTelemetry } from './hooks/useTelemetry'
import { useTelemetryHistory } from './hooks/useTelemetryHistory'
import { useOrbitHistory } from './hooks/useOrbitHistory'
import './App.css'

type ViewMode = 'attitude' | 'orbit';

function App() {
  const telemetryState = useTelemetry();
  const { history, addTelemetry, clear } = useTelemetryHistory();
  const { history: orbitHistory, addTelemetry: addOrbitTelemetry, clear: clearOrbitHistory } = useOrbitHistory();
  const [viewMode, setViewMode] = useState<ViewMode>('attitude');

  // Add telemetry to history when received
  useEffect(() => {
    if (telemetryState.telemetry) {
      addTelemetry(telemetryState.telemetry);
      addOrbitTelemetry(telemetryState.telemetry);
    }
  }, [telemetryState.telemetry, addTelemetry, addOrbitTelemetry]);

  // Clear history on reset
  useEffect(() => {
    if (telemetryState.simulationState === 'STOPPED') {
      clear();
      clearOrbitHistory();
    }
  }, [telemetryState.simulationState, clear, clearOrbitHistory]);

  return (
    <div className="app">
      <header className="app-header">
        <h1>CubeSat Simulator</h1>
        <p>6U CubeSat Attitude Control Simulator</p>
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <SimulationControls telemetryState={telemetryState} />
        </aside>

        <section className="visualization">
          <div className="view-mode-toggle">
            <button
              className={viewMode === 'attitude' ? 'active' : ''}
              onClick={() => setViewMode('attitude')}
            >
              Attitude
            </button>
            <button
              className={viewMode === 'orbit' ? 'active' : ''}
              onClick={() => setViewMode('orbit')}
            >
              Orbit
            </button>
          </div>
          {viewMode === 'attitude' ? (
            <SatelliteView telemetry={telemetryState.telemetry} />
          ) : (
            <GlobeView telemetry={telemetryState.telemetry} orbitHistory={orbitHistory} />
          )}
        </section>

        <section className="charts">
          <TelemetryCharts history={history} />
        </section>
      </main>
    </div>
  )
}

export default App
