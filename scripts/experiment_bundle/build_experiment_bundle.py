from __future__ import annotations

import argparse
import ast
import re
import shutil
import zlib
from pathlib import Path
from typing import Any

import geopandas as gpd
import orjson
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PROJECT_ROOT.parent
DEFAULT_SOURCE_ROOT = REPO_ROOT / "Pittsburgh_Network" / "Pittsburgh_DODE"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "public" / "data" / "experiments"
DEFAULT_RECORDS_ROOT = PROJECT_ROOT / "records" / "experiments"

MODALITY_CONFIG = {
    "car_count": {
        "label": "Car count",
        "coverage_column": "car_flow_count",
        "kind": "count",
        "unit_label": "count",
    },
    "truck_count": {
        "label": "Truck count",
        "coverage_column": "truck_flow_count",
        "kind": "count",
        "unit_label": "count",
    },
    "car_tt": {
        "label": "Car travel time",
        "coverage_column": "car_tt_count",
        "kind": "tt",
        "unit_label": "travel time",
    },
    "truck_tt": {
        "label": "Truck travel time",
        "coverage_column": "truck_tt_count",
        "kind": "tt",
        "unit_label": "travel time",
    },
}

HOUR_FILE_PATTERN = re.compile(r"^(?P<modality>.+)_hour_(?P<hour>\d+)\.csv$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one experiment bundle for the path-link demo.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--experiment-label", default=None)
    parser.add_argument("--network", required=True, type=Path)
    parser.add_argument("--nodes-geojson", default=None, type=Path)
    parser.add_argument("--path-table-csv", required=True, type=Path)
    parser.add_argument("--path-table-buffer", required=True, type=Path)
    parser.add_argument("--ratio-dir", required=True, type=Path)
    parser.add_argument("--coverage-csv", required=True, type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--records-root", type=Path, default=DEFAULT_RECORDS_ROOT)
    return parser.parse_args()


def parse_path_literal(value: object) -> list[int]:
    parsed = ast.literal_eval(str(value))
    if not isinstance(parsed, list):
        raise ValueError(f"Unexpected path literal: {value}")
    return [int(item) for item in parsed]


def build_directed_link_lookup(network_path: Path) -> dict[tuple[int, int], int]:
    gdf = gpd.read_file(network_path, columns=["linkID", "N1", "N2"]).copy()
    gdf["linkID"] = gdf["linkID"].astype(int)
    gdf["N1"] = gdf["N1"].astype(int)
    gdf["N2"] = gdf["N2"].astype(int)
    duplicated = gdf.duplicated(subset=["N1", "N2"], keep=False)
    if duplicated.any():
        sample = gdf.loc[duplicated, ["linkID", "N1", "N2"]].head(20).to_dict("records")
        raise ValueError(f"Duplicated directed node pairs found in network: {sample}")
    return {(int(row["N1"]), int(row["N2"])): int(row["linkID"]) for _, row in gdf.iterrows()}


def convert_node_path_to_link_path(
    node_sequence: list[int],
    lookup: dict[tuple[int, int], int],
) -> list[int]:
    if len(node_sequence) < 2:
        return []
    link_sequence: list[int] = []
    for start_node, end_node in zip(node_sequence, node_sequence[1:]):
        link_id = lookup.get((int(start_node), int(end_node)))
        if link_id is None:
            raise ValueError(
                f"Could not map node pair {(int(start_node), int(end_node))} to a link in the network."
            )
        link_sequence.append(link_id)
    return link_sequence


def normalize_network(network_path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(network_path).copy()
    if "linkID" in gdf.columns:
        gdf = gdf.rename(columns={"linkID": "link_id"})
    gdf["link_id"] = gdf["link_id"].astype(str)
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)
    return gdf[gdf.geometry.notnull()].copy()


def normalize_nodes(nodes_path: Path) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(nodes_path).copy()
    if "node_id" not in gdf.columns:
        raise ValueError(f"Node file {nodes_path} is missing `node_id`.")
    gdf["node_id"] = gdf["node_id"].astype(str)
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=3365)
    gdf = gdf.to_crs(epsg=4326)
    return gdf[gdf.geometry.notnull()].copy()


