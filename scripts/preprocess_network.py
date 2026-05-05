from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import orjson
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT = PROJECT_ROOT / "inputfile"
OUTPUT = PROJECT_ROOT / "public" / "data"
OUTPUT.mkdir(parents=True, exist_ok=True)

LINK_ID_ALIASES = ["link_id", "linkID", "linkid", "ID", "id", "link", "link_no"]


def find_network_file() -> Path:
    for name in ("network.gpkg", "network.shp"):
        candidate = INPUT / name
        if candidate.exists():
            return candidate

    gpkg_files = sorted(INPUT.glob("*.gpkg"))
    shp_files = sorted(INPUT.glob("*.shp"))
    if gpkg_files:
        return gpkg_files[0]
    if shp_files:
        return shp_files[0]
    raise FileNotFoundError("No network .gpkg or .shp found in inputfile/.")


def normalize_link_id(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    alias_map = {alias.lower(): alias for alias in LINK_ID_ALIASES}
    matched_column = None

    for column in gdf.columns:
        if column.lower() in alias_map:
            matched_column = column
            break

    if matched_column is None:
        raise ValueError(f"Could not find link_id column. Available columns: {list(gdf.columns)}")

    if matched_column != "link_id":
        gdf = gdf.rename(columns={matched_column: "link_id"})

    gdf["link_id"] = gdf["link_id"].astype(str)
    return gdf


def normalize_geometry(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        print("WARNING: network CRS is missing. Assuming EPSG:4326.")
        gdf = gdf.set_crs(epsg=4326)
    else:
        gdf = gdf.to_crs(epsg=4326)

    return gdf[gdf.geometry.notnull()].copy()


def merge_metrics(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    metrics_file = INPUT / "link_metrics.csv"
    if not metrics_file.exists():
        return gdf

    metrics = pd.read_csv(metrics_file)
    if "link_id" not in metrics.columns:
        raise ValueError("link_metrics.csv must contain a link_id column.")

    metrics["link_id"] = metrics["link_id"].astype(str)
    return gdf.merge(metrics, on="link_id", how="left")


def to_serializable_props(row: pd.Series) -> dict[str, object]:
    props: dict[str, object] = {}
    for key, value in row.items():
        if key == "geometry" or pd.isna(value):
            continue
        if hasattr(value, "item"):
            value = value.item()
        props[key] = value
    return props


def main() -> None:
    network_file = find_network_file()
    gdf = gpd.read_file(network_file)
    gdf = normalize_link_id(gdf)
    gdf = normalize_geometry(gdf)
    gdf = merge_metrics(gdf)

    links_geojson_path = OUTPUT / "links.geojson"
    gdf.to_file(links_geojson_path, driver="GeoJSON")

    link_index: dict[str, dict[str, object]] = {}
    for _, row in gdf.iterrows():
        link_index[str(row["link_id"])] = {
            "properties": to_serializable_props(row.drop(labels=["geometry"])),
            "geometry": row.geometry.__geo_interface__,
        }

    (OUTPUT / "links_index.json").write_bytes(orjson.dumps(link_index))

    print(f"Wrote {links_geojson_path}")
    print(f"Wrote {OUTPUT / 'links_index.json'}")


if __name__ == "__main__":
    main()
