# Path-Link Visualization Demo

## 项目原理

这个 demo 把三类信息叠在同一个交互界面里：

1. 路网几何  
   从 `links_ver2.shp` 读取 link 形状。

2. 路径覆盖关系  
   从 `path_table.csv` 中的 node 序列恢复每条 path 经过的 link 序列，并建立：
   - `link -> paths`
   - `path -> link_sequence`
   - `link -> path contribution`

3. 实验结果着色  
   从 `Pittsburgh_DODE/results/<exp>/ratio_bias_wape_analysis/` 和 `link_observation_coverage.csv` 读取 observed / estimate / bias / wape，并支持：
   - `Total`
   - `By interval`

## 目录结构

```text
path-link-visualization-demo/
  public/data/experiments/       # 每个实验的静态数据包
  records/                       # 审计记录和说明
  scripts/experiment_bundle/     # 把实验结果打包成 demo 可读格式
  src/components/                # Toolbar、Sidebar、Legend 等
  src/layers/                    # deck.gl 图层
  src/data/                      # 数据加载与颜色映射
  src/store/                     # 前端状态
```

## Pull 之后要安装什么

Python 侧：

- `python >= 3.10`
- `geopandas`
- `pandas`
- `numpy`
- `orjson`
- `pyogrio`
- `shapely`

前端：

- `node >= 18`
- `npm >= 9`

推荐：

```bash
conda env create -f environment.yml
conda activate "/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/.conda/path-link-demo-env"
cd "/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo"
npm install
```

## 启动方式

```bash
conda activate "/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/.conda/path-link-demo-env"
cd "/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo"
npm run dev
```

构建检查：

```bash
npm run build
```

## 当前交互

- `Experiment`：选择实验，比如 `exp21`
- `Color file`：只显示当前实验实际存在的数据主题
- `Metric`：`Observed / Estimate / WAPE / Bias`
- `Period`：只保留两种
  - `Total`
  - `By interval`
- 当 `Period = By interval` 时，会显示离散刻度滑键  
  刻度数量和标签直接由 `ratio_bias_wape_analysis` 里的 interval 文件名解析得到
- `Displayed paths`：控制点击 link 后最多显示多少条 path
- `Path opacity`：控制点击 link 后路径高亮的不透明度，默认 `10%`
- `Link path-count filter`：按 path 数量过滤 link
- `Hide unobserved links`：隐藏当前 color file 下没有 observed 覆盖的 link
- `Path-covered links only`：只显示有 path 覆盖的 link
- `Show OD points / Show OD labels`：控制 O/D 点和标签
- `WAPE / Bias`：使用 IQR 四分位距法识别 outlier，并在地图上用黄色 halo 高亮对应 link

## 如果想改参数，去哪里改

颜色映射：

- [/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/data/metrics.ts](/Users/exps/Person%20Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/data/metrics.ts)

切换逻辑说明：

- 修改 `Color file`、`Metric` 或 `Period` 时，demo 会尽量保持另外两个当前选择不变
- 只有当新数据主题下当前选择不存在时，才会退回到该主题下可用的第一个选项

outlier 规则说明：

- `WAPE` 和 `Bias` 都用 IQR 四分位距法确定 outlier
- `Bias` 会识别高侧和低侧 outlier
- `WAPE` 只识别高侧 outlier
- outlier link 会在地图上叠加黄色 halo

主筛选逻辑：

- [/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/App.tsx](/Users/exps/Person%20Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/App.tsx)
- [/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/components/Toolbar.tsx](/Users/exps/Person%20Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/components/Toolbar.tsx)

路径排序与展示：

- [/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/App.tsx](/Users/exps/Person%20Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/App.tsx)
- [/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/components/Sidebar.tsx](/Users/exps/Person%20Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/components/Sidebar.tsx)

地图线宽、偏移、OD 点样式：

- [/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/layers/createLinkLayer.ts](/Users/exps/Person%20Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/layers/createLinkLayer.ts)
- [/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/layers/createHighlightedPathLayer.ts](/Users/exps/Person%20Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/layers/createHighlightedPathLayer.ts)
- [/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/layers/linkOffset.ts](/Users/exps/Person%20Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/layers/linkOffset.ts)
- [/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/layers/createOdPointLayers.ts](/Users/exps/Person%20Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/src/layers/createOdPointLayers.ts)

