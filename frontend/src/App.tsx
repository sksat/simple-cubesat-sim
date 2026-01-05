import { SimulationControls } from './components/SimulationControls'
import './App.css'

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>CubeSat Simulator</h1>
        <p>6U CubeSat Attitude Control Simulator</p>
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <SimulationControls />
        </aside>

        <section className="visualization">
          <div className="placeholder">
            <p>3D Visualization</p>
            <p>(Coming Soon)</p>
          </div>
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
