---
name: finebi-dashboard-export
description: 使用 FineBI Web 集成接口导出公共目录仪表板页签为 Excel，获取公共目录和公共数据列表，读取数据集字段和分页数据，并管理受控数据集或仪表板。用户要求操作 FineBI、中国 BI、日本 BI、公共目录、仪表板、页签、Excel、公共数据列表、数据集字段或数据集数据时使用。
---

# FineBI 公共目录和数据接口

## 适用场景

当用户要求操作 FineBI 公共目录资源、仪表板页签或公共数据集时使用本 Skill，例如：

- 导出“公司OKR”Excel
- 导出“月度复盘表”里的“总表”
- 根据公共目录名称查真实 `reportId`，用于后续调用 Excel 导出接口
- 批量整理公共目录资源和仪表板页签
- 获取 FineBI 公共数据列表
- 查看某个公共数据集的字段
- 分页拉取某个 FineBI 数据集的数据
- 新增、重命名或更新受控测试数据集
- 新建、重命名或另存为受控测试仪表板

## 配置文件要求

默认配置文件放在用户目录下的 `~/.config/finebi/.env`，不要依赖 Cursor、项目根目录或某个 Skill 安装路径。同一台机器支持多套 FineBI 配置，使用环境前缀区分：

```text
FINEBI_PROFILE=cn

FINEBI_CN_HOST=http://...
FINEBI_CN_USERNAME=...
FINEBI_CN_PASSWORD=...

FINEBI_JP_HOST=http://...
FINEBI_JP_USERNAME=...
FINEBI_JP_PASSWORD=...
```

脚本也兼容 `cn.host`、`cn_host`、`FINEBI_CN_HOST` 这类写法。命令行传 `--profile cn` 或 `--profile jp` 时，会优先使用对应 profile；不传时使用 `FINEBI_PROFILE`，再回退到旧的无前缀配置。

如果必须临时使用其他配置文件，命令行传 `--config /path/to/.env`。不要在回复或日志里打印 `.env` 中的敏感信息。

当用户用自然语言指定环境时，按下面规则选择 profile：

- “中国 BI”“国内 BI”“中国 FineBI”使用 `--profile cn`
- “日本 BI”“日本 FineBI”使用 `--profile jp`
- 脚本也接受 `--profile 中国`、`--profile 日本`、`--profile china`、`--profile japan`，会自动归一到 `cn` 或 `jp`

## 认证方式

以下 FineBI 产品接口使用 FineBI 账号登录态，不走开放平台应用密钥：

1. 使用 FineBI 产品账号登录：
   `GET /webroot/decision/login/cross/domain`
2. 从响应中取 `accessToken`，后续请求带：
   `Authorization: Bearer <accessToken>`
3. 部分接口还需要显式把 token 放到查询参数：
   `fine_auth_token=<accessToken>`

## 仪表板导出流程

已验证可用的路径如下：

1. 获取公共目录树：
   `GET /webroot/decision/v10/view/entry/tree`
2. 按展示字段 `text` 定位公共目录节点。
   `text` 是公共目录名称，`path` 是它来源于“我的分析”的路径。
3. 获取 BI 报表树：
   `GET /webroot/decision/v5/platform/dashboard/reports/tree`
4. 用公共目录节点的来源 `path` 匹配报表树中的 BI 主题。
   真正可导出的仪表板页签是该主题下的子节点。
5. 使用仪表板页签的真实 `reportId` 导出 Excel：
   `GET /webroot/decision/v5/api/dashboard/report/export/excel?reportId=...`
6. 保存前确认响应以 XLSX 文件头 `PK\x03\x04` 开头。

关键区别：

- 公共目录节点的 `templateId` 不一定能直接导出。
- `dashboard/search` 常返回 `name=仪表板`，这通常只是页签名。
- Excel 导出接口需要仪表板页签的真实 `reportId`，不是公共目录节点 ID，也不是公共目录节点 `templateId`。
- 因此，“根据公共目录名称查真实 `reportId`”的用途是先定位可导出的页签，再把该页签 `reportId` 传给 Excel 导出接口。

## 公共数据列表

获取公共数据列表时，不能只取第一层目录；需要递归遍历数据目录：

1. 获取根目录或数据分组：
   `GET /webroot/decision/v5/api/conf/groups`
2. 对每个目录继续获取内容：
   `GET /webroot/decision/v5/api/conf/packs/{packId}`
3. 对每个目录获取结构并递归子目录：
   `GET /webroot/decision/v5/api/conf/packs/{packId}/structure`
4. 如果接口提示缺少 `fine_auth_token`，在 URL 查询参数里补：
   `?fine_auth_token=<accessToken>`

注意事项：

