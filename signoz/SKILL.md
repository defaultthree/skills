---
name: signoz
description: "生成可直接导入 SigNoz 的 dashboard JSON 文件及说明文档。当用户提到生成 otel 看板、SigNoz 仪表盘、监控面板 JSON、导出指标到 SigNoz、或任何涉及 OpenTelemetry 指标可视化的需求时，都应使用此 skill。"
---

# SigNoz Dashboard 生成器

根据用户描述的 OpenTelemetry 指标，生成可直接导入 SigNoz 的 dashboard JSON 文件和配套说明文档。

## 输出要求

1. **JSON 文件** — 符合 SigNoz v4 dashboard 导入格式，可直接通过 SigNoz UI 导入
2. **说明文档** (.md) — 描述看板包含哪些面板、各面板用途、使用的指标名称
3. **输出目录** — 默认保存到项目的 `docs/otel/` 目录下
4. **面板标题** — 优先使用中文，description 可用英文

## 工作流程

### 1. 收集需求

向用户了解以下信息（如果用户没有主动提供）：

- 服务名称（用于文件命名和 dashboard 标题）
- 需要监控的指标名称及类型（Counter / Gauge / Histogram）
- 需要按哪些 label/attribute 过滤或分组
- 面板的分组方式（按"请求指标"、"延迟指标"、"系统指标"等分区）

如果用户直接给出了代码中的 OTel 埋点代码，从代码中提取指标信息，不需要反复询问。

### 2. 生成 JSON

使用 `reference/template.json` 作为完整骨架（已包含全部 7 种官方面板类型 + row 分区），按需裁剪。
深入字段语义请查 `reference/panel-types.md`（每种面板都有可粘贴的 JSON 示例）。

**文件命名**：`{service}-dashboard.json`

**铁律 7 条**（错任意一条会导致导入失败或图表空白 / not_found）：

1. **顶层用 `title` 字段**（**不是** `name`），所有官方模板都是 `title`
2. **`version` 写 `"v4"`**（v5 也合法，但兼容范围窄；本 skill 默认产出 v4）
3. **每个 widget 的 `id` 必须唯一**，layout 里 `i` 字段必须与之对应
4. **`aggregateAttribute.id` 格式**：`{key}--{dataType}--{type}--{isColumn}`，例：`http_requests_total--float64--Sum--true`
5. **filter `key.id` 格式**：`{key}--{dataType}--tag--false`
6. **每个 query 都要带 `clickhouse_sql` 和 `promql` 空占位**，否则导入解析失败
7. **OTel Histogram 必须用 `.bucket` 后缀**作为 `key` 和 `id` 中的指标名（见下方 Histogram 三铁律）。**这是最容易遗漏、最常导致 "could not find the metric" 的错误**

### 3. 生成说明文档

**文件命名**：`{service}-dashboard.md`

```markdown
# {服务名} SigNoz 监控看板

## 概览
简要描述看板用途和覆盖范围。

## 面板列表

### {分区名称}
| 面板 | 类型 | 指标 | 说明 |
|------|------|------|------|
| 面板中文标题 | graph/value/... | metric_name | 用途描述 |

## 导入方式
1. 打开 SigNoz → Dashboards → + New Dashboard
2. 点击 "Import JSON"
3. 上传或粘贴生成的 JSON 文件

## 使用的指标清单
列出所有指标名称、类型、单位。
```

## 全局约束（来自 [signoz.io/docs/userguide/manage-panels](https://signoz.io/docs/userguide/manage-panels/)）

适用于所有面板类型，违反会导入失败或行为异常：

- **每个面板最多 10 个查询 + formula 组合**（含 query A/B/C... 与 queryFormulas 之和）
- 三种查询模式：`builder`（默认）、`clickhouse_sql`、`promql`，各自一份占位即使不用也要带（**铁律 #6**）
- **functions 数组**支持的数学变换：`exp`、`log`、`sqrt`、`sin`、`cos`、`abs`、`ceil`、`floor`、`cumSum`、`runningDiff`、`timeShift` 等。为空时写 `"functions": []`，不能省字段。
- 修改 function/formula 后 SigNoz UI 必须按 **Stage & Run Query**；导入式 dashboard 不需要这步，但说明导出的 JSON 必然带最终态。
- 每个 widget 的 `dataSource` 三选一：`metrics` / `logs` / `traces`。**`list` 面板仅支持 `logs` / `traces`**，写 `metrics` 会被 SigNoz 拒掉。

