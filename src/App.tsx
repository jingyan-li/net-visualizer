import { useEffect, useMemo, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { Toolbar } from "./components/Toolbar";
import { Legend } from "./components/Legend";
import { MapView } from "./components/MapView";
import { dataProvider } from "./data/DataProvider";
import { buildPathGeometry } from "./data/buildPathGeometry";
import { computeFieldStats } from "./data/metrics";
import { useAppStore } from "./store/useAppStore";
import "./styles.css";
import type {
  ColorFileDefinition,
  ColorFileEntry,
  ColorMeasureDefinition,
  ExperimentIndexEntry,
  ExperimentManifest,
  PathContribution,
  PathSummary
} from "./types";

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

function rankContributions(records: PathContribution[]): PathContribution[] {
  const sorted = [...records].sort((left, right) => {
    const contributionDelta = (right.contribution ?? 0) - (left.contribution ?? 0);
    if (contributionDelta !== 0) {
      return contributionDelta;
    }
    const leftOd = `${left.origin ?? ""}_${left.destination ?? ""}`;
    const rightOd = `${right.origin ?? ""}_${right.destination ?? ""}`;
    if (leftOd !== rightOd) {
      return leftOd.localeCompare(rightOd);
    }
    return left.path_id.localeCompare(right.path_id);
  });

  const grouped = new Map<string, PathContribution[]>();
  for (const record of sorted) {
    const key = String(record.contribution ?? Number.NEGATIVE_INFINITY);
    const bucket = grouped.get(key);
    if (bucket) {
      bucket.push(record);
    } else {
      grouped.set(key, [record]);
    }
  }

  const ranked: PathContribution[] = [];
  for (const group of grouped.values()) {
    const seenOds = new Set<string>();
    const duplicateOds: PathContribution[] = [];

    for (const record of group) {
      const odKey = `${record.origin ?? "n/a"}__${record.destination ?? "n/a"}`;
      if (seenOds.has(odKey)) {
        duplicateOds.push(record);
        continue;
      }
      seenOds.add(odKey);
      ranked.push(record);
    }

    ranked.push(...duplicateOds);
  }

  return ranked;
}

function buildFallbackContributions(
  linkId: string,
  linkToPaths: Record<string, string[]>,
  pathSummary: Record<string, PathSummary>
): PathContribution[] {
  const pathIds = linkToPaths[linkId] ?? [];

  const rawRecords = pathIds.map((pathId) => {
    const path = pathSummary[pathId];
    if (!path) {
      return null;
    }

    const contribution = path.path_flow ?? 1;
    return {
      link_id: linkId,
      path_id: pathId,
      od_id: path.od_id,
      origin: path.origin,
      destination: path.destination,
      origin_node_id: path.origin_node_id,
      destination_node_id: path.destination_node_id,
      depart_interval: path.depart_interval,
      vehicle_class: path.vehicle_class,
      path_flow: path.path_flow,
      contribution
    } as PathContribution;
  });

  const records = rawRecords.filter((record): record is PathContribution => record !== null);
  records.sort((left, right) => {
    const delta = (right.contribution ?? 0) - (left.contribution ?? 0);
    return delta !== 0 ? delta : left.path_id.localeCompare(right.path_id);
  });
  return records;
}

export default function App() {
  const {
    linksGeojson,
    odPointsGeojson,
    linksIndex,
    linkToPaths,
    pathSummary,
    linkPathContrib,
    selectedLinkId,
    selectedPathId,
    highlightedPathIds,
    colorBy,
    maxHighlightedPaths,
    linkWidthScale,
    lineOffsetPixels,
    odPointSize,
    odLabelSize,
    pathCountThreshold,
    showCoveredLinksOnly,
    hideUnobservedLinks,
    showOdPoints,
    showOdLabels,
    loading,
    error,
    setInitialData,
    setSelectedLinkId,
    setSelectedPathId,
    setColorBy,
    setMaxHighlightedPaths,
    setLinkWidthScale,
    setLineOffsetPixels,
    setOdPointSize,
    setOdLabelSize,
    setPathCountThreshold,
    setShowCoveredLinksOnly,
    setHideUnobservedLinks,
    setShowOdPoints,
    setShowOdLabels,
    setLinkContributions,
    setHighlightedPathIds,
    setLoading,
    setError,
    clearSelection
  } = useAppStore();

  const [experiments, setExperiments] = useState<ExperimentIndexEntry[]>([]);
  const [selectedExperimentId, setSelectedExperimentId] = useState("");
  const [manifest, setManifest] = useState<ExperimentManifest | null>(null);
  const [colorFiles, setColorFiles] = useState<ColorFileEntry[]>([]);
  const [selectedColorFileId, setSelectedColorFileId] = useState("");
  const [colorFileDefinition, setColorFileDefinition] = useState<ColorFileDefinition | null>(null);
  const [selectedMeasureId, setSelectedMeasureId] = useState("");
  const [selectedPeriodId, setSelectedPeriodId] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        setLoading(true);
        const experimentIndex = await dataProvider.loadExperimentIndex();
        if (cancelled) {
          return;
        }
        setExperiments(experimentIndex);
        setSelectedExperimentId((current) => current || experimentIndex[0]?.id || "");
        setError(null);
      } catch (bootstrapError) {
        if (!cancelled) {
          setError(
            bootstrapError instanceof Error
              ? bootstrapError.message
              : "Failed to load experiment index."
          );
          setLoading(false);
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [setError, setLoading]);

  useEffect(() => {
    if (!selectedExperimentId) {
      return;
    }

    const entry = experiments.find((item) => item.id === selectedExperimentId);
    if (!entry) {
      return;
    }
    const activeEntry = entry;

    let cancelled = false;
    async function loadExperiment() {
      try {
        setLoading(true);
        const nextManifest = await dataProvider.loadManifest(activeEntry.manifestPath);
        const initialData = await dataProvider.loadInitialData(nextManifest);
        if (cancelled) {
          return;
        }

        setManifest(nextManifest);
        setColorFiles(nextManifest.colorFiles);
        setSelectedColorFileId(
          nextManifest.defaultColorFileId ?? nextManifest.colorFiles[0]?.id ?? ""
        );
        setInitialData(initialData, [], []);
        clearSelection();
        setError(null);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load experiment.");
          setLoading(false);
        }
      }
    }

    void loadExperiment();
    return () => {
      cancelled = true;
    };
  }, [clearSelection, experiments, selectedExperimentId, setError, setInitialData, setLoading]);

  useEffect(() => {
    if (!manifest || !selectedColorFileId) {
      return;
    }

    const colorFile = manifest.colorFiles.find((item) => item.id === selectedColorFileId);
    if (!colorFile) {
      return;
    }
    const activeColorFile = colorFile;

    let cancelled = false;
    async function loadDefinition() {
      try {
        const definition = await dataProvider.loadColorFile(activeColorFile.path);
        if (cancelled) {
          return;
        }
        setColorFileDefinition(definition);
        setSelectedMeasureId(definition.defaultMeasureId ?? definition.measures[0]?.id ?? "");
        setSelectedPeriodId(
          definition.defaultPeriodId ?? Object.keys(definition.periodLabels)[0] ?? ""
        );
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load color file.");
        }
      }
    }

    void loadDefinition();
    return () => {
      cancelled = true;
    };
  }, [manifest, selectedColorFileId, setError]);

  useEffect(() => {
    if (!colorFileDefinition) {
      return;
    }

    if (!colorFileDefinition.measures.some((item) => item.id === selectedMeasureId)) {
      setSelectedMeasureId(colorFileDefinition.defaultMeasureId ?? colorFileDefinition.measures[0]?.id ?? "");
    }

    if (!(selectedPeriodId in colorFileDefinition.periodLabels)) {
      setSelectedPeriodId(
        colorFileDefinition.defaultPeriodId ?? Object.keys(colorFileDefinition.periodLabels)[0] ?? ""
      );
    }
  }, [colorFileDefinition, selectedMeasureId, selectedPeriodId]);

  const activeMeasure = useMemo<ColorMeasureDefinition | null>(
    () => colorFileDefinition?.measures.find((item) => item.id === selectedMeasureId) ?? null,
    [colorFileDefinition, selectedMeasureId]
  );

  const activeField = activeMeasure?.fieldByPeriod[selectedPeriodId] ?? "";
  const activeMaskField = activeMeasure?.maskFieldByPeriod?.[selectedPeriodId];
  const activeScaleType = activeMeasure?.scaleType ?? "sequential";
  const activeObservedField = selectedColorFileId ? `${selectedColorFileId}_observed_any` : "";
  const activeVisibilityField = activeMaskField ?? activeObservedField;
  const activeLegendTitle = [
    colorFiles.find((item) => item.id === selectedColorFileId)?.label ?? "",
    activeMeasure?.label ?? "",
    colorFileDefinition?.periodLabels[selectedPeriodId] ?? ""
  ]
    .filter(Boolean)
    .join(" | ");

  useEffect(() => {
    if (activeField && activeField !== colorBy) {
      setColorBy(activeField);
    }
  }, [activeField, colorBy, setColorBy]);

  useEffect(() => {
    if (showCoveredLinksOnly && selectedLinkId && !(selectedLinkId in linkToPaths)) {
      clearSelection();
    }
  }, [clearSelection, linkToPaths, selectedLinkId, showCoveredLinksOnly]);

  useEffect(() => {
    if (!hideUnobservedLinks || !selectedLinkId || !activeVisibilityField) {
      return;
    }
    const selectedObserved = coerceBoolean(
      linksIndex[selectedLinkId]?.properties?.[activeVisibilityField]
    );
    if (!selectedObserved) {
      clearSelection();
    }
  }, [activeVisibilityField, clearSelection, hideUnobservedLinks, linksIndex, selectedLinkId]);

  useEffect(() => {
    async function refreshContributions() {
      if (!selectedLinkId) {
        setError(null);
        setHighlightedPathIds([]);
        return;
      }

      if (!manifest) {
        return;
      }

      const existing = linkPathContrib[selectedLinkId];
      if (existing) {
        const rankedExisting = rankContributions(existing);
        setError(null);
        setHighlightedPathIds(
          rankedExisting
            .slice(0, Math.min(rankedExisting.length, maxHighlightedPaths))
            .map((record) => record.path_id)
        );
        return;
      }

      try {
        setLoading(true);
        const records = await dataProvider.getLinkContributions(manifest, selectedLinkId);
        const resolvedRecords =
          records.length > 0
            ? records
            : buildFallbackContributions(selectedLinkId, linkToPaths, pathSummary);
        const rankedRecords = rankContributions(resolvedRecords);
        setLinkContributions(selectedLinkId, rankedRecords);
        setHighlightedPathIds(
          rankedRecords
            .slice(0, Math.min(rankedRecords.length, maxHighlightedPaths))
            .map((record) => record.path_id)
        );
        setError(null);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load link contributions.");
      } finally {
        setLoading(false);
      }
    }

    void refreshContributions();
  }, [
    linkPathContrib,
    linkToPaths,
    manifest,
    maxHighlightedPaths,
    pathSummary,
    selectedLinkId,
    setError,
    setHighlightedPathIds,
    setLinkContributions,
    setLoading
  ]);

  const contributions = useMemo(
    () => (selectedLinkId ? rankContributions(linkPathContrib[selectedLinkId] ?? []) : []),
    [linkPathContrib, selectedLinkId]
  );
  const displayedContributions = useMemo(
    () => contributions.slice(0, Math.min(contributions.length, maxHighlightedPaths)),
    [contributions, maxHighlightedPaths]
  );
  const maxHighlightedPathsLimit = selectedLinkId ? Math.max(1, contributions.length) : 40;
  const hasPathCoverage = selectedLinkId ? selectedLinkId in linkToPaths : false;

  const pathCountThresholdMax = useMemo(() => {
    if (!linksGeojson) {
      return 0;
    }
    const counts = linksGeojson.features
      .filter((feature) => {
        if (activeVisibilityField) {
          return coerceBoolean(feature.properties?.[activeVisibilityField]);
        }
        const value = feature.properties?.[activeField || colorBy];
        return Number.isFinite(Number(value));
      })
      .map((feature) => {
        const linkId = String(feature.properties?.link_id ?? "");
        return linkToPaths[linkId]?.length ?? 0;
      });
    return counts.length > 0 ? Math.max(...counts) : 0;
  }, [activeField, activeVisibilityField, colorBy, linkToPaths, linksGeojson]);

  const activePathCountThreshold = pathCountThreshold ?? pathCountThresholdMax;

  useEffect(() => {
    if (pathCountThreshold === null) {
      return;
    }
    if (pathCountThreshold > pathCountThresholdMax) {
      setPathCountThreshold(pathCountThresholdMax);
    }
  }, [pathCountThreshold, pathCountThresholdMax, setPathCountThreshold]);

  useEffect(() => {
    if (pathCountThreshold === null) {
      return;
    }
    if (selectedLinkId && (linkToPaths[selectedLinkId]?.length ?? 0) > pathCountThreshold) {
      clearSelection();
    }
  }, [clearSelection, linkToPaths, pathCountThreshold, selectedLinkId]);

  const displayedLinksGeojson = useMemo<GeoJSON.FeatureCollection | null>(() => {
    if (!linksGeojson) {
      return null;
    }
    if (!showCoveredLinksOnly && !hideUnobservedLinks) {
      return linksGeojson;
    }
    return {
      ...linksGeojson,
      features: linksGeojson.features.filter((feature) => {
        const linkId = String(feature.properties?.link_id ?? "");
        const coveredOk = !showCoveredLinksOnly || linkId in linkToPaths;
        const observedOk =
          !hideUnobservedLinks ||
          !activeVisibilityField ||
          coerceBoolean(feature.properties?.[activeVisibilityField]);
        const pathCountOk = (linkToPaths[linkId]?.length ?? 0) <= activePathCountThreshold;
        return coveredOk && observedOk && pathCountOk;
      })
    };
  }, [
    activePathCountThreshold,
    activeVisibilityField,
    hideUnobservedLinks,
    linkToPaths,
    linksGeojson,
    showCoveredLinksOnly
  ]);

  const fieldStats = useMemo(() => {
    if (!displayedLinksGeojson || !activeField) {
      return null;
    }
    return computeFieldStats(displayedLinksGeojson, activeField, {
      maskField: activeMaskField,
      scaleType: activeScaleType
    });
  }, [activeField, activeMaskField, activeScaleType, displayedLinksGeojson]);

  const selectedLinkFeature = useMemo(() => {
    if (!selectedLinkId || !displayedLinksGeojson) {
      return null;
    }
    return (
      displayedLinksGeojson.features.find(
        (feature) => String(feature.properties?.link_id ?? "") === selectedLinkId
      ) ?? null
    );
  }, [displayedLinksGeojson, selectedLinkId]);

  const highlightedPaths = useMemo<GeoJSON.FeatureCollection>(() => {
    const features = highlightedPathIds
      .map((pathId) => {
        const path = pathSummary[pathId];
        if (!path) {
          return null;
        }
        return buildPathGeometry(path, linksIndex);
      })
      .filter(
        (
          feature
        ): feature is GeoJSON.Feature<GeoJSON.LineString | GeoJSON.MultiLineString> =>
          feature !== null
      );

    return {
      type: "FeatureCollection",
      features: features as GeoJSON.Feature[]
    };
  }, [highlightedPathIds, linksIndex, pathSummary]);

  const linkProperties = selectedLinkId ? linksIndex[selectedLinkId]?.properties ?? null : null;
  const activeMetricValue =
    selectedLinkId && linksIndex[selectedLinkId]
      ? linksIndex[selectedLinkId].properties?.[activeField || colorBy]
      : null;

  useEffect(() => {
    if (selectedLinkId && contributions.length > 0 && maxHighlightedPaths > contributions.length) {
      setMaxHighlightedPaths(contributions.length);
    }
  }, [contributions.length, maxHighlightedPaths, selectedLinkId, setMaxHighlightedPaths]);

  if (error) {
    return <div className="app-shell error-state">{error}</div>;
  }

  if (loading && !linksGeojson) {
    return <div className="app-shell loading-state">Loading experiment data...</div>;
  }

  if (!linksGeojson) {
    return <div className="app-shell error-state">No experiment data available.</div>;
  }

  const activeLinksGeojson = displayedLinksGeojson ?? linksGeojson;

  return (
    <div className="app-shell">
      <Toolbar
        experiments={experiments}
        selectedExperimentId={selectedExperimentId}
        colorFiles={colorFiles}
        selectedColorFileId={selectedColorFileId}
        colorFileDefinition={colorFileDefinition}
        selectedMeasureId={selectedMeasureId}
        selectedPeriodId={selectedPeriodId}
        maxHighlightedPaths={maxHighlightedPaths}
        maxHighlightedPathsLimit={maxHighlightedPathsLimit}
        pathCountThreshold={activePathCountThreshold}
        pathCountThresholdMax={pathCountThresholdMax}
        linkWidthScale={linkWidthScale}
        lineOffsetPixels={lineOffsetPixels}
        odPointSize={odPointSize}
        odLabelSize={odLabelSize}
        showCoveredLinksOnly={showCoveredLinksOnly}
        hideUnobservedLinks={hideUnobservedLinks}
        showOdPoints={showOdPoints}
        showOdLabels={showOdLabels}
        onExperimentChange={setSelectedExperimentId}
        onColorFileChange={setSelectedColorFileId}
        onMeasureChange={setSelectedMeasureId}
        onPeriodChange={setSelectedPeriodId}
        onMaxHighlightedPathsChange={setMaxHighlightedPaths}
        onPathCountThresholdChange={setPathCountThreshold}
        onLinkWidthScaleChange={setLinkWidthScale}
        onLineOffsetPixelsChange={setLineOffsetPixels}
        onOdPointSizeChange={setOdPointSize}
        onOdLabelSizeChange={setOdLabelSize}
        onShowCoveredLinksOnlyChange={setShowCoveredLinksOnly}
        onHideUnobservedLinksChange={setHideUnobservedLinks}
        onShowOdPointsChange={setShowOdPoints}
        onShowOdLabelsChange={setShowOdLabels}
        onClearSelection={clearSelection}
      />
      <div className="content-shell">
        <div className="map-column">
          <MapView
            linksGeojson={activeLinksGeojson}
            odPointsGeojson={showOdPoints ? odPointsGeojson : null}
            highlightedPaths={highlightedPaths}
            selectedLinkFeature={selectedLinkFeature}
            selectedPathId={selectedPathId}
            colorBy={activeField || colorBy}
            stats={fieldStats}
            maskField={activeMaskField}
            scaleType={activeScaleType}
            lineWidthScale={linkWidthScale}
            lineOffsetPixels={lineOffsetPixels}
            odPointSize={odPointSize}
            odLabelSize={odLabelSize}
            showOdLabels={showOdLabels}
            onSelectLink={setSelectedLinkId}
            onSelectPath={setSelectedPathId}
          />
          <Legend field={activeLegendTitle || activeField || colorBy} stats={fieldStats} />
        </div>
        <Sidebar
          selectedLinkId={selectedLinkId}
          selectedPathId={selectedPathId}
          linkProperties={linkProperties}
          contributions={contributions}
          displayedContributions={displayedContributions}
          totalPathCount={contributions.length}
          hasPathCoverage={hasPathCoverage}
          activeMetricLabel={activeLegendTitle || activeField || colorBy}
          activeMetricValue={activeMetricValue}
          onSelectPath={setSelectedPathId}
          loading={loading && Boolean(selectedLinkId)}
        />
      </div>
    </div>
  );
}
