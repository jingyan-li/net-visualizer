import type { PathContribution } from "../types";

interface PathListProps {
  paths: PathContribution[];
  selectedPathId: string | null;
  onSelectPath: (pathId: string) => void;
}

export function PathList({ paths, selectedPathId, onSelectPath }: PathListProps) {
  if (paths.length === 0) {
    return <p className="empty-state">No paths found for this link.</p>;
  }

  return (
    <div className="path-list">
      {paths.map((record) => {
        const active = record.path_id === selectedPathId;
        return (
          <button
            key={`${record.path_id}-${record.depart_interval ?? "all"}-${record.vehicle_class ?? "all"}`}
            type="button"
            className={`path-card ${active ? "active" : ""}`}
            onClick={() => onSelectPath(record.path_id)}
          >
            <div className="path-card-row">
              <strong>{record.path_id}</strong>
              <span>{record.contribution?.toFixed?.(2) ?? "n/a"}</span>
            </div>
            <div className="path-card-meta">
              <span>{record.od_id ?? "OD n/a"}</span>
              <span>{record.depart_interval ?? "Interval n/a"}</span>
              <span>{record.vehicle_class ?? "Class n/a"}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

