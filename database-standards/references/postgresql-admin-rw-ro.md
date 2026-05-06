# PostgreSQL 权限最佳实践（仅保留一个 admin）

使用边界：

- 本文档只用于生成和审阅 SQL
- 本文档中的 SQL 是变更建议，不代表已执行
- 使用本 skill 时，只输出 SQL、解释、影响范围、注意事项、回滚建议
- 不直接连接数据库
- 不直接执行 `CREATE`、`ALTER`、`GRANT`、`REVOKE`、`REASSIGN OWNED` 等变更语句
- 本文档当前只覆盖 PostgreSQL 权限方案，不覆盖迁移、备份、容灾等其他数据库专题
- 生产环境数据库变更必须走 DBW 工单流程，禁止直接执行

## 一、目标

- 全实例只有一个管理登录用户：`admin`
- 每个数据库只保留两个业务登录用户：`<db>_rw`、`<db>_ro`
- 新建数据库自动覆盖未来对象权限
- 已存在老库也能平滑纳管，包括“业务用户直接 owner”的历史模式

---

## 二、最终模型

以数据库 `tcgadmin` 为例：

```text
admin (LOGIN)       -> 全局管理、DDL、owner
tcgadmin (LOGIN) -> 应用读写
tcgadmin_ro (LOGIN) -> 查询/报表只读
```

关键点：

- `admin` 是全局唯一管理入口
- 数据库、schema、表、序列、函数的 owner 统一收敛到 `admin`
- `tcgadmin` / `tcgadmin_ro` 直接承载业务访问权限
- 后续所有 DDL 都由 `admin` 直接执行

---

## 三、这个模型的取舍

### 优点

- 结构最简单
- 最容易理解和落地
- 每库只有 `rw` / `ro` 两个业务账号
- 不需要额外维护中间 role

### 代价

- ownership 直接落在 `admin` 上
- 如果未来要更换 `admin` 为另一个管理账号，需要额外做 owner 迁移

如果你的目标是“极简、易落地”，这个模型是成立的。  
如果未来你更看重“ownership 与登录账号解耦”，再回到 `admin_role` 模型会更稳。

---

## 四、核心原则

### 1. 业务 user 不要做 owner

不要让 `tcgadmin` 或其他业务账号直接做 owner，否则：

- DDL 能力会混入业务账号
- 默认权限会跟着业务账号走
- 应用账号泄漏时，破坏面会扩大

### 2. 默认权限只影响未来对象

必须同时做两类授权：

- `GRANT ON ALL TABLES / SEQUENCES / FUNCTIONS`
  作用：覆盖当前已有对象
- `ALTER DEFAULT PRIVILEGES`
  作用：覆盖后续新建对象

两者缺一不可。

### 3. 默认权限跟“实际创建对象的人”绑定

这是老库改造最容易漏掉的点。