def infer_nodes_geojson_path(network_path: Path) -> Path:
    candidate = network_path.parent / "nodes_ver2__codex_tmp.json"
    if not candidate.exists():
        raise FileNotFoundError(
            f"Could not infer nodes geojson next to network file. Expected: {candidate}"
        )
    return candidate


def build_long_path_table(path_table_csv: Path, path_table_buffer: Path, network_path: Path) -> pd.DataFrame:
    path_df = pd.read_csv(path_table_csv).copy()
    lookup = build_directed_link_lookup(network_path)
    path_df["node_sequence_list"] = path_df["path"].apply(parse_path_literal)
    path_df["link_sequence_list"] = path_df["node_sequence_list"].apply(
        lambda values: convert_node_path_to_link_path(values, lookup)
    )
    path_df["path_str"] = path_df["node_sequence_list"].apply(lambda values: " ".join(map(str, values)))
    path_df = path_df.sort_values("path_str", kind="stable").reset_index(drop=True)

    raw_text_lines = path_table_csv.with_name("path_table").read_text(encoding="utf-8").splitlines()
    text_lines = [line.strip() for line in raw_text_lines if line.strip()]
    if len(text_lines) != len(path_df):
        raise ValueError("path_table text rows do not match path_table.csv rows.")
    if text_lines[:1000] != path_df["path_str"].head(1000).tolist():
        raise ValueError("Sorted path_table.csv rows are not aligned with path_table text ordering.")

    buffer_df = pd.read_csv(path_table_buffer, sep=r"\s+", header=None)
    if len(buffer_df) != len(path_df):
        raise ValueError("path_table_buffer rows do not match sorted path table rows.")
    path_share = buffer_df.mean(axis=1)

    output_df = pd.DataFrame(
        {
            "path_id": [str(index + 1) for index in range(len(path_df))],
            "node_sequence": path_df["node_sequence_list"].apply(lambda values: ",".join(map(str, values))),
            "link_sequence": path_df["link_sequence_list"].apply(lambda values: ",".join(map(str, values))),
            "od_id": path_df["Origin_ID"].astype(str) + "_" + path_df["Destination_ID"].astype(str),
            "origin": path_df["Origin_ID"].astype(str),
            "destination": path_df["Destination_ID"].astype(str),
            "origin_node_id": path_df["node_sequence_list"].apply(lambda values: str(values[0]) if values else ""),
            "destination_node_id": path_df["node_sequence_list"].apply(lambda values: str(values[-1]) if values else ""),
            "rank": path_df["rank"].astype(int),
            "path_tt": pd.to_numeric(path_df["tt"], errors="coerce"),
            "shortest_tt": pd.to_numeric(path_df["shortest_tt"], errors="coerce"),
            "tt_ratio": pd.to_numeric(path_df["ratio"], errors="coerce"),
            "path_flow": pd.to_numeric(path_share, errors="coerce"),
        }
    )

    expanded = output_df.copy()
    expanded["link_id"] = expanded["link_sequence"].str.split(",")
    expanded = expanded.explode("link_id", ignore_index=True)
    expanded["link_id"] = expanded["link_id"].astype(str).str.strip()
    expanded = expanded.loc[expanded["link_id"] != ""].copy()
    expanded["seq"] = expanded.groupby("path_id").cumcount() + 1
    return expanded


