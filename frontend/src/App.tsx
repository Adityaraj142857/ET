import { useState } from "react";
import { useSceneData } from "./hooks/useSceneData";
import { useSimulationStore } from "./store/simulationStore";
import { Header } from "./components/Header";
import { Scene } from "./components/Scene";
import { DetailPanel } from "./components/DetailPanel";
import { StatusPanel } from "./components/StatusPanel";
import { TimeScrubber } from "./components/TimeScrubber";
import { Legend } from "./components/Legend";
import { SafetyIntelligence } from "./components/SafetyIntelligence";

type Tab = "dashboard" | "safety-intel";

export default function App() {
  useSceneData();
  const loading = useSimulationStore((s) => s.loading);
  const error = useSimulationStore((s) => s.error);
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div className="app">
      <Header />
      <nav className="app-tabs">
        <button
          className={`app-tabs__tab ${tab === "dashboard" ? "app-tabs__tab--active" : ""}`}
          onClick={() => setTab("dashboard")}
        >
          3D Dashboard
        </button>
        <button
          className={`app-tabs__tab ${tab === "safety-intel" ? "app-tabs__tab--active" : ""}`}
          onClick={() => setTab("safety-intel")}
        >
          Safety Intelligence
        </button>
      </nav>

      {tab === "dashboard" ? (
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
