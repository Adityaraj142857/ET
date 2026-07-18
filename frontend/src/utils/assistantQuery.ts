/** Turns a rule-engine risk_reason string (e.g. "CO 78ppm + active hot-work
 * permit + exhauster fault") into a natural-language question for the
 * Safety Intelligence Assistant, so a click on an oven's detail panel can
 * hand off a relevant pre-filled query instead of making the operator
 * re-type context. Purely a text transform — does not touch retrieval or
 * synthesis logic. */
function describeSegment(segment: string): string {
  const s = segment.trim();

  if (/^CO \d+(\.\d+)?ppm$/i.test(s)) return "elevated CO levels";
  if (/^LEL [\d.]+%$/i.test(s)) return "elevated combustible gas (LEL) readings";

  const permitMatch = s.match(/^active (.+) permit$/i);
  if (permitMatch) return `${permitMatch[1].replace(/-/g, " ")} permits`;

  if (/^exhauster fault$/i.test(s)) return "exhauster faults";
  if (/^maintenance flag active$/i.test(s)) return "active maintenance flags";

  return s;
}

function joinNaturally(items: string[]): string {
  if (items.length === 1) return items[0];
  if (items.length === 2) return `${items[0]} combined with ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

export function assistantQueryFromRiskReason(ovenId: string, riskReason: string): string {
  if (!riskReason || riskReason.trim() === "Normal operating parameters") {
    return `What risk patterns have historically preceded incidents at ovens like ${ovenId} that were otherwise reading normal operating parameters?`;
  }

  const segments = riskReason.split("+").map(describeSegment);
  return `What recurring patterns exist around ${joinNaturally(segments)}?`;
}
