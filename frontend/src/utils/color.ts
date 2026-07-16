// Status palette (fixed, never themed) — from the project's dataviz skill
// reference palette. Reserved meaning: good / warning / critical, always
// paired with an icon + label in the UI, never color alone.
//
// Deliberately driven by risk_category (a discrete function of which
// conditions are present — see compoundrisk/rule_engine.py) rather than by
// interpolating the continuous risk_score. A continuous green->red gradient
// over risk_score would visually blur "two factors, maxed out" and "three
// factors, barely over threshold" into similar hues — exactly the
// two-of-three-looks-like-compound confusion the rule engine's category
// logic was fixed to avoid (see code review history). Color must not
// reintroduce that mistake at the pixel level.
import type { RiskCategoryCode } from "../types";

export const STATUS_COLOR = {
  low: "#0ca30c",
  medium: "#fab219",
  high: "#d03b3b",
} as const;

export const STATUS_LABEL = {
  low: "Low",
  medium: "Medium",
  high: "High — compound risk",
} as const;

// A short glyph per status so identity never rides on hue alone (colorblind
// / grayscale / projector-in-a-bright-room safe).
export const STATUS_GLYPH = {
  low: "●", // ●
  medium: "▲", // ▲
  high: "✖", // ✖
} as const;

export const RISK_CATEGORY_NAME: Record<RiskCategoryCode, keyof typeof STATUS_COLOR> = {
  0: "low",
  1: "medium",
  2: "high",
};

export function colorForCategory(code: RiskCategoryCode): string {
  return STATUS_COLOR[RISK_CATEGORY_NAME[code]];
}

// Idle/unknown state before data loads — a neutral, unmistakably "not a
// status color" gray so it can never be misread as "low risk".
export const PENDING_COLOR = "#4a4a48";