def build_od_points_geojson(long_df: pd.DataFrame, nodes_path: Path) -> dict[str, Any]:
    nodes_gdf = normalize_nodes(nodes_path)
    node_lookup = {
        str(row["node_id"]): row.geometry.__geo_interface__
        for _, row in nodes_gdf.iterrows()
    }

    origin_points = (
        long_df[["origin", "origin_node_id"]]
        .drop_duplicates()
        .rename(columns={"origin": "point_id", "origin_node_id": "node_id"})
        .assign(point_role="O")
    )
    destination_points = (
        long_df[["destination", "destination_node_id"]]
        .drop_duplicates()
        .rename(columns={"destination": "point_id", "destination_node_id": "node_id"})
        .assign(point_role="D")
    )

    point_df = pd.concat([origin_points, destination_points], ignore_index=True)
    point_df = point_df.drop_duplicates(subset=["point_id", "node_id", "point_role"]).copy()

    features: list[dict[str, Any]] = []
    missing_nodes: list[tuple[str, str]] = []
    for _, row in point_df.iterrows():
        node_id = str(row["node_id"])
        geometry = node_lookup.get(node_id)
        if geometry is None:
            missing_nodes.append((str(row["point_id"]), node_id))
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "point_id": str(row["point_id"]),
                    "node_id": node_id,
                    "point_role": str(row["point_role"]),
                    "label": node_id,
                },
                "geometry": geometry,
            }
        )

    if missing_nodes:
        sample = ", ".join(f"{point_id}->{node_id}" for point_id, node_id in missing_nodes[:10])
        raise ValueError(f"Missing OD node coordinates for: {sample}")

    return {"type": "FeatureCollection", "features": features}


def build_path_outputs(long_df: pd.DataFrame) -> tuple[dict[str, Any], dict[str, list[str]], dict[str, list[dict[str, Any]]]]:
    grouped = long_df.groupby("path_id", sort=False)
    sequence_by_path = grouped["link_id"].agg(list)
    counts_by_path = grouped.size()
    first_values = grouped[
        ["od_id", "origin", "destination", "origin_node_id", "destination_node_id", "path_flow"]
    ].first()

    path_summary: dict[str, Any] = {}
    for path_id in sequence_by_path.index:
        first = first_values.loc[path_id]
        path_summary[str(path_id)] = {
            "path_id": str(path_id),
            "od_id": str(first["od_id"]),
            "origin": str(first["origin"]),
            "destination": str(first["destination"]),
            "origin_node_id": str(first["origin_node_id"]),
            "destination_node_id": str(first["destination_node_id"]),
            "path_flow": float(first["path_flow"]) if pd.notna(first["path_flow"]) else None,
            "num_links": int(counts_by_path.loc[path_id]),
            "link_sequence": [str(link_id) for link_id in sequence_by_path.loc[path_id]],
        }

    unique_pairs = long_df[["link_id", "path_id"]].drop_duplicates()
    link_to_paths_grouped = unique_pairs.groupby("link_id", sort=False)["path_id"].agg(list)
    link_to_paths = {
        str(link_id): [str(path_id) for path_id in path_ids]
        for link_id, path_ids in link_to_paths_grouped.items()
    }

    contrib_group = long_df[
        [
            "link_id",
            "path_id",
            "od_id",
            "origin",
            "destination",
            "origin_node_id",
            "destination_node_id",
            "path_flow",
        ]
    ].copy()
    contrib_group["contribution"] = contrib_group["path_flow"]
    link_path_contrib: dict[str, list[dict[str, Any]]] = {}
    for link_id, group in contrib_group.groupby("link_id", sort=False):
        records = group[
            [
                "path_id",
                "od_id",
                "origin",
                "destination",
                "origin_node_id",
                "destination_node_id",
                "path_flow",
                "contribution",
            ]
        ].to_dict("records")
        records.sort(key=lambda item: float(item.get("contribution", 0.0)), reverse=True)
        link_path_contrib[str(link_id)] = records

    return path_summary, link_to_paths, link_path_contrib


