# Path-Link Visualization Demo

## 项目原理

这个 demo 的核心目标是把“链路表现”和“经过该链路的路径集合”放到同一个交互界面里看。

整体逻辑分三层：

1. 网络层  
   以 `links_ver2` 为底图，每条 link 都带有多组可着色属性，例如 `observed / estimate / wape / bias`。

2. 路径层  
   每条 path 先从 `path_table.csv` 的 node 序列转换为 link 序列，再建立：
   - `link -> paths`
   - `path -> link_sequence`
   - `link -> contribution records`

3. 实验层  
   每次实验结果打成一个独立 bundle，放在 `public/data/experiments/<exp_id>/`。  
   前端先选 `Experiment`，再选 `Color file / Metric / Period`，因此后续新增 `exp22 / exp23` 时不需要改前端结构。

## 目录结构

```text
path-link-visualization-demo/
  public/data/experiments/       # 每个实验的静态可视化数据包
  records/                       # 审计记录、说明文档
  scripts/
    experiment_bundle/           # 把实验结果打包成 demo 可读格式
  src/
    components/                  # Toolbar、Sidebar、Legend 等界面组件
    layers/                      # deck.gl 图层
    data/                        # 数据加载与颜色计算
    store/                       # zustand 状态
```

## 运行方式

先激活本项目环境：

```bash
conda activate "/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo/.conda/path-link-demo-env"
cd "/Users/exps/Person Materials/Phd-CMU-CEE/2-Research-Materials/Server_code/path-link-visualization-demo"
```

启动前端：

```bash
npm run dev
```

如果要重新构建 `exp21`：

```bash
python scripts/experiment_bundle/build_experiment_bundle.py \
  --experiment-id exp21 \
  --experiment-label "Exp 21" \
  --network "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/gis/links_ver2.shp" \
  --path-table-csv "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/original_output/path_table.csv" \
  --path-table-buffer "../Pittsburgh_Network/Pittsburgh_DODE/input_files_v3/original_output/path_table_buffer" \
  --ratio-dir "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/ratio_bias_wape_analysis" \
  --coverage-csv "../Pittsburgh_Network/Pittsburgh_DODE/results/exp21/link_observation_coverage.csv"
```

## 前端交互说明

- `Color file`：选择数据主题，例如 `car_count / car_tt / truck_count / truck_tt`
- `Metric`：选择 `Observed / Estimate / WAPE / Bias`
- `Period`：选择总时段或小时级结果
- `Displayed paths`：控制当前点击 link 后最多显示多少条 path
- `Path-covered links only`：只显示有 path 覆盖的 link
- `Hide unobserved links`：按当前视图的有效 mask 过滤无值 link
- `Show OD points`：显示所有 O/D 点，用黑点和编号标注

## 如果要修改颜色设置，改哪里

### 1. 颜色数值映射

文件：
- `src/data/metrics.ts`

这里控制：
- `bias` 的蓝-白-红映射
- `wape / observed / estimate` 的白-红映射
- outlier clipping 的计算方式

如果你想：
- 改红色更深/更浅：改 `getColorForValue()`
- 改 outlier 阈值：改 `computeFieldStats()` 里 IQR 裁剪逻辑

### 2. 图例颜色条

文件：
- `src/components/Legend.tsx`

现在图例直接复用 `getColorForValue()`。  
如果以后颜色改了，图例通常不用单独改；除非你想改图例标签格式或显示方式。

## 如果要修改 path 展示逻辑，改哪里

文件：
- `src/App.tsx`
- `src/components/PathList.tsx`

当前逻辑：
- 先按 `contribution` 从大到小排序
- 如果贡献相同，优先展示 OD 对不同的 path
- 再由 `Displayed paths` 滑条决定展示多少条

如果你想：
- 改默认展示条数：改 `src/store/useAppStore.ts` 里的 `maxHighlightedPaths`
- 改最大展示上限：改 `src/components/Toolbar.tsx` 里滑条的 `max`
- 改 path 排序策略：改 `src/App.tsx` 里的 `rankContributions()`

## 如果要修改链路宽度、偏移和图层样式，改哪里

文件：
- `src/layers/createLinkLayer.ts`
- `src/layers/createSelectedLinkLayer.ts`
- `src/layers/createHighlightedPathLayer.ts`
- `src/layers/createOdPointLayers.ts`

常见修改：
- 改普通 link 线宽：`createLinkLayer.ts`
- 改选中 link 样式：`createSelectedLinkLayer.ts`
- 改 path 高亮粗细/颜色：`createHighlightedPathLayer.ts`
- 改 O/D 点大小、文字大小：`createOdPointLayers.ts`

## 如果要给新实验生成可视化数据，怎么做

主脚本：
- `scripts/experiment_bundle/build_experiment_bundle.py`

它会自动生成：
- 网络 GeoJSON
- links index
- path summary
- link to paths
- contribution bucket files
- color file 定义
- OD points GeoJSON

只要你的实验结果目录里有：
- `ratio_bias_wape_analysis/*_link_metrics.csv`
- `ratio_bias_wape_analysis/*_hour_*.csv`
- `link_observation_coverage.csv`

就可以按相同方式生成 `exp22 / exp23`。

## 数据口径提醒

1. `Origin_ID / Destination_ID` 是 OD 点编号，不一定等于网络 node id。  
   demo 里：
   - 地图上 O/D 点旁边显示的是 OD 点编号
   - sidebar 的 OD 汇总表显示的是对应的 `origin_node_id / destination_node_id`

2. `Hide unobserved links` 现在优先按当前视图的 `valid mask` 过滤，  
   所以它隐藏的是“当前 metric + 当前 period 下无有效值”的 link。

3. path 高亮显示的是“当前 link 对应的 path 集合中的前 N 条”，  
   不是把所有 path 一次性全部画出来。
