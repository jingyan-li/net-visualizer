import type {
  ColorFileDefinition,
  ExperimentIndexEntry,
  ExperimentManifest,
  InitialData,
  LinkIndexRecord,
  PathContribution,
  PathSummary
} from "../types";

export async function loadJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load ${url}: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function loadExperimentIndex(): Promise<ExperimentIndexEntry[]> {
  return await loadJson<ExperimentIndexEntry[]>("/data/experiments/index.json");
}

export async function loadExperimentManifest(url: string): Promise<ExperimentManifest> {
  return await loadJson<ExperimentManifest>(url);
}

export async function loadInitialData(manifest: ExperimentManifest): Promise<InitialData> {
  const [linksGeojson, odPointsGeojson, linksIndex, linkToPaths, pathSummary] = await Promise.all([
    loadJson<GeoJSON.FeatureCollection>(manifest.linksGeojson),
    manifest.odPointsGeojson
      ? loadJson<GeoJSON.FeatureCollection>(manifest.odPointsGeojson)
      : Promise.resolve(null),
    loadJson<Record<string, LinkIndexRecord>>(manifest.linksIndex),
    loadJson<Record<string, string[]>>(manifest.linkToPaths),
    loadJson<Record<string, PathSummary>>(manifest.pathSummary)
  ]);

  return {
    linksGeojson,
    odPointsGeojson,
    linksIndex,
    linkToPaths,
    pathSummary,
    linkPathContrib: undefined
  };
}

export async function loadColorFile(path: string): Promise<ColorFileDefinition> {
  return await loadJson<ColorFileDefinition>(path);
}

export async function loadContribBucket(
  manifest: ExperimentManifest,
  bucketFile: string
): Promise<Record<string, PathContribution[]>> {
  if (!manifest.linkPathContribBucketDir) {
    return {};
  }
  const bucketUrl = `${manifest.linkPathContribBucketDir}/${bucketFile}`;
  const response = await fetch(bucketUrl);
  const contentType = response.headers.get("content-type") ?? "";
  if (response.ok && contentType.includes("application/json")) {
    return (await response.json()) as Record<string, PathContribution[]>;
  }
  return {};
}

export async function loadLegacyContribShard(
  manifest: ExperimentManifest,
  linkId: string
): Promise<PathContribution[]> {
  if (!manifest.linkPathContribDir) {
    return [];
  }
  const response = await fetch(`${manifest.linkPathContribDir}/${linkId}.json`);
  const contentType = response.headers.get("content-type") ?? "";
  if (response.ok && contentType.includes("application/json")) {
    return (await response.json()) as PathContribution[];
  }
  return [];
}
