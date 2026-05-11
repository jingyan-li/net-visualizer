import { LinkAttributeTable } from "./LinkAttributeTable";
import { OdSummaryTable } from "./OdSummaryTable";
import { PathList } from "./PathList";
import type { PathContribution } from "../types";

interface SidebarProps {
  selectedLinkId: string | null;
  selectedPathId: string | null;
  selectedOdFeature: GeoJSON.Feature<GeoJSON.Point, Record<string, unknown>> | null;
  selectedOdDemand: { origin: number; destination: number } | null;
  linkProperties: Record<string, unknown> | null;
  contributions: PathContribution[];
  displayedContributions: PathContribution[];
  totalPathCount: number;
  hasPathCoverage: boolean;
  activeMetricLabel: string;
  activeMetricValue: unknown;
  onSelectPath: (pathId: string) => void;
  loading: boolean;
}

function summarize(records: PathContribution[]) {
  const totalContribution = records.reduce((sum, record) => sum + (record.contribution ?? 0), 0);
  const byOd = new Map<string, number>();

  for (const record of records) {
    const key = record.od_id ?? "unknown";
    byOd.set(key, (byOd.get(key) ?? 0) + (record.contribution ?? 0));
  }

  const topOds = Array.from(byOd.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([key]) => key);

  return {
    totalContribution,
    topOds
  };
}

export function Sidebar({
  selectedLinkId,
  selectedPathId,
  selectedOdFeature,
  selectedOdDemand,
  linkProperties,
  contributions,
  displayedContributions,
  totalPathCount,
  hasPathCoverage,
  activeMetricLabel,
  activeMetricValue,
  onSelectPath,
  loading
}: SidebarProps) {
  if (selectedOdFeature) {
    const props = selectedOdFeature.properties ?? {};
    const role = String(props.point_role ?? "");
    const roleLabel = role === "O" ? "Origin" : role === "D" ? "Destination" : role || "n/a";
    const ownDemand =
      role === "O"
        ? selectedOdDemand?.origin
        : role === "D"
          ? selectedOdDemand?.destination
          : undefined;
    const coords = (selectedOdFeature.geometry?.coordinates ?? []) as number[];
    const [lng, lat] = coords;
    return (
      <aside className="sidebar">
        <h2>Selected OD Node</h2>
        <div className="sidebar-card">
          <div className="metric-grid">
            <div>
              <span className="metric-label">Node ID</span>
              <strong>{String(props.node_id ?? props.point_id ?? "n/a")}</strong>
            </div>
            <div>
              <span className="metric-label">Role</span>
              <strong>{roleLabel}</strong>
            </div>
            <div>
              <span className="metric-label">{role === "D" ? "Destination demand" : "Origin demand"}</span>
              <strong>{ownDemand !== undefined ? ownDemand.toFixed(3) : "0"}</strong>
            </div>
            <div>
              <span className="metric-label">Origin demand (this node)</span>
              <strong>{(selectedOdDemand?.origin ?? 0).toFixed(3)}</strong>
            </div>
            <div>
              <span className="metric-label">Destination demand (this node)</span>
              <strong>{(selectedOdDemand?.destination ?? 0).toFixed(3)}</strong>
            </div>
            {Number.isFinite(lng) && Number.isFinite(lat) ? (
              <div>
                <span className="metric-label">Lon, Lat</span>
                <strong>{`${lng.toFixed(5)}, ${lat.toFixed(5)}`}</strong>
              </div>
            ) : null}
          </div>
        </div>

        <section className="sidebar-section">
          <h3>OD Properties</h3>
          <LinkAttributeTable properties={props} />
        </section>
      </aside>
    );
  }

  if (!selectedLinkId) {
    return (
      <aside className="sidebar">
        <h2>Inspector</h2>
        <p className="empty-state">Click a link or an OD node to inspect attributes.</p>
      </aside>
    );
  }

  const summary = summarize(contributions);
  const activeMetricDisplay =
    activeMetricValue === null || activeMetricValue === undefined || activeMetricValue === ""
      ? "n/a"
      : typeof activeMetricValue === "number"
        ? activeMetricValue.toFixed(4)
        : String(activeMetricValue);

  return (
    <aside className="sidebar">
      <h2>Selected Link</h2>
      <div className="sidebar-card">
        <div className="metric-grid">
          <div>
            <span className="metric-label">Link ID</span>
            <strong>{selectedLinkId}</strong>
          </div>
          <div>
            <span className="metric-label">Paths</span>
            <strong>{totalPathCount}</strong>
          </div>
          <div>
            <span className="metric-label">Displayed</span>
            <strong>{displayedContributions.length}</strong>
          </div>
          <div>
            <span className="metric-label">{activeMetricLabel || "Selected metric"}</span>
            <strong>{activeMetricDisplay}</strong>
          </div>
          <div>
            <span className="metric-label">Total contribution</span>
            <strong>{summary.totalContribution.toFixed(2)}</strong>
          </div>
          <div>
            <span className="metric-label">Top ODs</span>
            <strong>{summary.topOds.join(", ") || "n/a"}</strong>
          </div>
        </div>
      </div>

      <section className="sidebar-section">
        <h3>Link Attributes</h3>
        {linkProperties ? <LinkAttributeTable properties={linkProperties} /> : <p className="empty-state">No link properties found.</p>}
      </section>

      <section className="sidebar-section">
        <h3>OD Summary</h3>
        <OdSummaryTable contributions={contributions} />
      </section>

      <section className="sidebar-section">
        <h3>Paths</h3>
        {loading ? (
          <p className="empty-state">Loading contribution records...</p>
        ) : !hasPathCoverage ? (
          <p className="empty-state">
            This link is not covered by the current `path_table.csv`, so there are no
            associated paths to highlight.
          </p>
        ) : (
          <PathList paths={displayedContributions} selectedPathId={selectedPathId} onSelectPath={onSelectPath} />
        )}
      </section>
    </aside>
  );
}
