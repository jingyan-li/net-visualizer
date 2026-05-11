import type { ColorFileDefinition, ColorFileEntry, ExperimentIndexEntry, IntervalDefinition } from "../types";

interface ToolbarProps {
  experiments: ExperimentIndexEntry[];
  selectedExperimentId: string;
  colorFiles: ColorFileEntry[];
  selectedColorFileId: string;
  colorFileDefinition: ColorFileDefinition | null;
  selectedMeasureId: string;
  selectedPeriodMode: "total" | "interval";
  selectedIntervalKey: string | null;
  intervals: IntervalDefinition[];
  maxHighlightedPaths: number;
  maxHighlightedPathsLimit: number;
  pathCountThreshold: number;
  pathCountThresholdMax: number;
  linkWidthScale: number;
  lineOffsetPixels: number;
  odPointSize: number;
  odLabelSize: number;
  pathOpacityPercent: number;
  showCoveredLinksOnly: boolean;
  hideUnobservedLinks: boolean;
  showOdPoints: boolean;
  showOdLabels: boolean;
  odDemandMode: "off" | "origin" | "destination";
  onExperimentChange: (value: string) => void;
  onColorFileChange: (value: string) => void;
  onMeasureChange: (value: string) => void;
  onPeriodModeChange: (value: "total" | "interval") => void;
  onIntervalKeyChange: (value: string | null) => void;
  onMaxHighlightedPathsChange: (value: number) => void;
  onPathCountThresholdChange: (value: number) => void;
  onLinkWidthScaleChange: (value: number) => void;
  onLineOffsetPixelsChange: (value: number) => void;
  onOdPointSizeChange: (value: number) => void;
  onOdLabelSizeChange: (value: number) => void;
  onPathOpacityPercentChange: (value: number) => void;
  onShowCoveredLinksOnlyChange: (value: boolean) => void;
  onHideUnobservedLinksChange: (value: boolean) => void;
  onShowOdPointsChange: (value: boolean) => void;
  onShowOdLabelsChange: (value: boolean) => void;
  onOdDemandModeChange: (value: "off" | "origin" | "destination") => void;
  onClearSelection: () => void;
}