如果现在对象还是由 `legacy` 创建，那么在 owner 没收敛到 `admin` 之前，必须对 `legacy` 配默认权限：

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE legacy ...
```

只对 `admin` 配默认权限，不会影响 `legacy` 新建对象。

### 4. 仅在 owner 替换或 owner 收敛时，必须按三阶段执行

只要需求里出现数据库、schema、表、序列、函数等对象的 owner 替换或 owner 收敛，就必须拆成三阶段 DBW 工单，不能压成一条 SQL 或一个 DBW 工单。

以下情况视为命中：

- 明确要求把 owner 从角色 A 改到角色 B
- 明确要求把 owner 收敛到 `admin`
- SQL 中出现 `ALTER DATABASE ... OWNER`
- SQL 中出现 `ALTER SCHEMA ... OWNER`
- SQL 中出现 `ALTER TABLE ... OWNER`
- SQL 中出现 `ALTER SEQUENCE ... OWNER`
- SQL 中出现 `ALTER FUNCTION ... OWNER`
- SQL 中出现 `REASSIGN OWNED`

如果请求不涉及 owner 替换或 owner 收敛，则不强制套用三阶段。

固定采用三阶段 DBW 工单：

1. 先补业务账号对现有对象的显式权限
2. 再切数据库和 schema owner
3. 再补 `admin` 的默认权限、按需回收业务账号的 `CREATE`，并单独处理历史对象 owner 收敛

这样做的核心目的，是先把业务访问能力从“依赖 owner 身份”改成“依赖显式 GRANT”，再处理 ownership。

### 5. `REASSIGN OWNED` 必须归入第三阶段

`REASSIGN OWNED BY legacy TO admin` 的作用范围是：

- 当前数据库内该角色拥有的全部对象
- 不只限于 `public` schema

因此：

- 当需求是 owner 替换或 owner 收敛时，`REASSIGN OWNED` 不得放进第二阶段的数据库级 owner 切换工单
- 只有在第三阶段，并且已经完成对象盘点后，才应提议使用
- 如果对象范围不清楚，也必须继续留在第三阶段或后续单独工单，不得与数据库级 owner 切换一起执行
- 最终输出默认必须包含完整三阶段，不能只给第二阶段或第二、三阶段的裁剪版方案

---

## 五、命名规范

以数据库 `tcgadmin` 为例：

```text
admin
tcgadmin
tcgadmin_ro
```

建议：

- `admin` 全实例唯一
- 每个库只保留一对 `rw` / `ro`

---

## 六、新建数据库标准方案

以下以 `tcgadmin` 为例。

### Step 1：创建全局 admin user

```sql
CREATE USER admin PASSWORD 'replace_me';
```

如果 `admin` 需要负责建库、建用户，可按平台能力补充：

```sql
ALTER ROLE admin CREATEDB CREATEROLE;
```

说明：

- 托管 PostgreSQL 是否允许 `CREATEDB` / `CREATEROLE`，取决于平台
- 如果平台不允许，由实例管理员预创建即可

### Step 2：创建业务登录用户

```sql
CREATE USER tcgadmin PASSWORD 'replace_me';
CREATE USER tcgadmin_ro PASSWORD 'replace_me';
```

### Step 3：创建数据库，并把 owner 设为 admin

```sql
CREATE DATABASE tcgadmin OWNER admin;
```

### Step 4：在目标库内初始化权限

以下 SQL 需要在 `tcgadmin` 库内执行。

```sql
REVOKE ALL ON DATABASE tcgadmin FROM PUBLIC;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
ALTER SCHEMA public OWNER TO admin;
```

SQL解释：

- `REVOKE ALL ON DATABASE ... FROM PUBLIC` 撤销所有用户默认继承的数据库级权限，避免未授权账号自动获得 `CONNECT`
- `REVOKE CREATE ON SCHEMA public FROM PUBLIC` 阻止任意账号在 `public` schema 里建对象
- `ALTER SCHEMA public OWNER TO admin` 把 schema owner 收敛到统一管理账号

影响范围：

- 立即影响数据库级和 schema 级入口权限
- 不直接修改现有表、序列、函数的对象级授权
- 会影响之后谁可以连接库、谁可以在 `public` 建对象

注意事项：

- 如果已有其他账号依赖默认 `CONNECT`，执行后会立刻断开后续连接能力
- `ALTER SCHEMA ... OWNER` 只改 schema owner，不会自动改表 owner
- 如果业务使用的不是 `public`，要替换成实际 schema

回滚建议：

- 如需回滚数据库连接入口，按需重新 `GRANT CONNECT ON DATABASE ... TO ...`
- 如需回滚 schema owner，执行 `ALTER SCHEMA public OWNER TO <old_owner>`
- 如需恢复 `PUBLIC` 的默认创建能力，执行 `GRANT CREATE ON SCHEMA public TO PUBLIC`，但通常不建议

#### rw 授权 SQL

```sql
GRANT CONNECT, TEMP ON DATABASE tcgadmin TO tcgadmin;

GRANT USAGE ON SCHEMA public TO tcgadmin;

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA public
TO tcgadmin;

GRANT USAGE, SELECT, UPDATE
ON ALL SEQUENCES IN SCHEMA public
TO tcgadmin;

