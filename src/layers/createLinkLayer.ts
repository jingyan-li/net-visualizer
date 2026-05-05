import { GeoJsonLayer } from "@deck.gl/layers";
import { PathStyleExtension } from "@deck.gl/extensions";
import { getColorForValue, type FieldStats } from "../data/metrics";
import { getDirectionalLineOffset } from "./linkOffset";

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

interface CreateLinkLayerOptions {
  data: GeoJSON.FeatureCollection;
  colorBy: string;
  stats: FieldStats | null;
  maskField?: string;
  scaleType: "sequential" | "diverging";
  lineWidthScale: number;
  lineOffsetPixels: number;
  selectionActive: boolean;
  onClick: (linkId: string) => void;
}

function buildLayer(
  id: string,
  data: GeoJSON.FeatureCollection,
  colorBy: string,
  stats: FieldStats | null,
  scaleType: "sequential" | "diverging",
  lineWidthScale: number,
  lineOffsetPixels: number,
  selectionActive: boolean,
  onClick: (linkId: string) => void,
  mode: "valid" | "invalid"
) {
  return new GeoJsonLayer({
    id,
    data,
    pickable: true,
    stroked: true,
    filled: false,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 220],
    lineWidthUnits: "pixels",
    lineWidthScale: 1,
    lineWidthMinPixels: Math.max(mode === "valid" ? 4 : 1.5, lineWidthScale + (mode === "valid" ? 0.5 : -1)),
    getLineWidth: () => (mode === "valid" ? lineWidthScale + 0.5 : Math.max(1, lineWidthScale - 1)),
    extensions: [new PathStyleExtension({ offset: true })],
    getOffset: (feature: GeoJSON.Feature) => getDirectionalLineOffset(feature, lineOffsetPixels),
    getLineColor: (feature) => {
      if (mode === "invalid") {
        return [0, 0, 0, selectionActive ? 70 : 120];
      }

      const [r, g, b, a] = getColorForValue(feature.properties?.[colorBy], stats, {
        scaleType,
        hasData: true
      });
      return [r, g, b, selectionActive ? Math.max(45, Math.round(a * 0.4)) : a];
    },
    onClick: (info) => {
      const linkId = info.object?.properties?.link_id;
      if (linkId !== undefined && linkId !== null) {
        onClick(String(linkId));
      }
    },
    onHover: () => {
      document.body.style.cursor = "pointer";
    },
    getTooltip: ({ object }: { object?: GeoJSON.Feature | null }) =>
      object ? `link_id: ${String(object.properties?.link_id ?? "unknown")}` : null
  });
}

export function createLinkLayer({
  data,
  colorBy,
  stats,
  maskField,
  scaleType,
  lineWidthScale,
  lineOffsetPixels,
  selectionActive,
  onClick
}: CreateLinkLayerOptions) {
  const validFeatures = data.features.filter((feature) =>
    maskField ? coerceBoolean(feature.properties?.[maskField]) : true
  );
  const invalidFeatures = data.features.filter((feature) =>
    maskField ? !coerceBoolean(feature.properties?.[maskField]) : false
  );

  const layers = [];

  if (invalidFeatures.length > 0) {
    layers.push(
      buildLayer(
        "links-invalid",
        { type: "FeatureCollection", features: invalidFeatures },
        colorBy,
        stats,
        scaleType,
        lineWidthScale,
        lineOffsetPixels,
        selectionActive,
        onClick,
        "invalid"
      )
    );
  }

  if (validFeatures.length > 0) {
    layers.push(
      buildLayer(
        "links-valid",
        { type: "FeatureCollection", features: validFeatures },
        colorBy,
        stats,
        scaleType,
        lineWidthScale,
        lineOffsetPixels,
        selectionActive,
        onClick,
        "valid"
      )
    );
  }

  return layers;
}
