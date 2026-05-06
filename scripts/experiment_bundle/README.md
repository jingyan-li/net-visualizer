# Experiment Bundle Scripts

## 用途

这些脚本把 `Pittsburgh_DODE` 的实验结果打包成 demo 能直接读取的实验包。

主要输出是：

- `public/data/experiments/<exp>/manifest.json`
- `public/data/experiments/<exp>/network/*`
- `public/data/experiments/<exp>/od/*`
- `public/data/experiments/<exp>/paths/*`
- `public/data/experiments/<exp>/color_files/*`

## 脚本

- `build_experiment_bundle.py`
  把路网、节点、path table、interval CSV、coverage CSV 组装成 demo 数据包。

- `audit_experiment_coverage.py`
  对比 observed 覆盖和 ratio interval 覆盖，生成审计记录。

## 示例

```bash
conda activate "/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/.conda/path-link-demo-env"

cd "/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo"

python scripts/experiment_bundle/build_experiment_bundle.py \
  --experiment-id exp21 \
  --experiment-label "Exp 21" \
  --network "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/gis/links_ver2.shp" \
  --nodes "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/gis/nodes_ver2.shp" \
  --path-table-csv "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/original_output/path_table.csv" \
  --path-table-buffer "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/path_table_buffer" \
  --ratio-dir "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/ratio_bias_wape_analysis" \
  --coverage-csv "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/link_observation_coverage.csv"

python scripts/experiment_bundle/audit_experiment_coverage.py \
  --experiment-id exp21 \
  --ratio-dir "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/ratio_bias_wape_analysis" \
  --coverage-csv "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/link_observation_coverage.csv"
```

## 新实验如何复用

1. 在 `results/` 下生成新的实验目录，例如 `exp22/`
2. 确保其中有：
   - `ratio_bias_wape_analysis/{car/truck}_{count/tt}_{hour/15min}_<interval>.csv`
   - `link_observation_coverage.csv`
3. 用新的 `--experiment-id exp22` 重跑上面两条脚本
4. 刷新 demo，在 `Experiment` 里选择 `exp22`

## interval 文件识别规则

bundle 脚本会用正则表达式自动识别：

- `{modality}_hour_<hour>.csv`
- `{modality}_15min_<hour>-<quarter>.csv`

例如：

- `car_count_hour_15.csv`
- `car_tt_15min_15-2.csv`

因此：

- 不再依赖 `*_link_metrics.csv`
- 不再写死 `15/16/17`
- interval 滑键刻度由实际文件数量自动决定