GRANT EXECUTE
ON ALL FUNCTIONS IN SCHEMA public
TO tcgadmin;
```

SQL解释：

- 给 `tcgadmin` 数据库连接能力和可选的临时表能力
- 给 `tcgadmin` schema 使用权
- 给 `tcgadmin` 当前所有表的读写权限、序列使用权限、函数执行权限

影响范围：

- 只覆盖当前已经存在的对象
- 不会自动覆盖未来新建的表、序列、函数
- 只影响 `public` schema，不影响其他 schema

注意事项：

- `TEMP` 允许创建临时表，不需要时可以去掉
- `ON ALL TABLES/SEQUENCES/FUNCTIONS` 不会处理未来对象，必须配合默认权限
- 如果库里有多个 schema，要对每个 schema 单独执行

回滚建议：

- 回滚时按对象类型执行 `REVOKE`，例如 `REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM tcgadmin`
- 如果只想撤掉部分能力，优先精确回滚单个权限而不是整段全撤
- 回滚后要检查应用是否仍依赖该账号访问现有对象

#### ro 授权 SQL

```sql
GRANT CONNECT ON DATABASE tcgadmin TO tcgadmin_ro;

GRANT USAGE ON SCHEMA public TO tcgadmin_ro;

GRANT SELECT
ON ALL TABLES IN SCHEMA public
TO tcgadmin_ro;

GRANT SELECT
ON ALL SEQUENCES IN SCHEMA public
TO tcgadmin_ro;

GRANT EXECUTE
ON ALL FUNCTIONS IN SCHEMA public
TO tcgadmin_ro;
```

SQL解释：

- 给 `tcgadmin_ro` 数据库连接能力和 schema 使用权
- 给 `tcgadmin_ro` 当前所有表的只读权限
- 给 `tcgadmin_ro` 当前所有序列的只读权限，以及函数执行权限

影响范围：

- 只覆盖当前已经存在的对象
- 不会自动覆盖未来新建的表、序列、函数
- 只影响 `public` schema

注意事项：

- `ro` 是否需要 `EXECUTE ON FUNCTIONS` 取决于业务和安全要求
- 某些函数虽然只执行不写表，也可能间接修改数据，要单独评估
- 如果只读账号不应该看到序列值或函数结果，应删除对应授权

回滚建议：

- 回滚时按对象类型执行 `REVOKE SELECT ON ALL TABLES/SEQUENCES ...` 和 `REVOKE EXECUTE ON ALL FUNCTIONS ...`
- 如果风险集中在函数执行权限，可只回滚 `EXECUTE`
- 回滚后要确认报表、BI、查询链路是否受影响

说明：

- `rw` 是否需要 `TEMP`，看应用是否会建临时表
- 如果一个库里有多个 schema，要按 schema 分别授权
- 如果只读账号不需要调用函数，可以不授予 `FUNCTIONS`

### Step 5：配置未来对象默认权限

以下 SQL 也需要在 `tcgadmin` 库内执行。

#### rw 默认权限 SQL

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tcgadmin;

ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO tcgadmin;

ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT EXECUTE ON FUNCTIONS TO tcgadmin;
```

SQL解释：

- 为 `admin` 未来在 `public` schema 新建的表、序列、函数预设 `rw` 权限
- 确保后续新增对象不需要再手工补 `rw` 授权

影响范围：

- 只影响未来新建对象
- 不影响已经存在的对象
- 只对 `admin` 创建的对象生效，不对其他创建者生效

注意事项：

- 这是 PostgreSQL 最容易误解的点：默认权限跟创建者绑定，不跟库绑定
- 如果未来对象是别的 owner 创建的，这里不会生效
- 做 DDL 的账号必须稳定收敛到 `admin`

回滚建议：

- 回滚默认权限可执行 `ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public REVOKE ... FROM tcgadmin`
- 如果只想停止未来授权，回滚默认权限即可，历史对象无需强制回收
- 回滚后要补充人工授权流程，否则未来新对象会再次漏权

