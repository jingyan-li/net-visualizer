import { GeoJsonLayer } from "@deck.gl/layers";

export function createHighlightedPathLayer(
  data: GeoJSON.FeatureCollection,
  selectedPathId: string | null,
  pathOpacityPercent: number,
  onClick: (pathId: string) => void
) {
  const baseAlpha = Math.max(0, Math.min(255, Math.round((pathOpacityPercent / 100) * 255)));
  return new GeoJsonLayer({
    id: "highlighted-paths",
    data,
    pickable: true,
    stroked: true,
    filled: false,
    lineWidthUnits: "pixels",
    lineWidthMinPixels: 4,
    getLineWidth: (feature) =>
      selectedPathId === String(feature.properties?.path_id) ? 8 : 5,
    getLineColor: (feature) =>
      selectedPathId === String(feature.properties?.path_id)
        ? [255, 214, 10, 255]
        : [0, 200, 255, baseAlpha],
    updateTriggers: {
      getLineWidth: [selectedPathId],
      getLineColor: [selectedPathId, baseAlpha]
    },
    onClick: (info) => {
      const pathId = info.object?.properties?.path_id;
      if (pathId !== undefined && pathId !== null) {
        onClick(String(pathId));
      }
    }
  });
}
