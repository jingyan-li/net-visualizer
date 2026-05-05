import {
  loadColorFile,
  loadContribBucket,
  loadLegacyContribShard,
  loadJson,
  loadExperimentIndex,
  loadExperimentManifest,
  loadInitialData
} from "./loadData";
import { buildPathGeometry } from "./buildPathGeometry";
import type {
  ColorFileDefinition,
  ExperimentIndexEntry,
  ExperimentManifest,
  InitialData,
  PathContribution,
  PathSummary
} from "../types";

export interface DataProvider {
  loadExperimentIndex(): Promise<ExperimentIndexEntry[]>;
  loadManifest(manifestPath: string): Promise<ExperimentManifest>;
  loadInitialData(manifest: ExperimentManifest): Promise<InitialData>;
  loadColorFile(path: string): Promise<ColorFileDefinition>;
  getLinkContributions(manifest: ExperimentManifest, linkId: string): Promise<PathContribution[]>;
  getPathSummary(manifest: ExperimentManifest, pathId: string): Promise<PathSummary | null>;
  getPathGeometry(manifest: ExperimentManifest, pathId: string): Promise<GeoJSON.Feature | null>;
}

export class StaticJsonDataProvider implements DataProvider {
  private initialDataCache = new Map<string, InitialData>();
  private manifestCache = new Map<string, ExperimentManifest>();
  private colorFileCache = new Map<string, ColorFileDefinition>();
  private experimentIndexCache: ExperimentIndexEntry[] | null = null;
  private contribBucketIndexCache = new Map<string, Record<string, string>>();
  private contribBucketCache = new Map<string, Record<string, PathContribution[]>>();

  async loadExperimentIndex(): Promise<ExperimentIndexEntry[]> {
    if (this.experimentIndexCache) {
      return this.experimentIndexCache;
    }
    this.experimentIndexCache = await loadExperimentIndex();
    return this.experimentIndexCache;
  }

  async loadManifest(manifestPath: string): Promise<ExperimentManifest> {
    const cached = this.manifestCache.get(manifestPath);
    if (cached) {
      return cached;
    }
    const manifest = await loadExperimentManifest(manifestPath);
    this.manifestCache.set(manifestPath, manifest);
    return manifest;
  }

  async loadInitialData(manifest: ExperimentManifest): Promise<InitialData> {
    const cached = this.initialDataCache.get(manifest.id);
    if (cached) {
      return cached;
    }
    const loaded = await loadInitialData(manifest);
    this.initialDataCache.set(manifest.id, loaded);
    return loaded;
  }

  async loadColorFile(path: string): Promise<ColorFileDefinition> {
    const cached = this.colorFileCache.get(path);
    if (cached) {
      return cached;
    }
    const loaded = await loadColorFile(path);
    this.colorFileCache.set(path, loaded);
    return loaded;
  }

  async getLinkContributions(
    manifest: ExperimentManifest,
    linkId: string
  ): Promise<PathContribution[]> {
    const data = await this.loadInitialData(manifest);
    if (data.linkPathContrib?.[linkId]) {
      return data.linkPathContrib[linkId];
    }
    if (!manifest.linkPathContribBucketIndex || !manifest.linkPathContribBucketDir) {
      return await loadLegacyContribShard(manifest, linkId);
    }
    let bucketIndex = this.contribBucketIndexCache.get(manifest.id);
    if (!bucketIndex) {
      bucketIndex = await loadJson<Record<string, string>>(manifest.linkPathContribBucketIndex);
      this.contribBucketIndexCache.set(manifest.id, bucketIndex);
    }

    const bucketFile = bucketIndex[linkId];
    if (!bucketFile) {
      return [];
    }

    const bucketCacheKey = `${manifest.id}:${bucketFile}`;
    let bucket = this.contribBucketCache.get(bucketCacheKey);
    if (!bucket) {
      bucket = await loadContribBucket(manifest, bucketFile);
      this.contribBucketCache.set(bucketCacheKey, bucket);
      return bucket[linkId] ?? [];
    }

    return bucket[linkId] ?? [];
  }

  async getPathSummary(manifest: ExperimentManifest, pathId: string): Promise<PathSummary | null> {
    const data = await this.loadInitialData(manifest);
    return data.pathSummary[pathId] ?? null;
  }

  async getPathGeometry(
    manifest: ExperimentManifest,
    pathId: string
  ): Promise<GeoJSON.Feature | null> {
    const data = await this.loadInitialData(manifest);
    const path = data.pathSummary[pathId];
    if (!path) {
      return null;
    }
    return buildPathGeometry(path, data.linksIndex);
  }
}

export const dataProvider = new StaticJsonDataProvider();
