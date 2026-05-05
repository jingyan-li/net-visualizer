import type { LinkIndexRecord, PathSummary } from "../types";

export function buildPathGeometry(
  path: PathSummary,
  linksIndex: Record<string, LinkIndexRecord>
): GeoJSON.Feature<GeoJSON.MultiLineString | GeoJSON.LineString> | null {
  const segments: GeoJSON.Position[][] = [];

  for (const linkId of path.link_sequence) {
    const link = linksIndex[String(linkId)];
    if (!link) {
      continue;
    }

    const geometry = link.geometry;
    if (geometry.type === "LineString") {
      segments.push(geometry.coordinates);
    } else if (geometry.type === "MultiLineString") {
      segments.push(...geometry.coordinates);
    }
  }

  if (segments.length === 0) {
    return null;
  }

  return {
    type: "Feature",
    properties: {
      ...path
    },
    geometry: {
      type: "MultiLineString",
      coordinates: segments
    }
  };
}