- 只拉第一层会漏数据，之前只能得到几十条。
- 递归遍历所有 pack 后可拿到完整公共数据目录。
- 对外展示的表名和物理库表名不同。数据接口需要 FineBI 数据集的 `tableName`，不是数据库物理表名。

## 数据集字段和分页取数

已验证的数据集接口：

- `POST /webroot/decision/v5/api/tables/fields/page`
- `POST /webroot/decision/v5/api/tables/data/page`

请求体常用字段：

```json
{
  "tableName": "FineBI 数据集 tableName",
  "pageIndex": "1",
  "pageSize": "1000",
  "limit": "1000000"
}
```

接口差异和注意事项：

- `tableName` 必须是 FineBI 数据集 ID/名称，不是数据库物理表名。
- `/v5/api/tables/data/page` 存在 `100000` 行窗口限制；翻到 10w 后继续分页返回空数据，不能靠多次分页突破。
- `/v5/api/tables/fields/page` 不传 `limit` 时默认约 `5000` 行窗口。
- `/v5/api/tables/fields/page` 的可翻页窗口受 `limit` 控制；调大 `limit` 可继续翻页超过 10w。
- 大 `limit` 请求会明显变慢，可能给 FineBI 或底层数据库带来压力；批量导出时优先小 `pageSize` 分页、记录进度，并避免在高峰期跑全量。

## Web 集成数据集管理

使用新增、更新、重命名等写接口时必须遵守：

- 不删除任何已有对象。
- 不修改已有业务数据集、公共目录资源或仪表板。
- 需要使用写操作时，先新增 `finebi_agent_` 前缀的受控对象，再只在该对象上修改。
- 写接口除 `Authorization: Bearer <accessToken>` 外，通常还要在 URL 查询参数带 `fine_auth_token=<accessToken>`。

已验证成功的 Web 集成数据集能力：

- 获取数据集信息：
  `GET /webroot/decision/v5/api/table/{tableName}/get?fine_auth_token=...`
- 新增 SQL 数据集：
  `POST /webroot/decision/v5/api/table/add?fine_auth_token=...`
- 修改数据集转义名：
  `POST /webroot/decision/v5/api/tables/{tableName}/rename?fine_auth_token=...`
- 更新 SQL 数据集：
  `POST /webroot/decision/v5/api/table/update?fine_auth_token=...`
- 读取新增或更新后的数据：
  `POST /webroot/decision/v5/api/tables/fields/page`
  或 `POST /webroot/decision/v5/api/tables/data/page`

SQL 数据集新增请求示例：

```json
{
  "type": 2,
  "connectionName": "MYSQL生产环境-匹配查找只读节点",
  "sql": "select 1 as finebi_agent_value",
  "name": "finebi_agent_dataset_...",
  "parentId": "28a679af4f084752bc9125e5ff288068",
  "initTime": 0,
  "engineType": "direct",
  "comment": "FineBI agent controlled dataset."
}
```

注意事项：

- `/v5/api/table/add` 可创建 SQL 数据集，响应中的 `data.name` 是后续接口使用的真实 `tableName`。
- `/v5/api/table/update` 可更新受控 SQL 数据集的 SQL；更新后用 `/fields/page` 读取能看到新 SQL 的结果。
- `/v5/api/tables/{tableName}/rename` 修改的是展示名 `transferName`，不改变真实 `tableName`。
- `/v5/api/analysis/table/execute/sql/{tableName}` 不是执行任意 SQL 的接口；它最多用于获取部分直连分析表的生成 SQL，常返回空 `data`。
- 删除接口 `/webroot/decision/v5/api/pack/delete` 不要主动测试，除非用户明确要求删除受控测试对象。

## 脚本

使用脚本时不要依赖任何特定工具目录；按实际路径调用即可：

```bash
python "finebi-dashboard-export/scripts/export_finebi_excel.py" --entry "月度复盘表" --report "总表"
```

指定中国或日本环境：

```bash
python "finebi-dashboard-export/scripts/export_finebi_excel.py" --profile cn --entry "月度复盘表" --report "总表"
python "finebi-dashboard-export/scripts/export_finebi_excel.py" --profile jp --entry "月度复盘表" --report "总表"
```

只查看某个公共目录下可导出的页签，不导出文件：

```bash
python "finebi-dashboard-export/scripts/export_finebi_excel.py" --entry "月度复盘表" --list
```

脚本默认把 Excel 文件保存到当前运行目录的 `exports/`；需要指定其他目录时传 `--out-dir /path/to/exports`。

## 回复用户

导出完成后，向用户说明：

- 公共目录名称
- 来源路径
- 仪表板页签名称
- `reportId`
- 保存的文件路径
- 是否已验证响应为 `.xlsx`
