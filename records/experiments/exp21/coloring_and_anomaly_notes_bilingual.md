# Exp21 Coloring And Anomaly Notes / Exp21 着色与异常说明

## 1. What was checked / 做了什么检查

- Source checked for observed coverage:
  `results/exp21/link_observation_coverage.csv`
- Hourly ratio files checked:
  `results/exp21/ratio_bias_wape_analysis/*_hour_15.csv`,
  `*_hour_16.csv`,
  `*_hour_17.csv`

## 2. Coverage findings / 覆盖结论

- `car_count`: observed links = `336`, valid ratio-hour links = `319`
- `truck_count`: observed links = `336`, valid ratio-hour links = `319`
- `car_tt`: observed links = `1771`, valid ratio-hour links = `1714`
- `truck_tt`: observed links = `1791`, valid ratio-hour links = `1734`

This means the ratio files are subsets of the observed-coverage source.

这说明 ratio 文件是 observed 覆盖源文件的子集。

## 3. Why the previous demo mixed in too many abnormal links / 为什么上一版 demo 会混入很多异常链路

There were two separate issues:

有两个叠加的问题：

1. The old demo used one flat merged network layer and did not enforce the correct observed/valid mask for each metric view.
1. 旧版 demo 使用了一个平铺合并后的网络图层，没有针对不同指标视图严格套用对应的 observed/valid 掩码。

2. The `*_valid_*` fields were serialized into GeoJSON as strings like `"True"` and `"False"`. In the frontend, `Boolean("False")` is still `true`, so many links were incorrectly treated as valid.
2. `*_valid_*` 字段写入 GeoJSON 后变成了 `"True"` / `"False"` 这样的字符串。前端里 `Boolean("False")` 仍然会得到 `true`，因此很多本不该算作有效的链路被错误当成了有效链路。

That second bug is the direct reason why so many abnormal links were colored in the previous version.

第二个 bug 就是上一版里大量异常链路被着色的直接原因。

## 4. What is fixed now / 现在修复了什么

- The demo now loads experiment bundles from `public/data/experiments/<exp_id>/`.
- Demo 现在从 `public/data/experiments/<exp_id>/` 加载实验数据包。
- The UI now uses multi-level selection:
  `Experiment -> Color file -> Metric -> Period`
- 界面现在改成多级选择：
  `Experiment -> Color file -> Metric -> Period`
- The frontend now coerces `"True"` / `"False"` strings into real booleans before applying masks.
- 前端现在会先把 `"True"` / `"False"` 字符串转换为真正的布尔值，再应用掩码。
- `bias` and `wape` views use valid-mask-based coloring, so links without valid observed-vs-estimated comparison render in black.
- `bias` 和 `wape` 视图现在基于 valid mask 着色，因此没有有效 observed-vs-estimated 对比的链路会显示为黑色。

## 5. Files to inspect / 推荐查看文件

- Coverage audit CSV / 覆盖审计 CSV:
  `records/experiments/exp21/coverage_gap_audit.csv`
- Coverage audit note / 覆盖审计说明:
  `records/experiments/exp21/coverage_gap_audit_bilingual.md`
- Experiment manifest / 实验清单:
  `public/data/experiments/exp21/manifest.json`