def build_contribution_buckets(
    link_path_contrib: dict[str, list[dict[str, Any]]],
    bucket_count: int = 64,
) -> tuple[dict[str, str], dict[str, dict[str, list[dict[str, Any]]]]]:
    bucket_index: dict[str, str] = {}
    buckets: dict[str, dict[str, list[dict[str, Any]]]] = {}

    for link_id, records in link_path_contrib.items():
        try:
            bucket_number = int(link_id) % bucket_count
        except ValueError:
            bucket_number = zlib.crc32(link_id.encode("utf-8")) % bucket_count
        bucket_file = f"bucket_{bucket_number:02d}.json"
        bucket_index[link_id] = bucket_file
        buckets.setdefault(bucket_file, {})[link_id] = records

    return bucket_index, buckets


def discover_hour_ids(ratio_dir: Path) -> dict[str, list[str]]:
    hour_map: dict[str, set[str]] = {}
    for csv_path in ratio_dir.glob("*_hour_*.csv"):
        match = HOUR_FILE_PATTERN.match(csv_path.name)
        if not match:
            continue
        modality = match.group("modality")
        hour = match.group("hour")
        hour_map.setdefault(modality, set()).add(hour)

    if not hour_map:
        raise FileNotFoundError(f"No *_hour_*.csv files found in {ratio_dir}")

    return {
        modality: sorted(hours, key=lambda value: int(value))
        for modality, hours in hour_map.items()
    }


def build_modality_metrics(
    modality: str,
    ratio_dir: Path,
    coverage_df: pd.DataFrame,
    network_link_ids: pd.Series,
    hour_ids: list[str],
) -> pd.DataFrame:
    config = MODALITY_CONFIG[modality]
    link_metrics_path = ratio_dir / f"{modality}_link_metrics.csv"
    base_df = pd.DataFrame({"link_id": network_link_ids.astype(str)})

    totals = pd.read_csv(link_metrics_path).copy()
    totals = totals.rename(columns={"linkID": "link_id"})
    totals["link_id"] = totals["link_id"].astype(str)
    totals["valid_total"] = (
        pd.to_numeric(totals["obs_total"], errors="coerce").fillna(0).gt(0)
        & pd.to_numeric(totals["bias_total"], errors="coerce").notna()
        & pd.to_numeric(totals["wape_total"], errors="coerce").notna()
    )
    totals["observed_valid_total"] = pd.to_numeric(totals["obs_total"], errors="coerce").fillna(0).gt(0)
    totals = totals[
        [
            "link_id",
            "obs_total",
            "est_total",
            "bias_total",
            "wape_total",
            "valid_total",
            "observed_valid_total",
        ]
    ].rename(
        columns={
            "obs_total": f"{modality}_obs_3h",
            "est_total": f"{modality}_est_3h",
            "bias_total": f"{modality}_bias_3h",
            "wape_total": f"{modality}_wape_3h",
            "valid_total": f"{modality}_valid_3h",
            "observed_valid_total": f"{modality}_obs_valid_3h",
        }
    )

    result = base_df.merge(totals, on="link_id", how="left")

    coverage_column = config["coverage_column"]
    coverage_copy = coverage_df[["linkID", coverage_column]].copy()
    coverage_copy = coverage_copy.rename(
        columns={
            "linkID": "link_id",
            coverage_column: f"{modality}_observed_count",
        }
    )
    coverage_copy["link_id"] = coverage_copy["link_id"].astype(str)
    coverage_copy[f"{modality}_observed_any"] = coverage_copy[f"{modality}_observed_count"].fillna(0).gt(0)
    result = result.merge(coverage_copy, on="link_id", how="left")
    result[f"{modality}_observed_count"] = result[f"{modality}_observed_count"].fillna(0).astype(int)
    result[f"{modality}_observed_any"] = result[f"{modality}_observed_any"].fillna(False)

    for hour in hour_ids:
        hour_df = pd.read_csv(ratio_dir / f"{modality}_hour_{hour}.csv").copy()
        hour_df = hour_df.rename(columns={"linkID": "link_id"})
        hour_df["link_id"] = hour_df["link_id"].astype(str)
        period_id = f"hour_{hour}"
        hour_df[f"{modality}_obs_valid_{period_id}"] = (
            pd.to_numeric(hour_df["OBS"], errors="coerce").fillna(0).gt(0)
        )
        hour_df[f"{modality}_valid_{period_id}"] = (
            pd.to_numeric(hour_df["OBS"], errors="coerce").fillna(0).gt(0)
            & pd.to_numeric(hour_df["BIAS"], errors="coerce").notna()
            & pd.to_numeric(hour_df["WAPE"], errors="coerce").notna()
        )
        hour_df = hour_df[
            [
                "link_id",
                "OBS",
                "EST",
                "BIAS",
                "WAPE",
                f"{modality}_valid_{period_id}",
                f"{modality}_obs_valid_{period_id}",
            ]
        ].rename(
            columns={
                "OBS": f"{modality}_obs_{period_id}",
                "EST": f"{modality}_est_{period_id}",
                "BIAS": f"{modality}_bias_{period_id}",
                "WAPE": f"{modality}_wape_{period_id}",
            }
        )
        result = result.merge(hour_df, on="link_id", how="left")
        result[f"{modality}_valid_{period_id}"] = result[f"{modality}_valid_{period_id}"].fillna(False)
        result[f"{modality}_obs_valid_{period_id}"] = result[f"{modality}_obs_valid_{period_id}"].fillna(False)

    return result


