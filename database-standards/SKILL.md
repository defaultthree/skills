---
name: database-standards
description: "Design, review, and document database standards and solution proposals across permissions, governance, schema strategy, migration, backup and recovery, high availability, and related operational patterns. Use when Codex needs to generate SQL, change plans, standards, or architecture guidance for database work. This skill is specification-only: it outputs proposals and explanations, and must not execute SQL or make live changes. The current built-in reference set starts with PostgreSQL permission rules and should be extended with additional database-specific standard references over time."
---

# 数据库规范

Use this skill when the user is defining or changing database-related solution proposals for application systems.

This skill is specification-only:

- generate SQL
- explain SQL
- review SQL
- do not execute SQL
- do not connect to databases
- do not apply live permission changes
- all database changes must go through DBW workflow
- absolutely forbid direct execution through `psql`, bastion hosts, or ad hoc database clients

Read the relevant database-specific reference before producing SQL or recommendations.

Current built-in reference:

- DBW SQL 变更流程: [references/dbw-sql-change-workflow.md](./references/dbw-sql-change-workflow.md)
- PostgreSQL: [references/postgresql-admin-rw-ro.md](./references/postgresql-admin-rw-ro.md)

## Current Scope

Current built-in material focuses on PostgreSQL permission design:

- one global `admin`
- per-database `rw` / `ro`
- new database setup
- legacy database migration
- SQL explanation, impact scope, cautions, and rollback notes

## Planned Expansion

This skill name is intentionally broader than permissions. Future references can extend it to cover:

- schema and naming conventions
- migration and cutover plans
- backup and restore patterns
- high availability and disaster recovery
- connection management and pooling
- data governance and environment isolation
- engine-specific operating standards for PostgreSQL, MySQL, Oracle, SQL Server, and others

## Workflow

1. Identify the database engine and the problem type first.
2. Identify whether the request is about permissions, migration, governance, schema strategy, backup, HA/DR, or another database topic.
3. Confirm whether the current reference set actually covers that topic.
4. If the topic is covered, keep the output consistent with the selected reference unless the user explicitly asks to change it.
5. If the topic is not yet covered by a built-in reference, say so explicitly and treat the answer as a proposal draft rather than an established standard.
6. Output `rw` and `ro` SQL in separate blocks whenever you generate grants or default privileges.
7. Call out any assumptions that change behavior, especially:
   - which database engine is targeted
   - which schema or namespace is used
   - whether `rw` needs temporary-object capability
   - whether `ro` should have execute permission on routines
   - whether legacy objects are still created by a historical owner
8. After each SQL block, explain three things briefly:
   - what the SQL does
   - what scope it affects now and in the future
   - what operational cautions or rollback concerns matter
9. Use one fixed explanation template for every SQL block.
10. Never execute the SQL produced by this skill. Only provide it as a change proposal or runbook artifact.
11. For any change request, output content in a form suitable for DBW ticket submission.
12. If the user asks for direct execution, refuse direct execution and convert the answer into a DBW-ready change proposal.

## Topic And Engine Selection

- If the request is clearly for PostgreSQL, use the PostgreSQL reference directly.
- If the request targets another engine, say that this skill currently ships with PostgreSQL permission references only and extend the answer carefully as a draft.
- Do not reuse PostgreSQL syntax for MySQL, Oracle, SQL Server, or other engines without adapting the model and syntax.
- If the request is not about permissions, state whether the current skill has a built-in reference for that topic before giving a proposal.

## DBW Enforcement

- Treat DBW as mandatory for production database changes.
- Do not provide instructions that tell the user to execute SQL directly through `psql`, a bastion host, or a GUI client.
- Default deliverable for change requests:
  - DBW 工单标题
  - 数据库类型
  - 实例/数据库
  - 工单类型建议
  - 执行方式建议
  - SQL 正文
  - 影响范围
  - 回滚方案
  - 注意事项
- If the user explicitly asks to execute changes directly, state that this violates the standard and provide DBW-ready content instead.

## New Database Tasks

For a new database:

- create the global `admin` user only once per instance
- create per-database `rw` and `ro` users
- create the database with `admin` as owner
- separate shared initialization SQL from `rw` SQL and `ro` SQL
- add both current-object grants and `ALTER DEFAULT PRIVILEGES`

When writing SQL, keep these sections distinct:

- shared setup
- `rw` grants
- `ro` grants
- `rw` default privileges
- `ro` default privileges

## Legacy Database Tasks

For a legacy database:

- first grant access to existing objects for the new `rw` and `ro` users
- if legacy objects are still created by `legacy` or another historical owner, add default privileges for each real creator
- only after that, plan ownership convergence back to `admin`
- after ownership convergence, switch default privileges to `FOR ROLE admin`

When the legacy database has multiple historical owners, do not collapse them into one statement. Produce one default-privilege block per owner.

## PostgreSQL Rules To Preserve

- `GRANT ON ALL ...` covers existing objects only
- `ALTER DEFAULT PRIVILEGES` covers future objects only
- default privileges are tied to the role that creates the object
- database-level privileges do not replace schema-level or object-level privileges
- business users should not be object owners in this model

## Output Guidelines

- Prefer executable SQL text over prose when the user is asking for implementation, but do not run it.
- Keep `rw` and `ro` SQL split into separate fenced blocks.
- By default, add short explanations for each SQL block, not just the SQL itself.
- For each SQL block, use this fixed template:
  - `SQL解释`
  - `影响范围`
  - `注意事项`
  - `回滚建议`
- State clearly that the SQL is for manual execution or separate change workflow.
- State clearly that the SQL is intended for DBW ticket submission, not direct execution.
- If the user asks for explanation, explain the reason for each block briefly.
- Reuse the naming style already present in the environment unless the user asks to rename it.

Recommended outer structure for change requests:

```md
DBW工单标题：

数据库类型：

实例/数据库：

工单类型建议：

执行方式建议：

SQL：
```sql
...
```

影响范围：

回滚方案：

注意事项：
```

Recommended rendering:

```md
SQL解释：

- ...

影响范围：

- ...

注意事项：

- ...

回滚建议：

- ...
```

## Reference

- DBW SQL change process: [references/dbw-sql-change-workflow.md](./references/dbw-sql-change-workflow.md)
- PostgreSQL model and example SQL: [references/postgresql-admin-rw-ro.md](./references/postgresql-admin-rw-ro.md)