### functions 数组示例

```json
"functions": [
  {"name": "log", "args": []},
  {"name": "timeShift", "args": [{"name": "shift", "value": "-1d"}]}
]
```

常用：`log` 平滑大跨度数据、`cumSum` 累计求和、`timeShift` 同比环比、`runningDiff` 看相邻点变化。

## 面板类型速查（7 种官方 + row）

⚠️ **命名陷阱**：SigNoz docs 把时序图叫 "Timeseries"，但 JSON 字段必须写 `"graph"`。100% 官方模板（apm-metrics、hostmetrics 等）都是 `graph`。

| docs 名 | JSON `panelTypes` | 数据源 | 适用场景 | 关键字段 |
|---------|------------------|--------|---------|----------|
| Timeseries | **`graph`** ⚠️ | M/L/T | 指标随时间变化的趋势 | `isStacked` / `fillSpans` / `softMin/Max` / `thresholds`（横线形态） / `nullZeroValues`（fill gaps）|
| Value | `value` | M/L/T | 单个聚合数 + 阈值染色 | `reduceTo` (avg/sum/max/min/latest) / `thresholds`（染色形态） |
| Table | `table` | M/L/T | 多维聚合明细 | 必须 `groupBy` / `columnUnits`（官方文档化）/ `columnWidths`、`orderBy`（schema 支持）|
| Pie | `pie` | M/L/T | 维度占比 | **必须 `groupBy`** / `legendPosition` / `limit` (建议 6-12) |
| Bar | `bar` | M/L/T | 离散类别对比，**默认堆叠** | `isStacked` / `stackedBarChart` / 推荐 `groupBy` / `limit` (建议 12-20) |
| List | `list` | **L/T only** | logs/traces 原始行列表（含 infinite scroll + search）| **仅 logs/traces**，需 `selectColumns` / `pageSize` / `orderBy` |
| Histogram | `histogram` | M/L/T | 任意数值的频率分布（看分布形状/偏度）| `bucketCount`(默认30) / `bucketWidth`(0=auto) / `mergeAllActiveQueries` |
| — | `row` | — | UI 分区折叠标题 | 无；建议同步加 `panelMap` |

数据源缩写：M=metrics, L=logs, T=traces。**`list` 是唯一不接 metrics 的面板**。

⚠️ 区分两个 "histogram"：
- **`panelTypes: "histogram"`** = 把任意时序数据按值范围分桶绘频率分布（官方 99 个模板里**未被使用**，常被 `graph + 百分位` 替代）
- **`aggregateAttribute.type: "Histogram"`** = OTel SDK 的 Histogram 指标，应配合 `panelTypes: "graph"` + `spaceAggregation: "p99"` 使用

## OTel 指标 → 聚合字段映射

| OTel 类型 | `aggregateAttribute.type` | `key` 后缀 | `aggregateOperator` | `timeAggregation` | `spaceAggregation` |
|----------|--------------------------|-----------|--------------------|-------------------|---------------------|
| Counter | `Sum` | （无） | `rate` / `increase` / `sum` | `rate` / `increase` / `latest` | `sum` |
| **UpDownCounter** | `Sum` ⚠️ | （无） | `avg` / `sum` / `latest` | **`latest`**（gauge 语义，**勿用 `rate`**） | `sum` / `avg` |
| Gauge / ObservableGauge | `Gauge` | （无） | `avg` / `latest` / `max` / `min` | `avg` / `latest` | `avg` / `sum` |
| Histogram (count 形式) | `Histogram` | `.bucket` | **`count`** | **`rate`** | **`p50` / `p90` / `p99`** |
| Histogram (increase 形式) | `Histogram` | `.bucket` | **`increase`** | **`""`** | **`p50` / `p90` / `p99`** |

