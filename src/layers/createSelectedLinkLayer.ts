import { GeoJsonLayer } from "@deck.gl/layers";
import { PathStyleExtension } from "@deck.gl/extensions";
import { getDirectionalLineOffset } from "./linkOffset";

export function createSelectedLinkLayer(feature: GeoJSON.Feature | null, lineOffsetPixels: number) {
  if (!feature) {
    return null;
  }

  return new GeoJsonLayer({
    id: "selected-link",
    data: {
      type: "FeatureCollection",
      features: [feature]
    },
    pickable: false,
    stroked: true,
    filled: false,
    lineWidthUnits: "pixels",
    extensions: [new PathStyleExtension({ offset: true })],
    lineWidthMinPixels: 7,
    getOffset: (currentFeature: GeoJSON.Feature) =>
      getDirectionalLineOffset(currentFeature, lineOffsetPixels),
    getLineWidth: 8,
    getLineColor: [255, 230, 66, 255]
  });
}
