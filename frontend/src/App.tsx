import { useEffect, useState } from 'react'
import { Panel, Group, Separator } from 'react-resizable-panels'
import { SimulationControls } from './components/SimulationControls'
import { TimelinePanel } from './components/timeline'
import { PointingConfigPanel } from './components/PointingConfigPanel'
import { SatelliteView } from './components/visualization/SatelliteView'
import { GlobeView } from './components/visualization/GlobeView'
import { TelemetryCharts } from './components/charts/TelemetryCharts'
import { useTelemetry } from './hooks/useTelemetry'
import { useTelemetryHistory } from './hooks/useTelemetryHistory'
import { useOrbitHistory } from './hooks/useOrbitHistory'
import { useTimeline } from './hooks/useTimeline'
import './App.css'

type ViewMode = 'attitude' | 'orbit';
type ViewCenter = 'earth' | 'satellite';

function App() {
  const telemetryState = useTelemetry();
  const { history, addTelemetry, clear } = useTelemetryHistory();
  const { history: orbitHistory, addTelemetry: addOrbitTelemetry, clear: clearOrbitHistory } = useOrbitHistory();
  const { addAction, removeAction, refreshContact, setImagingPreset } = useTimeline();
  const [viewMode, setViewMode] = useState<ViewMode>('attitude');
  const [viewCenter, setViewCenter] = useState<ViewCenter>('satellite');

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
          <TimelinePanel
            telemetry={telemetryState.telemetry}
            isConnected={telemetryState.isConnected}
            onAddAction={addAction}
            onRemoveAction={removeAction}
            onRefreshContact={refreshContact}
            onSetImagingPreset={setImagingPreset}
          />
          <PointingConfigPanel isConnected={telemetryState.isConnected} />
        </aside>

        <div className="content-area">
          <Group orientation="vertical" id="cubesat-layout" style={{ flex: 1 }}>
            <Panel defaultSize={66} minSize={20}>
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
                  {viewMode === 'orbit' && (
                    <>
                      <button
                        className={viewCenter === 'earth' ? 'active' : ''}
                        onClick={() => setViewCenter('earth')}
                      >
                        Earth
                      </button>
                      <button
                        className={viewCenter === 'satellite' ? 'active' : ''}
                        onClick={() => setViewCenter('satellite')}
                      >
                        Satellite
                      </button>
                    </>
                  )}
                </div>
                {viewMode === 'attitude' ? (
                  <SatelliteView telemetry={telemetryState.telemetry} />
                ) : (
                  <GlobeView telemetry={telemetryState.telemetry} orbitHistory={orbitHistory} viewCenter={viewCenter} onViewCenterChange={setViewCenter} />
                )}
              </section>
            </Panel>
            <Separator className="resize-handle" />
            <Panel defaultSize={34} minSize={15}>
              <section className="charts">
                <TelemetryCharts history={history} />
              </section>
            </Panel>
          </Group>
        </div>
      </main>
    </div>
  )
}

export default App
