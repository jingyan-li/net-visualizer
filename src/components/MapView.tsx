import { useMemo } from "react";
import type { Layer, MapViewState } from "@deck.gl/core";
import DeckGL from "@deck.gl/react";
import { Map } from "react-map-gl/maplibre";
import { createHighlightedPathLayer } from "../layers/createHighlightedPathLayer";
import { createLinkLayer } from "../layers/createLinkLayer";
import { createOdPointLayers } from "../layers/createOdPointLayers";
import { createSelectedLinkLayer } from "../layers/createSelectedLinkLayer";
import type { ColorScaleType, FieldStats } from "../data/metrics";

const INITIAL_VIEW_STATE: MapViewState = {
  longitude: -79.9959,
  latitude: 40.4406,
  zoom: 10,
  pitch: 0,
  bearing: 0
};

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
  onSelectLink: (linkId: string) => void;
  onSelectPath: (pathId: string) => void;
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
  odPointsGeojson,
  onSelectLink,
  onSelectPath
}: MapViewProps) {
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
      result.push(...createOdPointLayers(odPointsGeojson, odPointSize, odLabelSize, showOdLabels));
    }

    return result;
  }, [
    colorBy,
    highlightedPaths,
    lineOffsetPixels,
    lineWidthScale,
    linksGeojson,
    maskField,
    odPointSize,
    odLabelSize,
    odPointsGeojson,
    pathOpacityPercent,
    showOdLabels,
    onSelectLink,
    onSelectPath,
    scaleType,
    selectedLinkFeature,
    selectedPathId,
    stats
  ]);

  return (
    <div className="map-shell">
      <DeckGL initialViewState={INITIAL_VIEW_STATE} controller layers={layers}>
        <Map
          mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
          attributionControl={true}
        />
      </DeckGL>
    </div>
  );
}