def build_all_metrics(
    network_gdf: gpd.GeoDataFrame,
    ratio_dir: Path,
    coverage_csv: Path,
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    coverage_df = pd.read_csv(coverage_csv)
    discovered_hours = discover_hour_ids(ratio_dir)
    merged: pd.DataFrame | None = None

    for modality in MODALITY_CONFIG:
        modality_df = build_modality_metrics(
            modality,
            ratio_dir,
            coverage_df,
            network_gdf["link_id"],
            discovered_hours.get(modality, []),
        )
        merged = modality_df if merged is None else merged.merge(modality_df, on="link_id", how="outer")

    assert merged is not None
    return merged, discovered_hours


def to_serializable_props(row: pd.Series) -> dict[str, object]:
    props: dict[str, object] = {}
    for key, value in row.items():
        if key == "geometry" or pd.isna(value):
            continue
        if hasattr(value, "item"):
            value = value.item()
        props[key] = value
    return props


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))


def build_period_labels(hour_ids: list[str]) -> dict[str, str]:
    labels = {"3h": f"Total ({len(hour_ids)}h)" if hour_ids else "Total"}
    for hour in hour_ids:
        labels[f"hour_{hour}"] = f"{int(hour):02d}:00-{int(hour) + 1:02d}:00"
    return labels


