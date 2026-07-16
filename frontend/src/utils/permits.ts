import type { Permit } from "../types";

/** Permits covering `ovenId` at `date`, matching the same active-status +
 * time-bounds check the rule engine applies server-side (compoundrisk/
 * rule_engine.py::_permit_condition) — but here filtering is done live,
 * client-side, straight off the small permit_log table, matching the
 * spec's data-flow: "clicking an oven looks up its full sensor/permit
 * context from tables 4.2 and 4.3 for that timestamp." */
export function activePermitsForOven(permits: Permit[], ovenId: string, date: Date): Permit[] {
  const t = date.getTime();
  return permits.filter((p) => {
    if (p.oven_id !== ovenId) return false;
    if (p.status !== "active") return false;
    const issued = Date.parse(p.issued_time);
    const validUntil = Date.parse(p.valid_until);
    return t >= issued && t <= validUntil;
  });
}

/** All permits on file for the oven (including closed / out-of-window ones)
 * — shown in the detail panel so an operator can see e.g. a permit that was
 * closed early, not just the ones currently active. */
export function allPermitsForOven(permits: Permit[], ovenId: string): Permit[] {
  return permits.filter((p) => p.oven_id === ovenId);
}
