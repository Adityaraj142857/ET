// Mirrors the JSON shape written by compoundrisk/export_frontend.py.
// Keep this in lockstep with that module — it's the contract between the
// Python pipeline and this app.

export type RiskCategoryCode = 0 | 1 | 2; // low, medium, high — see meta.risk_categories
export type ZoneStatusCode = 0 | 1; // normal, restricted — see meta.zone_statuses

export interface SceneMeta {
  battery_id: string;
  n_ovens: number;
  sim_start: string; // ISO 8601, UTC (explicit "Z" suffix)
  interval_min: number;
  n_steps: number;
  co_alert_ppm: number;
  lel_alert_pct: number;
  oven_spacing_m: number;
  risk_categories: ["low", "medium", "high"];
  zone_statuses: ["normal", "restricted"];
}

export interface OvenMeta {
  oven_id: string;
  zone_id: string;
  x: number;
  y: number;
  z: number;
  volume_m3: number;
  coal_charge_tons: number;
}

export interface ZoneMeta {
  zone_id: string;
  x: number;
  y: number;
  z: number;
  zone_type: "oven_battery" | "coal_chemical_plant" | "exhauster_house";
}

export interface Permit {
  permit_id: string;
  oven_id: string;
  permit_type: "hot_work" | "confined_space_entry" | "cold_work";
  status: "active" | "closed";
  issued_time: string;
  valid_until: string;
}

export interface OvenSeries {
  risk_score: number[];
  risk_category: RiskCategoryCode[];
  compound_risk_flag: (0 | 1)[];
  co_ppm: number[];
  lel_pct: number[];
  gas_temp_c: number[];
  exhauster_fault: (0 | 1)[];
  maintenance_flag: (0 | 1)[];
  risk_reason: string[];
}

export interface WorkerMeta {
  worker_id: string;
}

// Zone-level occupancy only — never a continuous coordinate. See Section 6
// of coke_oven_risk_project_context.md: individual worker GPS/location
// tracking is explicitly out of scope; a worker's state is "which zone",
// full stop.
export type WorkerEventType = "warning_issued" | "entry_blocked";

export interface WorkerEvent {
  event_id: string;
  timestamp: string; // ISO 8601, UTC
  step: number; // index into the shared timeline, same convention as series
  worker_id: string;
  zone_id: string;
  event_type: WorkerEventType;
  message: string;
}

export interface ScenePayload {
  meta: SceneMeta;
  ovens: OvenMeta[];
  zones: ZoneMeta[];
  permits: Permit[];
  series: Record<string, OvenSeries>;
  workers: WorkerMeta[];
  zone_status: Record<string, ZoneStatusCode[]>; // zone_id -> status per step
  worker_zones: Record<string, string[]>; // worker_id -> zone_id per step
  events: WorkerEvent[];
}