## Demo 需要哪些输入文件

### 1. 路网和节点

- `input_files_v3/gis/links_ver2.shp`
- `input_files_v3/gis/nodes_ver2.shp`

节点文件要求：

- 必须包含 `node_id`
- 必须包含几何

### 2. Path 基础文件

- `input_files_v3/original_output/path_table.csv`
- `input_files_v3/path_table_buffer`

`path_table.csv` 至少要有：

- `Origin_ID`
- `Destination_ID`
- `path`
- `rank`

其中 `path` 是 node id 序列，例如：

```text
[4000, 2341, 1680, ...]
```

`path_table_buffer`：

- 空格分隔文本
- 每一行对应 `path_table.csv` 中同序的一条 path
- 每列表示一个时间段下该 path 的份额或权重

### 3. 实验结果文件

- `results/<exp>/ratio_bias_wape_analysis/`
- `results/<exp>/link_observation_coverage.csv`

当前不再需要：

- `nodes_ver2__codex_tmp.json`
- `*_link_metrics.csv`
- `epoch_estimates.npz`

## `ratio_bias_wape_analysis` 的文件格式

### 文件名规则

- hourly:
  `{car/truck}_{count/tt}_hour_<hour>.csv`
- 15min:
  `{car/truck}_{count/tt}_15min_<hour>-<quarter>.csv`

示例：

- `car_count_hour_15.csv`
- `truck_count_hour_17.csv`
- `car_tt_15min_15-0.csv`
- `truck_tt_15min_17-3.csv`

这些文件名会被 demo 自动解析成 `By interval` 的离散滑键。

### 每个 interval CSV 的列

至少需要：

- `linkID`
- `OBS`
- `EST`
- `RATIO`
- `BIAS`
- `WAPE`
- `VALID`

可选说明列：

- `INTERVAL_ID`
- `INTERVAL_LABEL`
- `INTERVAL_KIND`

## `link_observation_coverage.csv` 的格式

至少应包含：

- `linkID`
- `car_flow_count`
- `truck_flow_count`
- `car_tt_count`
- `truck_tt_count`
- `flow_count`
- `tt_count`
- `total_count`
- `car_flow_ratio`
- `truck_flow_ratio`
- `car_tt_ratio`
- `truck_tt_ratio`
- `flow_ratio`
- `tt_ratio`
- `total_ratio`

demo 用它来判断：

- 哪些 link 在当前 color file 下属于 observed
- `Hide unobserved links` 应该隐藏哪些 link

## 生成一个新的实验包

主脚本：

- [/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/scripts/experiment_bundle/build_experiment_bundle.py](/Users/exps/Person%20Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/scripts/experiment_bundle/build_experiment_bundle.py)

示例：

```bash
python scripts/experiment_bundle/build_experiment_bundle.py \
  --experiment-id exp21 \
  --experiment-label "Exp 21" \
  --network "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/gis/links_ver2.shp" \
  --nodes "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/gis/nodes_ver2.shp" \
  --path-table-csv "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/original_output/path_table.csv" \
  --path-table-buffer "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/path_table_buffer" \
  --ratio-dir "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/ratio_bias_wape_analysis" \
  --coverage-csv "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/link_observation_coverage.csv"
```

说明：

- `--nodes` 现在直接接 `nodes_ver2.shp`
- 如果不传，脚本会优先自动寻找 `nodes_ver2.shp`
- bundle 脚本不再依赖 `*_link_metrics.csv`

## 鲁棒性说明

当前版本支持：

- 只有 `car`，没有 `truck`
- 只有 `truck`，没有 `car`
- 只有 `count`，没有 `tt`
- 只有 `tt`，没有 `count`

规则是：

- `ratio_bias_wape_analysis` 里实际存在哪个 modality 的 CSV，demo 就只显示哪个
- 缺失的 modality 不会出现在 `Color file` 下拉框里
- `link_observation_coverage.csv` 中缺失 modality 会按 `0` 处理