#### ro 默认权限 SQL

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT SELECT ON TABLES TO tcgadmin_ro;

ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT SELECT ON SEQUENCES TO tcgadmin_ro;

ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT EXECUTE ON FUNCTIONS TO tcgadmin_ro;
```

SQL解释：

- 为 `admin` 未来新建的表、序列、函数预设 `ro` 权限
- 让 `ro` 自动获得后续对象的只读访问能力

影响范围：

- 只影响未来对象
- 不影响现有对象
- 只对 `admin` 创建的对象生效

注意事项：

- `ro` 的函数执行权限要谨慎，必要时可以取消
- 如果 `ro` 不应读取序列或不应访问某类对象，需要单独收窄权限
- 老库在 owner 未统一前，不能直接把这段当成唯一默认权限方案

回滚建议：

- 回滚默认权限可执行 `ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public REVOKE ... FROM tcgadmin_ro`
- 如仅需收回未来函数调用能力，可单独回滚 `EXECUTE ON FUNCTIONS`
- 回滚后要评估只读链路对未来对象是否还需要人工补权

### Step 6：以后所有 DDL 统一由 admin 执行

```sql
CREATE TABLE t_order (
    id bigserial PRIMARY KEY,
    order_no text NOT NULL
);
```

SQL解释：

- 这表示后续对象统一由 `admin` 创建，从而让 owner 和默认权限模型保持一致

影响范围：

- 影响所有未来 DDL 的对象 owner 和默认权限继承链路
- 不会修改历史对象

注意事项：

- 如果后续有人绕过 `admin` 直接建表，默认权限可能马上失效
- 需要在发布和运维流程里约束 DDL 执行入口

回滚建议：

- 不存在独立 SQL 回滚动作，本质上是流程约束问题
- 如果已出现绕过 `admin` 的对象，需要把 owner 迁回 `admin` 并补默认权限
- 回滚发布策略前，先确认不会再次引入多 owner

做到这里后：

- owner 统一归 `admin`
- 管理入口统一是 `admin`
- 业务访问统一走 `rw` / `ro`
- 已有对象和未来对象权限都能覆盖

---

## 七、老库改造方案（当前是“业务用户直接 owner”）

假设当前老库 `tcgadmin` 存在这些历史情况：

- 数据库 owner 是 `legacy`
- 表 owner 也是 `legacy`
- 应用直接用 `legacy` 连库

推荐顺序仍然是“先兼容，再收敛”。

### Phase 1：先补齐新模型

```sql
CREATE USER admin PASSWORD 'replace_me';
CREATE USER tcgadmin PASSWORD 'replace_me';
CREATE USER tcgadmin_ro PASSWORD 'replace_me';
```

如果实例里已经有 `admin`，这里跳过即可。

### Phase 2：先让新 user 能访问已有对象

以下 SQL 在 `tcgadmin` 库内执行：

```sql
REVOKE ALL ON DATABASE tcgadmin FROM PUBLIC;
```

SQL解释：

- 先收口数据库级默认开放权限，避免历史库继续依赖 `PUBLIC` 的默认访问能力

影响范围：

- 立即影响所有尚未显式授权的用户连接能力
- 不修改现有表、序列、函数授权

注意事项：

- 执行前要确认新旧应用账号都已显式拿到 `CONNECT`
- 如果历史上有人通过 `PUBLIC` 间接访问库，这一步会立即暴露问题

回滚建议：

- 如需恢复默认入口，可执行 `GRANT CONNECT ON DATABASE tcgadmin TO PUBLIC`
- 更推荐只对需要的账号重新显式授权，而不是重新开放 `PUBLIC`
- 回滚前先识别依赖 `PUBLIC` 的真实账号范围

#### rw 授权 SQL

```sql
GRANT CONNECT, TEMP ON DATABASE tcgadmin TO tcgadmin;

GRANT USAGE ON SCHEMA public TO tcgadmin;

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA public
TO tcgadmin;

GRANT USAGE, SELECT, UPDATE
ON ALL SEQUENCES IN SCHEMA public
TO tcgadmin;

