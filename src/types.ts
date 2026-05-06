export type LinkId = string;
export type PathId = string;

export interface LinkIndexRecord {
  properties: Record<string, unknown>;
  geometry: GeoJSON.LineString | GeoJSON.MultiLineString;
}

export interface PathSummary {
  path_id: string;
  od_id?: string;
  origin?: string;
  destination?: string;
  origin_node_id?: string;
  destination_node_id?: string;
  depart_interval?: string;
  vehicle_class?: string;
  path_flow?: number;
  num_links?: number;
  link_sequence: string[];
}

export interface PathContribution {
  link_id?: string;
  path_id: string;
  od_id?: string;
  origin?: string;
  destination?: string;
  origin_node_id?: string;
  destination_node_id?: string;
  depart_interval?: string;
  vehicle_class?: string;
  path_flow?: number;
  contribution?: number;
}

export interface InitialData {
  linksGeojson: GeoJSON.FeatureCollection;
  odPointsGeojson: GeoJSON.FeatureCollection | null;
  linksIndex: Record<LinkId, LinkIndexRecord>;
  linkToPaths: Record<LinkId, PathId[]>;
  pathSummary: Record<PathId, PathSummary>;
  linkPathContrib?: Record<LinkId, PathContribution[]>;
}

export interface ExperimentIndexEntry {
  id: string;
  label: string;
  manifestPath: string;
}

export interface ExperimentManifest {
  id: string;
  label: string;
  linksGeojson: string;
  odPointsGeojson?: string;
  linksIndex: string;
  linkToPaths: string;
  pathSummary: string;
  linkPathContribBucketDir?: string;
  linkPathContribBucketIndex?: string;
  linkPathContribDir?: string;
  colorFiles: ColorFileEntry[];
  defaultColorFileId?: string;
}

export interface ColorFileEntry {
  id: string;
  label: string;
  path: string;
}

export interface ColorMeasureDefinition {
  id: string;
  label: string;
  scaleType: "sequential" | "diverging";
  fieldTotal: string;
  fieldByInterval: Record<string, string>;
  maskFieldTotal?: string;
  maskFieldByInterval?: Record<string, string>;
  visibilityFieldTotal?: string;
  visibilityFieldByInterval?: Record<string, string>;
}

export interface IntervalDefinition {
  id: string;
  key: string;
  kind: "hour" | "15min";
  label: string;
  index: number;
}

export interface ColorFileDefinition {
  id: string;
  label: string;
  sourceFile?: string;
  defaultMeasureId?: string;
  defaultPeriodMode?: "total" | "interval";
  defaultIntervalKey?: string | null;
  intervals: IntervalDefinition[];
  measures: ColorMeasureDefinition[];
  notes?: Record<string, string>;
}
