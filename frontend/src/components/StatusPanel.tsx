import { useMemo } from "react";
import { useSimulationStore } from "../store/simulationStore";
import type { WorkerEvent } from "../types";
import { formatStepTimestamp } from "../utils/time";

const RECENT_COUNT = 5;

const EVENT_BADGE: Record<string, string> = {
  warning_issued: "WARNED",
  entry_blocked: "BLOCKED",
};

interface Stats {
  activeRiskEvents: number;
  restrictedZones: number;
  recentEvents: WorkerEvent[];
}

/** Live dashboard summary for the currently-scrubbed timestamp — the one
 * place the risk heatmap (active risk events), the zone restriction system
 * (restricted zones), and the worker warning log (recent entries) are tied
 * back together. Everything here reads the same `currentStep` the 3D scene
 * and the time scrubber use, so it updates in lockstep with them rather
 * than drifting on its own clock. */
export function StatusPanel() {
  const data = useSimulationStore((s) => s.data);
  const currentStep = useSimulationStore((s) => s.currentStep);

  const stats = useMemo<Stats>(() => {
    if (!data) return { activeRiskEvents: 0, restrictedZones: 0, recentEvents: [] };

    let activeRiskEvents = 0;
    for (const oven of data.ovens) {
      const category = data.series[oven.oven_id]?.risk_category[currentStep] ?? 0;
      if (category > 0) activeRiskEvents++; // same medium/high gate the heatmap sprites use
    }

    let restrictedZones = 0;
    for (const zone of data.zones) {
      if (data.zone_status[zone.zone_id]?.[currentStep] === 1) restrictedZones++;
    }

    const recentEvents = data.events
      .filter((e) => e.step <= currentStep)
      .slice(-RECENT_COUNT)
      .reverse();

    return { activeRiskEvents, restrictedZones, recentEvents };
  }, [data, currentStep]);

  if (!data) return null;

  return (
    <aside className="status-panel">
      <div className="status-panel__stats">
        <StatTile
          label="Active risk events"
          value={stats.activeRiskEvents}
          tone={stats.activeRiskEvents > 0 ? "warning" : "good"}
        />
        <StatTile
          label="Restricted zones"
          value={stats.restrictedZones}
          tone={stats.restrictedZones > 0 ? "critical" : "good"}
        />
      </div>

      <div className="status-panel__log">
        <div className="status-panel__log-header">
          <h3>Recent Warnings</h3>
          <span className="muted tabular">{formatStepTimestamp(data.meta, currentStep)}</span>
        </div>
        <div className="status-panel__list">
          {stats.recentEvents.length === 0 && (
            <p className="muted status-panel__empty">No zone warnings or blocked entries yet.</p>
          )}
          {stats.recentEvents.map((e) => (
            <div key={e.event_id} className={`status-panel__row status-panel__row--${e.event_type}`}>
              <div className="status-panel__row-top">
                <span className="status-panel__badge">{EVENT_BADGE[e.event_type] ?? e.event_type}</span>
                <time className="muted tabular">{formatStepTimestamp(data.meta, e.step)}</time>
              </div>
              <p className="status-panel__message">{e.message}</p>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}

function StatTile({ label, value, tone }: { label: string; value: number; tone: "good" | "warning" | "critical" }) {
  return (
    <div className={`stat-tile stat-tile--${tone}`}>
      <span className="stat-tile__value tabular">{value}</span>
      <span className="stat-tile__label">{label}</span>
    </div>
  );
}
