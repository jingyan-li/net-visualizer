import type { Layer } from "@deck.gl/core";
import { ScatterplotLayer, TextLayer } from "@deck.gl/layers";

interface OdPointProperties {
  point_id?: string;
  point_role?: string;
  node_id?: string | number;
  label?: string;
}

type OdPointFeature = GeoJSON.Feature<GeoJSON.Point, OdPointProperties>;

export interface NodeDemand {
  origin: number;
  destination: number;
}

export type OdDemandRole = "origin" | "destination";

interface DemandOptions {
  demandByNode: Record<string, NodeDemand>;
  role: OdDemandRole;
  minRadiusPx: number;
  maxRadiusPx: number;
}

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

const ROLE_FILTER: Record<OdDemandRole, string> = {
  origin: "O",
  destination: "D"
};

function demandValue(
  feature: OdPointFeature,
  demandByNode: Record<string, NodeDemand>,
  role: OdDemandRole
): number {
  const nodeId = String(feature.properties?.node_id ?? "");
  const record = demandByNode[nodeId];
  if (!record) return 0;
  return role === "origin" ? record.origin : record.destination;
}

export function createOdPointLayers(
  data: GeoJSON.FeatureCollection,
  pointSize: number,
  labelSize: number,
  showLabels: boolean,
  demand: DemandOptions | undefined,
  onSelect: ((key: string) => void) | undefined
): Layer[] {
  const allPoints = data.features.filter(
    (feature): feature is OdPointFeature =>
      feature.geometry?.type === "Point" &&
      Array.isArray(feature.geometry.coordinates) &&
      feature.geometry.coordinates.length >= 2
  );

  if (allPoints.length === 0) {
    return [];
  }

  const points = demand
    ? allPoints.filter((feature) => feature.properties?.point_role === ROLE_FILTER[demand.role])
    : allPoints;

  if (points.length === 0) {
    return [];
  }

  let logMin = Infinity;
  let logMax = -Infinity;
  if (demand) {
    for (const feature of points) {
      const value = demandValue(feature, demand.demandByNode, demand.role);
      if (value <= 0) continue;
      const logged = Math.log10(value);
      if (logged < logMin) logMin = logged;
      if (logged > logMax) logMax = logged;
    }
    if (!Number.isFinite(logMin) || !Number.isFinite(logMax)) {
      logMin = 0;
      logMax = 0;
    }
  }

  const logSpan = demand ? Math.max(logMax - logMin, 1e-9) : 0;

  const getRadius = demand
    ? (feature: OdPointFeature) => {
        const value = demandValue(feature, demand.demandByNode, demand.role);
        if (value <= 0) return demand.minRadiusPx;
        const normalized = logMax === logMin ? 1 : (Math.log10(value) - logMin) / logSpan;
        return demand.minRadiusPx + normalized * (demand.maxRadiusPx - demand.minRadiusPx);
      }
    : () => pointSize;

  // 50% opacity = 128/255
  const getFillColor = demand
    ? (() => {
        const color: [number, number, number, number] =
          demand.role === "origin" ? [33, 102, 172, 128] : [178, 24, 43, 128];
        return () => color;
      })()
    : () => [0, 0, 0, 220] as [number, number, number, number];

  const radiusMaxPx = demand ? demand.maxRadiusPx : Math.max(2, pointSize);

  const layers: Layer[] = [
    new ScatterplotLayer<OdPointFeature>({
      id: demand ? `od-points-demand-${demand.role}` : "od-points",
      data: points,
      pickable: true,
      radiusUnits: "pixels",
      radiusMinPixels: demand ? Math.max(1, demand.minRadiusPx) : Math.max(2, pointSize),
      radiusMaxPixels: radiusMaxPx,
      getRadius,
      getPosition: (feature) => feature.geometry.coordinates as [number, number],
      getFillColor,
      getLineColor: () => [255, 255, 255, 160],
      stroked: true,
      lineWidthMinPixels: 1,
      onClick: onSelect
        ? (info) => {
            const props = (info.object as OdPointFeature | undefined)?.properties;
            if (!props) return false;
            const pointId = String(props.point_id ?? props.node_id ?? "");
            const role = String(props.point_role ?? "");
            if (!pointId) return false;
            onSelect(`${pointId}__${role}`);
            return true;
          }
        : undefined,
      updateTriggers: {
        getRadius: demand ? [demand.demandByNode, demand.role, logMin, logMax] : [pointSize],
        getFillColor: [demand?.role ?? null]
      }
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
