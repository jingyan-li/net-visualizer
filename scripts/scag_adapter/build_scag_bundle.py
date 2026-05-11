from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_SCRIPT = PROJECT_ROOT / "scripts" / "experiment_bundle" / "build_experiment_bundle.py"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Adapt SCAG/MacPOSTS native files into a net-visualizer experiment bundle."
    )
    p.add_argument("--experiment-id", required=True)
    p.add_argument("--experiment-label", default=None)
    p.add_argument(
        "--macposts-dir",
        required=True,
        type=Path,
        help="Directory containing MacPOSTS native files: path_table, path_table_buffer.",
    )
    p.add_argument("--link-geojson", required=True, type=Path)
    p.add_argument("--eval-npz", required=True, type=Path)
    p.add_argument(
        "--taz-geojson",
        type=Path,
        default=None,
        help="Optional TAZ geojson. Only used as a fallback for OD node coords if a node is not present in the link network.",
    )
    p.add_argument(
        "--taz-crs",
        default="EPSG:26911",
        help="CRS to force on the TAZ geojson if its declared CRS is wrong (SCAG default UTM 11N).",
    )
    p.add_argument(
        "--interval-kind",
        choices=["15min", "hour"],
        default="15min",
        help="How to interpret abs_interval_idx from the eval npz.",
    )
    p.add_argument("--stage-root", type=Path, default=PROJECT_ROOT / "inputfile")
    p.add_argument(
        "--skip-bundle",
        action="store_true",
        help="Just stage the normalized inputs; do not invoke build_experiment_bundle.py.",
    )
    p.add_argument(
        "--max-od-pairs",
        type=int,
        default=None,
        help="If set, randomly subsample OD pairs (keeping all K paths per pair). "
             "Use for big networks where the bundle/browser cannot handle all paths.",
    )
    p.add_argument(
        "--sample-seed",
        type=int,
        default=0,
        help="RNG seed for --max-od-pairs subsampling.",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Step 1: link geojson -> linkID/N1/N2 schema
# ---------------------------------------------------------------------------

def adapt_network(link_geojson: Path, out_path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(link_geojson)
    rename = {}
    for src, dst in (("ID", "linkID"), ("FROM_NODE_ID", "N1"), ("TO_NODE_ID", "N2")):
        if src in gdf.columns and dst not in gdf.columns:
            rename[src] = dst
    if rename:
        gdf = gdf.rename(columns=rename)
    missing = [c for c in ("linkID", "N1", "N2") if c not in gdf.columns]
    if missing:
        raise SystemExit(f"link geojson is missing columns after rename: {missing}")
    gdf["linkID"] = gdf["linkID"].astype(int)
    gdf["N1"] = gdf["N1"].astype(int)
    gdf["N2"] = gdf["N2"].astype(int)
    gdf = gdf[gdf.geometry.notnull()].copy()

    dup_mask = gdf.duplicated(subset=["N1", "N2"], keep="first")
    dropped = int(dup_mask.sum())
    if dropped > 0:
        sample = gdf.loc[dup_mask, ["linkID", "N1", "N2"]].head(5).to_dict("records")
        print(
            f"[adapter] dropping {dropped} parallel-link duplicate(s) on (N1, N2); "
            f"keeping first by file order. sample: {sample}"
        )
        gdf = gdf.loc[~dup_mask].copy()

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    keep = ["linkID", "N1", "N2", "geometry"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    gdf[keep].to_file(out_path, driver="GeoJSON")
    return gdf[keep]


# ---------------------------------------------------------------------------
# Step 2a: nodes geojson derived from link endpoints (+ optional TAZ fallback)
# ---------------------------------------------------------------------------

def build_node_coords(network_gdf: gpd.GeoDataFrame) -> dict[int, tuple[float, float]]:
    coords: dict[int, tuple[float, float]] = {}
    for _, row in network_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        pts = list(geom.coords)
        n1 = int(row["N1"])
        n2 = int(row["N2"])
        if n1 not in coords:
            coords[n1] = (float(pts[0][0]), float(pts[0][1]))
        if n2 not in coords:
            coords[n2] = (float(pts[-1][0]), float(pts[-1][1]))
    return coords


def load_taz_fallback(taz_geojson: Path | None, taz_crs: str) -> dict[int, tuple[float, float]]:
    if taz_geojson is None:
        return {}
    gdf = gpd.read_file(taz_geojson)
    if gdf.crs is None or str(gdf.crs).upper() == "EPSG:4326":
        sample_geom = gdf.geometry.iloc[0]
        x = sample_geom.x if hasattr(sample_geom, "x") else sample_geom.centroid.x
        if abs(x) > 180:
            print(f"[adapter] TAZ geojson claims EPSG:4326 but coords look projected; forcing {taz_crs}")
            gdf = gdf.set_crs(taz_crs, allow_override=True)
    gdf = gdf.to_crs(epsg=4326)

    out: dict[int, tuple[float, float]] = {}
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        point = geom if hasattr(geom, "x") else geom.centroid
        lon, lat = float(point.x), float(point.y)
        for col in ("O_node_ID", "D_node_ID"):
            if col in gdf.columns and pd.notna(row.get(col)):
                out[int(row[col])] = (lon, lat)
    return out


def adapt_nodes(
    network_gdf: gpd.GeoDataFrame,
    needed_node_ids: set[int],
    taz_geojson: Path | None,
    taz_crs: str,
    out_path: Path,
) -> None:
    network_coords = build_node_coords(network_gdf)
    fallback = load_taz_fallback(taz_geojson, taz_crs)

    features = []
    missing: list[int] = []
    for nid in sorted(needed_node_ids):
        coord = network_coords.get(nid) or fallback.get(nid)
        if coord is None:
            missing.append(nid)
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {"node_id": int(nid)},
                "geometry": {"type": "Point", "coordinates": [coord[0], coord[1]]},
            }
        )

    if missing:
        raise SystemExit(
            f"No coordinates for {len(missing)} OD node(s) (e.g. {missing[:10]}). "
            "Pass --taz-geojson with a CRS-correct file, or check that connector links exist."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    geojson = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }
    out_path.write_text(json.dumps(geojson))


# ---------------------------------------------------------------------------
# Step 2b: macposts path_table -> path_table.csv + sibling text + buffer
# ---------------------------------------------------------------------------

def adapt_path_table(
    macposts_path_table: Path,
    macposts_buffer: Path,
    out_csv: Path,
    out_text: Path,
    out_buffer: Path,
    max_od_pairs: int | None,
    sample_seed: int,
) -> set[int]:
    raw_paths = [line.strip() for line in macposts_path_table.read_text().splitlines() if line.strip()]
    raw_buffer = [line.strip() for line in macposts_buffer.read_text().splitlines() if line.strip()]
    if len(raw_paths) != len(raw_buffer):
        raise SystemExit(
            f"path_table ({len(raw_paths)} rows) and path_table_buffer ({len(raw_buffer)} rows) do not match."
        )

    # Group by OD pair (origin, destination) for optional subsampling.
    by_od: dict[tuple[int, int], list[tuple[str, str]]] = {}
    for path_str, buf_str in zip(raw_paths, raw_buffer):
        toks = path_str.split()
        if len(toks) < 2:
            continue
        key = (int(toks[0]), int(toks[-1]))
        by_od.setdefault(key, []).append((path_str, buf_str))

    selected_keys = list(by_od.keys())
    if max_od_pairs is not None and max_od_pairs < len(selected_keys):
        rng = np.random.default_rng(sample_seed)
        idx = rng.choice(len(selected_keys), size=max_od_pairs, replace=False)
        selected_keys = [selected_keys[i] for i in sorted(idx)]
        print(
            f"[adapter] subsampling OD pairs: {max_od_pairs}/{len(by_od)} "
            f"(seed={sample_seed})"
        )

    paired: list[tuple[str, str, int]] = []
    for key in selected_keys:
        for rank, (path_str, buf_str) in enumerate(by_od[key], start=1):
            paired.append((path_str, buf_str, rank))
    paired.sort(key=lambda x: x[0])

    sorted_text: list[str] = []
    sorted_buffer: list[str] = []
    csv_rows: list[dict] = []
    od_node_ids: set[int] = set()

    for path_str, buf_str, rank in paired:
        nodes = [int(tok) for tok in path_str.split()]
        origin = nodes[0]
        destination = nodes[-1]
        od_node_ids.add(origin)
        od_node_ids.add(destination)
        csv_rows.append(
            {
                "Origin_ID": origin,
                "Destination_ID": destination,
                "path": str(nodes),
                "rank": rank,
                "tt": "",
                "shortest_tt": "",
                "ratio": "",
            }
        )
        sorted_text.append(path_str)
        sorted_buffer.append(buf_str)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(csv_rows).to_csv(out_csv, index=False)
    out_text.write_text("\n".join(sorted_text) + "\n")
    out_buffer.write_text("\n".join(sorted_buffer) + "\n")
    print(f"           {len(paired)} paths across {len(selected_keys)} OD pairs")
    return od_node_ids


# ---------------------------------------------------------------------------
# Step 3: eval npz -> ratio_bias_wape_analysis/* + link_observation_coverage.csv
# ---------------------------------------------------------------------------

def adapt_eval_npz(
    npz_path: Path,
    ratio_dir: Path,
    coverage_csv: Path,
    interval_kind: str,
) -> None:
    z = np.load(npz_path, allow_pickle=False)
    link_ids = z["all_link_ids"].astype(int)
    in_window = z["in_observation_window"].astype(bool)
    abs_idx = z["abs_interval_idx"].astype(int)
    mask = z["mask"].astype(bool)
    x_obs = z["x_obs"].astype(float)
    x_pred = z["x_pred"].astype(float)
    tt_pred = z["tt_pred"].astype(float)

    if not in_window.any():
        raise SystemExit("No interval is flagged in_observation_window=True in the eval npz.")

    ratio_dir.mkdir(parents=True, exist_ok=True)

    nan_column = np.full(link_ids.shape, np.nan, dtype=float)

    for t in range(len(abs_idx)):
        if not bool(in_window[t]):
            continue
        idx_value = int(abs_idx[t])
        if interval_kind == "15min":
            hour = idx_value // 4
            quarter = idx_value % 4
            suffix = f"15min_{hour}-{quarter}"
        else:
            suffix = f"hour_{idx_value}"

        # car_count: EST for every link; OBS is NaN where mask=False.
        m = mask[t]
        obs_full = np.where(m, x_obs[t], np.nan)
        pd.DataFrame(
            {
                "linkID": link_ids,
                "OBS": obs_full,
                "EST": x_pred[t],
            }
        ).to_csv(ratio_dir / f"car_count_{suffix}.csv", index=False)

        # car_tt: no observed travel time in the eval npz, so OBS = NaN everywhere; EST = tt_pred.
        pd.DataFrame(
            {
                "linkID": link_ids,
                "OBS": nan_column,
                "EST": tt_pred[t],
            }
        ).to_csv(ratio_dir / f"car_tt_{suffix}.csv", index=False)

    # Coverage CSV: flow has PEMS coverage where mask is True. TT is never observed.
    obs_intervals = mask[in_window]
    car_flow_count = obs_intervals.sum(axis=0).astype(int)
    n_intervals = int(in_window.sum())
    denom = max(n_intervals, 1)

    cov = pd.DataFrame({"linkID": link_ids})
    cov["car_flow_count"] = car_flow_count
    cov["truck_flow_count"] = 0
    cov["car_tt_count"] = 0
    cov["truck_tt_count"] = 0
    cov["flow_count"] = cov["car_flow_count"]
    cov["tt_count"] = 0
    cov["total_count"] = cov["flow_count"]
    cov["car_flow_ratio"] = cov["car_flow_count"] / denom
    cov["truck_flow_ratio"] = 0.0
    cov["car_tt_ratio"] = 0.0
    cov["truck_tt_ratio"] = 0.0
    cov["flow_ratio"] = cov["flow_count"] / denom
    cov["tt_ratio"] = 0.0
    cov["total_ratio"] = cov["total_count"] / denom

    coverage_csv.parent.mkdir(parents=True, exist_ok=True)
    cov.to_csv(coverage_csv, index=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    macposts_dir = args.macposts_dir
    if not (macposts_dir / "path_table").exists():
        raise SystemExit(f"path_table not found under {macposts_dir}")
    if not (macposts_dir / "path_table_buffer").exists():
        raise SystemExit(f"path_table_buffer not found under {macposts_dir}")

    stage = args.stage_root / args.experiment_id
    stage.mkdir(parents=True, exist_ok=True)

    print(f"[adapter] staging at {stage}")

    print("[adapter] step 1: normalizing link geojson...")
    network_gdf = adapt_network(args.link_geojson, stage / "links.geojson")
    print(f"           wrote {stage/'links.geojson'} ({len(network_gdf)} links)")

    print("[adapter] step 2: converting macposts path_table...")
    od_node_ids = adapt_path_table(
        macposts_dir / "path_table",
        macposts_dir / "path_table_buffer",
        stage / "path_table.csv",
        stage / "path_table",
        stage / "path_table_buffer",
        args.max_od_pairs,
        args.sample_seed,
    )
    print(f"           wrote path_table.csv with {len(od_node_ids)} unique OD nodes")

    print("[adapter] step 2b: building nodes geojson from link endpoints...")
    adapt_nodes(
        network_gdf,
        od_node_ids,
        args.taz_geojson,
        args.taz_crs,
        stage / "nodes.geojson",
    )
    print(f"           wrote {stage/'nodes.geojson'}")

    print("[adapter] step 3: extracting ratio_dir + coverage from eval npz...")
    ratio_dir = stage / "ratio_bias_wape_analysis"
    coverage_csv = stage / "link_observation_coverage.csv"
    adapt_eval_npz(args.eval_npz, ratio_dir, coverage_csv, args.interval_kind)
    n_csv = len(list(ratio_dir.glob("*.csv")))
    print(f"           wrote {n_csv} interval CSVs + coverage CSV")

    cmd = [
        sys.executable,
        str(BUNDLE_SCRIPT),
        "--experiment-id", args.experiment_id,
        "--experiment-label", args.experiment_label or args.experiment_id,
        "--network", str(stage / "links.geojson"),
        "--nodes", str(stage / "nodes.geojson"),
        "--path-table-csv", str(stage / "path_table.csv"),
        "--path-table-buffer", str(stage / "path_table_buffer"),
        "--ratio-dir", str(ratio_dir),
        "--coverage-csv", str(coverage_csv),
    ]
    mnm_demand = macposts_dir / "MNM_input_demand"
    if mnm_demand.exists():
        cmd.extend(["--od-demand", str(mnm_demand)])
        print(f"[adapter] passing OD demand from {mnm_demand}")
    else:
        print(f"[adapter] no MNM_input_demand at {mnm_demand}; OD-demand by-interval will be unavailable")

    if args.skip_bundle:
        print("[adapter] --skip-bundle set; next command to run:")
        print("  " + " ".join(cmd))
        return

    print("[adapter] step 4: invoking build_experiment_bundle.py")
    subprocess.run(cmd, check=True)
    print("[adapter] done.")


if __name__ == "__main__":
    main()
