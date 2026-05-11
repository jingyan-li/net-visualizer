import { useMemo } from "react";
import type { Layer, MapViewState } from "@deck.gl/core";
import { WebMercatorViewport } from "@deck.gl/core";
import DeckGL from "@deck.gl/react";
import { Map } from "react-map-gl/maplibre";
import { createHighlightedPathLayer } from "../layers/createHighlightedPathLayer";
import { createLinkLayer } from "../layers/createLinkLayer";
import { createOdPointLayers, type NodeDemand, type OdDemandRole } from "../layers/createOdPointLayers";
import { createSelectedLinkLayer } from "../layers/createSelectedLinkLayer";
import type { ColorScaleType, FieldStats } from "../data/metrics";

const FALLBACK_VIEW_STATE: MapViewState = {
  longitude: -118.2437,
  latitude: 34.0522,
  zoom: 9,
  pitch: 0,
  bearing: 0
};

interface BBox {
  minLng: number;
  minLat: number;
  maxLng: number;
  maxLat: number;
}

function expandBBox(box: BBox, lng: number, lat: number): void {
  if (lng < box.minLng) box.minLng = lng;
  if (lng > box.maxLng) box.maxLng = lng;
  if (lat < box.minLat) box.minLat = lat;
  if (lat > box.maxLat) box.maxLat = lat;
}

function computeBBox(features: GeoJSON.Feature[]): BBox | null {
  const box: BBox = {
    minLng: Infinity,
    minLat: Infinity,
    maxLng: -Infinity,
    maxLat: -Infinity
  };
  let found = false;

  const visitCoords = (coords: unknown): void => {
    if (!Array.isArray(coords)) return;
    if (typeof coords[0] === "number" && typeof coords[1] === "number") {
      expandBBox(box, coords[0] as number, coords[1] as number);
      found = true;
      return;
    }
    for (const child of coords) visitCoords(child);
  };

  for (const feature of features) {
    const geom = feature.geometry as GeoJSON.Geometry | null;
    if (!geom) continue;
    if (geom.type === "GeometryCollection") {
      for (const g of geom.geometries) visitCoords((g as { coordinates: unknown }).coordinates);
    } else {
      visitCoords((geom as { coordinates: unknown }).coordinates);
    }
  }

  return found ? box : null;
}

function computeInitialViewState(linksGeojson: GeoJSON.FeatureCollection): MapViewState {
  const bbox = computeBBox(linksGeojson.features);
  if (!bbox) return FALLBACK_VIEW_STATE;

  try {
    const viewport = new WebMercatorViewport({ width: 1024, height: 768 });
    const fitted = viewport.fitBounds(
      [
        [bbox.minLng, bbox.minLat],
        [bbox.maxLng, bbox.maxLat]
      ],
      { padding: 40 }
    );
    return {
      longitude: fitted.longitude,
      latitude: fitted.latitude,
      zoom: Math.min(fitted.zoom, 15),
      pitch: 0,
      bearing: 0
    };
  } catch {
    return {
      longitude: (bbox.minLng + bbox.maxLng) / 2,
      latitude: (bbox.minLat + bbox.maxLat) / 2,
      zoom: 9,
      pitch: 0,
      bearing: 0
    };
  }
}

interface MapViewProps {
  linksGeojson: GeoJSON.FeatureCollection;
  odPointsGeojson: GeoJSON.FeatureCollection | null;
  highlightedPaths: GeoJSON.FeatureCollection;
  selectedLinkFeature: GeoJSON.Feature | null;
  selectedPathId: string | null;
  colorBy: string;
  stats: FieldStats | null;
  maskField?: string;
  scaleType: ColorScaleType;
  lineWidthScale: number;
  lineOffsetPixels: number;
  odPointSize: number;
  odLabelSize: number;
  pathOpacityPercent: number;
  showOdLabels: boolean;
  odDemandMode: "off" | OdDemandRole;
  demandByNode: Record<string, NodeDemand>;
  viewKey: string;
  onSelectLink: (linkId: string) => void;
  onSelectPath: (pathId: string) => void;
  onSelectOd: (key: string) => void;
}

export function MapView({
  linksGeojson,
  highlightedPaths,
  selectedLinkFeature,
  selectedPathId,
  colorBy,
  stats,
  maskField,
  scaleType,
  lineWidthScale,
  lineOffsetPixels,
  odPointSize,
  odLabelSize,
  pathOpacityPercent,
  showOdLabels,
  odDemandMode,
  demandByNode,
  odPointsGeojson,
  viewKey,
  onSelectLink,
  onSelectPath,
  onSelectOd
}: MapViewProps) {
  const initialViewState = useMemo(() => computeInitialViewState(linksGeojson), [linksGeojson]);

  const layers = useMemo<Layer[]>(() => {
    const result: Layer[] = [
      ...createLinkLayer({
        data: linksGeojson,
        colorBy,
        stats,
        maskField,
        scaleType,
        lineWidthScale,
        lineOffsetPixels,
        selectionActive: selectedLinkFeature !== null,
        onClick: onSelectLink
      })
    ];

    const selectedLinkLayer = createSelectedLinkLayer(selectedLinkFeature, lineOffsetPixels);
    if (selectedLinkLayer) {
      result.push(selectedLinkLayer);
    }

    if (highlightedPaths.features.length > 0) {
      result.push(
        createHighlightedPathLayer(highlightedPaths, selectedPathId, pathOpacityPercent, onSelectPath)
      );
    }

    if (odPointsGeojson) {
      const demandOptions =
        odDemandMode !== "off"
          ? {
              demandByNode,
              role: odDemandMode,
              minRadiusPx: Math.max(2, odPointSize * 0.6),
              maxRadiusPx: Math.max(odPointSize * 6, 20)
            }
          : undefined;
      result.push(
        ...createOdPointLayers(
          odPointsGeojson,
          odPointSize,
          odLabelSize,
          showOdLabels,
          demandOptions,
          onSelectOd
        )
      );
    }

    return result;
  }, [
    colorBy,
    demandByNode,
    highlightedPaths,
    lineOffsetPixels,
    lineWidthScale,
    linksGeojson,
    maskField,
    odDemandMode,
    odPointSize,
    odLabelSize,
    odPointsGeojson,
    pathOpacityPercent,
    showOdLabels,
    onSelectLink,
    onSelectPath,
    onSelectOd,
    scaleType,
    selectedLinkFeature,
    selectedPathId,
    stats
  ]);

  return (
    <div className="map-shell">
      <DeckGL key={viewKey} initialViewState={initialViewState} controller layers={layers}>
        <Map
          mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
          attributionControl={true}
        />
      </DeckGL>
    </div>
  );
}
