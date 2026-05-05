# Experiment Bundle Scripts / 实验数据包脚本

## Purpose / 用途

These scripts build one experiment folder that the demo can load directly, for example:

这些脚本会生成一个 demo 可直接加载的实验文件夹，例如：

- `public/data/experiments/exp21/manifest.json`
- `public/data/experiments/exp21/network/*`
- `public/data/experiments/exp21/paths/*`
- `public/data/experiments/exp21/color_files/*`

## Scripts / 脚本

- `build_experiment_bundle.py`
  Builds the demo-ready experiment bundle from the network, path table, ratio files, and coverage CSV.
  从网络、路径表、ratio 文件和 coverage CSV 构建 demo 可直接使用的实验数据包。

- `audit_experiment_coverage.py`
  Compares observed coverage and ratio-hourly coverage, then writes bilingual audit outputs.
  对比 observed 覆盖与 ratio 小时覆盖，并输出双语审计结果。

## Example / 示例

Use the conda environment created for this demo.

请使用为本 demo 创建的 conda 环境。

```bash
conda activate "/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/.conda/path-link-demo-env"

cd "/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo"

python scripts/experiment_bundle/build_experiment_bundle.py \
  --experiment-id exp21 \
  --experiment-label "Exp 21" \
  --network "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/gis/links_ver2.shp" \
  --path-table-csv "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/original_output/path_table.csv" \
  --path-table-buffer "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/original_output/path_table_buffer" \
  --ratio-dir "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/ratio_bias_wape_analysis" \
  --coverage-csv "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/link_observation_coverage.csv"

python scripts/experiment_bundle/audit_experiment_coverage.py \
  --experiment-id exp21 \
  --ratio-dir "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/ratio_bias_wape_analysis" \
  --coverage-csv "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/link_observation_coverage.csv"
```

## For a new experiment / 新实验复用方法

1. Create a new source result folder such as `results/exp22/`.
2. Make sure it contains:
   `ratio_bias_wape_analysis/*_link_metrics.csv`,
   `ratio_bias_wape_analysis/*_hour_*.csv`,
   and `link_observation_coverage.csv`.
3. Run the same two scripts with `--experiment-id exp22`.
4. Refresh the demo and choose `exp22` in the experiment selector.

1. 新建结果目录，例如 `results/exp22/`。
2. 确保其中包含：
   `ratio_bias_wape_analysis/*_link_metrics.csv`、
   `ratio_bias_wape_analysis/*_hour_*.csv`，
   以及 `link_observation_coverage.csv`。
3. 使用 `--experiment-id exp22` 运行同样两条脚本。
4. 刷新 demo，并在实验选择器中选中 `exp22`。

## Hour detection / 小时窗口识别

The bundle builder reads `*_hour_*.csv` with a regular expression and keeps whatever hour ids are present.

数据包脚本会用正则表达式读取 `*_hour_*.csv`，并保留其中实际存在的小时编号。

The upstream `Pittsburgh_DODE/analyze_ratio_bias_wape.py` script now derives those hour ids from:

上游 `Pittsburgh_DODE/analyze_ratio_bias_wape.py` 现在会从以下配置自动推导小时编号：

- `ExpConfig.json -> time_offset`
- `config.conf -> unit_time`
- `config.conf -> total_interval`

So after an experiment finishes, the generated hourly files are no longer restricted to `15/16/17`.

因此实验结束后生成的小时文件不再局限于 `15/16/17`。
