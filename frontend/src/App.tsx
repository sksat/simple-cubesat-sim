import { SimulationControls } from './components/SimulationControls'
import { SatelliteView } from './components/visualization/SatelliteView'
import { useTelemetry } from './hooks/useTelemetry'
import './App.css'

function App() {
  const telemetryState = useTelemetry();

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
          <div className="placeholder">
            <p>Time Series Charts</p>
            <p>(Coming Soon)</p>
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
