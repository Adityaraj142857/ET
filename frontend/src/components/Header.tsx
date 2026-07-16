import { useSimulationStore } from "../store/simulationStore";

/** Persistent synthetic-data disclosure: Section 7 of the project spec is
 * explicit that this must never be mistakable for a live SCADA feed. This
 * banner is not a footnote — it's always visible, next to the title. */
export function Header() {
  const data = useSimulationStore((s) => s.data);

  return (
    <header className="app-header">
      <div>
        <h1>Compound Risk Detection — Coke Oven Battery {data?.meta.battery_id ?? ""}</h1>
        <p className="muted">
          {data ? `${data.meta.n_ovens} ovens · rule-based 3-factor compound risk engine` : "Loading…"}
        </p>
      </div>
      <span className="synthetic-badge">SYNTHETIC DATA — NOT LIVE SCADA</span>
    </header>
  );
}
