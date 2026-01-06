import { useEffect } from 'react'
import { SimulationControls } from './components/SimulationControls'
import { SatelliteView } from './components/visualization/SatelliteView'
import { TelemetryCharts } from './components/charts/TelemetryCharts'
import { useTelemetry } from './hooks/useTelemetry'
import { useTelemetryHistory } from './hooks/useTelemetryHistory'
import './App.css'

function App() {
  const telemetryState = useTelemetry();
  const { history, addTelemetry, clear } = useTelemetryHistory();

  // Add telemetry to history when received
  useEffect(() => {
    if (telemetryState.telemetry) {
      addTelemetry(telemetryState.telemetry);
    }
  }, [telemetryState.telemetry, addTelemetry]);

  // Clear history on reset
  useEffect(() => {
    if (telemetryState.simulationState === 'STOPPED') {
      clear();
    }
  }, [telemetryState.simulationState, clear]);

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
          <SatelliteView telemetry={telemetryState.telemetry} />
        </section>

        <section className="charts">
          <TelemetryCharts history={history} />
        </section>
      </main>
    </div>
  )
}

export default App