⚠️ **UpDownCounter 陷阱**：OTel SDK 把 UpDownCounter 上报为 `Sum` 类型（IsMonotonic=false），看起来和 Counter 一样，但**语义是当前并发数 / 队列长度**这种可正可负的瞬时值。
对 UpDownCounter 用 `timeAggregation: rate` 会得到一段时间内的"净变化率"，几乎肯定不是你想看的；要看当前值用 `timeAggregation: latest`。典型例子：bulkhead/semaphore/connection-pool 的 `active` 计数。

⚠️ **Histogram 三铁律**（写错会报 `not_found: could not find the metric <name>` 或图表空白）：
1. **`aggregateAttribute.key` 必须以 `.bucket` 结尾**（例：`request_duration_ms.bucket`），`id` 同步。**SigNoz 接收 OTel Histogram 后会拆成 5 列存储**：`<name>.bucket` / `.count` / `.sum` / `.max` / `.min` —— **裸名 `<name>` 在 ClickHouse 里不存在**，查询会直接 not_found
2. `aggregateOperator` 必须是 `count` 或 `increase`，**不能写 `p50`/`p99`**
3. 百分位写在 **`spaceAggregation`**，不是 `timeAggregation`

apm-metrics、key-operations 用 count+rate；jvm、argocd 用 increase+""，两种都 OK。

✅ 正确：
```json
"aggregateAttribute": {"key":"request_duration_ms.bucket","id":"request_duration_ms.bucket--float64--Histogram--true",...}
```
❌ 错误（最常见，导入后报 not_found）：
```json
"aggregateAttribute": {"key":"request_duration_ms","id":"request_duration_ms--float64--Histogram--true",...}
```

## 顶层 dashboard 必备字段

```json
{
  "title": "看板标题",
  "description": "...",
  "tags": [],
  "version": "v4",
  "uploadedGrafana": false,
  "layout": [{"h":3,"i":"widget-1","w":3,"x":0,"y":0,"minH":1,"minW":1,"moved":false,"static":false}, ...],
  "panelMap": {},
  "variables": {},
  "widgets": [...]
}
```

`uuid` / `image` 服务端会自动生成，可省。`panelMap` 仅在使用 `row` 时才需要（让分区可折叠）。

## Y 轴单位（yAxisUnit）

| 类别 | 值 |
|------|-----|
| 通用 | `none`、`short`、`percent`、`percentunit` |
| 时间 | `s`、`ms`、`us`、`ns` |
| 字节 | `bytes`、`decbytes`、`kbytes`、`mbytes` |
| 速率 | `reqps`、`ops`、`Bps`、`pps` |
| 货币 | `currencyUSD`、`currencyEUR`、`currencyCNY` |

## 布局规则

`layout` 网格：`w` 1-12 满宽 12，`h` 行数（数值卡片 3、图表 6、row 1），`x` 水平 0-11，`y` 垂直从 0 起。

推荐：
- 数值卡片一行 3-4 个（w=3 或 w=4）
- 时序图一行 1-2 个（w=12 或 w=6）
- 分区 row：`h=1, w=12, x=0`

## Variables（看板变量，4 种类型）

| 类型 | 用法 | 关键字段 |
|------|------|----------|
| `DYNAMIC` | 自动从某属性取候选值（**最常用，无需写 SQL**） | `dynamicVariablesAttribute`、`dynamicVariablesSource` |
| `QUERY` | 用 ClickHouse SQL 查值 | `queryValue`（SQL 字符串） |
| `CUSTOM` | 预定义值列表 | `customValue`（"a, b, c"） |
| `TEXTBOX` | 用户自由输入 | `textboxValue`（默认值） |

引用语法（v4 query builder）：filter 的 `value: ["{{.var_name}}"]`。详细示例见 `reference/panel-types.md`。

## 示例：最常见的 4 种面板（速粘版）

