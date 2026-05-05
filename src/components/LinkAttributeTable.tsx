interface LinkAttributeTableProps {
  properties: Record<string, unknown>;
}

export function LinkAttributeTable({ properties }: LinkAttributeTableProps) {
  const entries = Object.entries(properties);

  if (entries.length === 0) {
    return <p className="empty-state">No link attributes available.</p>;
  }

  return (
    <table className="data-table">
      <tbody>
        {entries.map(([key, value]) => (
          <tr key={key}>
            <th>{key}</th>
            <td>{String(value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

