import { useSceneData } from "./hooks/useSceneData";
import { useSimulationStore } from "./store/simulationStore";
import { Header } from "./components/Header";
import { Scene } from "./components/Scene";
import { DetailPanel } from "./components/DetailPanel";
import { StatusPanel } from "./components/StatusPanel";
import { TimeScrubber } from "./components/TimeScrubber";
import { Legend } from "./components/Legend";
import { SafetyIntelligence } from "./components/SafetyIntelligence";

export default function App() {
  useSceneData();
  const loading = useSimulationStore((s) => s.loading);
  const error = useSimulationStore((s) => s.error);
  const tab = useSimulationStore((s) => s.activeTab);
  const setActiveTab = useSimulationStore((s) => s.setActiveTab);

  return (
    <div className="app">
      <Header />
      <nav className="app-tabs">
        <button
          className={`app-tabs__tab ${tab === "simulation" ? "app-tabs__tab--active" : ""}`}
          onClick={() => setActiveTab("simulation")}
        >
          Live Simulation
        </button>
        <button
          className={`app-tabs__tab ${tab === "assistant" ? "app-tabs__tab--active" : ""}`}
          onClick={() => setActiveTab("assistant")}
        >
          Safety Intelligence Assistant
        </button>
      </nav>

      {tab === "simulation" ? (
        <>
          <div className="app__body">
            <div className="scene-container">
              {loading && <div className="overlay-message">Loading simulation data…</div>}
              {error && (
                <div className="overlay-message overlay-message--error">
                  Couldn't load scene data.
                  <br />
                  {error}
                </div>
              )}
              {!loading && !error && <Scene />}
            </div>
            <DetailPanel />
            <StatusPanel />
          </div>
          <footer className="app__footer">
            <Legend />
            <TimeScrubber />
          </footer>
        </>
      ) : (
        <SafetyIntelligence />
      )}
    </div>
  );
}
