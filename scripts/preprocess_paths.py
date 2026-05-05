from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import orjson
import pandas as pd
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT = PROJECT_ROOT / "inputfile"
OUTPUT = PROJECT_ROOT / "public" / "data"
OUTPUT.mkdir(parents=True, exist_ok=True)
GLOBAL_CONTRIB_RECORD_LIMIT = 500_000


def read_path_table() -> pd.DataFrame:
    path_table = INPUT / "path_table.csv"
    if not path_table.exists():
        raise FileNotFoundError("inputfile/path_table.csv not found.")
    return pd.read_csv(path_table)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [column.strip() for column in df.columns]
    return df


def normalize_path_table(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)
    if "path_id" not in df.columns:
        raise ValueError("path_table.csv must contain path_id.")

    df["path_id"] = df["path_id"].astype(str)

    if "link_sequence" in df.columns:
        expanded = df.copy()
        expanded["link_id"] = expanded["link_sequence"].astype(str).str.replace(";", ",").str.split(",")
        expanded = expanded.explode("link_id", ignore_index=True)
        expanded["link_id"] = expanded["link_id"].astype(str).str.strip()
        expanded = expanded.loc[expanded["link_id"] != ""].copy()
        expanded["seq"] = expanded.groupby("path_id").cumcount() + 1
        return expanded

    required = {"path_id", "seq", "link_id"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Long path table missing required fields: {sorted(missing)}")

    df["link_id"] = df["link_id"].astype(str)
    df["seq"] = pd.to_numeric(df["seq"], errors="raise").astype(int)
    return df


def clean_value(column: str, value: Any) -> Any:
    if pd.isna(value):
        return None
    if column in {"path_flow", "contribution"}:
        return float(value)
    return str(value)


def build_path_summary(long_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    optional_columns = [
        "od_id",
        "origin",
        "destination",
        "depart_interval",
        "vehicle_class",
        "path_flow",
    ]
    available_optional = [column for column in optional_columns if column in long_df.columns]
    grouped = long_df.groupby("path_id", sort=False)
    sequence_by_path = grouped["link_id"].agg(list)
    counts_by_path = grouped.size()
    first_values = grouped[available_optional].first() if available_optional else pd.DataFrame(index=sequence_by_path.index)

    path_summary: dict[str, dict[str, Any]] = {}
    for path_id in tqdm(sequence_by_path.index, total=len(sequence_by_path), desc="Building path_summary"):
        record: dict[str, Any] = {
            "path_id": str(path_id),
            "num_links": int(counts_by_path.loc[path_id]),
            "link_sequence": [str(link_id) for link_id in sequence_by_path.loc[path_id]],
        }
        if available_optional:
            first = first_values.loc[path_id]
            for column in available_optional:
                value = clean_value(column, first[column])
                if value is not None:
                    record[column] = value
        path_summary[str(path_id)] = record

    return path_summary


def build_link_to_paths(long_df: pd.DataFrame) -> dict[str, list[str]]:
    unique_pairs = long_df[["link_id", "path_id"]].drop_duplicates()
    grouped = unique_pairs.groupby("link_id", sort=False)["path_id"].agg(list)
    return {
        str(link_id): [str(path_id) for path_id in path_ids]
        for link_id, path_ids in tqdm(grouped.items(), total=len(grouped), desc="Building link_to_paths")
    }


def load_contrib_source(long_df: pd.DataFrame) -> pd.DataFrame:
    buffer_file = INPUT / "path_table_buffer.csv"
    if not buffer_file.exists():
        contrib_df = long_df.copy()
    else:
        contrib_df = pd.read_csv(buffer_file)
        contrib_df = normalize_columns(contrib_df)
        if "link_id" not in contrib_df.columns or "path_id" not in contrib_df.columns:
            raise ValueError("path_table_buffer.csv must contain link_id and path_id.")

    contrib_df["link_id"] = contrib_df["link_id"].astype(str)
    contrib_df["path_id"] = contrib_df["path_id"].astype(str)

    if "contribution" not in contrib_df.columns:
        if "path_flow" in contrib_df.columns:
            contrib_df["contribution"] = contrib_df["path_flow"]
        else:
            contrib_df["contribution"] = 1.0

    return contrib_df


def build_link_path_contrib(long_df: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    contrib_df = load_contrib_source(long_df)
    keep_columns = [
        column
        for column in [
            "link_id",
            "path_id",
            "od_id",
            "origin",
            "destination",
            "depart_interval",
            "vehicle_class",
            "path_flow",
            "contribution",
        ]
        if column in contrib_df.columns
    ]

    contrib_df = contrib_df[keep_columns].copy()
    link_path_contrib: dict[str, list[dict[str, Any]]] = {}

    for link_id, group in tqdm(contrib_df.groupby("link_id", sort=False), desc="Building link_path_contrib"):
        records: list[dict[str, Any]] = []
        for row in group.to_dict("records"):
            record: dict[str, Any] = {}
            for column in keep_columns:
                if column == "link_id":
                    continue
                value = clean_value(column, row[column])
                if value is not None:
                    record[column] = value
            records.append(record)

        records.sort(key=lambda item: float(item.get("contribution", 0.0)), reverse=True)
        link_path_contrib[str(link_id)] = records

    return link_path_contrib


def write_json(name: str, payload: Any) -> None:
    (OUTPUT / name).write_bytes(orjson.dumps(payload))
    print(f"Wrote {OUTPUT / name}")


def write_sharded_contrib(link_path_contrib: dict[str, list[dict[str, Any]]]) -> None:
    out_dir = OUTPUT / "link_path_contrib_by_link"
    out_dir.mkdir(parents=True, exist_ok=True)
    for link_id, records in link_path_contrib.items():
        (out_dir / f"{link_id}.json").write_bytes(orjson.dumps(records))
    print(f"Wrote sharded contribution files to {out_dir}")


def main() -> None:
    raw_df = read_path_table()
    long_df = normalize_path_table(raw_df)
    path_summary = build_path_summary(long_df)
    link_to_paths = build_link_to_paths(long_df)
    link_path_contrib = build_link_path_contrib(long_df)

    write_json("path_summary.json", path_summary)
    write_json("link_to_paths.json", link_to_paths)
    total_contrib_records = sum(len(records) for records in link_path_contrib.values())
    if total_contrib_records <= GLOBAL_CONTRIB_RECORD_LIMIT:
        write_json("link_path_contrib.json", link_path_contrib)
    else:
        print(
            "Skipped global link_path_contrib.json because the dataset is large; "
            "using sharded link_path_contrib_by_link/ files instead."
        )
    write_sharded_contrib(link_path_contrib)


if __name__ == "__main__":
    main()
