# exp21 fit vs GIS diagnosis

## Core ratios
- Car TT underfit links: 445; count also bad 22 (4.9%) over all links, 36.7% among links with count observations.
- Truck TT underfit links: 508; count also bad 52 (10.2%) over all links, 86.7% among links with count observations.
- Car count underfit links: 117; TT also bad 15 (12.8%) over all links, 26.3% among links with TT observations.
- Truck count underfit links: 245; TT also bad 47 (19.2%) over all links, 33.6% among links with TT observations.

## Road class and count reasonableness
- Car TT underfit road classes: local:391(87.9%), highway:53(11.9%), arterial:1(0.2%); GIS CLVL: HIGH:381(85.6%), MID:55(12.4%), LOW:7(1.6%), NA:2(0.4%).
- Car count underfit road classes: local:110(94.0%), highway:7(6.0%); GIS CLVL: HIGH:93(79.5%), MID:18(15.4%), LOW:3(2.6%), NA:3(2.6%).
- Car TT underfit links with plausible observed count magnitude: 60 / 60.
- Car count underfit links with plausible observed count magnitude: 117 / 117.

## Likely issue patterns
- Car TT underfit zero-path share: 251 / 445 (56.4%); low-path(1-9) share: 7 / 445.
- Car count underfit zero-path share: 64 / 117 (54.7%); low-path(1-9) share: 1 / 117.
- Car TT underfit median path_count=0.0, median length_mile=0.2, short-link share=23.8%.
- Car count underfit median path_count=0.0, median length_mile=0.4, short-link share=9.4%.
- Speedlimit=999 / connector-like links exported separately: 0 links.

## Exported GIS files
- bad_fit_with_low_path_1_9.geojson: 13 links
- bad_fit_with_zero_path.geojson: 501 links
- car_count_underfit__tt_bad.geojson: 15 links
- car_count_underfit__tt_good.geojson: 42 links
- car_count_underfit__tt_missing.geojson: 60 links
- car_tt_underfit__count_bad.geojson: 22 links
- car_tt_underfit__count_good.geojson: 38 links
- car_tt_underfit__count_missing.geojson: 385 links
- count_implausible_high.geojson: 0 links
- speedlimit_999_or_connector.geojson: 0 links
- truck_count_underfit__tt_bad.geojson: 47 links
- truck_count_underfit__tt_good.geojson: 93 links
- truck_count_underfit__tt_missing.geojson: 105 links
- truck_tt_underfit__count_bad.geojson: 52 links
- truck_tt_underfit__count_good.geojson: 8 links
- truck_tt_underfit__count_missing.geojson: 448 links

## Notes
- `road_class_inferred` follows the same thresholds used in the existing observed-link path analysis: connector / highway / arterial / local.
- `car_count_reasonableness` is judged by observed mean count versus modeled per-hour total capacity (`cap_car_vph * lane`).
- `count also bad` means count fit status is `underfit` or `overfit`; missing count observations are reported separately.