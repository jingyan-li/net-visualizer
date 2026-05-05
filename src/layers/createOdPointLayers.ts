import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer, TextLayer } from "@deck.gl/layers";

interface OdPointProperties {
  point_id?: string;
  point_role?: string;
  node_id?: string | number;
  label?: string;
}

type OdPointFeature = GeoJSON.Feature<GeoJSON.Point, OdPointProperties>;

function hashLabel(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

function getLabelOffset(feature: OdPointFeature, labelSize: number): [number, number] {
  const seed = hashLabel(
    String(feature.properties?.node_id ?? feature.properties?.point_id ?? feature.properties?.label ?? "")
  );
  const directions: Array<[number, number]> = [
    [1, 0],
    [1, -1],
    [0, -1],
    [-1, -1],
    [-1, 0],
    [-1, 1],
    [0, 1],
    [1, 1]
  ];
  const [dx, dy] = directions[seed % directions.length];
  const radius = 6 + (seed % 3) * 4 + labelSize * 0.35;
  return [Math.round(dx * radius), Math.round(dy * radius)];
}

export function createOdPointLayers(
  data: GeoJSON.FeatureCollection,
  pointSize: number,
  labelSize: number,
  showLabels: boolean
): Layer[] {
  const points = data.features.filter(
    (feature): feature is OdPointFeature =>
      feature.geometry?.type === "Point" &&
      Array.isArray(feature.geometry.coordinates) &&
      feature.geometry.coordinates.length >= 2
  );

  if (points.length === 0) {
    return [];
  }

  const layers: Layer[] = [
    new ScatterplotLayer<OdPointFeature>({
      id: "od-points",
      data: points,
      pickable: false,
      radiusUnits: "pixels",
      radiusMinPixels: Math.max(2, pointSize),
      radiusMaxPixels: Math.max(2, pointSize),
      getRadius: () => pointSize,
      getPosition: (feature) => feature.geometry.coordinates as [number, number],
      getFillColor: () => [0, 0, 0, 220],
      getLineColor: () => [255, 255, 255, 120],
      stroked: true,
      lineWidthMinPixels: 1
    })
  ];

  if (showLabels) {
    layers.push(
      new TextLayer<OdPointFeature>({
        id: "od-point-labels",
        data: points,
        pickable: false,
        getPosition: (feature) => feature.geometry.coordinates as [number, number],
        getText: (feature) =>
          String(feature.properties?.node_id ?? feature.properties?.label ?? feature.properties?.point_id ?? ""),
        getColor: () => [0, 0, 0, 235],
        getSize: () => labelSize,
        sizeUnits: "pixels",
        getTextAnchor: () => "start",
        getAlignmentBaseline: () => "center",
        getPixelOffset: (feature) => getLabelOffset(feature, labelSize),
        fontFamily: "Menlo, Monaco, Consolas, monospace",
        characterSet: "auto",
        background: true,
        getBackgroundColor: () => [255, 255, 255, 200]
      })
    );
  }

  return layers;
}
