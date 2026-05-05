from __future__ import annotations

import ast
from pathlib import Path

import geopandas as gpd
import orjson
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT.parent
SOURCE_ROOT = REPO_ROOT / "Pittsburgh_Network" / "Pittsburgh_DODE"
INPUT_DIR = PROJECT_ROOT / "inputfile"
INPUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_NETWORK = SOURCE_ROOT / "input_files_v3" / "gis" / "links_ver2.shp"
PATH_TABLE_CSV = SOURCE_ROOT / "input_files_v3" / "original_output" / "path_table.csv"
PATH_TABLE_BUFFER = SOURCE_ROOT / "input_files_v3" / "original_output" / "path_table_buffer"
RATIO_DIR = SOURCE_ROOT / "results" / "exp21" / "ratio_bias_wape_analysis"
DIAG_SUMMARY = SOURCE_ROOT / "results" / "exp21" / "fit_gis_diagnosis" / "summary.md"
RECORD_DIR = PROJECT_ROOT / "records"
RECORD_DIR.mkdir(parents=True, exist_ok=True)

HOUR_LAYER_MAP = {
    "hour_15": "15_16",
    "hour_16": "16_17",
    "hour_17": "17_18",
}
MODALITIES = ["car_count", "truck_count", "car_tt", "truck_tt"]
DEFAULT_METRIC_MODALITY = "car_tt"


