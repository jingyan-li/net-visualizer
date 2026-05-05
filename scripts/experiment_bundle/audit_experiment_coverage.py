from __future__ import annotations

import argparse
from pathlib import Path

import orjson
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_ROOT = PROJECT_ROOT.parent / "Pittsburgh_Network" / "Pittsburgh_DODE" / "results"
DEFAULT_RECORDS_ROOT = PROJECT_ROOT / "records" / "experiments"

MODALITY_CONFIG = {
    "car_count": {
        "coverage_column": "car_flow_count",
        "ratio_hours": ["car_count_hour_15.csv", "car_count_hour_16.csv", "car_count_hour_17.csv"],
    },
    "truck_count": {
        "coverage_column": "truck_flow_count",
        "ratio_hours": ["truck_count_hour_15.csv", "truck_count_hour_16.csv", "truck_count_hour_17.csv"],
    },
    "car_tt": {
        "coverage_column": "car_tt_count",
        "ratio_hours": ["car_tt_hour_15.csv", "car_tt_hour_16.csv", "car_tt_hour_17.csv"],
    },
    "truck_tt": {
        "coverage_column": "truck_tt_count",
        "ratio_hours": ["truck_tt_hour_15.csv", "truck_tt_hour_16.csv", "truck_tt_hour_17.csv"],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit observed coverage versus valid ratio rows.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--ratio-dir", required=True, type=Path)
    parser.add_argument("--coverage-csv", required=True, type=Path)
    parser.add_argument("--records-root", type=Path, default=DEFAULT_RECORDS_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    coverage = pd.read_csv(args.coverage_csv)
    rows: list[dict[str, object]] = []
    summary_lines: list[str] = []

    for modality, config in MODALITY_CONFIG.items():
        observed = set(
            coverage.loc[coverage[config["coverage_column"]].fillna(0) > 0, "linkID"].astype(int)
        )
        ratio_links: set[int] = set()
        for filename in config["ratio_hours"]:
            hour_df = pd.read_csv(args.ratio_dir / filename)
            ratio_links |= set(hour_df["linkID"].dropna().astype(int))

        observed_only = sorted(observed - ratio_links)
        ratio_only = sorted(ratio_links - observed)
        rows.append(
            {
                "modality": modality,
                "observed_links": len(observed),
                "ratio_links": len(ratio_links),
                "intersection_links": len(observed & ratio_links),
                "observed_only_links": len(observed_only),
                "ratio_only_links": len(ratio_only),
                "observed_link_id_min": min(observed) if observed else None,
                "observed_link_id_max": max(observed) if observed else None,
                "ratio_link_id_min": min(ratio_links) if ratio_links else None,
                "ratio_link_id_max": max(ratio_links) if ratio_links else None,
                "observed_only_link_ids": ",".join(map(str, observed_only)),
                "ratio_only_link_ids": ",".join(map(str, ratio_only)),
            }
        )
        summary_lines.extend(
            [
                f"## {modality}",
                "",
                f"- Observed links / observed 链路数: `{len(observed)}`",
                f"- Ratio hourly links / ratio 小时链路数: `{len(ratio_links)}`",
                f"- Observed-only links / 仅 observed 的链路数: `{len(observed_only)}`",
                f"- Ratio-only links / 仅 ratio 的链路数: `{len(ratio_only)}`",
                f"- Observed link ID range / observed linkID 范围: `{min(observed) if observed else 'n/a'} - {max(observed) if observed else 'n/a'}`",
                f"- Ratio link ID range / ratio linkID 范围: `{min(ratio_links) if ratio_links else 'n/a'} - {max(ratio_links) if ratio_links else 'n/a'}`",
                f"- Observed-only sample / 仅 observed 样例: `{','.join(map(str, observed_only[:20])) or 'none'}`",
                f"- Ratio-only sample / 仅 ratio 样例: `{','.join(map(str, ratio_only[:20])) or 'none'}`",
                "",
            ]
        )

    record_dir = args.records_root / args.experiment_id
    record_dir.mkdir(parents=True, exist_ok=True)
    audit_df = pd.DataFrame(rows)
    audit_df.to_csv(record_dir / "coverage_gap_audit.csv", index=False)
    (record_dir / "coverage_gap_audit_bilingual.md").write_text(
        "# Coverage Gap Audit / 覆盖差异审计\n\n" + "\n".join(summary_lines),
        encoding="utf-8",
    )
    (record_dir / "coverage_gap_audit.json").write_bytes(
        orjson.dumps(rows, option=orjson.OPT_INDENT_2)
    )
    print(f"Wrote audit outputs to {record_dir}")


if __name__ == "__main__":
    main()
