import { create } from "zustand";
import type { InitialData, LinkId, PathContribution, PathId } from "../types";

interface AppState {
  linksGeojson: GeoJSON.FeatureCollection | null;
  odPointsGeojson: GeoJSON.FeatureCollection | null;
  linksIndex: InitialData["linksIndex"];
  linkToPaths: InitialData["linkToPaths"];
  pathSummary: InitialData["pathSummary"];
  linkPathContrib: Record<LinkId, PathContribution[]>;
  selectedLinkId: LinkId | null;
  selectedPathId: PathId | null;
  highlightedPathIds: PathId[];
  colorBy: string;
  numericFields: string[];
  categoricalFields: string[];
  maxHighlightedPaths: number;
  linkWidthScale: number;
  lineOffsetPixels: number;
  odPointSize: number;
  odLabelSize: number;
  pathOpacityPercent: number;
  pathCountThreshold: number | null;
  showCoveredLinksOnly: boolean;
  hideUnobservedLinks: boolean;
  showOdPoints: boolean;
  showOdLabels: boolean;
  loading: boolean;
  error: string | null;
  setInitialData: (data: InitialData, numericFields: string[], categoricalFields: string[]) => void;
  setSelectedLinkId: (id: LinkId | null) => void;
  setSelectedPathId: (id: PathId | null) => void;
  setColorBy: (field: string) => void;
  setMaxHighlightedPaths: (value: number) => void;
  setLinkWidthScale: (value: number) => void;
  setLineOffsetPixels: (value: number) => void;
  setOdPointSize: (value: number) => void;
  setOdLabelSize: (value: number) => void;
  setPathOpacityPercent: (value: number) => void;
  setPathCountThreshold: (value: number | null) => void;
  setShowCoveredLinksOnly: (value: boolean) => void;
  setHideUnobservedLinks: (value: boolean) => void;
  setShowOdPoints: (value: boolean) => void;
  setShowOdLabels: (value: boolean) => void;
  setLinkContributions: (linkId: LinkId, records: PathContribution[]) => void;
  setHighlightedPathIds: (ids: PathId[]) => void;
  setLoading: (value: boolean) => void;
  setError: (message: string | null) => void;
  clearSelection: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  linksGeojson: null,
  odPointsGeojson: null,
  linksIndex: {},
  linkToPaths: {},
  pathSummary: {},
  linkPathContrib: {},
  selectedLinkId: null,
  selectedPathId: null,
  highlightedPathIds: [],
  colorBy: "link_id",
  numericFields: [],
  categoricalFields: [],
  maxHighlightedPaths: 3,
  linkWidthScale: 3,
  lineOffsetPixels: 2.5,
  odPointSize: 3.5,
  odLabelSize: 12,
  pathOpacityPercent: 10,
  pathCountThreshold: null,
  showCoveredLinksOnly: false,
  hideUnobservedLinks: false,
  showOdPoints: false,
  showOdLabels: true,
  loading: true,
  error: null,
  setInitialData: (data, numericFields, categoricalFields) =>
    set(() => ({
      linksGeojson: data.linksGeojson,
      odPointsGeojson: data.odPointsGeojson,
      linksIndex: data.linksIndex,
      linkToPaths: data.linkToPaths,
      pathSummary: data.pathSummary,
      linkPathContrib: data.linkPathContrib ?? {},
      numericFields,
      categoricalFields,
      colorBy: numericFields[0] ?? "link_id",
      loading: false,
      error: null
    })),
  setSelectedLinkId: (id) =>
    set(() => ({
      selectedLinkId: id,
      selectedPathId: null
    })),
  setSelectedPathId: (id) => set(() => ({ selectedPathId: id })),
  setColorBy: (field) => set(() => ({ colorBy: field })),
  setMaxHighlightedPaths: (value) => set(() => ({ maxHighlightedPaths: value })),
  setLinkWidthScale: (value) => set(() => ({ linkWidthScale: value })),
  setLineOffsetPixels: (value) => set(() => ({ lineOffsetPixels: value })),
  setOdPointSize: (value) => set(() => ({ odPointSize: value })),
  setOdLabelSize: (value) => set(() => ({ odLabelSize: value })),
  setPathOpacityPercent: (value) => set(() => ({ pathOpacityPercent: value })),
  setPathCountThreshold: (value) => set(() => ({ pathCountThreshold: value })),
  setShowCoveredLinksOnly: (value) => set(() => ({ showCoveredLinksOnly: value })),
  setHideUnobservedLinks: (value) => set(() => ({ hideUnobservedLinks: value })),
  setShowOdPoints: (value) => set(() => ({ showOdPoints: value })),
  setShowOdLabels: (value) => set(() => ({ showOdLabels: value })),
  setLinkContributions: (linkId, records) =>
    set((state) => ({
      linkPathContrib: {
        ...state.linkPathContrib,
        [linkId]: records
      }
    })),
  setHighlightedPathIds: (ids) => set(() => ({ highlightedPathIds: ids })),
  setLoading: (value) => set(() => ({ loading: value })),
  setError: (message) => set(() => ({ error: message })),
  clearSelection: () =>
    set(() => ({
      selectedLinkId: null,
      selectedPathId: null,
      highlightedPathIds: []
    }))
}));