GRANT EXECUTE
ON ALL FUNCTIONS IN SCHEMA public
TO tcgadmin;
```

SQL解释：

- 给新的 `rw` 账号补齐对老库当前对象的访问能力
- 让应用先切换到新账号，而不必等 owner 迁移完成

影响范围：

- 只覆盖老库当前已有对象
- 不覆盖后续新增对象
- 只作用于当前列出的 schema 和对象类型

注意事项：

- 这一步是兼容过渡，不是最终稳态
- 如果老库里有自定义类型、物化视图、外部表等特殊对象，需要额外检查
- 如果对象 owner 很多，未来新增对象仍会漏授权，必须继续做 Phase 3

回滚建议：

- 回滚时按对象类型执行 `REVOKE ... FROM tcgadmin`
- 如果只需暂停新账号切流，可先回滚连接串，再逐步回收对象权限
- 回滚后要确认旧账号仍具备完整访问能力

#### ro 授权 SQL

```sql
GRANT CONNECT ON DATABASE tcgadmin TO tcgadmin_ro;

GRANT USAGE ON SCHEMA public TO tcgadmin_ro;

GRANT SELECT
ON ALL TABLES IN SCHEMA public
TO tcgadmin_ro;

GRANT SELECT
ON ALL SEQUENCES IN SCHEMA public
TO tcgadmin_ro;

GRANT EXECUTE
ON ALL FUNCTIONS IN SCHEMA public
TO tcgadmin_ro;
```

SQL解释：

- 给新的 `ro` 账号补齐对老库当前对象的只读访问能力
- 让查询、报表、BI 等流量先切换到独立只读账号

影响范围：

- 只覆盖当前已有对象
- 不覆盖未来对象
- 只作用于当前 schema

注意事项：

- 只读函数执行权限仍需单独评估风险
- 如果报表账号不应看到某些敏感对象，需要额外收窄授权范围
- 切流后仍要继续处理默认权限和 owner 收敛

回滚建议：

- 回滚时按对象类型执行 `REVOKE ... FROM tcgadmin_ro`
- 如只需收回高风险能力，优先回滚函数执行权限和序列读取权限
- 回滚前确认报表、BI、审计任务已切回旧账号或备用账号

这一步完成后，新的 `rw` / `ro` 已经可以访问当前对象。

### Phase 3：owner 还没收敛前，先补未来对象默认权限

如果当前对象还是由 `legacy` 创建，那么默认权限必须配在 `legacy` 名下：

#### rw 默认权限 SQL

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE legacy IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tcgadmin;

ALTER DEFAULT PRIVILEGES FOR ROLE legacy IN SCHEMA public
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO tcgadmin;

ALTER DEFAULT PRIVILEGES FOR ROLE legacy IN SCHEMA public
GRANT EXECUTE ON FUNCTIONS TO tcgadmin;
```

SQL解释：

- 给 `legacy` 未来创建的对象预设 `rw` 权限
- 解决 owner 还没迁移前，新对象继续由历史 owner 创建导致的漏授权问题

影响范围：

- 只影响 `legacy` 之后新建的对象
- 不影响现有对象
- 不影响其他 historical owner 创建的对象

注意事项：

- 如果有 `legacy_a`、`legacy_b` 等多个 owner，要逐个配置
- 这是过渡期配置，不代表最终 owner 模型
- 一旦创建者换成 `admin`，这里就不再覆盖新对象

回滚建议：

- 回滚默认权限可执行 `ALTER DEFAULT PRIVILEGES FOR ROLE legacy IN SCHEMA public REVOKE ... FROM tcgadmin`
- 回滚只影响未来由 `legacy` 创建的对象，不影响历史对象
- 回滚前确认应用是否仍依赖 `legacy` 创建的新对象自动授权

#### ro 默认权限 SQL

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE legacy IN SCHEMA public
GRANT SELECT ON TABLES TO tcgadmin_ro;

ALTER DEFAULT PRIVILEGES FOR ROLE legacy IN SCHEMA public
GRANT SELECT ON SEQUENCES TO tcgadmin_ro;

