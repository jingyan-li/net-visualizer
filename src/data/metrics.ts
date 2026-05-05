export type ColorScaleType = "sequential" | "diverging";

export interface FieldStats {
  min: number;
  max: number;
  displayMin: number;
  displayMax: number;
  midpoint: number;
  clipped: boolean;
  scaleType: ColorScaleType;
}

export interface FieldStatsOptions {
  maskField?: string;
  scaleType: ColorScaleType;
}

function quantile(sortedValues: number[], q: number): number {
  if (sortedValues.length === 0) {
    return NaN;
  }

  const position = (sortedValues.length - 1) * Math.max(0, Math.min(1, q));
  const lowerIndex = Math.floor(position);
  const upperIndex = Math.ceil(position);
  const lower = sortedValues[lowerIndex];
  const upper = sortedValues[upperIndex];

  if (lowerIndex === upperIndex) {
    return lower;
  }

  const fraction = position - lowerIndex;
  return lower + (upper - lower) * fraction;
}

function coerceBoolean(value: unknown): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "true") {
      return true;
    }
    if (normalized === "false" || normalized === "") {
      return false;
    }
  }
  if (typeof value === "number") {
    return value !== 0;
  }
  return Boolean(value);
}

function isMaskedIn(feature: GeoJSON.Feature, maskField?: string): boolean {
  if (!maskField) {
    return true;
  }
  return coerceBoolean(feature.properties?.[maskField]);
}

export function computeFieldStats(
  fc: GeoJSON.FeatureCollection,
  field: string,
  options: FieldStatsOptions
): FieldStats | null {
  const values = fc.features
    .filter((feature) => isMaskedIn(feature, options.maskField))
    .map((feature) => Number(feature.properties?.[field]))
    .filter((value) => Number.isFinite(value))
    .sort((left, right) => left - right);

  if (values.length === 0) {
    return null;
  }

  const min = values[0];
  const max = values[values.length - 1];

  if (options.scaleType === "diverging") {
    const q1 = quantile(values, 0.25);
    const q3 = quantile(values, 0.75);
    const iqr = q3 - q1;
    const displayMin = Math.max(min, q1 - 1.5 * iqr);
    const displayMax = Math.min(max, q3 + 1.5 * iqr);
    return {
      min,
      max,
      displayMin: Math.min(displayMin, 0),
      displayMax: Math.max(displayMax, 0),
      midpoint: 0,
      clipped: min < displayMin || max > displayMax,
      scaleType: options.scaleType
    };
  }

  const q1 = quantile(values, 0.25);
  const q3 = quantile(values, 0.75);
  const iqr = q3 - q1;
  const displayMin = Math.max(0, min);
  const displayMax = Math.max(displayMin + 1e-9, Math.min(max, q3 + 1.5 * iqr));
  return {
    min,
    max,
    displayMin,
    displayMax,
    midpoint: (displayMin + displayMax) / 2,
    clipped: max > displayMax,
    scaleType: options.scaleType
  };
}

export interface ColorValueOptions {
  scaleType: ColorScaleType;
  hasData: boolean;
}

export function getColorForValue(
  value: unknown,
  stats: FieldStats | null,
  options: ColorValueOptions
): [number, number, number, number] {
  if (!options.hasData) {
    return [0, 0, 0, 220];
  }

  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || !stats) {
    return [56, 56, 56, 180];
  }

  if (options.scaleType === "diverging") {
    if (numericValue === 0) {
      return [245, 245, 245, 225];
    }

    if (numericValue > 0) {
      const max = Math.max(stats.displayMax, 1e-9);
      const t = Math.max(0, Math.min(1, numericValue / max));
      return [
        245 - Math.round(49 * t),
        245 - Math.round(191 * t),
        245 - Math.round(207 * t),
        210 + Math.round(45 * t)
      ];
    }

    const min = Math.min(stats.displayMin, -1e-9);
    const t = Math.max(0, Math.min(1, numericValue / min));
    return [
      245 - Math.round(210 * t),
      245 - Math.round(159 * t),
      245 - Math.round(72 * t),
      210 + Math.round(45 * t)
    ];
  }

  const min = stats.displayMin;
  const max = stats.displayMax;
  const denom = max - min || 1;
  const t = Math.max(0, Math.min(1, (numericValue - min) / denom));
  return [
    245 - Math.round(52 * t),
    245 - Math.round(205 * t),
    245 - Math.round(209 * t),
    205 + Math.round(50 * t)
  ];
}
