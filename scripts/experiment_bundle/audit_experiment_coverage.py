from __future__ import annotations

import argparse
import re
from pathlib import Path

import orjson
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECORDS_ROOT = PROJECT_ROOT / "records" / "experiments"

MODALITY_CONFIG = {
    "car_count": {"coverage_column": "car_flow_count"},
    "truck_count": {"coverage_column": "truck_flow_count"},
    "car_tt": {"coverage_column": "car_tt_count"},
    "truck_tt": {"coverage_column": "truck_tt_count"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit observed coverage versus valid ratio rows.")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--ratio-dir", required=True, type=Path)
    parser.add_argument("--coverage-csv", required=True, type=Path)
    parser.add_argument("--records-root", type=Path, default=DEFAULT_RECORDS_ROOT)
    return parser.parse_args()


def discover_ratio_files(ratio_dir: Path) -> dict[str, list[Path]]:
    pattern = re.compile(r"^(?P<modality>.+)_(?P<interval_kind>hour|15min)_(?P<interval_id>\d+|(?:\d+-[0-3]))\.csv$")
    mapping: dict[str, list[Path]] = {}
    for csv_path in ratio_dir.glob("*.csv"):
        match = pattern.match(csv_path.name)
        if not match:
            continue
        modality = match.group("modality")
        if modality not in MODALITY_CONFIG:
            continue
        mapping.setdefault(modality, []).append(csv_path)
    return mapping


def main() -> None:
    args = parse_args()
    coverage = pd.read_csv(args.coverage_csv)
    discovered = discover_ratio_files(args.ratio_dir)
    rows: list[dict[str, object]] = []
    summary_lines: list[str] = []

    for modality, config in MODALITY_CONFIG.items():
        observed = set(
            coverage.loc[coverage[config["coverage_column"]].fillna(0) > 0, "linkID"].astype(int)
        )
        ratio_links: set[int] = set()
        for csv_path in discovered.get(modality, []):
            interval_df = pd.read_csv(csv_path)
            ratio_links |= set(interval_df["linkID"].dropna().astype(int))

        observed_only = sorted(observed - ratio_links)
        ratio_only = sorted(ratio_links - observed)
        rows.append(
            {
                "modality": modality,
                "ratio_files": len(discovered.get(modality, [])),
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
                f"- Ratio files / ratio 文件数: `{len(discovered.get(modality, []))}`",
                f"- Observed links / observed 链路数: `{len(observed)}`",
                f"- Ratio links / ratio 链路数: `{len(ratio_links)}`",
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