def build_color_file_definition(modality: str, hour_ids: list[str]) -> dict[str, Any]:
    label = MODALITY_CONFIG[modality]["label"]
    field_by_period_obs = {"3h": f"{modality}_obs_3h"}
    field_by_period_est = {"3h": f"{modality}_est_3h"}
    field_by_period_wape = {"3h": f"{modality}_wape_3h"}
    field_by_period_bias = {"3h": f"{modality}_bias_3h"}
    mask_by_period = {"3h": f"{modality}_valid_3h"}
    observed_mask_by_period = {"3h": f"{modality}_obs_valid_3h"}

    for hour in hour_ids:
        period_id = f"hour_{hour}"
        field_by_period_obs[period_id] = f"{modality}_obs_{period_id}"
        field_by_period_est[period_id] = f"{modality}_est_{period_id}"
        field_by_period_wape[period_id] = f"{modality}_wape_{period_id}"
        field_by_period_bias[period_id] = f"{modality}_bias_{period_id}"
        mask_by_period[period_id] = f"{modality}_valid_{period_id}"
        observed_mask_by_period[period_id] = f"{modality}_obs_valid_{period_id}"

    return {
        "id": modality,
        "label": label,
        "sourceFile": f"{modality}.json",
        "defaultMeasureId": "bias",
        "defaultPeriodId": "3h",
        "periodLabels": build_period_labels(hour_ids),
        "measures": [
            {
                "id": "obs",
                "label": "Observed",
                "scaleType": "sequential",
                "fieldByPeriod": field_by_period_obs,
                "maskFieldByPeriod": observed_mask_by_period,
            },
            {
                "id": "est",
                "label": "Estimate",
                "scaleType": "sequential",
                "fieldByPeriod": field_by_period_est,
                "maskFieldByPeriod": mask_by_period,
            },
            {
                "id": "wape",
                "label": "WAPE",
                "scaleType": "sequential",
                "fieldByPeriod": field_by_period_wape,
                "maskFieldByPeriod": mask_by_period,
            },
            {
                "id": "bias",
                "label": "Bias",
                "scaleType": "diverging",
                "fieldByPeriod": field_by_period_bias,
                "maskFieldByPeriod": mask_by_period,
            },
        ],
        "notes": {
            "en": "Links without valid observed-versus-estimated comparison are rendered in black for bias/WAPE views.",
            "zh": "在 bias/WAPE 视图中，没有有效 observed-versus-estimated 对比的链路会显示为黑色。",
        },
    }


def build_manifest(experiment_id: str, experiment_label: str, experiment_dir: Path) -> dict[str, Any]:
    color_files = [
        {
            "id": modality,
            "label": MODALITY_CONFIG[modality]["label"],
            "path": f"/data/experiments/{experiment_id}/color_files/{modality}.json",
        }
        for modality in MODALITY_CONFIG
    ]
    return {
        "id": experiment_id,
        "label": experiment_label,
        "linksGeojson": f"/data/experiments/{experiment_id}/network/links.geojson",
        "odPointsGeojson": f"/data/experiments/{experiment_id}/od/od_points.geojson",
        "linksIndex": f"/data/experiments/{experiment_id}/network/links_index.json",
        "linkToPaths": f"/data/experiments/{experiment_id}/paths/link_to_paths.json",
        "pathSummary": f"/data/experiments/{experiment_id}/paths/path_summary.json",
        "linkPathContribBucketDir": f"/data/experiments/{experiment_id}/paths/link_path_contrib_buckets",
        "linkPathContribBucketIndex": f"/data/experiments/{experiment_id}/paths/link_path_contrib_bucket_index.json",
        "colorFiles": color_files,
        "defaultColorFileId": "car_tt",
    }


def update_experiment_index(output_root: Path) -> None:
    index_path = output_root / "index.json"
    entries: list[dict[str, str]] = []
    for manifest_path in sorted(output_root.glob("*/manifest.json")):
        manifest = orjson.loads(manifest_path.read_bytes())
        entries.append(
            {
                "id": str(manifest["id"]),
                "label": str(manifest["label"]),
                "manifestPath": f"/data/experiments/{manifest['id']}/manifest.json",
            }
        )
    write_json(index_path, entries)


def write_records(
    experiment_id: str,
    experiment_label: str,
    records_root: Path,
    network_path: Path,
    ratio_dir: Path,
    coverage_csv: Path,
    long_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
) -> None:
    target_dir = records_root / experiment_id
    target_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "experiment_id": experiment_id,
        "experiment_label": experiment_label,
        "network_source": str(network_path),
        "ratio_source_dir": str(ratio_dir),
        "coverage_source_csv": str(coverage_csv),
        "path_count": int(long_df["path_id"].nunique()),
        "link_count": int(metrics_df["link_id"].nunique()),
        "color_files": list(MODALITY_CONFIG.keys()),
    }
    write_json(target_dir / "bundle_summary.json", summary)

    readme = f"""# {experiment_label} Bundle / {experiment_label} 数据包

## What this folder stores / 本文件夹内容

- `bundle_summary.json`: build summary / 构建摘要
- `coverage_gap_audit.csv`: observed coverage versus valid ratio gap / observed 覆盖与有效 ratio 差异
- `coverage_gap_audit_bilingual.md`: bilingual audit note / 双语审计说明

## Source inputs / 来源输入

- Network / 网络: `{network_path}`
- Ratio directory / ratio 目录: `{ratio_dir}`
- Coverage CSV / 覆盖 CSV: `{coverage_csv}`

## Demo import target / Demo 导入目标

- `/public/data/experiments/{experiment_id}/manifest.json`
"""
    (target_dir / "README.md").write_text(readme, encoding="utf-8")