ALTER DEFAULT PRIVILEGES FOR ROLE legacy IN SCHEMA public
GRANT EXECUTE ON FUNCTIONS TO tcgadmin_ro;
```

SQL解释：

- 给 `legacy` 未来创建的对象预设 `ro` 权限
- 确保只读账号在 owner 未统一前仍能自动看到未来对象

影响范围：

- 只影响 `legacy` 后续创建的对象
- 不影响历史对象
- 不影响其他 owner

注意事项：

- 如果有多个历史 owner，需要为每个 owner 重复配置
- `ro` 的函数权限仍应按最小权限原则评估
- owner 收敛完成后，应切回 `FOR ROLE admin` 的标准方案

回滚建议：

- 回滚默认权限可执行 `ALTER DEFAULT PRIVILEGES FOR ROLE legacy IN SCHEMA public REVOKE ... FROM tcgadmin_ro`
- 如果只读风险集中在函数，可优先回滚 `EXECUTE`
- 回滚后要接受未来由 `legacy` 创建的新对象不再自动开放给 `ro`

如果历史上有多个 owner，比如：

- `legacy_a`
- `legacy_b`

那就需要对每个 owner 都执行一遍。

### Phase 4：逐步把 owner 收敛到 admin

最终稳态应该把 ownership 收回到 `admin`：

```sql
ALTER DATABASE tcgadmin OWNER TO admin;
ALTER SCHEMA public OWNER TO admin;
REASSIGN OWNED BY legacy TO admin;
```

SQL解释：

- 把数据库、schema、以及 `legacy` 名下对象 owner 统一迁回 `admin`
- 是老库从历史 owner 模式切换到标准模型的核心步骤

影响范围：

- 直接修改 ownership
- `REASSIGN OWNED` 影响当前数据库内该角色拥有的全部对象，不限于 `public`
- 会影响后续谁能做 DDL、谁的默认权限生效
- 不会自动替你重写应用连接串，但会改变管理边界

注意事项：

- `REASSIGN OWNED` 通常要求高权限，托管实例上常需要管理员配合
- 如果当前目标是“不影响业务”或“尽量不停服”，不要默认把这一段与数据库级 owner 切换放在同一工单
- 执行前要确认 `legacy` 下是否还有不应迁移的对象
- owner 迁移后要立即补标准默认权限，避免新对象授权断层

回滚建议：

- 回滚 owner 迁移通常需要反向执行 `REASSIGN OWNED BY admin TO legacy` 或逐个 `ALTER ... OWNER TO legacy`
- 反向回滚前要确认 `admin` 迁移期间是否新建了对象，否则会混入新的 owner 分叉
- owner 迁移回滚风险高，建议先在测试环境验证对象清单

注意：

- `REASSIGN OWNED` 要在目标数据库内执行
- 执行者通常需要足够高的权限
- 托管 PostgreSQL 场景下，往往需要实例管理员配合

### Phase 4A：低风险第一阶段，只切数据库与 schema owner

当优先目标是“先不影响业务，再逐步治理历史 owner”时，建议先执行：

```sql
ALTER DATABASE tcgadmin OWNER TO admin;
ALTER SCHEMA public OWNER TO admin;
```

SQL解释：

- 只切换数据库对象和 `public` schema 的 owner 到 `admin`
- 不在这一阶段迁移现有表、序列、函数等历史对象 owner

影响范围：

- 只影响数据库级与 schema 级 ownership
- 不修改现有表、序列、函数的 owner
- 业务账号如果已提前补齐显式权限，通常可以持续正常读写

注意事项：

- 这不是完整 owner 收敛，只是低风险第一阶段
- 后续仍应盘点历史对象 owner，并决定是否进入全量 owner 迁移
- 如果业务 schema 不是 `public`，需替换为实际 schema

回滚建议：

- 执行 `ALTER DATABASE tcgadmin OWNER TO <old_owner>`
- 执行 `ALTER SCHEMA public OWNER TO <old_owner>`
- 回滚前确认切换后没有新增依赖 `admin` ownership 的管理动作

### Phase 5：owner 收敛后，切回标准默认权限

当主要对象 owner 已经统一到 `admin` 后，再执行正式默认权限：

#### rw 默认权限 SQL

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tcgadmin;

ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO tcgadmin;

ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT EXECUTE ON FUNCTIONS TO tcgadmin;
```

SQL解释：

