# exp21 Demo Setup

## Source selection

- `exp21` config points to `Pittsburgh_Network/Pittsburgh_DODE/input_files_v3`.
- The demo therefore uses:
- base network from `input_files_v3/gis/links_ver2.shp`
- path metadata from `input_files_v3/original_output/path_table.csv`
- path share weights from `input_files_v3/original_output/path_table_buffer`
- hourly fit metrics from `results/exp21/ratio_bias_wape_analysis/*.gpkg`

## Default map metric

- The demo aliases `bias_3h`, `wape_3h`, and `class` to the `car_tt` 3-hour metrics because `car_tt` has much wider observed coverage than count.

## Generated outputs

- `inputfile/network.gpkg`: 2.5 MB
- `inputfile/link_metrics.csv`: 1.8 MB
- `inputfile/path_table.csv`: 48 MB
- `public/data/links.geojson`: 32 MB
- `public/data/links_index.json`: 8.1 MB
- `public/data/path_summary.json`: 69 MB
- `public/data/link_to_paths.json`: 51 MB
- `public/data/link_path_contrib_by_link/`: sharded contribution files for on-demand loading
- The frontend is configured not to eagerly load a giant global contribution JSON at startup.

## One-command refresh

```bash
/Users/exps/Person\ Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/scripts/run_exp21_demo_setup.sh
```

## Then run the app

```bash
cd /Users/exps/Person\ Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo
npm run dev
```
