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
  OdDemandPayload,
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

function getLegacyPeriodMap<T>(measure: ColorMeasureDefinition, key: "fieldByPeriod" | "maskFieldByPeriod") {
  return (measure as unknown as Record<string, T | undefined>)[key] as Record<string, T> | undefined;
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
    selectedOdKey,
    highlightedPathIds,
    colorBy,
    maxHighlightedPaths,
    linkWidthScale,
    lineOffsetPixels,
    odPointSize,
    odLabelSize,
    pathOpacityPercent,
    pathCountThreshold,
    showCoveredLinksOnly,
    hideUnobservedLinks,
    showOdPoints,
    showOdLabels,
    odDemandMode,
    loading,
    error,
    setInitialData,
    setSelectedLinkId,
    setSelectedPathId,
    setSelectedOdKey,
    setColorBy,
    setMaxHighlightedPaths,
    setLinkWidthScale,
    setLineOffsetPixels,
    setOdPointSize,
    setOdLabelSize,
    setPathOpacityPercent,
    setPathCountThreshold,
    setShowCoveredLinksOnly,
    setHideUnobservedLinks,
    setShowOdPoints,
    setShowOdLabels,
    setOdDemandMode,
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
  const [odDemand, setOdDemand] = useState<OdDemandPayload | null>(null);
  const [selectedMeasureId, setSelectedMeasureId] = useState("");
  const [selectedPeriodMode, setSelectedPeriodMode] = useState<"total" | "interval">("total");
  const [selectedIntervalKey, setSelectedIntervalKey] = useState<string | null>(null);

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
        const demandPayload = await dataProvider.loadOdDemand(nextManifest);
        if (!cancelled) {
          setOdDemand(demandPayload);
        }
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
        const nextMeasureId = definition.measures.some((item) => item.id === selectedMeasureId)
          ? selectedMeasureId
          : definition.defaultMeasureId ?? definition.measures[0]?.id ?? "";
        const nextPeriodMode = selectedPeriodMode;
        const nextIntervalKey = definition.intervals.some((item) => item.key === selectedIntervalKey)
          ? selectedIntervalKey
          : definition.intervals[0]?.key ?? null;
        setSelectedMeasureId(nextMeasureId);
        setSelectedPeriodMode(nextPeriodMode);
        setSelectedIntervalKey(nextIntervalKey);
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
  }, [manifest, selectedColorFileId, selectedIntervalKey, selectedMeasureId, selectedPeriodMode, setError]);

  useEffect(() => {
    if (!colorFileDefinition) {
      return;
    }

    if (!colorFileDefinition.measures.some((item) => item.id === selectedMeasureId)) {
      setSelectedMeasureId(colorFileDefinition.defaultMeasureId ?? colorFileDefinition.measures[0]?.id ?? "");
    }

    if (selectedPeriodMode !== "total" && selectedPeriodMode !== "interval") {
      setSelectedPeriodMode(colorFileDefinition.defaultPeriodMode ?? "total");
    }

    if (
      (colorFileDefinition.intervals?.length ?? 0) > 0 &&
      !colorFileDefinition.intervals.some((item) => item.key === selectedIntervalKey)
    ) {
      setSelectedIntervalKey(colorFileDefinition.defaultIntervalKey ?? colorFileDefinition.intervals[0]?.key ?? null);
    }
  }, [colorFileDefinition, selectedIntervalKey, selectedMeasureId, selectedPeriodMode]);

  const activeMeasure = useMemo<ColorMeasureDefinition | null>(
    () => colorFileDefinition?.measures.find((item) => item.id === selectedMeasureId) ?? null,
    [colorFileDefinition, selectedMeasureId]
  );

  const intervals = colorFileDefinition?.intervals ?? [];
  const activeInterval = intervals.find((item) => item.key === selectedIntervalKey) ?? intervals[0] ?? null;
  const legacyFieldByPeriod = activeMeasure ? getLegacyPeriodMap<string>(activeMeasure, "fieldByPeriod") : undefined;
  const legacyMaskByPeriod = activeMeasure ? getLegacyPeriodMap<string>(activeMeasure, "maskFieldByPeriod") : undefined;
  const fallbackIntervalField =
    activeInterval && legacyFieldByPeriod
      ? legacyFieldByPeriod[activeInterval.key] ??
        legacyFieldByPeriod[activeInterval.id] ??
        legacyFieldByPeriod[`hour_${activeInterval.id}`]
      : "";
  const fallbackIntervalMask =
    activeInterval && legacyMaskByPeriod
      ? legacyMaskByPeriod[activeInterval.key] ??
        legacyMaskByPeriod[activeInterval.id] ??
        legacyMaskByPeriod[`hour_${activeInterval.id}`]
      : undefined;
  const activeField =
    selectedPeriodMode === "interval"
      ? activeMeasure?.fieldByInterval?.[activeInterval?.key ?? ""] ?? fallbackIntervalField ?? ""
      : activeMeasure?.fieldTotal ?? "";
  const activeMaskField =
    selectedPeriodMode === "interval"
      ? activeMeasure?.maskFieldByInterval?.[activeInterval?.key ?? ""] ?? fallbackIntervalMask
      : activeMeasure?.maskFieldTotal;
  const activeScaleType = activeMeasure?.scaleType ?? "sequential";
  const activeObservedField = selectedColorFileId ? `${selectedColorFileId}_observed_any` : "";
  const activeVisibilityField =
    selectedPeriodMode === "interval"
      ? activeMeasure?.visibilityFieldByInterval?.[activeInterval?.key ?? ""]
      : activeMeasure?.visibilityFieldTotal;
  const activeHideFilterField = activeVisibilityField ?? activeMaskField ?? activeObservedField;
  const activeLegendTitle = [
    colorFiles.find((item) => item.id === selectedColorFileId)?.label ?? "",
    activeMeasure?.label ?? "",
    selectedPeriodMode === "interval" ? activeInterval?.label ?? "" : "Total"
  ]
    .filter(Boolean)
    .join(" | ");
  const activeLinksIndex = linksIndex;

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
    if (!hideUnobservedLinks || !selectedLinkId || !activeHideFilterField) {
      return;
    }
    const selectedObserved = coerceBoolean(
      activeLinksIndex[selectedLinkId]?.properties?.[activeHideFilterField]
    );
    if (!selectedObserved) {
      clearSelection();
    }
  }, [activeHideFilterField, activeLinksIndex, clearSelection, hideUnobservedLinks, selectedLinkId]);

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

  const activeLinksGeojsonBase = useMemo<GeoJSON.FeatureCollection | null>(() => {
    return linksGeojson;
  }, [linksGeojson]);

  const selectedOdFeature = useMemo<
    GeoJSON.Feature<GeoJSON.Point, Record<string, unknown>> | null
  >(() => {
    if (!selectedOdKey || !odPointsGeojson) return null;
    const [pointId, role] = selectedOdKey.split("__");
    for (const feature of odPointsGeojson.features) {
      const props = feature.properties as Record<string, unknown> | null;
      if (!props || feature.geometry?.type !== "Point") continue;
      const featurePointId = String(props.point_id ?? props.node_id ?? "");
      const featureRole = String(props.point_role ?? "");
      if (featurePointId === pointId && featureRole === role) {
        return feature as GeoJSON.Feature<GeoJSON.Point, Record<string, unknown>>;
      }
    }
    return null;
  }, [odPointsGeojson, selectedOdKey]);

  type NodeDemandValue = { origin: number; destination: number };

  // Aggregate OD demand by node: "_total" key = sum across all intervals; per-interval keys
  // match the keys discovered from ratio_dir CSVs.
  const demandByNodeByPeriod = useMemo<Record<string, Record<string, NodeDemandValue>>>(() => {
    if (!odDemand) {
      return { _total: {} };
    }
    const result: Record<string, Record<string, NodeDemandValue>> = { _total: {} };
    for (const interval of odDemand.intervals) {
      result[interval.key] = {};
    }
    for (const [nodeId, record] of Object.entries(odDemand.by_node)) {
      let totalOrigin = 0;
      let totalDestination = 0;
      for (let k = 0; k < odDemand.intervals.length; k += 1) {
        const intervalKey = odDemand.intervals[k].key;
        const origin = Number(record.origin?.[k] ?? 0) || 0;
        const destination = Number(record.destination?.[k] ?? 0) || 0;
        if (origin || destination) {
          result[intervalKey][nodeId] = { origin, destination };
        }
        totalOrigin += origin;
        totalDestination += destination;
      }
      if (totalOrigin || totalDestination) {
        result._total[nodeId] = { origin: totalOrigin, destination: totalDestination };
      }
    }
    return result;
  }, [odDemand]);

  const activeDemandKey =
    selectedPeriodMode === "interval" && selectedIntervalKey ? selectedIntervalKey : "_total";
  const demandByNode = demandByNodeByPeriod[activeDemandKey] ?? demandByNodeByPeriod._total ?? {};

  const pathCountThresholdMax = useMemo(() => {
    if (!activeLinksGeojsonBase) {
      return 0;
    }
    const counts = activeLinksGeojsonBase.features
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
  }, [activeField, activeLinksGeojsonBase, activeVisibilityField, colorBy, linkToPaths]);

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
    if (!activeLinksGeojsonBase) {
      return null;
    }
    return {
      ...activeLinksGeojsonBase,
      features: activeLinksGeojsonBase.features.filter((feature) => {
        const linkId = String(feature.properties?.link_id ?? "");
        const coveredOk = !showCoveredLinksOnly || linkId in linkToPaths;
        const observedOk =
          !hideUnobservedLinks ||
          !activeHideFilterField ||
          coerceBoolean(feature.properties?.[activeHideFilterField]);
        const pathCountOk = (linkToPaths[linkId]?.length ?? 0) <= activePathCountThreshold;
        return coveredOk && observedOk && pathCountOk;
      })
    };
  }, [
    activeHideFilterField,
    activeLinksGeojsonBase,
    activePathCountThreshold,
    hideUnobservedLinks,
    linkToPaths,
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
        return buildPathGeometry(path, activeLinksIndex);
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
  }, [activeLinksIndex, highlightedPathIds, pathSummary]);

  const linkProperties = selectedLinkId ? activeLinksIndex[selectedLinkId]?.properties ?? null : null;
  const activeMetricValue =
    selectedLinkId && activeLinksIndex[selectedLinkId]
      ? activeLinksIndex[selectedLinkId].properties?.[activeField || colorBy]
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
        selectedPeriodMode={selectedPeriodMode}
        selectedIntervalKey={selectedIntervalKey}
        intervals={intervals}
        maxHighlightedPaths={maxHighlightedPaths}
        maxHighlightedPathsLimit={maxHighlightedPathsLimit}
        pathCountThreshold={activePathCountThreshold}
        pathCountThresholdMax={pathCountThresholdMax}
        linkWidthScale={linkWidthScale}
        lineOffsetPixels={lineOffsetPixels}
        odPointSize={odPointSize}
        odLabelSize={odLabelSize}
        pathOpacityPercent={pathOpacityPercent}
        showCoveredLinksOnly={showCoveredLinksOnly}
        hideUnobservedLinks={hideUnobservedLinks}
        showOdPoints={showOdPoints}
        showOdLabels={showOdLabels}
        odDemandMode={odDemandMode}
        onExperimentChange={setSelectedExperimentId}
        onColorFileChange={setSelectedColorFileId}
        onMeasureChange={setSelectedMeasureId}
        onPeriodModeChange={setSelectedPeriodMode}
        onIntervalKeyChange={setSelectedIntervalKey}
        onMaxHighlightedPathsChange={setMaxHighlightedPaths}
        onPathCountThresholdChange={setPathCountThreshold}
        onLinkWidthScaleChange={setLinkWidthScale}
        onLineOffsetPixelsChange={setLineOffsetPixels}
        onOdPointSizeChange={setOdPointSize}
        onOdLabelSizeChange={setOdLabelSize}
        onPathOpacityPercentChange={setPathOpacityPercent}
        onShowCoveredLinksOnlyChange={setShowCoveredLinksOnly}
        onHideUnobservedLinksChange={setHideUnobservedLinks}
        onShowOdPointsChange={setShowOdPoints}
        onShowOdLabelsChange={setShowOdLabels}
        onOdDemandModeChange={setOdDemandMode}
        onClearSelection={clearSelection}
      />
      <div className="content-shell">
        <div className="map-column">
          <MapView
            linksGeojson={activeLinksGeojson}
            odPointsGeojson={showOdPoints || odDemandMode !== "off" ? odPointsGeojson : null}
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
            pathOpacityPercent={pathOpacityPercent}
            showOdLabels={showOdLabels}
            odDemandMode={odDemandMode}
            demandByNode={demandByNode}
            viewKey={selectedExperimentId || "default"}
            onSelectLink={setSelectedLinkId}
            onSelectPath={setSelectedPathId}
            onSelectOd={setSelectedOdKey}
          />
          <Legend field={activeLegendTitle || activeField || colorBy} stats={fieldStats} />
        </div>
        <Sidebar
          selectedLinkId={selectedLinkId}
          selectedPathId={selectedPathId}
          selectedOdFeature={selectedOdFeature}
          selectedOdDemand={
            selectedOdFeature
              ? demandByNode[
                  String(
                    (selectedOdFeature.properties as Record<string, unknown> | null)?.node_id ??
                      (selectedOdFeature.properties as Record<string, unknown> | null)?.point_id ??
                      ""
                  )
                ] ?? { origin: 0, destination: 0 }
              : null
          }
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
