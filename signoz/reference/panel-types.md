# SigNoz 面板类型完全参考

本文件覆盖 SigNoz 官方文档列出的全部 7 种面板类型 + `row` 分区行，以及它们的实际 JSON 形态（来自 `github.com/SigNoz/dashboards` 真实模板）。

## 命名陷阱：docs 名 vs JSON 值

| 官方文档名 | 文档 URL | **JSON 中的 `panelTypes` 值** |
|-----------|---------|-----------------------------|
| Timeseries | `/panel-types/timeseries/` | `"graph"` ⚠️ |
| Value | `/panel-types/value/` | `"value"` |
| Table | `/panel-types/table/` | `"table"` |
| Pie | `/panel-types/pie/` | `"pie"` |
| Bar | `/panel-types/bar/` | `"bar"` |
| List | `/panel-types/list/` | `"list"` |
| Histogram | `/panel-types/histogram/` | `"histogram"` |
| (Row 分区行) | — | `"row"` |

⚠️ 文档说 "Timeseries" 但 JSON 字段固定写 `"graph"`。这是 SigNoz 历史遗留命名，所有官方模板（apm-metrics、hostmetrics、key-operations 等）至今都用 `graph`。

## 两套查询 schema：v4 vs v5

SigNoz 仍同时支持两套查询结构，看板 `version` 字段决定使用哪一套：

### v4（应用最广，apm/hostmetrics/jvm 等仍是 v4）

```json
{
  "aggregateAttribute": {
    "dataType": "float64",
    "id": "metric--float64--Sum--true",
    "isColumn": true,
    "key": "metric",
    "type": "Sum"
  },
  "aggregateOperator": "rate",
  "filters": {"items": [...], "op": "AND"},
  "having": [],
  "reduceTo": "avg",
  "spaceAggregation": "sum",
  "timeAggregation": "rate",
  "stepInterval": 60
}
```

### v5（新模板偏多，claude-code、groq、anthropic 等是 v5）

```json
{
  "aggregations": [{
    "metricName": "claude_code.token.usage",
    "reduceTo": "sum",
    "spaceAggregation": "sum",
    "temporality": null,
    "timeAggregation": "sum"
  }],
  "filter": {"expression": "service.name in $service_name AND has_error = false"},
  "having": {"expression": ""},
  "stepInterval": 60
}
```

**生成新看板时建议沿用 v4** —— 兼容范围更广，且和最常被复用的 APM/jvm/hostmetrics 模板同源。本 skill 默认产出 v4 格式。

## 面板类型 × 数据源支持矩阵（来自官方文档）

| 面板 | metrics | logs | traces | 官方文档化的配置项 |
|------|---------|------|--------|--------------------|
| `graph` | ✅ | ✅ | ✅ | Fill Gaps、Y-axis Unit、Soft Min/Max、Thresholds |
| `value` | ✅ | ✅ | ✅ | Reduce (avg/sum/max/min/latest)、Unit、Threshold-based coloring |
| `table` | ✅ | ✅ | ✅ | Column Units（其他选项 schema 支持但官方未文档化）|
| `pie` | ✅ | ✅ | ✅ | "doesn't support any configuration"（官方原话）|
| `bar` | ✅ | ✅ | ✅ | Y-axis Unit、Soft Min/Max、Thresholds、Stack Series 切换 |
| `list` | ❌ | ✅ | ✅ | "doesn't support any configuration" + 内置 Infinite scroll & Search |
| `histogram` | ✅ | ✅ | ✅ | Number of Buckets (默认 30)、Bucket Width (auto)、Merge All Series Into One |

⚠️ **`list` 是唯一不支持 metrics 的面板**——其他 6 种都接 metrics / logs / traces 三选一。

## 7 种面板类型 + Row

### 1. `graph` — 时序图（Timeseries）

最常用面板，覆盖 Counter / Gauge 速率与百分位。

**适用**：所有"指标随时间变化"场景。
**关键字段**：`isStacked`、`fillSpans`、`opacity`、`softMin/softMax`、`thresholds`、`yAxisUnit`、`isLogScale`、`legendPosition`。

