import { useMemo } from "react";
import { useSimulationStore } from "../store/simulationStore";
import { colorForCategory, RISK_CATEGORY_NAME, STATUS_GLYPH, STATUS_LABEL } from "../utils/color";
import { activePermitsForOven, allPermitsForOven } from "../utils/permits";
import { dateForStep } from "../utils/time";
import { assistantQueryFromRiskReason } from "../utils/assistantQuery";
import { Sparkline } from "./Sparkline";

const TRAILING_HOURS = 6;

export function DetailPanel() {
  const data = useSimulationStore((s) => s.data);
  const currentStep = useSimulationStore((s) => s.currentStep);
  const selectedOvenId = useSimulationStore((s) => s.selectedOvenId);
  const askAssistantAbout = useSimulationStore((s) => s.askAssistantAbout);

  const trailingSteps = data ? Math.round((TRAILING_HOURS * 60) / data.meta.interval_min) : 0;

  const context = useMemo(() => {
    if (!data || !selectedOvenId) return null;
    const oven = data.ovens.find((o) => o.oven_id === selectedOvenId);
    const series = data.series[selectedOvenId];
    if (!oven || !series) return null;

    const start = Math.max(0, currentStep - trailingSteps);
    const now = dateForStep(data.meta, currentStep);

    return {
      oven,
      series,
      coTrail: series.co_ppm.slice(start, currentStep + 1),
      lelTrail: series.lel_pct.slice(start, currentStep + 1),
      activePermits: activePermitsForOven(data.permits, selectedOvenId, now),
      allPermits: allPermitsForOven(data.permits, selectedOvenId),
    };
  }, [data, selectedOvenId, currentStep, trailingSteps]);

  if (!data) return null;

  if (!context) {
    return (
      <aside className="detail-panel detail-panel--empty">
        <p className="muted">Click an oven block to inspect its current readings, active permits, and risk reason.</p>
      </aside>
    );
  }

  const { oven, series, coTrail, lelTrail, activePermits, allPermits } = context;
  const riskCode = series.risk_category[currentStep];
  const categoryName = RISK_CATEGORY_NAME[riskCode];
  const co = series.co_ppm[currentStep];
  const lel = series.lel_pct[currentStep];
  const gasTemp = series.gas_temp_c[currentStep];
  const exhausterFault = series.exhauster_fault[currentStep] === 1;
  const maintenanceFlag = series.maintenance_flag[currentStep] === 1;
  const reason = series.risk_reason[currentStep];
  const coOver = co > data.meta.co_alert_ppm;
  const lelOver = lel > data.meta.lel_alert_pct;

  return (
    <aside className="detail-panel">
      <div className="detail-panel__header">
        <div>
          <h2>{oven.oven_id}</h2>
          <p className="muted">{oven.zone_id}</p>
        </div>
        <span className="status-badge" style={{ color: colorForCategory(riskCode), borderColor: colorForCategory(riskCode) }}>
          {STATUS_GLYPH[categoryName]} {STATUS_LABEL[categoryName]}
        </span>
      </div>

      <p className="detail-panel__reason">{reason}</p>

      <button
        type="button"
        className="detail-panel__ask-assistant"
        onClick={() => askAssistantAbout(assistantQueryFromRiskReason(oven.oven_id, reason))}
      >
        Ask Safety Assistant about this pattern →
      </button>

      <dl className="metric-grid">
        <MetricRow label="CO" value={`${co.toFixed(1)} ppm`} alert={coOver} alertLabel={`> ${data.meta.co_alert_ppm} ppm`} />
        <MetricRow
          label="Combustible gas"
          value={`${lel.toFixed(2)}% LEL`}
          alert={lelOver}
          alertLabel={`> ${data.meta.lel_alert_pct}% LEL`}
        />
        <MetricRow label="Raw gas temp" value={`${gasTemp.toFixed(0)}°C`} />
        <MetricRow label="Exhauster" value={exhausterFault ? "FAULT" : "Normal"} alert={exhausterFault} />
        <MetricRow label="Maintenance flag" value={maintenanceFlag ? "Active" : "—"} alert={maintenanceFlag} />
        <MetricRow label="Oven volume" value={`${oven.volume_m3} m³`} />
        <MetricRow label="Coal charge" value={`${oven.coal_charge_tons} t`} />
      </dl>

      <div className="sparkline-block">
        <p className="sparkline-block__label">CO ppm — trailing {TRAILING_HOURS}h</p>
        <Sparkline values={coTrail} color={coOver ? "#d03b3b" : "#3987e5"} thresholdValue={data.meta.co_alert_ppm} />
      </div>
      <div className="sparkline-block">
        <p className="sparkline-block__label">Combustible gas %LEL — trailing {TRAILING_HOURS}h</p>
        <Sparkline values={lelTrail} color={lelOver ? "#d03b3b" : "#3987e5"} thresholdValue={data.meta.lel_alert_pct} />
      </div>

      <div className="permit-block">
        <p className="permit-block__label">Active permits ({activePermits.length})</p>
        {activePermits.length === 0 && <p className="muted">None</p>}
        {activePermits.map((p) => (
          <PermitRow key={p.permit_id} permit={p} />
        ))}

        {allPermits.length > activePermits.length && (
          <details className="permit-block__history">
            <summary>All permits on file ({allPermits.length})</summary>
            {allPermits.map((p) => (
              <PermitRow key={p.permit_id} permit={p} />
            ))}
          </details>
        )}
      </div>
    </aside>
  );
}

function MetricRow({
  label,
  value,
  alert,
  alertLabel,
}: {
  label: string;
  value: string;
  alert?: boolean;
  alertLabel?: string;
}) {
  return (
    <div className={`metric-row${alert ? " metric-row--alert" : ""}`}>
      <dt>{label}</dt>
      <dd>
        <span className="tabular">{value}</span>
        {alert && <span className="metric-row__flag">{alertLabel ?? "ALERT"}</span>}
      </dd>
    </div>
  );
}

function PermitRow({ permit }: { permit: ReturnType<typeof allPermitsForOven>[number] }) {
  return (
    <div className={`permit-row permit-row--${permit.status}`}>
      <span className="permit-row__type">{permit.permit_type.replace(/_/g, " ")}</span>
      <span className="permit-row__status">{permit.status}</span>
      <span className="permit-row__valid muted">until {new Date(permit.valid_until).toISOString().slice(0, 16).replace("T", " ")} UTC</span>
    </div>
  );
}
