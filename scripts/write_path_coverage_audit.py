from __future__ import annotations

import csv
from pathlib import Path

import orjson


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "public" / "data"
RECORD_DIR = PROJECT_ROOT / "records"
RECORD_DIR.mkdir(parents=True, exist_ok=True)


def load_json(name: str):
    return orjson.loads((DATA_DIR / name).read_bytes())


def write_csv(links_index: dict, link_to_paths: dict[str, list[str]]) -> None:
    links_keys = set(links_index)
    path_keys = set(link_to_paths)

    missing_in_paths = sorted(links_keys - path_keys, key=lambda value: int(value) if value.isdigit() else value)
    missing_in_network = sorted(path_keys - links_keys, key=lambda value: int(value) if value.isdigit() else value)

    out_path = RECORD_DIR / "link_id_mismatch_audit.csv"
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "mismatch_type",
                "link_id",
                "in_links_index",
                "in_link_to_paths",
                "path_count",
                "sample_path_ids",
                "street_name_1",
                "street_name_2",
                "street_name_3",
                "note",
            ],
        )
        writer.writeheader()

        for link_id in missing_in_paths:
            properties = links_index[link_id].get("properties", {})
            writer.writerow(
                {
                    "mismatch_type": "missing_in_link_to_paths",
                    "link_id": link_id,
                    "in_links_index": 1,
                    "in_link_to_paths": 0,
                    "path_count": 0,
                    "sample_path_ids": "",
                    "street_name_1": properties.get("ST_NAME_1", ""),
                    "street_name_2": properties.get("ST_NAME_2", ""),
                    "street_name_3": properties.get("ST_NAME_3", ""),
                    "note": properties.get("note", ""),
                }
            )

        for link_id in missing_in_network:
            path_ids = link_to_paths.get(link_id, [])
            writer.writerow(
                {
                    "mismatch_type": "missing_in_links_index",
                    "link_id": link_id,
                    "in_links_index": 0,
                    "in_link_to_paths": 1,
                    "path_count": len(path_ids),
                    "sample_path_ids": ",".join(path_ids[:10]),
                    "street_name_1": "",
                    "street_name_2": "",
                    "street_name_3": "",
                    "note": "",
                }
            )


def write_bilingual_summary(links_index: dict, link_to_paths: dict[str, list[str]], path_summary: dict) -> None:
    links_keys = set(links_index)
    path_keys = set(link_to_paths)

    missing_in_paths = sorted(links_keys - path_keys, key=lambda value: int(value) if value.isdigit() else value)
    missing_in_network = sorted(path_keys - links_keys, key=lambda value: int(value) if value.isdigit() else value)

    total_segments = 0
    missing_segments = 0
    partial_paths = 0
    for path in path_summary.values():
      sequence = path.get("link_sequence", [])
      total_segments += len(sequence)
      missing = sum(1 for link_id in sequence if link_id not in links_keys)
      missing_segments += missing
      if missing > 0:
        partial_paths += 1

    sample_link_id = "308"
    sample_path_count = len(link_to_paths.get(sample_link_id, []))

    text = f"""# Path Coverage Audit / 路径覆盖审计

## Coverage summary / 覆盖概况

- Network links in `links_index.json`: `{len(links_keys)}`
- `links_index.json` 中的网络 link 数量：`{len(links_keys)}`
- Links covered by `link_to_paths.json`: `{len(path_keys)}`
- `link_to_paths.json` 中有路径覆盖的 link 数量：`{len(path_keys)}`
- Links missing from `link_to_paths.json`: `{len(missing_in_paths)}`
- 在 `link_to_paths.json` 中缺失的网络 link 数量：`{len(missing_in_paths)}`
- Link IDs present in `link_to_paths.json` but absent from `links_index.json`: `{len(missing_in_network)}`
- 出现在 `link_to_paths.json` 但不在 `links_index.json` 中的 link ID 数量：`{len(missing_in_network)}`

## Sample interpretation / 示例解释

- `link_id = {sample_link_id}` currently maps to `{sample_path_count}` path records.
- 当前 `link_id = {sample_link_id}` 对应 `{sample_path_count}` 条 path 记录。
- In the current app, that means `{sample_path_count}` distinct `path_id` entries include this link.
- 在当前应用里，这表示有 `{sample_path_count}` 个不同的 `path_id` 记录包含这个 link。

## Contribution meaning / contribution 含义

- In this demo, `contribution` is currently taken from the fallback `path_flow` field when a dedicated contribution shard is unavailable.
- 在这个 demo 中，如果没有单独的 contribution 分片文件，`contribution` 当前会回退为 `path_flow` 字段。
- The current `path_flow` values are mostly `0.333333` and occasionally `1.0`, so they behave like path weights or shares rather than absolute traffic counts.
- 当前 `path_flow` 数值大多是 `0.333333`，少数是 `1.0`，因此它更像路径权重或份额，而不是绝对车流量。
- Therefore `total contribution` should currently be interpreted as summed path weight on the selected link, not as vehicles/hour.
- 因此当前的 `total contribution` 应解释为该 link 上累计的路径权重，而不是“辆/小时”。

## Geometry mismatch / 几何不匹配

- Paths with at least one missing geometry segment: `{partial_paths}`
- 至少缺失一个几何片段的 path 数量：`{partial_paths}`
- Missing segment share: `{(missing_segments / total_segments) if total_segments else 0:.4%}`
- 缺失片段占全部 path 片段的比例：`{(missing_segments / total_segments) if total_segments else 0:.4%}`

## CSV output / CSV 输出

- Detailed mismatch rows are written to `records/link_id_mismatch_audit.csv`.
- 详细的不匹配明细已经写入 `records/link_id_mismatch_audit.csv`。
"""

    (RECORD_DIR / "path_coverage_audit_bilingual.md").write_text(text, encoding="utf-8")


def main() -> None:
    links_index = load_json("links_index.json")
    link_to_paths = load_json("link_to_paths.json")
    path_summary = load_json("path_summary.json")
    write_csv(links_index, link_to_paths)
    write_bilingual_summary(links_index, link_to_paths, path_summary)
    print(f"Wrote {RECORD_DIR / 'link_id_mismatch_audit.csv'}")
    print(f"Wrote {RECORD_DIR / 'path_coverage_audit_bilingual.md'}")


if __name__ == "__main__":
    main()
