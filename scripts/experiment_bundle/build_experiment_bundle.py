from __future__ import annotations

import argparse
import ast
import re
import shutil
import zlib
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one experiment bundle for the path-link demo.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--experiment-label", default=None)
    parser.add_argument("--network", required=True, type=Path)
    parser.add_argument("--nodes", default=None, type=Path)
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
    candidates = [
        network_path.parent / "nodes_ver2.shp",
        network_path.parent / "nodes_ver2__codex_tmp.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not infer node file next to network file. Tried: {', '.join(str(path) for path in candidates)}"
    )


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


def sanitize_interval_id(interval_id: str) -> str:
    return interval_id.replace("-", "_").replace(".", "_")


def parse_interval_numeric_value(interval_id: str) -> float:
    if "-" in interval_id:
        hour_text, quarter_text = interval_id.split("-", 1)
        return int(hour_text) + int(quarter_text) / 4.0
    return float(interval_id)


def format_interval_label(interval_kind: str, interval_id: str, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    if interval_kind == "hour":
        whole = int(round(parse_interval_numeric_value(interval_id)))
        return f"{whole:02d}:00-{whole + 1:02d}:00"
    value = parse_interval_numeric_value(interval_id)
    start_minutes = int(round(value * 60))
    end_minutes = start_minutes + 15
    return f"{start_minutes // 60:02d}:{start_minutes % 60:02d}-{end_minutes // 60:02d}:{end_minutes % 60:02d}"


def discover_interval_files(ratio_dir: Path) -> dict[str, list[dict[str, Any]]]:
    interval_map: dict[str, list[dict[str, Any]]] = {}
    pattern = re.compile(
        r"^(?P<modality>.+)_(?P<interval_kind>hour|15min)_(?P<interval_id>\d+|(?:\d+-[0-3]))\.csv$"
    )

    for csv_path in ratio_dir.glob("*.csv"):
        match = pattern.match(csv_path.name)
        if not match:
            continue
        modality = match.group("modality")
        if modality not in MODALITY_CONFIG:
            continue
        interval_map.setdefault(modality, []).append(
            {
                "interval_kind": match.group("interval_kind"),
                "interval_id": match.group("interval_id"),
                "interval_key": f"interval_{sanitize_interval_id(match.group('interval_id'))}",
                "path": csv_path,
            }
        )

    if not interval_map:
        raise FileNotFoundError(f"No interval CSV files found in {ratio_dir}")

    for modality, items in interval_map.items():
        interval_map[modality] = sorted(
            items,
            key=lambda item: parse_interval_numeric_value(str(item["interval_id"])),
        )
    return interval_map


def build_modality_metrics(
    modality: str,
    interval_files: list[dict[str, Any]],
    coverage_df: pd.DataFrame,
    network_link_ids: pd.Series,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    config = MODALITY_CONFIG[modality]
    result = pd.DataFrame({"link_id": network_link_ids.astype(str)})
    interval_specs: list[dict[str, Any]] = []
    obs_interval_columns: list[str] = []
    est_interval_columns: list[str] = []

    for index, interval in enumerate(interval_files):
        frame = pd.read_csv(interval["path"]).copy()
        if "linkID" not in frame.columns:
            raise ValueError(f"{interval['path']} must contain linkID.")
        if "OBS" not in frame.columns or "EST" not in frame.columns:
            raise ValueError(f"{interval['path']} must contain OBS and EST columns.")
        frame = frame.rename(columns={"linkID": "link_id"})
        frame["link_id"] = frame["link_id"].astype(str)

        interval_key = str(interval["interval_key"])
        interval_id = str(interval["interval_id"])
        interval_kind = str(interval["interval_kind"])
        label = format_interval_label(
            interval_kind,
            interval_id,
            str(frame["INTERVAL_LABEL"].iloc[0]) if "INTERVAL_LABEL" in frame.columns and not frame.empty else None,
        )

        obs_col = f"{modality}_obs_{interval_key}"
        est_col = f"{modality}_est_{interval_key}"
        bias_col = f"{modality}_bias_{interval_key}"
        wape_col = f"{modality}_wape_{interval_key}"
        valid_col = f"{modality}_valid_{interval_key}"
        obs_valid_col = f"{modality}_obs_valid_{interval_key}"
        est_valid_col = f"{modality}_est_valid_{interval_key}"

        obs_numeric = pd.to_numeric(frame["OBS"], errors="coerce")
        est_numeric = pd.to_numeric(frame["EST"], errors="coerce")
        if "BIAS" in frame.columns:
            bias_numeric = pd.to_numeric(frame["BIAS"], errors="coerce")
        else:
            bias_numeric = np.where(
                obs_numeric.to_numpy(dtype=float) > 0,
                (est_numeric.to_numpy(dtype=float) - obs_numeric.to_numpy(dtype=float))
                / obs_numeric.to_numpy(dtype=float),
                np.nan,
            )
            bias_numeric = pd.Series(bias_numeric, index=frame.index)

        if "WAPE" in frame.columns:
            wape_numeric = pd.to_numeric(frame["WAPE"], errors="coerce")
        else:
            wape_numeric = np.where(
                obs_numeric.to_numpy(dtype=float) > 0,
                np.abs(est_numeric.to_numpy(dtype=float) - obs_numeric.to_numpy(dtype=float))
                / obs_numeric.to_numpy(dtype=float),
                np.nan,
            )
            wape_numeric = pd.Series(wape_numeric, index=frame.index)

        frame["OBS"] = obs_numeric
        frame["EST"] = est_numeric
        frame["BIAS"] = bias_numeric
        frame["WAPE"] = wape_numeric

        frame[obs_valid_col] = obs_numeric.fillna(0).gt(0)
        frame[est_valid_col] = est_numeric.notna()
        if "VALID" in frame.columns:
            valid_values = frame["VALID"]
            frame[valid_col] = valid_values.astype(str).str.lower().map({"true": True, "false": False}).fillna(valid_values.astype(bool))
        else:
            frame[valid_col] = (
                obs_numeric.fillna(0).gt(0)
                & pd.to_numeric(frame["BIAS"], errors="coerce").notna()
                & pd.to_numeric(frame["WAPE"], errors="coerce").notna()
            )

        frame = frame[
            [
                "link_id",
                "OBS",
                "EST",
                "BIAS",
                "WAPE",
                obs_valid_col,
                est_valid_col,
                valid_col,
            ]
        ].rename(
            columns={
                "OBS": obs_col,
                "EST": est_col,
                "BIAS": bias_col,
                "WAPE": wape_col,
            }
        )
        result = result.merge(frame, on="link_id", how="left")
        result[obs_valid_col] = result[obs_valid_col].fillna(False)
        result[est_valid_col] = result[est_valid_col].fillna(False)
        result[valid_col] = result[valid_col].fillna(False)

        obs_interval_columns.append(obs_col)
        est_interval_columns.append(est_col)
        interval_specs.append(
            {
                "id": interval_id,
                "key": interval_key,
                "kind": interval_kind,
                "label": label,
                "index": index,
            }
        )

    obs_matrix = result[obs_interval_columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    est_matrix = result[est_interval_columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    finite_pairs = np.isfinite(obs_matrix) & np.isfinite(est_matrix)
    safe_obs = np.where(finite_pairs, obs_matrix, 0.0)
    safe_est = np.where(finite_pairs, est_matrix, 0.0)

    total_obs = np.where(finite_pairs.any(axis=1), safe_obs.sum(axis=1), np.nan)
    total_est = np.where(np.isfinite(est_matrix).any(axis=1), np.nansum(est_matrix, axis=1), np.nan)
    total_bias = np.where(total_obs > 0, (safe_est.sum(axis=1) - safe_obs.sum(axis=1)) / safe_obs.sum(axis=1), np.nan)
    total_wape = np.where(total_obs > 0, np.abs(safe_est - safe_obs).sum(axis=1) / safe_obs.sum(axis=1), np.nan)

    result[f"{modality}_obs_total"] = total_obs
    result[f"{modality}_est_total"] = total_est
    result[f"{modality}_bias_total"] = total_bias
    result[f"{modality}_wape_total"] = total_wape
    result[f"{modality}_obs_valid_total"] = np.isfinite(total_obs) & (total_obs > 0)
    result[f"{modality}_est_valid_total"] = np.isfinite(total_est)
    result[f"{modality}_valid_total"] = result[f"{modality}_obs_valid_total"] & np.isfinite(total_bias) & np.isfinite(total_wape)

    coverage_column = config["coverage_column"]
    if coverage_column in coverage_df.columns:
        coverage_copy = coverage_df[["linkID", coverage_column]].copy()
        coverage_copy = coverage_copy.rename(columns={"linkID": "link_id", coverage_column: f"{modality}_observed_count"})
        coverage_copy["link_id"] = coverage_copy["link_id"].astype(str)
        coverage_copy[f"{modality}_observed_any"] = coverage_copy[f"{modality}_observed_count"].fillna(0).gt(0)
        result = result.merge(coverage_copy, on="link_id", how="left")
        result[f"{modality}_observed_count"] = result[f"{modality}_observed_count"].fillna(0).astype(int)
        result[f"{modality}_observed_any"] = result[f"{modality}_observed_any"].fillna(False)
    else:
        result[f"{modality}_observed_count"] = 0
        result[f"{modality}_observed_any"] = False

    return result, interval_specs


def build_all_metrics(
    network_gdf: gpd.GeoDataFrame,
    ratio_dir: Path,
    coverage_csv: Path,
) -> tuple[pd.DataFrame, dict[str, list[dict[str, Any]]], list[str]]:
    coverage_df = pd.read_csv(coverage_csv)
    discovered_intervals = discover_interval_files(ratio_dir)
    merged: pd.DataFrame | None = None
    available_modalities: list[str] = []
    interval_specs_by_modality: dict[str, list[dict[str, Any]]] = {}

    for modality, interval_files in discovered_intervals.items():
        modality_df, interval_specs = build_modality_metrics(
            modality,
            interval_files,
            coverage_df,
            network_gdf["link_id"],
        )
        merged = modality_df if merged is None else merged.merge(modality_df, on="link_id", how="outer")
        interval_specs_by_modality[modality] = interval_specs
        available_modalities.append(modality)

    if merged is None:
        raise ValueError("No modality metrics could be built.")
    return merged, interval_specs_by_modality, available_modalities


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


def build_color_file_definition(
    modality: str,
    interval_specs: list[dict[str, Any]],
) -> dict[str, Any]:
    label = MODALITY_CONFIG[modality]["label"]
    interval_field_obs = {spec["key"]: f"{modality}_obs_{spec['key']}" for spec in interval_specs}
    interval_field_est = {spec["key"]: f"{modality}_est_{spec['key']}" for spec in interval_specs}
    interval_field_wape = {spec["key"]: f"{modality}_wape_{spec['key']}" for spec in interval_specs}
    interval_field_bias = {spec["key"]: f"{modality}_bias_{spec['key']}" for spec in interval_specs}
    interval_mask = {spec["key"]: f"{modality}_valid_{spec['key']}" for spec in interval_specs}
    interval_est_mask = {spec["key"]: f"{modality}_est_valid_{spec['key']}" for spec in interval_specs}
    interval_obs_mask = {spec["key"]: f"{modality}_obs_valid_{spec['key']}" for spec in interval_specs}

    definition = {
        "id": modality,
        "label": label,
        "sourceFile": f"{modality}.json",
        "defaultMeasureId": "bias",
        "defaultPeriodMode": "total",
        "defaultIntervalKey": interval_specs[0]["key"] if interval_specs else None,
        "intervals": interval_specs,
        "measures": [
            {
                "id": "obs",
                "label": "Observed",
                "scaleType": "sequential",
                "fieldTotal": f"{modality}_obs_total",
                "fieldByInterval": interval_field_obs,
                "maskFieldTotal": f"{modality}_obs_valid_total",
                "maskFieldByInterval": interval_obs_mask,
            },
            {
                "id": "est",
                "label": "Estimate",
                "scaleType": "sequential",
                "fieldTotal": f"{modality}_est_total",
                "fieldByInterval": interval_field_est,
                "maskFieldTotal": f"{modality}_est_valid_total",
                "maskFieldByInterval": interval_est_mask,
            },
            {
                "id": "wape",
                "label": "WAPE",
                "scaleType": "sequential",
                "fieldTotal": f"{modality}_wape_total",
                "fieldByInterval": interval_field_wape,
                "maskFieldTotal": f"{modality}_valid_total",
                "maskFieldByInterval": interval_mask,
                "visibilityFieldTotal": f"{modality}_valid_total",
                "visibilityFieldByInterval": interval_mask,
            },
            {
                "id": "bias",
                "label": "Bias",
                "scaleType": "diverging",
                "fieldTotal": f"{modality}_bias_total",
                "fieldByInterval": interval_field_bias,
                "maskFieldTotal": f"{modality}_valid_total",
                "maskFieldByInterval": interval_mask,
                "visibilityFieldTotal": f"{modality}_valid_total",
                "visibilityFieldByInterval": interval_mask,
            },
        ],
        "notes": {
            "en": "Links without valid observed-versus-estimated comparison are rendered in black for bias/WAPE views.",
            "zh": "在 bias/WAPE 视图中，没有有效 observed-versus-estimated 对比的链路会显示为黑色。",
        },
    }
    return definition


def build_manifest(experiment_id: str, experiment_label: str, color_modalities: list[str]) -> dict[str, Any]:
    color_files = [
        {
            "id": modality,
            "label": MODALITY_CONFIG[modality]["label"],
            "path": f"/data/experiments/{experiment_id}/color_files/{modality}.json",
        }
        for modality in color_modalities
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
        "defaultColorFileId": "car_tt" if "car_tt" in color_modalities else color_modalities[0],
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
    color_modalities: list[str],
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
        "color_files": color_modalities,
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
    metrics_df, interval_specs_by_modality, available_modalities = build_all_metrics(
        network_gdf,
        args.ratio_dir,
        args.coverage_csv,
    )
    merged_gdf = network_gdf.merge(metrics_df, on="link_id", how="left")

    long_df = build_long_path_table(args.path_table_csv, args.path_table_buffer, args.network)
    nodes_path = args.nodes or infer_nodes_geojson_path(args.network)
    od_points_geojson = build_od_points_geojson(long_df, nodes_path)
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

    for modality in available_modalities:
        write_json(
            color_dir / f"{modality}.json",
            build_color_file_definition(
                modality,
                interval_specs_by_modality.get(modality, []),
            ),
        )

    write_json(experiment_dir / "manifest.json", build_manifest(experiment_id, experiment_label, available_modalities))
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
        available_modalities,
    )

    print(f"Wrote experiment bundle to {experiment_dir}")


if __name__ == "__main__":
    main()
