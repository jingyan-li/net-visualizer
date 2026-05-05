import type { PathContribution } from "../types";

interface OdSummaryTableProps {
  contributions: PathContribution[];
}

interface OdSummaryRow {
  odKey: string;
  originNodeId: string;
  destinationNodeId: string;
  pathCount: number;
  totalContribution: number;
}

function buildRows(contributions: PathContribution[]): OdSummaryRow[] {
  const grouped = new Map<string, OdSummaryRow & { pathIds: Set<string> }>();

  for (const record of contributions) {
    const originNodeId = record.origin_node_id ?? "n/a";
    const destinationNodeId = record.destination_node_id ?? "n/a";
    const odKey = `${originNodeId}__${destinationNodeId}`;
    const existing = grouped.get(odKey);

    if (existing) {
      existing.pathIds.add(record.path_id);
      existing.totalContribution += record.contribution ?? 0;
      continue;
    }

      grouped.set(odKey, {
        odKey,
        originNodeId,
        destinationNodeId,
        pathCount: 0,
        totalContribution: record.contribution ?? 0,
        pathIds: new Set([record.path_id])
    });
  }

  return Array.from(grouped.values())
    .map((row) => ({
      odKey: row.odKey,
      originNodeId: row.originNodeId,
      destinationNodeId: row.destinationNodeId,
      pathCount: row.pathIds.size,
      totalContribution: row.totalContribution
    }))
    .sort((left, right) => {
      const contributionDelta = right.totalContribution - left.totalContribution;
      if (contributionDelta !== 0) {
        return contributionDelta;
      }
      const pathCountDelta = right.pathCount - left.pathCount;
      if (pathCountDelta !== 0) {
        return pathCountDelta;
      }
      return left.odKey.localeCompare(right.odKey);
    });
}

export function OdSummaryTable({ contributions }: OdSummaryTableProps) {
  const rows = buildRows(contributions);

  if (rows.length === 0) {
    return <p className="empty-state">No OD summary available.</p>;
  }

  return (
    <table className="data-table od-summary-table">
      <thead>
        <tr>
          <th>O node id</th>
          <th>D node id</th>
          <th>Paths / Contribution</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.odKey}>
            <td>{row.originNodeId}</td>
            <td>{row.destinationNodeId}</td>
            <td>{`${row.pathCount} / ${row.totalContribution.toFixed(4)}`}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