### Counter 速率（graph）
```json
{
  "id": "request-rate", "panelTypes": "graph", "title": "请求速率",
  "yAxisUnit": "reqps", "fillSpans": false, "isStacked": false,
  "nullZeroValues": "zero", "opacity": "1", "softMin": 0, "softMax": 0,
  "thresholds": [], "timePreferance": "GLOBAL_TIME",
  "query": {
    "builder": {
      "queryData": [{
        "aggregateAttribute": {"dataType":"float64","id":"http_requests_total--float64--Sum--true","isColumn":true,"key":"http_requests_total","type":"Sum"},
        "aggregateOperator":"rate","dataSource":"metrics","disabled":false,"expression":"A",
        "filters":{"items":[],"op":"AND"},"functions":[],
        "groupBy":[{"dataType":"string","id":"status--string--tag--false","isColumn":false,"key":"status","type":"tag"}],
        "having":[],"legend":"{{status}}","limit":null,"orderBy":[],"queryName":"A",
        "reduceTo":"avg","spaceAggregation":"sum","stepInterval":60,"timeAggregation":"rate"
      }],"queryFormulas":[]
    },
    "clickhouse_sql":[{"disabled":false,"legend":"","name":"A","query":""}],
    "promql":[{"disabled":false,"legend":"","name":"A","query":""}],
    "queryType":"builder"
  }
}
```

### OTel Histogram 百分位（graph + bucket）
```json
{
  "id":"latency-p99","panelTypes":"graph","title":"延迟 P50/P90/P99","yAxisUnit":"ms",
  "fillSpans":false,"isStacked":false,"nullZeroValues":"zero","opacity":"1","softMin":0,"softMax":0,
  "thresholds":[],"timePreferance":"GLOBAL_TIME",
  "query":{"builder":{"queryData":[
    {"aggregateAttribute":{"dataType":"float64","id":"request_duration_ms.bucket--float64--Histogram--true","isColumn":true,"key":"request_duration_ms.bucket","type":"Histogram"},"aggregateOperator":"count","dataSource":"metrics","disabled":false,"expression":"A","filters":{"items":[],"op":"AND"},"functions":[],"groupBy":[],"having":[],"legend":"P50","limit":null,"orderBy":[],"queryName":"A","reduceTo":"avg","spaceAggregation":"p50","stepInterval":60,"timeAggregation":"rate"},
    {"aggregateAttribute":{"dataType":"float64","id":"request_duration_ms.bucket--float64--Histogram--true","isColumn":true,"key":"request_duration_ms.bucket","type":"Histogram"},"aggregateOperator":"count","dataSource":"metrics","disabled":false,"expression":"B","filters":{"items":[],"op":"AND"},"functions":[],"groupBy":[],"having":[],"legend":"P90","limit":null,"orderBy":[],"queryName":"B","reduceTo":"avg","spaceAggregation":"p90","stepInterval":60,"timeAggregation":"rate"},
    {"aggregateAttribute":{"dataType":"float64","id":"request_duration_ms.bucket--float64--Histogram--true","isColumn":true,"key":"request_duration_ms.bucket","type":"Histogram"},"aggregateOperator":"count","dataSource":"metrics","disabled":false,"expression":"C","filters":{"items":[],"op":"AND"},"functions":[],"groupBy":[],"having":[],"legend":"P99","limit":null,"orderBy":[],"queryName":"C","reduceTo":"avg","spaceAggregation":"p99","stepInterval":60,"timeAggregation":"rate"}
  ],"queryFormulas":[]},"clickhouse_sql":[{"disabled":false,"legend":"","name":"A","query":""}],"promql":[{"disabled":false,"legend":"","name":"A","query":""}],"queryType":"builder"}
}
```

