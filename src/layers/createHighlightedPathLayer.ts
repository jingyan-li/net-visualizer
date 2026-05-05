import { GeoJsonLayer } from "@deck.gl/layers";

export function createHighlightedPathLayer(
  data: GeoJSON.FeatureCollection,
  selectedPathId: string | null,
  onClick: (pathId: string) => void
) {
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
        : [0, 200, 255, 235],
    onClick: (info) => {
      const pathId = info.object?.properties?.path_id;
      if (pathId !== undefined && pathId !== null) {
        onClick(String(pathId));
      }
    }
  });
}
