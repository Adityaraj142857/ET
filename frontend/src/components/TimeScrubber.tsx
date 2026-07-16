import { useEffect, useMemo } from "react";
import { useSimulationStore } from "../store/simulationStore";
import { formatElapsed, formatStepTimestamp } from "../utils/time";

const TICK_MS = 150;
const SPEED_OPTIONS = [
  { label: "1x", stepsPerTick: 1 },
  { label: "4x", stepsPerTick: 4 },
  { label: "16x", stepsPerTick: 16 },
];

/** Precomputes which steps had at least one oven at "high" (compound)
 * risk — a real alarm-history log derived from the engine's own output,
 * not an oracle. Only ticks at or before the current step are drawn, so
 * playback never previews an alarm before it "happens". */
function useHighRiskSteps(): boolean[] {
  const data = useSimulationStore((s) => s.data);
  return useMemo(() => {
    if (!data) return [];
    const flags = new Array(data.meta.n_steps).fill(false);
    for (const series of Object.values(data.series)) {
      series.risk_category.forEach((cat, i) => {
        if (cat === 2) flags[i] = true;
      });
    }
    return flags;
  }, [data]);
}

export function TimeScrubber() {
  const data = useSimulationStore((s) => s.data);
  const currentStep = useSimulationStore((s) => s.currentStep);
  const playing = useSimulationStore((s) => s.playing);
  const speedStepsPerTick = useSimulationStore((s) => s.speedStepsPerTick);
  const setStep = useSimulationStore((s) => s.setStep);
  const advanceStep = useSimulationStore((s) => s.advanceStep);
  const togglePlaying = useSimulationStore((s) => s.togglePlaying);
  const setSpeed = useSimulationStore((s) => s.setSpeed);

  const highRiskSteps = useHighRiskSteps();

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(advanceStep, TICK_MS);
    return () => window.clearInterval(id);
  }, [playing, advanceStep]);

  if (!data) return null;

  const n = data.meta.n_steps;
  const atEnd = currentStep >= n - 1;

  return (
    <div className="time-scrubber">
      <button
        className="play-button"
        onClick={() => {
          if (atEnd) setStep(0);
          togglePlaying();
        }}
        aria-label={playing ? "Pause" : "Play"}
      >
        {playing ? "⏸" : atEnd ? "↺" : "▶"}
      </button>

      <div className="time-scrubber__track">
        <div className="time-scrubber__ticks">
          {highRiskSteps.map((isHigh, i) =>
            isHigh && i <= currentStep ? (
              <div key={i} className="time-scrubber__tick" style={{ left: `${(i / (n - 1)) * 100}%` }} />
            ) : null
          )}
        </div>
        <input
          type="range"
          min={0}
          max={n - 1}
          value={currentStep}
          onChange={(e) => setStep(Number(e.target.value))}
          aria-label="Simulation time"
        />
      </div>

      <div className="time-scrubber__readout">
        <span className="tabular">{formatElapsed(data.meta, currentStep)}</span>
        <span className="muted">{formatStepTimestamp(data.meta, currentStep)}</span>
      </div>

      <div className="speed-select" role="group" aria-label="Playback speed">
        {SPEED_OPTIONS.map((opt) => (
          <button
            key={opt.label}
            className={speedStepsPerTick === opt.stepsPerTick ? "speed-select__btn active" : "speed-select__btn"}
            onClick={() => setSpeed(opt.stepsPerTick)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