### 数值卡片（value）
```json
{
  "id":"current-value","panelTypes":"value","title":"当前值","yAxisUnit":"none",
  "isStacked":false,"nullZeroValues":"zero","opacity":"1","timePreferance":"GLOBAL_TIME",
  "thresholds":[{"index":"t1","isEditEnabled":false,"keyIndex":0,"selectedGraph":"value","thresholdColor":"Red","thresholdFormat":"Text","thresholdLabel":"High","thresholdOperator":">","thresholdTableOptions":"A","thresholdUnit":"none","thresholdValue":100}],
  "query":{"builder":{"queryData":[{"aggregateAttribute":{"dataType":"float64","id":"some_metric--float64--Gauge--true","isColumn":true,"key":"some_metric","type":"Gauge"},"aggregateOperator":"avg","dataSource":"metrics","disabled":false,"expression":"A","filters":{"items":[],"op":"AND"},"functions":[],"groupBy":[],"having":[],"legend":"","limit":null,"orderBy":[],"queryName":"A","reduceTo":"latest","spaceAggregation":"avg","stepInterval":60,"timeAggregation":"latest"}],"queryFormulas":[]},"clickhouse_sql":[{"disabled":false,"legend":"","name":"A","query":""}],"promql":[{"disabled":false,"legend":"","name":"A","query":""}],"queryType":"builder"}
}
```

### 分区行（row + panelMap）

widget 本身极简：
```json
{"id":"row-system","panelTypes":"row","title":"系统指标","query":{}}
```

顶层同时加 `panelMap`，让 row 真正可折叠并归集子 widget：
```json
{
  "panelMap": {
    "row-system": {
      "collapsed": false,
      "widgets": [
        {"h":6,"i":"cpu-graph","moved":false,"static":false,"w":6,"x":0,"y":1},
        {"h":6,"i":"mem-graph","moved":false,"static":false,"w":6,"x":6,"y":1}
      ]
    }
  }
}
```

## 拓展面板（pie / bar / list / table）

完整 JSON 模板请查 `reference/template.json` 或 `reference/panel-types.md`：
- **table**：必须 `groupBy`，按维度聚合后表格化，可调 `columnUnits`/`columnWidths`
- **pie**：必须 `groupBy`，按维度切片占比；`legendPosition: "bottom"` 是常用样式
- **bar**：类似 graph 但渲染为柱状，开 `isStacked: true` + `stackedBarChart: true` 做堆叠
- **list**：`dataSource: "logs"` 或 `"traces"`，要写 `selectColumns[]` 指定显示哪些列、`pageSize`、`orderBy`

⚠️ **pie / bar 必须给 `limit`**：当 groupBy 维度基数高（比如按 `domain` / `feature_key` / `route` 分组）时，所有 series 都会渲染，超过 ~12 切片人眼就读不出。约定：pie 给 `limit: 6-12`，bar 给 `limit: 12-20`，graph 默认 `null`（堆叠时同样建议封顶）。

## Filter `op` 字段速查

`filters.items[].op` 不止 `=`。常用：

| op | 用途 | value 形态 |
|----|------|-----------|
| `=` / `!=` | 精确匹配 | `"foo"` |
| `<` / `<=` / `>` / `>=` | 数值/字典序比较（status_code、duration） | `"500"` |
| `in` / `nin` | 集合（多选过滤） | `["a", "b", "c"]` ⚠️ 数组 |
| `like` / `nlike` | 通配符（`%` 占位） | `"%error%"` |
| `regex` / `nregex` | 正则 | `"^/api/"` |
| `exists` / `nexists` | 该 attribute 是否存在 | （无 value） |

注意：`in` 的 `value` 必须是数组；其他 op 的 `value` 是字符串/数字。错把 `in` 写成单值会被 SigNoz 安静地降级为 `=`。

## 阈值（thresholds）形态差异

graph 横线：
```json
"thresholds": [{"color": "#EF4444", "label": "Alert", "value": 100, "isEditEnabled": false}]
```

value 染色（**字段完全不同**）：
```json
"thresholds": [{"index":"...","keyIndex":0,"selectedGraph":"value","thresholdColor":"Red","thresholdFormat":"Text","thresholdLabel":"...","thresholdOperator":">","thresholdTableOptions":"A","thresholdUnit":"none","thresholdValue":100,"isEditEnabled":false}]
```

## 排错：导入后报 not_found / 面板空白

按概率排序（先查最常见的）：

### A. Histogram 没加 `.bucket` 后缀（90% 的情况）

错误信息形态：`could not find the metric <name>`（`<name>` 是 OTel 上报的原始名）。