def classify_bias(value: float | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    if value < -0.2:
        return "under_est"
    if value > 0.2:
        return "over_est"
    return "good"


def parse_path_literal(value: object) -> list[int]:
    parsed = ast.literal_eval(str(value))
    if not isinstance(parsed, list):
        raise ValueError(f"Unexpected path literal: {value}")
    return [int(item) for item in parsed]


def build_directed_link_lookup() -> dict[tuple[int, int], int]:
    gdf = gpd.read_file(BASE_NETWORK, columns=["linkID", "N1", "N2"]).copy()
    gdf["linkID"] = gdf["linkID"].astype(int)
    gdf["N1"] = gdf["N1"].astype(int)
    gdf["N2"] = gdf["N2"].astype(int)

    duplicated = gdf.duplicated(subset=["N1", "N2"], keep=False)
    if duplicated.any():
        duplicate_rows = gdf.loc[duplicated, ["linkID", "N1", "N2"]].head(20).to_dict("records")
        raise ValueError(f"Found duplicated directed node pairs in network: {duplicate_rows}")

    return {
        (int(row["N1"]), int(row["N2"])): int(row["linkID"])
        for _, row in gdf.iterrows()
    }


def convert_node_path_to_link_path(node_sequence: list[int], lookup: dict[tuple[int, int], int]) -> list[int]:
    if len(node_sequence) < 2:
        return []

    link_sequence: list[int] = []
    for start_node, end_node in zip(node_sequence, node_sequence[1:]):
        key = (int(start_node), int(end_node))
        link_id = lookup.get(key)
        if link_id is None:
            raise ValueError(
                f"Could not map node pair {key} to a directed link in links_ver2.shp."
            )
        link_sequence.append(link_id)
    return link_sequence


def build_ratio_metrics(modality: str) -> pd.DataFrame:
    gpkg_path = RATIO_DIR / f"{modality}.gpkg"
    wide: pd.DataFrame | None = None

    for layer_name, suffix in HOUR_LAYER_MAP.items():
        gdf = gpd.read_file(gpkg_path, layer=layer_name)[
            ["linkID", "OBS", "EST", "RATIO", "BIAS", "WAPE", "FIT_CLASS"]
        ].copy()
        gdf = gdf.rename(
            columns={
                "linkID": "link_id",
                "OBS": f"{modality}_obs_{suffix}",
                "EST": f"{modality}_est_{suffix}",
                "RATIO": f"{modality}_ratio_{suffix}",
                "BIAS": f"{modality}_bias_{suffix}",
                "WAPE": f"{modality}_wape_{suffix}",
                "FIT_CLASS": f"{modality}_fit_class_{suffix}",
            }
        )

        for column in gdf.columns:
            if column == "link_id" or column.endswith("fit_class_" + suffix):
                continue
            gdf[column] = pd.to_numeric(gdf[column], errors="coerce")

        gdf["link_id"] = gdf["link_id"].astype(str)
        wide = gdf if wide is None else wide.merge(gdf, on="link_id", how="outer")

    assert wide is not None

    obs_cols = [f"{modality}_obs_{suffix}" for suffix in HOUR_LAYER_MAP.values()]
    est_cols = [f"{modality}_est_{suffix}" for suffix in HOUR_LAYER_MAP.values()]
    abs_diff = (wide[est_cols].to_numpy(dtype=float) - wide[obs_cols].to_numpy(dtype=float)).__abs__()
    obs_vals = wide[obs_cols].to_numpy(dtype=float)

    obs_sum = wide[obs_cols].sum(axis=1, min_count=1)
    est_sum = wide[est_cols].sum(axis=1, min_count=1)
    abs_diff_sum = pd.Series(abs_diff.sum(axis=1), index=wide.index)
    obs_abs_sum = pd.Series(abs(obs_vals).sum(axis=1), index=wide.index)

    wide[f"{modality}_obs_3h"] = obs_sum.where(obs_sum.notna())
    wide[f"{modality}_est_3h"] = est_sum.where(est_sum.notna())
    wide[f"{modality}_bias_3h"] = (est_sum - obs_sum) / obs_sum.replace(0, pd.NA)
    wide[f"{modality}_wape_3h"] = abs_diff_sum / obs_abs_sum.replace(0, pd.NA)
    wide[f"{modality}_fit_class_3h"] = wide[f"{modality}_bias_3h"].apply(classify_bias)
    wide[f"{modality}_observed_hours"] = wide[obs_cols].notna().sum(axis=1)

    return wide


def build_link_metrics() -> pd.DataFrame:
    merged: pd.DataFrame | None = None

    for modality in MODALITIES:
        modality_df = build_ratio_metrics(modality)
        merged = modality_df if merged is None else merged.merge(modality_df, on="link_id", how="outer")

    assert merged is not None
    default_prefix = DEFAULT_METRIC_MODALITY
    for suffix in ["15_16", "16_17", "17_18"]:
        merged[f"obs_{suffix}"] = merged[f"{default_prefix}_obs_{suffix}"]
        merged[f"est_{suffix}"] = merged[f"{default_prefix}_est_{suffix}"]
        merged[f"bias_{suffix}"] = merged[f"{default_prefix}_bias_{suffix}"]
        merged[f"wape_{suffix}"] = merged[f"{default_prefix}_wape_{suffix}"]

    merged["obs_3h"] = merged[f"{default_prefix}_obs_3h"]
    merged["est_3h"] = merged[f"{default_prefix}_est_3h"]
    merged["bias_3h"] = merged[f"{default_prefix}_bias_3h"]
    merged["wape_3h"] = merged[f"{default_prefix}_wape_3h"]
    merged["class"] = merged[f"{default_prefix}_fit_class_3h"]
    merged["default_metric_mode"] = default_prefix
    return merged


def write_network_file() -> None:
    gdf = gpd.read_file(BASE_NETWORK).copy()
    if "linkID" in gdf.columns:
        gdf = gdf.rename(columns={"linkID": "link_id"})
    gdf["link_id"] = gdf["link_id"].astype(str)
    network_gpkg = INPUT_DIR / "network.gpkg"
    if network_gpkg.exists():
        network_gpkg.unlink()
    gdf.to_file(network_gpkg, layer="links", driver="GPKG")


def write_path_table() -> pd.DataFrame:
    path_df = pd.read_csv(PATH_TABLE_CSV)
    directed_link_lookup = build_directed_link_lookup()
    path_df["node_sequence"] = path_df["path"].apply(parse_path_literal)
    path_df["link_sequence_list"] = path_df["node_sequence"].apply(
        lambda values: convert_node_path_to_link_path(values, directed_link_lookup)
    )
    path_df["path_str"] = path_df["node_sequence"].apply(lambda values: " ".join(map(str, values)))
    path_df = path_df.sort_values("path_str", kind="stable").reset_index(drop=True)

    raw_text_lines = PATH_TABLE_CSV.with_name("path_table").read_text(encoding="utf-8").splitlines()
    text_lines = [line.strip() for line in raw_text_lines if line.strip()]
    if len(text_lines) != len(path_df):
        raise ValueError("path_table text rows do not match path_table.csv rows.")
    if text_lines[:1000] != path_df["path_str"].head(1000).tolist():
        raise ValueError("Sorted path_table.csv rows are not aligned with path_table text ordering.")

    buffer_df = pd.read_csv(PATH_TABLE_BUFFER, sep=r"\s+", header=None)
    if len(buffer_df) != len(path_df):
        raise ValueError("path_table_buffer rows do not match sorted path table rows.")

    path_share = buffer_df.mean(axis=1)
    output_df = pd.DataFrame(
        {
            "path_id": [str(index + 1) for index in range(len(path_df))],
            "node_sequence": path_df["node_sequence"].apply(lambda values: ",".join(map(str, values))),
            "link_sequence": path_df["link_sequence_list"].apply(lambda values: ",".join(map(str, values))),
            "od_id": path_df["Origin_ID"].astype(str) + "_" + path_df["Destination_ID"].astype(str),
            "origin": path_df["Origin_ID"].astype(str),
            "destination": path_df["Destination_ID"].astype(str),
            "rank": path_df["rank"].astype(int),
            "path_tt": pd.to_numeric(path_df["tt"], errors="coerce"),
            "shortest_tt": pd.to_numeric(path_df["shortest_tt"], errors="coerce"),
            "tt_ratio": pd.to_numeric(path_df["ratio"], errors="coerce"),
            "path_flow": pd.to_numeric(path_share, errors="coerce"),
        }
    )
    output_df.to_csv(INPUT_DIR / "path_table.csv", index=False)
    return output_df


def write_metrics_file() -> pd.DataFrame:
    metrics_df = build_link_metrics()
    metrics_df.to_csv(INPUT_DIR / "link_metrics.csv", index=False)
    return metrics_df


def write_record(path_table_df: pd.DataFrame, metrics_df: pd.DataFrame) -> None:
    summary_text = DIAG_SUMMARY.read_text(encoding="utf-8")
    record = {
        "source_network": str(BASE_NETWORK),
        "source_path_table_csv": str(PATH_TABLE_CSV),
        "source_path_table_buffer": str(PATH_TABLE_BUFFER),
        "source_ratio_dir": str(RATIO_DIR),
        "default_metric_mode": DEFAULT_METRIC_MODALITY,
        "path_count": int(len(path_table_df)),
        "metric_rows": int(len(metrics_df)),
        "files_written": [
            str(INPUT_DIR / "network.gpkg"),
            str(INPUT_DIR / "link_metrics.csv"),
            str(INPUT_DIR / "path_table.csv"),
        ],
    }
    (RECORD_DIR / "exp21_input_prep_summary.json").write_bytes(orjson.dumps(record, option=orjson.OPT_INDENT_2))
    (RECORD_DIR / "exp21_diagnosis_summary.md").write_text(summary_text, encoding="utf-8")
    bilingual_text = f"""# Exp21 Input Preparation Summary / Exp21 输入准备摘要

## Overview / 概览

- Default metric mode: `{DEFAULT_METRIC_MODALITY}`
- 默认指标模式：`{DEFAULT_METRIC_MODALITY}`
- Path count written to `inputfile/path_table.csv`: `{len(path_table_df)}`
- 写入 `inputfile/path_table.csv` 的路径数量：`{len(path_table_df)}`
- Link metric rows written to `inputfile/link_metrics.csv`: `{len(metrics_df)}`
- 写入 `inputfile/link_metrics.csv` 的链路指标行数：`{len(metrics_df)}`

## Files written / 输出文件

- `{INPUT_DIR / 'network.gpkg'}`
- `{INPUT_DIR / 'link_metrics.csv'}`
- `{INPUT_DIR / 'path_table.csv'}`

## Source inputs / 来源输入

- Network source / 网络来源：`{BASE_NETWORK}`
- Path table CSV source / 路径表 CSV 来源：`{PATH_TABLE_CSV}`
- Path table buffer source / 路径表 buffer 来源：`{PATH_TABLE_BUFFER}`
- Ratio diagnostics source / 偏差诊断来源：`{RATIO_DIR}`
"""
    (RECORD_DIR / "exp21_input_prep_summary_bilingual.md").write_text(bilingual_text, encoding="utf-8")


def main() -> None:
    write_network_file()
    metrics_df = write_metrics_file()
    path_table_df = write_path_table()
    write_record(path_table_df, metrics_df)
    print(f"Wrote {INPUT_DIR / 'network.gpkg'}")
    print(f"Wrote {INPUT_DIR / 'link_metrics.csv'}")
    print(f"Wrote {INPUT_DIR / 'path_table.csv'}")
    print(f"Wrote {RECORD_DIR / 'exp21_input_prep_summary.json'}")
    print(f"Wrote {RECORD_DIR / 'exp21_diagnosis_summary.md'}")


if __name__ == "__main__":
    main()
