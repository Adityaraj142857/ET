interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  color: string;
  thresholdValue?: number;
}

/** Minimal trend line — no axes, per the dataviz skill's sparkline spec:
 * 2px line, threshold reference as a recessive solid hairline (never
 * dashed), current value called out as an end-dot in the series color. */
export function Sparkline({ values, width = 220, height = 48, color, thresholdValue }: SparklineProps) {
  if (values.length === 0) return null;

  const maxCandidate = Math.max(...values, thresholdValue ?? 0);
  const max = maxCandidate <= 0 ? 1 : maxCandidate * 1.15;
  const min = 0;
  const pad = 4;

  const xFor = (i: number) => pad + (i / Math.max(1, values.length - 1)) * (width - pad * 2);
  const yFor = (v: number) => height - pad - ((v - min) / (max - min)) * (height - pad * 2);

  const points = values.map((v, i) => `${xFor(i)},${yFor(v)}`).join(" ");
  const lastX = xFor(values.length - 1);
  const lastY = yFor(values[values.length - 1]);

  return (
    <svg width={width} height={height} role="img" aria-label="trend sparkline">
      {thresholdValue !== undefined && (
        <line
          x1={pad}
          x2={width - pad}
          y1={yFor(thresholdValue)}
          y2={yFor(thresholdValue)}
          stroke="#898781"
          strokeWidth={1}
        />
      )}
      <polyline points={points} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lastX} cy={lastY} r={3} fill={color} stroke="#1a1a19" strokeWidth={2} />
    </svg>
  );
}
