import { getColorForValue, type FieldStats } from "../data/metrics";

interface LegendProps {
  field: string;
  stats: FieldStats | null;
}

export function Legend({ field, stats }: LegendProps) {
  const isBias = stats?.scaleType === "diverging";
  const labels = stats
    ? [
        stats.displayMin,
        stats.midpoint,
        stats.displayMax
      ]
    : null;
  const gradientStyle = stats
    ? {
        background: `linear-gradient(90deg, ${toCssColor(getColorForValue(stats.displayMin, stats, { scaleType: stats.scaleType, hasData: true }))} 0%, ${toCssColor(getColorForValue(stats.midpoint, stats, { scaleType: stats.scaleType, hasData: true }))} 50%, ${toCssColor(getColorForValue(stats.displayMax, stats, { scaleType: stats.scaleType, hasData: true }))} 100%)`
      }
    : undefined;

  return (
    <div className="legend">
      <div className="legend-title">{field}</div>
      <div
        className={`legend-bar ${isBias ? "diverging" : "sequential"}`}
        style={gradientStyle}
      />
      <div className="legend-labels">
        <span>{labels ? labels[0].toFixed(3) : "n/a"}</span>
        <span>{labels ? labels[1].toFixed(3) : "n/a"}</span>
        <span>{labels ? labels[2].toFixed(3) : "n/a"}</span>
      </div>
      {stats?.clipped ? (
        <div className="legend-note">
          {`IQR outliers clipped; map adds yellow highlight${stats.hasLowerOutliers ? " (low)" : ""}${stats.hasUpperOutliers ? stats.hasLowerOutliers ? " and high" : " (high)" : ""}.`}
        </div>
      ) : null}
    </div>
  );
}

function toCssColor([r, g, b, a]: [number, number, number, number]): string {
  return `rgba(${r}, ${g}, ${b}, ${Math.max(0, Math.min(255, a)) / 255})`;
}