- owner 收敛完成后，恢复标准 `rw` 默认权限模型
- 让未来由 `admin` 创建的新对象自动授给 `rw`

影响范围：

- 只影响 owner 收敛后未来由 `admin` 创建的对象
- 不修改现有对象

注意事项：

- 如果还有其他账号继续建对象，这段不会覆盖那些对象
- 应与流程治理一起落地，确保 DDL 不再由 legacy owner 执行

回滚建议：

- 回滚默认权限可执行 `ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public REVOKE ... FROM tcgadmin`
- 回滚后未来对象可能再次漏权，除非你已恢复其他自动授权机制
- 回滚只影响未来对象，不会撤掉已存在对象权限

#### ro 默认权限 SQL

```sql
ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT SELECT ON TABLES TO tcgadmin_ro;

ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT SELECT ON SEQUENCES TO tcgadmin_ro;

ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public
GRANT EXECUTE ON FUNCTIONS TO tcgadmin_ro;
```

SQL解释：

- owner 收敛完成后，恢复标准 `ro` 默认权限模型
- 让未来对象自动具备只读访问能力

影响范围：

- 只影响未来对象
- 不修改历史对象
- 只对 `admin` 创建的对象生效

注意事项：

- 如果后续 `ro` 权限边界要更细，比如部分 schema 不开放，需要拆分授权
- 函数执行权限仍应按安全要求决定是否保留

回滚建议：

- 回滚默认权限可执行 `ALTER DEFAULT PRIVILEGES FOR ROLE admin IN SCHEMA public REVOKE ... FROM tcgadmin_ro`
- 如只想回滚函数执行能力，可单独 `REVOKE EXECUTE ON FUNCTIONS`
- 回滚只影响未来对象，不影响历史对象

后续所有 DDL 都统一由 `admin` 直接执行。

### Phase 6：下线 legacy owner 直连

当应用都切到 `tcgadmin` / `tcgadmin_ro` 后，再处理历史账号：

- 下线 `legacy` 的应用连接配置
- 禁止 `legacy` 继续建对象
- 视情况回收其对象级显式授权

例如：

```sql
REVOKE CREATE ON SCHEMA public FROM legacy;
```

SQL解释：

- 阻止历史 owner 继续在 `public` schema 里创建新对象
- 用于切断旧链路，防止 owner 又分叉回去

影响范围：

- 立即影响 `legacy` 后续建表、建序列、建函数能力
- 不修改已有对象

注意事项：

- 执行前要确认应用和运维流程已经彻底切到 `admin`
- 如果 `legacy` 还负责其他 schema，对应 schema 也要一起检查

回滚建议：

- 如需恢复 `legacy` 的建对象能力，可执行 `GRANT CREATE ON SCHEMA public TO legacy`
- 回滚前要先确认恢复旧链路不会再次引入多 owner
- 如果仅部分对象需要临时由 `legacy` 管理，优先限定到具体 schema

如果历史账号未来不再需要登录，也可以进一步：

```sql
ALTER ROLE legacy NOLOGIN;
```

---

## 八、多 schema 场景

如果一个数据库里不止 `public` 一个 schema：

- 每个 schema 都要单独做 `USAGE`
- 每个 schema 都要单独做 `ON ALL TABLES / SEQUENCES / FUNCTIONS`
- 每个 schema 都要单独做 `ALTER DEFAULT PRIVILEGES ... IN SCHEMA ...`

数据库级授权不会自动覆盖 schema 内对象。

---

## 九、最终建议

稳态建议：

- 全局一个 `admin`
- 每库一个 `<db>_rw`
- 每库一个 `<db>_ro`
- `admin` 统一做 owner 和 DDL
- `rw` / `ro` 直接承载业务访问权限

不建议：

- 业务 user 直接做 owner
- 一个库里长期复用历史 owner 账号做应用连接
- 只做已有对象授权，不做默认权限

---

## 十、一句话结论

**如果你要最简模型，就只保留一个全局 `admin`，每库只保留 `rw` / `ro` 两个业务账号；对象 owner、DDL、默认权限全部统一收敛到 `admin`。**
