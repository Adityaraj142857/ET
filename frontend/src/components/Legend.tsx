import { STATUS_COLOR, STATUS_GLYPH, STATUS_LABEL } from "../utils/color";

const ORDER: (keyof typeof STATUS_COLOR)[] = ["low", "medium", "high"];

/** Status legend — always present (never color-alone): swatch + glyph +
 * label for each of the three risk categories, per the dataviz skill's
 * status-palette rule. */
export function Legend() {
  return (
    <div className="legend" role="list" aria-label="Risk status legend">
      {ORDER.map((key) => (
        <div className="legend__item" role="listitem" key={key}>
          <span className="legend__swatch" style={{ background: STATUS_COLOR[key] }} />
          <span className="legend__glyph">{STATUS_GLYPH[key]}</span>
          <span>{STATUS_LABEL[key]}</span>
        </div>
      ))}
    </div>
  );
}