export function Toolbar({
  experiments,
  selectedExperimentId,
  colorFiles,
  selectedColorFileId,
  colorFileDefinition,
  selectedMeasureId,
  selectedPeriodMode,
  selectedIntervalKey,
  intervals,
  maxHighlightedPaths,
  maxHighlightedPathsLimit,
  pathCountThreshold,
  pathCountThresholdMax,
  linkWidthScale,
  lineOffsetPixels,
  odPointSize,
  odLabelSize,
  pathOpacityPercent,
  showCoveredLinksOnly,
  hideUnobservedLinks,
  showOdPoints,
  showOdLabels,
  odDemandMode,
  onExperimentChange,
  onColorFileChange,
  onMeasureChange,
  onPeriodModeChange,
  onIntervalKeyChange,
  onMaxHighlightedPathsChange,
  onPathCountThresholdChange,
  onLinkWidthScaleChange,
  onLineOffsetPixelsChange,
  onOdPointSizeChange,
  onOdLabelSizeChange,
  onPathOpacityPercentChange,
  onShowCoveredLinksOnlyChange,
  onHideUnobservedLinksChange,
  onShowOdPointsChange,
  onShowOdLabelsChange,
  onOdDemandModeChange,
  onClearSelection
}: ToolbarProps) {
  const measures = colorFileDefinition?.measures ?? [];
  const intervalDatalistId = `interval-ticks-${selectedColorFileId || "default"}`;
  const selectedIntervalIndex = Math.max(
    0,
    intervals.findIndex((interval) => interval.key === selectedIntervalKey)
  );

  return (
    <div className="toolbar">
      <label>
        <span>Experiment</span>
        <select value={selectedExperimentId} onChange={(event) => onExperimentChange(event.target.value)}>
          {experiments.map((experiment) => (
            <option key={experiment.id} value={experiment.id}>
              {experiment.label}
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>Color file</span>
        <select value={selectedColorFileId} onChange={(event) => onColorFileChange(event.target.value)}>
          {colorFiles.map((colorFile) => (
            <option key={colorFile.id} value={colorFile.id}>
              {colorFile.label}
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>Metric</span>
        <select value={selectedMeasureId} onChange={(event) => onMeasureChange(event.target.value)}>
          {measures.map((measure) => (
            <option key={measure.id} value={measure.id}>
              {measure.label}
            </option>
          ))}
        </select>
      </label>

      <label>
        <span>Period</span>
        <select
          value={selectedPeriodMode}
          onChange={(event) => onPeriodModeChange(event.target.value as "total" | "interval")}
        >
          <option value="total">Total</option>
          <option value="interval">By interval</option>
        </select>
      </label>

      {selectedPeriodMode === "interval" && intervals.length > 0 ? (
        <label className="slider-control">
          <span>{`Interval (${intervals[selectedIntervalIndex]?.kind ?? "n/a"}): ${intervals[selectedIntervalIndex]?.label ?? "n/a"}`}</span>
          <input
            type="range"
            min="0"
            max={String(Math.max(0, intervals.length - 1))}
            step="1"
            value={selectedIntervalIndex}
            list={intervalDatalistId}
            onChange={(event) => {
              const nextInterval = intervals[Number(event.target.value)];
              onIntervalKeyChange(nextInterval?.key ?? null);
            }}
          />
          <datalist id={intervalDatalistId}>
            {intervals.map((interval) => (
              <option key={interval.key} value={interval.index} label={interval.id} />
            ))}
          </datalist>
        </label>
      ) : null}

      <label>
        <span>Displayed paths: {maxHighlightedPaths}</span>
        <input
          type="range"
          min="1"
          max={String(Math.max(1, maxHighlightedPathsLimit))}
          step="1"
          value={maxHighlightedPaths}
          onChange={(event) => onMaxHighlightedPathsChange(Number(event.target.value))}
        />
      </label>

      <label>
        <span>Link path-count filter: {pathCountThreshold}</span>
        <div className="number-control">
          <input
            type="number"
            min="0"
            max={String(Math.max(0, pathCountThresholdMax))}
            step="1"
            value={pathCountThreshold}
            onChange={(event) => onPathCountThresholdChange(Number(event.target.value))}
          />
          <span className="number-control-hint">{`max ${pathCountThresholdMax}`}</span>
        </div>
      </label>

      <label className="slider-control">
        <span>Link width: {linkWidthScale.toFixed(1)} px</span>
        <input
          type="range"
          min="1.5"
          max="10"
          step="0.5"
          value={linkWidthScale}
          onChange={(event) => onLinkWidthScaleChange(Number(event.target.value))}
        />
      </label>

      <label className="slider-control">
        <span>Centerline offset: {lineOffsetPixels.toFixed(1)} px</span>
        <input
          type="range"
          min="0"
          max="12"
          step="0.5"
          value={lineOffsetPixels}
          onChange={(event) => onLineOffsetPixelsChange(Number(event.target.value))}
        />
      </label>

      <label className="slider-control">
        <span>OD point size: {odPointSize.toFixed(1)} px</span>
        <input
          type="range"
          min="2"
          max="10"
          step="0.5"
          value={odPointSize}
          onChange={(event) => onOdPointSizeChange(Number(event.target.value))}
        />
      </label>

      <label className="slider-control">
        <span>OD label size: {odLabelSize.toFixed(0)} px</span>
        <input
          type="range"
          min="4"
          max="20"
          step="1"
          value={odLabelSize}
          onChange={(event) => onOdLabelSizeChange(Number(event.target.value))}
        />
      </label>

      <label>
        <span>Path opacity: {pathOpacityPercent}%</span>
        <div className="number-control">
          <input
            type="number"
            min="0"
            max="100"
            step="1"
            value={pathOpacityPercent}
            onChange={(event) => onPathOpacityPercentChange(Number(event.target.value))}
          />
          <span className="number-control-hint">0-100</span>
        </div>
      </label>

      <label className="toggle-control">
        <span>Path-covered links only</span>
        <input
          type="checkbox"
          checked={showCoveredLinksOnly}
          onChange={(event) => onShowCoveredLinksOnlyChange(event.target.checked)}
        />
      </label>

      <label className="toggle-control">
        <span>Hide unobserved links</span>
        <input
          type="checkbox"
          checked={hideUnobservedLinks}
          onChange={(event) => onHideUnobservedLinksChange(event.target.checked)}
        />
      </label>

      <label className="toggle-control">
        <span>Show OD points</span>
        <input
          type="checkbox"
          checked={showOdPoints}
          onChange={(event) => onShowOdPointsChange(event.target.checked)}
        />
      </label>

      <label className="toggle-control">
        <span>Show OD labels</span>
        <input
          type="checkbox"
          checked={showOdLabels}
          onChange={(event) => onShowOdLabelsChange(event.target.checked)}
        />
      </label>

      <div className="segmented-control">
        <span>OD demand</span>
        <div className="segmented-control-buttons">
          {([
            ["off", "Off"],
            ["origin", "O"],
            ["destination", "D"]
          ] as const).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={odDemandMode === value ? "segmented-active" : ""}
              onClick={() => onOdDemandModeChange(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <button type="button" onClick={onClearSelection}>
        Clear selection
      </button>
    </div>
  );
}
