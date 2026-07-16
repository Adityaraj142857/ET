import type { SceneMeta } from "../types";

/** Wall-clock Date for a given simulation step index. */
export function dateForStep(meta: SceneMeta, stepIndex: number): Date {
  const startMs = Date.parse(meta.sim_start);
  return new Date(startMs + stepIndex * meta.interval_min * 60_000);
}

/** Elapsed simulated hours since sim start, for a given step index. */
export function hoursForStep(meta: SceneMeta, stepIndex: number): number {
  return (stepIndex * meta.interval_min) / 60;
}

const DATE_FORMATTER = new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export function formatStepTimestamp(meta: SceneMeta, stepIndex: number): string {
  const date = dateForStep(meta, stepIndex);
  return `${DATE_FORMATTER.format(date)} UTC`;
}

export function formatElapsed(meta: SceneMeta, stepIndex: number): string {
  const hours = hoursForStep(meta, stepIndex);
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return `T+${h}h${m > 0 ? ` ${m}m` : ""}`;
}