**官方文档要点**（[panel-types/timeseries](https://signoz.io/docs/dashboards/panel-types/timeseries/)）：
- 数据源：logs / traces / metrics 三选一
- **Fill Gaps**（→ JSON `nullZeroValues: "zero"`）：把缺失的采样点补 0；典型：`{t1:12, t3:21}` → `{t1:12, t2:0, t3:21, t4:0}`
- **Soft Min/Max**（→ `softMin` / `softMax`）：默认 0/0 = 自动；显式设值能防止小波动被夸张拉伸（"prevent small values from being magnified too much"）
- **Thresholds**：值-颜色对，画水平参考线（颜色可选，省略则用系统默认）
- 标准用例：内存随时间变化、QPS 随时间变化等

```json
{
  "id": "request-rate",
  "panelTypes": "graph",
  "title": "请求速率",
  "description": "HTTP request rate per second",
  "fillSpans": false,
  "isStacked": false,
  "nullZeroValues": "zero",
  "opacity": "1",
  "softMin": 0,
  "softMax": 0,
  "thresholds": [],
  "timePreferance": "GLOBAL_TIME",
  "yAxisUnit": "reqps",
  "query": {
    "builder": {
      "queryData": [{
        "aggregateAttribute": {"dataType": "float64", "id": "http_requests_total--float64--Sum--true", "isColumn": true, "isJSON": false, "key": "http_requests_total", "type": "Sum"},
        "aggregateOperator": "rate",
        "dataSource": "metrics",
        "disabled": false,
        "expression": "A",
        "filters": {"items": [], "op": "AND"},
        "functions": [],
        "groupBy": [{"dataType": "string", "id": "status--string--tag--false", "isColumn": false, "key": "status", "type": "tag"}],
        "having": [],
        "legend": "{{status}}",
        "limit": null,
        "orderBy": [],
        "queryName": "A",
        "reduceTo": "avg",
        "spaceAggregation": "sum",
        "stepInterval": 60,
        "timeAggregation": "rate"
      }],
      "queryFormulas": []
    },
    "clickhouse_sql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "promql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "queryType": "builder"
  }
}
```

### 2. `value` — 数值卡片

显示单个聚合值，支持基于阈值染色。

**关键字段**：`reduceTo` (`avg`/`sum`/`max`/`min`/`latest`/`last`)、`thresholds` (value 形态)、`yAxisUnit`。

**官方文档要点**（[panel-types/value](https://signoz.io/docs/dashboards/panel-types/value/)）：
- 数据源：logs / traces / metrics 三选一
- **必须聚合到单值**：通过 `reduceTo` 把时序压成单值；官方明示的 5 个选项是 `avg`/`sum`/`max`/`min`/`latest`（real templates 里也见过 `last`，行为=`latest`）
- 例："applying `avg` to request rates across a time period yields the mean rate during that duration"
- **Threshold-Based Coloring**：值-颜色对，按数值染色卡片（颜色可选，省略走默认）
- 用例：单一总览数（活跃服务数、SLO 当前值、缓存命中率）

```json
{
  "id": "current-cache-size",
  "panelTypes": "value",
  "title": "Memcache Server (Current Size)",
  "description": "",
  "isStacked": false,
  "nullZeroValues": "zero",
  "opacity": "1",
  "thresholds": [],
  "timePreferance": "GLOBAL_TIME",
  "yAxisUnit": "decbytes",
  "query": {
    "builder": {
      "queryData": [{
        "aggregateAttribute": {"dataType": "float64", "id": "memcached.bytes--float64----true", "isColumn": true, "isJSON": false, "key": "memcached.bytes", "type": ""},
        "aggregateOperator": "avg",
        "dataSource": "metrics",
        "disabled": false,
        "expression": "A",
        "filters": {"items": [], "op": "AND"},
        "groupBy": [],
        "having": [],
        "legend": "",
        "limit": null,
        "orderBy": [],
        "queryName": "A",
        "reduceTo": "last",
        "spaceAggregation": "sum",
        "stepInterval": 60,
        "timeAggregation": "avg"
      }],
      "queryFormulas": []
    },
    "clickhouse_sql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "promql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "queryType": "builder"
  }
}
```

**Value 面板 thresholds 形态**（与 graph 不同）：

```json
"thresholds": [
  {
    "index": "uuid-here",
    "isEditEnabled": false,
    "keyIndex": 0,
    "selectedGraph": "value",
    "thresholdColor": "Red",
    "thresholdFormat": "Text",
    "thresholdLabel": "Critical",
    "thresholdOperator": ">",
    "thresholdTableOptions": "A",
    "thresholdUnit": "percentunit",
    "thresholdValue": 10
  }
]
```

### 3. `table` — 表格

按 `groupBy` 维度聚合后以表格展示，可调整列宽和单位。

**关键字段**：`groupBy[]`（必须）、`columnUnits` (列名→单位)、`columnWidths` (列名→像素宽度)、`decimalPrecision`。

**官方文档要点**（[panel-types/table](https://signoz.io/docs/dashboards/panel-types/table/)）：
- 数据源：logs / traces / metrics 三选一
- 官方明确文档化的配置仅 **Column Units**（→ JSON `columnUnits`），用于把列值格式化为人类可读
- `groupBy` / `orderBy` / `columnWidths` / `decimalPrecision` 官方文档未列，但在所有真实模板里都被广泛使用，导入会正确生效
- 用例：每个 service 的平均 req/s（service.name × method × status_code 多维度交叉看明细）

```json
{
  "id": "services-table",
  "panelTypes": "table",
  "title": "服务请求计数",
  "description": "",
  "columnUnits": {"A": "short"},
  "columnWidths": {"A": 145, "service.name": 200, "status_code": 120},
  "decimalPrecision": 2,
  "fillSpans": false,
  "isStacked": false,
  "legendPosition": "bottom",
  "nullZeroValues": "zero",
  "opacity": "1",
  "thresholds": [],
  "timePreferance": "GLOBAL_TIME",
  "yAxisUnit": "none",
  "query": {
    "builder": {
      "queryData": [{
        "aggregateAttribute": {"dataType": "float64", "id": "http_requests_total--float64--Sum--true", "isColumn": true, "key": "http_requests_total", "type": "Sum"},
        "aggregateOperator": "sum",
        "dataSource": "metrics",
        "expression": "A",
        "filters": {"items": [], "op": "AND"},
        "groupBy": [
          {"dataType": "string", "id": "service_name--string--tag--false", "isColumn": false, "key": "service_name", "type": "tag"},
          {"dataType": "string", "id": "status_code--string--tag--false", "isColumn": false, "key": "status_code", "type": "tag"}
        ],
        "having": [],
        "legend": "",
        "limit": null,
        "orderBy": [{"columnName": "A", "order": "desc"}],
        "queryName": "A",
        "reduceTo": "sum",
        "spaceAggregation": "sum",
        "stepInterval": 60,
        "timeAggregation": "rate"
      }],
      "queryFormulas": []
    },
    "clickhouse_sql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "promql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "queryType": "builder"
  }
}
```

### 4. `pie` — 饼图

按维度展示占比。**必须设置 `groupBy`**，否则没有切片可绘。

**关键字段**：`groupBy[]`（必须）、`legendPosition`、`decimalPrecision`、`customLegendColors`。

**官方文档要点**（[panel-types/pie](https://signoz.io/docs/dashboards/panel-types/pie/)）：
- 数据源：logs / traces / metrics 三选一
- 用途："display the proportion of a single or a few different categories"
- 官方原话：**"This panel type doesn't support any configuration"** —— 没有配置选项被官方文档化
- 但真实模板里 `legendPosition` / `decimalPrecision` / `customLegendColors` 都生效，是 schema 已支持但文档未跟上
- 用例：服务请求量在多个 service 间的分布
- 实践建议：高基数 groupBy（domain / feature_key）必须给 `limit: 6-12`，否则切片数超出可读阈值

```json
{
  "id": "errors-by-service",
  "panelTypes": "pie",
  "title": "按服务错误分布",
  "description": "",
  "decimalPrecision": 2,
  "legendPosition": "bottom",
  "customLegendColors": {},
  "isStacked": false,
  "nullZeroValues": "zero",
  "opacity": "1",
  "thresholds": [],
  "timePreferance": "GLOBAL_TIME",
  "yAxisUnit": "none",
  "query": {
    "builder": {
      "queryData": [{
        "aggregateAttribute": {"dataType": "float64", "id": "http_errors_total--float64--Sum--true", "isColumn": true, "key": "http_errors_total", "type": "Sum"},
        "aggregateOperator": "sum",
        "dataSource": "metrics",
        "expression": "A",
        "filters": {"items": [], "op": "AND"},
        "groupBy": [
          {"dataType": "string", "id": "service_name--string--tag--false", "isColumn": false, "key": "service_name", "type": "tag"}
        ],
        "having": [],
        "legend": "{{service_name}}",
        "limit": null,
        "orderBy": [],
        "queryName": "A",
        "reduceTo": "sum",
        "spaceAggregation": "sum",
        "stepInterval": 60,
        "timeAggregation": "rate"
      }],
      "queryFormulas": []
    },
    "clickhouse_sql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "promql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "queryType": "builder"
  }
}
```

### 5. `bar` — 柱状图

适合离散类别对比。可堆叠（`isStacked`）或并排。`stackedBarChart` 控制堆叠模式。

**关键字段**：`groupBy[]`（必须）、`isStacked`、`stackedBarChart`、`yAxisUnit`。

**官方文档要点**（[panel-types/bar](https://signoz.io/docs/dashboards/panel-types/bar/)）：
- 数据源：logs / traces / metrics 三选一
- 用途："frequency of a single or a few different categories over time"
- **堆叠模式默认开启**："Multiple series are combined into a single bar, with each series shown as a colored segment" —— 用 `Stack Series` 切换关掉变成并排柱
- 配置：`yAxisUnit`、Soft Min/Max（同 graph）、`thresholds`（值-颜色对，水平参考线）
- 用例：按状态码堆叠的 req/s、token 用量按 input/output/cache 拆分

```json
{
  "id": "tokens-by-type",
  "panelTypes": "bar",
  "title": "Token 用量按类型",
  "description": "Input, output, cache read, cache creation",
  "isStacked": true,
  "stackedBarChart": true,
  "fillSpans": false,
  "nullZeroValues": "zero",
  "opacity": "1",
  "thresholds": [],
  "timePreferance": "GLOBAL_TIME",
  "yAxisUnit": "short",
  "query": {
    "builder": {
      "queryData": [{
        "aggregateAttribute": {"dataType": "float64", "id": "claude_code_token_usage--float64--Sum--true", "isColumn": true, "key": "claude_code_token_usage", "type": "Sum"},
        "aggregateOperator": "sum",
        "dataSource": "metrics",
        "expression": "A",
        "filters": {"items": [], "op": "AND"},
        "groupBy": [
          {"dataType": "string", "id": "type--string--tag--false", "isColumn": false, "key": "type", "type": "tag"}
        ],
        "having": [],
        "legend": "{{type}}",
        "limit": null,
        "orderBy": [],
        "queryName": "A",
        "reduceTo": "sum",
        "spaceAggregation": "sum",
        "stepInterval": 60,
        "timeAggregation": "sum"
      }],
      "queryFormulas": []
    },
    "clickhouse_sql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "promql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "queryType": "builder"
  }
}
```

### 6. `list` — 列表（仅日志/链路）

显示原始 logs 行或 spans 行，**不支持 metrics 数据源**。常用于错误列表、慢请求列表。

**关键字段**：`dataSource: "logs"` 或 `"traces"`、`selectColumns[]`（要显示的列）、`pageSize`、`offset`、`orderBy`、`columnWidths`。

**官方文档要点**（[panel-types/list](https://signoz.io/docs/dashboards/panel-types/list/)）：
- **数据源仅支持 logs / traces**，写 `metrics` 会被 SigNoz 拒掉（这是 7 种里唯一不接 metrics 的）
- 用途："show a list of values in a single panel" —— 错误日志面板、链路明细面板
- 内置能力：**Infinite scrolling** + **built-in search**
- 官方原话："This panel type doesn't support any configuration" —— 但真实模板里 `selectColumns` / `pageSize` / `orderBy` / `columnWidths` 全都生效
- 用例：最近的错误链路（`has_error=true` + 按 timestamp 倒序）、慢查询列表（按 duration 倒序）

```json
{
  "id": "error-traces",
  "panelTypes": "list",
  "title": "错误链路",
  "description": "",
  "columnWidths": {"service.name": 145, "name": 200, "duration_nano": 145, "response_status_code": 120},
  "decimalPrecision": 2,
  "legendPosition": "bottom",
  "nullZeroValues": "zero",
  "opacity": "1",
  "thresholds": [],
  "timePreferance": "GLOBAL_TIME",
  "yAxisUnit": "none",
  "selectedTracesFields": [
    {"fieldContext": "resource", "fieldDataType": "string", "name": "service.name", "signal": "traces"},
    {"fieldContext": "span", "fieldDataType": "string", "name": "name", "signal": "traces"},
    {"fieldContext": "span", "fieldDataType": "", "name": "duration_nano", "signal": "traces"},
    {"fieldContext": "span", "fieldDataType": "", "name": "response_status_code", "signal": "traces"}
  ],
  "query": {
    "builder": {
      "queryData": [{
        "dataSource": "traces",
        "disabled": false,
        "expression": "A",
        "filters": {
          "items": [{"id": "err-filter", "key": {"dataType": "bool", "id": "has_error--bool--tag--false", "key": "has_error", "type": "tag"}, "op": "=", "value": "true"}],
          "op": "AND"
        },
        "functions": [],
        "groupBy": [],
        "having": [],
        "legend": "",
        "limit": null,
        "offset": 0,
        "orderBy": [{"columnName": "timestamp", "order": "desc"}],
        "pageSize": 10,
        "queryName": "A",
        "selectColumns": [
          {"fieldContext": "resource", "fieldDataType": "string", "name": "service.name", "signal": "traces"},
          {"fieldContext": "span", "fieldDataType": "string", "name": "name", "signal": "traces"},
          {"fieldContext": "span", "fieldDataType": "", "name": "duration_nano", "signal": "traces"},
          {"fieldContext": "span", "fieldDataType": "", "name": "response_status_code", "signal": "traces"}
        ],
        "stepInterval": null
      }],
      "queryFormulas": []
    },
    "clickhouse_sql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "promql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "queryType": "builder"
  }
}
```

### 7. `histogram` — 直方图（频率分布）

⚠️ **不要与 OTel Histogram 指标混淆**：`panelTypes: "histogram"` 是把任意时序数据按值范围分桶绘制频率分布；OTel Histogram 指标用 `panelTypes: "graph"` + `aggregateAttribute.type: "Histogram"` + `spaceAggregation: "p99"`。

`panelTypes: "histogram"` 在官方 99 个模板里**未被使用**，常见做法是用 graph + 百分位代替。仅在确实想看"分布形状"时使用。

**关键字段**：`bucketCount`（默认 30）、`bucketWidth`（0 = 自动）、`mergeAllActiveQueries`。

**官方文档要点**（[panel-types/histogram](https://signoz.io/docs/dashboards/panel-types/histogram/)）：
- 数据源：logs / traces / metrics 三选一
- 用途：识别**分布形状与偏度**（识别"分布是不是长尾"），bar 图但每条柱代表"值的范围"而非单个分类
- **Number of Buckets**（→ JSON `bucketCount`）：默认 30，影响每个 bin 的宽度
- **Bucket Width**（→ JSON `bucketWidth`）：默认 0 = 自动，可手动指定
- **MERGE ALL SERIES INTO ONE**（→ JSON `mergeAllActiveQueries: true`）：把多个 series 合并到单一直方图；多 series 同时画时一般不开
- 用例：单 series 看 req/s 分布；多 series 按 status_code 拆分别看分布

```json
{
  "id": "latency-distribution",
  "panelTypes": "histogram",
  "title": "请求时长分布",
  "description": "Distribution of request durations",
  "bucketCount": 30,
  "bucketWidth": 0,
  "mergeAllActiveQueries": false,
  "nullZeroValues": "zero",
  "opacity": "1",
  "thresholds": [],
  "timePreferance": "GLOBAL_TIME",
  "yAxisUnit": "short",
  "query": {
    "builder": {
      "queryData": [{
        "aggregateAttribute": {"dataType": "float64", "id": "request_duration_seconds--float64--Gauge--true", "isColumn": true, "key": "request_duration_seconds", "type": "Gauge"},
        "aggregateOperator": "avg",
        "dataSource": "metrics",
        "expression": "A",
        "filters": {"items": [], "op": "AND"},
        "groupBy": [],
        "having": [],
        "legend": "",
        "limit": null,
        "orderBy": [],
        "queryName": "A",
        "reduceTo": "avg",
        "spaceAggregation": "avg",
        "stepInterval": 60,
        "timeAggregation": "avg"
      }],
      "queryFormulas": []
    },
    "clickhouse_sql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "promql": [{"disabled": false, "legend": "", "name": "A", "query": ""}],
    "queryType": "builder"
  }
}
```

### 8. `row` — 分区行

把后续 widget 在 UI 上分组到一个折叠段下。`panelTypes: "row"`，几乎没有其他字段。

```json
{
  "id": "row-system",
  "panelTypes": "row",
  "title": "系统指标",
  "query": {}
}
```

**配套 `panelMap`**（顶层字段，让 row 真正生效折叠）：

```json
"panelMap": {
  "row-system": {
    "collapsed": false,
    "widgets": [
      {"h": 6, "i": "cpu-usage", "moved": false, "static": false, "w": 6, "x": 0, "y": 1},
      {"h": 6, "i": "mem-usage", "moved": false, "static": false, "w": 6, "x": 6, "y": 1}
    ]
  }
}
```

⚠️ 不写 `panelMap` 也能导入，但 row 折叠/展开不会工作；新看板建议带上。

## OTel 指标类型 → 聚合写法

| OTel 类型 | `aggregateAttribute.type` | `aggregateAttribute.key` 后缀 | `aggregateOperator` | `timeAggregation` | `spaceAggregation` |
|----------|--------------------------|------------------------------|--------------------|-------------------|---------------------|
| Counter | `Sum` | （无） | `rate` / `increase` / `sum` | `rate` / `increase` / `latest` | `sum` |
| Gauge | `Gauge` | （无） | `avg` / `latest` / `max` / `min` | `avg` / `latest` | `avg` / `sum` |
| Histogram (`count`) | `Histogram` | `.bucket` | **`count`** | **`rate`** | **`p50` / `p90` / `p99`** |
| Histogram (`increase`) | `Histogram` | `.bucket` | **`increase`** | **`""`** (空字符串) | **`p50` / `p90` / `p99`** |

两种 Histogram 写法都被官方模板使用：
- `count` + `rate`：apm-metrics、key-operations（更常见）
- `increase` + `""`：jvm、argocd（GC 累计场景常用）

⚠️ Histogram 三铁律：
1. `aggregateAttribute.key` 必须以 `.bucket` 结尾，`id` 同步带 `.bucket`。
2. `aggregateOperator` 用 `count` 或 `increase`，**绝不写 `p50`/`p99`**。
3. 百分位写在 `spaceAggregation`，**不是 `timeAggregation`**。

## 顶层 dashboard 字段

| 字段 | 必需 | 说明 |
|------|------|------|
| `title` | ✅ | 看板标题（**不是 `name`**）|
| `version` | ✅ | `"v4"` 或 `"v5"`，本 skill 默认产出 `v4` |
| `widgets` | ✅ | widget 数组 |
| `layout` | ✅ | 网格布局，每项 `{h,w,x,y,i,minH,minW,maxH,moved,static}` |
| `description` | 推荐 | 看板描述 |
| `tags` | 推荐 | 字符串数组 |
| `variables` | 可选 | 看板变量字典 |
| `panelMap` | 可选 | row 折叠映射（含 row 时建议带上）|
| `uuid` | 可选 | 服务端会自动生成 |
| `image` | 可选 | base64 SVG 图标 |
| `uploadedGrafana` | 可选 | 是否从 Grafana 迁移而来，默认 `false` |
| `dotMigrated` | 可选 | metric 名带 `.` 的迁移标记 |

## Layout 项完整字段

```json
{
  "h": 6,
  "i": "request-rate",
  "w": 6,
  "x": 0,
  "y": 1,
  "minH": 1,
  "minW": 1,
  "maxH": 100,
  "moved": false,
  "static": false
}
```

`row` 类型 layout 项约定 `h: 1, w: 12, minH: 1, minW: 12, maxH: 1, x: 0`。

## 变量类型完整列表（4 种）

### QUERY — ClickHouse SQL 取值（最强大）

```json
{
  "id": "uuid",
  "name": "service_name",
  "type": "QUERY",
  "queryValue": "SELECT DISTINCT JSONExtractString(labels,'service_name') FROM signoz_metrics.distributed_time_series_v4_1day WHERE metric_name='http_requests_total'",
  "selectedValue": "",
  "multiSelect": true,
  "showALLOption": true,
  "allSelected": true,
  "sort": "ASC",
  "order": 0,
  "description": "",
  "customValue": "",
  "textboxValue": ""
}
```

### DYNAMIC — 直接从某个属性自动取值（推荐，无需写 SQL）

```json
{
  "id": "uuid",
  "name": "host_name",
  "type": "DYNAMIC",
  "dynamicVariablesAttribute": "host.name",
  "dynamicVariablesSource": "Metrics",
  "selectedValue": "",
  "multiSelect": true,
  "showALLOption": true,
  "allSelected": true,
  "sort": "ASC",
  "order": 0
}
```

`dynamicVariablesSource` 可取 `"Metrics"` / `"Logs"` / `"Traces"` / `"All"`。

### CUSTOM — 预定义值列表

```json
{
  "id": "uuid",
  "name": "env",
  "type": "CUSTOM",
  "customValue": "prod, staging, dev",
  "selectedValue": "prod",
  "multiSelect": false,
  "order": 1
}
```

### TEXTBOX — 用户自由输入

```json
{
  "id": "uuid",
  "name": "search_term",
  "type": "TEXTBOX",
  "textboxValue": "",
  "selectedValue": "",
  "order": 2
}
```

### 在 query 中引用变量

```json
"value": ["{{.service_name}}"]   // v4：filter.value 用 {{.var}}，可数组也可标量
"value": "$service_name"          // v5：filter.expression 用 $var
```

## 阈值（thresholds）两种形态

### graph 面板：水平参考线

```json
"thresholds": [
  {"color": "#EF4444", "label": "P99 SLO", "value": 1000, "isEditEnabled": false}
]
```

### value 面板：基于值的染色

```json
"thresholds": [
  {
    "index": "uuid",
    "isEditEnabled": false,
    "keyIndex": 0,
    "selectedGraph": "value",
    "thresholdColor": "Red",
    "thresholdFormat": "Text",
    "thresholdLabel": "Critical",
    "thresholdOperator": ">",
    "thresholdTableOptions": "A",
    "thresholdUnit": "percentunit",
    "thresholdValue": 10
  }
]
```

`thresholdOperator` 取值：`>`、`>=`、`<`、`<=`、`=`、`!=`。

## 常用 yAxisUnit 速查

| 类别 | 值 |
|------|-----|
| 通用 | `none`、`short`、`percent`、`percentunit` |
| 时间 | `s`、`ms`、`us`、`ns` |
| 字节 | `bytes`、`decbytes`、`kbytes`、`mbytes` |
| 速率 | `reqps`、`ops`、`Bps`、`pps` |
| 货币 | `currencyUSD`、`currencyEUR`、`currencyCNY` |

## 常被遗漏的 widget 字段（v5 看板里几乎都带）

```json
"legendPosition": "bottom",      // "bottom" | "right"
"customLegendColors": {},         // 维度值 → 颜色覆盖
"decimalPrecision": 2,            // 小数位
"isLogScale": false,              // Y 轴对数刻度
"contextLinks": {"linksData": []},  // 点击数据点跳转
"columnWidths": {},               // table/list 列宽
"lineInterpolation": "linear",   // "linear" | "smooth" | "step"
"lineStyle": "solid",            // "solid" | "dashed" | "dotted"
"showPoints": "auto",            // "always" | "never" | "auto"
"fillMode": "opacity",           // "opacity" | "gradient" | "none"
"spanGaps": false                 // null 不连线
```

漏掉这些字段 SigNoz 会用默认值，**导入不会报错**，因此本 skill 默认只在样式有强需求时才生成。