修法：把 `key` 和 `id` 中的指标名都加 `.bucket`。详见上方 "Histogram 三铁律"。如果 dashboard 已经写错且面板很多，可用脚本批改：

```bash
python3 <<'EOF'
import json
HISTS = ["request_duration_ms", "rpc_duration_ms", ...]  # 你的 Histogram 列表
HISTS.sort(key=len, reverse=True)  # 长前缀在前防误替换
with open('dashboard.json') as f: c = f.read()
for m in HISTS:
    c = c.replace(f'"key": "{m}"', f'"key": "{m}.bucket"')
    c = c.replace(f'"id": "{m}--float64--Histogram--true"',
                  f'"id": "{m}.bucket--float64--Histogram--true"')
json.loads(c)  # 验证仍合法
open('dashboard.json','w').write(c)
EOF
```

### B. 服务还没产生过该指标

SigNoz 的指标元数据是**首次接收上报后才登记**的。新部署或从未走过的代码路径 → 元数据缺失 → not_found。

判断：接口/cron 实际触发一次后等 1-2 分钟，再刷新看板。看板修复了的话 `tcgprice_service.*` 这种"代码里有但还没流量"的指标会保持空，等流量来了自然出图。

### C. 命名规范化（少见，部分自部署 SigNoz）

某些部署经 prometheus 路径会把 `.` 替换为 `_`。可通过 autocomplete API 验证（见下方诊断 curl）。

### 直接查 SigNoz 验证指标存在性（推荐）

**列出所有以某前缀开头的真实指标名**（v3 autocomplete，无视 schema 版本）：

```bash
curl -s 'https://<HOST>/api/v3/autocomplete/aggregate_attributes?dataSource=metrics&aggregateOperator=count&searchText=<prefix>' \
  -H 'authorization: Bearer <TOKEN>' | jq -r '.data.attributeKeys[].key'
```

返回里 Histogram 会有多个 `.bucket` `.count` `.sum` `.max` `.min` 列；Counter 是裸名。直接看 `.bucket` 是否存在 → 决定 dashboard JSON 应该怎么写。

**直接 dry-run 一个查询**（v5 query_range，验证某条 metric 真能查出值）：

```bash
curl -s 'https://<HOST>/api/v5/query_range' \
  -H 'authorization: Bearer <TOKEN>' -H 'content-type: application/json' \
  --data-raw '{
    "schemaVersion":"v1",
    "start":<START_MS>,"end":<END_MS>,
    "requestType":"scalar",
    "compositeQuery":{"queries":[{"type":"builder_query","spec":{
      "name":"A","signal":"metrics","stepInterval":60,"disabled":false,
      "filter":{"expression":""},"having":{"expression":""},
      "aggregations":[{
        "metricName":"<METRIC>.bucket",
        "timeAggregation":"rate",
        "spaceAggregation":"p99",
        "reduceTo":"latest"
      }]
    }}]},
    "formatOptions":{"formatTableResultForUI":false,"fillGaps":false},
    "variables":{}
  }' | jq -c '.status, .data.data.results[0].data'
```

- 返回 `"error" {"code":"not_found",...}` → metric 不存在（拼错或还没数据）
- 返回 `"success" [[<value>]]` → 存在且能查出值，dashboard 用同名 key 一定能渲染

Token 获取：SigNoz 左下角头像 → API Keys，或浏览器 DevTools 抓任意一个看板请求的 `authorization` header（注意有效期通常很短，仅排错用，不要长期保留）。

## 进阶参考

- 详细字段语义、v4 vs v5 schema、所有 4 种 variables 类型、styling 字段（legendPosition、isLogScale、decimalPrecision、contextLinks 等）：见 `reference/panel-types.md`
- 完整 dashboard 骨架（涵盖 8 类 widget）：见 `reference/template.json`
- 官方真实模板（70+ 个，含 APM/AI/数据库/基础设施）：<https://github.com/SigNoz/dashboards>
- 官方面板类型文档：<https://signoz.io/docs/dashboards/panel-types/>
- 官方模板列表：<https://signoz.io/docs/dashboards/dashboard-templates/overview/>