def main() -> None:
    args = parse_args()
    experiment_id = args.experiment_id
    experiment_label = args.experiment_label or experiment_id

    experiment_dir = args.output_root / experiment_id
    network_dir = experiment_dir / "network"
    od_dir = experiment_dir / "od"
    paths_dir = experiment_dir / "paths"
    color_dir = experiment_dir / "color_files"
    records_root = args.records_root

    network_gdf = normalize_network(args.network)
    metrics_df, discovered_hours = build_all_metrics(network_gdf, args.ratio_dir, args.coverage_csv)
    merged_gdf = network_gdf.merge(metrics_df, on="link_id", how="left")

    long_df = build_long_path_table(args.path_table_csv, args.path_table_buffer, args.network)
    nodes_geojson_path = args.nodes_geojson or infer_nodes_geojson_path(args.network)
    od_points_geojson = build_od_points_geojson(long_df, nodes_geojson_path)
    path_summary, link_to_paths, link_path_contrib = build_path_outputs(long_df)

    network_dir.mkdir(parents=True, exist_ok=True)
    od_dir.mkdir(parents=True, exist_ok=True)
    paths_dir.mkdir(parents=True, exist_ok=True)
    color_dir.mkdir(parents=True, exist_ok=True)

    merged_gdf.to_file(network_dir / "links.geojson", driver="GeoJSON")
    write_json(od_dir / "od_points.geojson", od_points_geojson)

    links_index = {
        str(row["link_id"]): {
            "properties": to_serializable_props(row.drop(labels=["geometry"])),
            "geometry": row.geometry.__geo_interface__,
        }
        for _, row in merged_gdf.iterrows()
    }
    write_json(network_dir / "links_index.json", links_index)
    write_json(paths_dir / "path_summary.json", path_summary)
    write_json(paths_dir / "link_to_paths.json", link_to_paths)

    legacy_shard_dir = paths_dir / "link_path_contrib_by_link"
    if legacy_shard_dir.exists():
        shutil.rmtree(legacy_shard_dir)

    bucket_dir = paths_dir / "link_path_contrib_buckets"
    if bucket_dir.exists():
        shutil.rmtree(bucket_dir)
    bucket_dir.mkdir(parents=True, exist_ok=True)

    bucket_index, bucket_payloads = build_contribution_buckets(link_path_contrib)
    write_json(paths_dir / "link_path_contrib_bucket_index.json", bucket_index)
    for bucket_file, payload in bucket_payloads.items():
        write_json(bucket_dir / bucket_file, payload)

    for modality in MODALITY_CONFIG:
        write_json(
            color_dir / f"{modality}.json",
            build_color_file_definition(modality, discovered_hours.get(modality, [])),
        )

    write_json(experiment_dir / "manifest.json", build_manifest(experiment_id, experiment_label, experiment_dir))
    update_experiment_index(args.output_root)
    write_records(
        experiment_id,
        experiment_label,
        records_root,
        args.network,
        args.ratio_dir,
        args.coverage_csv,
        long_df,
        metrics_df,
    )

    print(f"Wrote experiment bundle to {experiment_dir}")


if __name__ == "__main__":
    main()
