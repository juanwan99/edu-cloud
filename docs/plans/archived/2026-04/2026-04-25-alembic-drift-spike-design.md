---
baseline_command: "cd ~/projects/edu-cloud && uv run python -m pytest --collect-only -q"
baseline_verified_at: "2026-04-25 00:40"
baseline_count: 2187
---

# T3-02 Alembic-ORM 列级 drift spike + 修复 design

<!-- key-start -->
## 0. 任务卡

| 项 | 值 |
|---|---|
| Topic | alembic-drift-spike |
| 父任务 | edu-deep-scan（D-03，见 `2026-04-24-edu-deep-scan-design.md` §11.1） |
| 触发 | 用户裁定（2026-04-25）"做 B" 起 T3 plan；codex 共识 D-02 > D-01 但 D-03 spike 是 D-02 前置（schema 稳后再改权限 safer） |
| 范围 | edu-cloud 一仓内的列级 ORM-DB drift 检测 + 增量 alembic migration 修复 |
| 形态 | brainstorming 产物（design 草稿）；**等用户 approve 后** writing-plans → 独立新会话 executing |
| 自治边界 | 本会话仅写 design，**不写 plan，不执行 spike** |
| 证据纪律 | 全部 D-03 上承 edu-deep-scan §2.5 unknown U-01 |
<!-- key-end -->

### 0.1 现状证据回顾（已 verify）

- **89 ORM `__tablename__`** vs **DB 90 表**（含 alembic_version → 89 业务表）→ **表级完全对齐**
- **alembic head in db**: `e241e1568792`
- **alembic/versions/ 文件数**: **31**（migration 集合）
- **create_all 4 处调用**：`api/app.py:70`、`data/seed_school.py:431`、`data/import_exam_xlsx.py:326`、`data/seed_highschool_supplement.py:540`
- **样例 PRAGMA**: `users` 表 DB 侧 19 列（username/display_name/hashed_password/is_active/phone/email/last_login_at/id/created_at/updated_at + 9 其他）

### 0.2 待验证 unknown（本 design spike 的目标）

- U-01.1 哪些表存在列级 drift（ORM 比 DB 多 / 少 / 类型不符）
- U-01.2 drift 是否会让 `alembic upgrade head` 在干净库上失败
- U-01.3 create_all 与 alembic 之间的 schema 决定权冲突点

---

## 1. 设计目标

**核心**：写一个**幂等可重跑**的 drift 检测脚本 → 输出全量 drift 报告 → 用户审 → 按需写增量 alembic migration → 修复后重跑验证。

**非目标**（本 design 范围外）：
- ❌ 移除 create_all（涉及 dev seed 流程，需独立 T3-02b）
- ❌ 重写 ORM 模型
- ❌ 数据迁移（drift 修复仅改 schema 不改数据；如需数据迁移由后续 plan 单独决策）

---

## 2. 检测器架构（spike 阶段产物）

### 2.1 输入

- ORM 侧：通过 `from edu_cloud.models.base import Base; Base.metadata.tables` 获取全 89 表的 `Column` 定义
- DB 侧：`PRAGMA table_info(<tname>)` 列出实际列

### 2.2 检测维度

| 维度 | 检测 | 输出 |
|---|---|---|
| **table_only_in_orm** | ORM 有 / DB 无 | 表级 drift（已验证为 0，但保留检测） |
| **table_only_in_db** | DB 有 / ORM 无 | 表级 drift（已验证 alembic_version 是唯一例外） |
| **column_only_in_orm** | 表共有但列只在 ORM | 候选 drift：ORM 加了列但无 migration |
| **column_only_in_db** | 表共有但列只在 DB | 候选 drift：DB 有列但 ORM 删了（应 deprecate）|
| **column_type_mismatch** | 列同名但类型不一致 | 候选 drift：ORM 改了类型未 migration |
| **column_nullable_mismatch** | 列同名但 nullable 不同 | 候选 drift：约束变更未 migration |
| **column_default_mismatch** | server_default 不同 | 候选 drift（信息级，非阻断）|

### 2.3 输出格式

```python
# scripts/check_alembic_drift.py
{
  "summary": {
    "total_tables_orm": 89,
    "total_tables_db": 90,
    "tables_aligned": 89,
    "drift_count_by_type": {
      "column_only_in_orm": int,
      "column_only_in_db": int,
      "column_type_mismatch": int,
      "column_nullable_mismatch": int,
      "column_default_mismatch": int,
    }
  },
  "drifts": [
    {
      "table": "users",
      "type": "column_only_in_orm",
      "column": "X",
      "orm_def": {"type": "VARCHAR(50)", "nullable": false, "default": null},
      "db_def": null,
      "severity": "blocking" | "info",
      "suggestion": "alembic revision -m 'add users.X column'"
    }
  ]
}
```

落盘：`~/projects/edu-cloud/docs/plans/2026-04-25-alembic-drift-spike-report.json`

### 2.4 spike 命令

```bash
cd ~/projects/edu-cloud && uv run python scripts/check_alembic_drift.py \
  --db edu_cloud.db --output docs/plans/2026-04-25-alembic-drift-spike-report.json
```

---

## 3. 修复策略

### 3.1 按 drift 类型决定修复方式

| drift 类型 | 修复 | 风险 |
|---|---|---|
| **column_only_in_orm**（ORM 比 DB 多） | `alembic revision -m "..." --autogenerate` 生成 add column migration | 低（增量） |
| **column_only_in_db**（DB 比 ORM 多） | 决策：保留（DB 列被业务用但 ORM 漏映射？）/ 或 drop（确认废弃后）| 中 |
| **column_type_mismatch** | 评估是否 SQLite 兼容（如 VARCHAR(50) vs VARCHAR(100)）；非破坏性可 alter | 中-高 |
| **column_nullable_mismatch** | 检查现有数据是否有 NULL；如有需先回填再改 | 高 |
| **server_default_mismatch** | 通常 info 级，不需修；除非被业务依赖 | 低 |

### 3.2 验证步骤

每个 drift migration 完成后：
1. `cd ~/projects/edu-cloud && uv run alembic upgrade head` 干净库测试
2. `cd ~/projects/edu-cloud && uv run python -m pytest tests/test_alembic*.py -v`
3. 重跑 spike 脚本，确认该 drift 已消失

### 3.3 全量验收

- 全部 drift 修复后：
  - **drift_count_by_type 全为 0**
  - `alembic upgrade head` 在 dev / staging / prod 干净库测试通过
  - 全量 pytest 维持 baseline（≥ 2187 passed）

---

## 4. create_all 4 处调用的处理

**本 design 不动它们**（理由）：
- `app.py:70` 的 lifespan create_all 是 dev 加速启动手段，移除涉及 dev seed 流程改造
- 3 处 seed 脚本是离线运维工具，移除涉及部署 SOP

**但本 spike 必须**：
- 在脚本头部加 docstring 警示"create_all 与 alembic 并存是已知风险"
- 在 design §6 推后续 T3-02b：移除 create_all（独立任务）

---

## 5. 风险与边界

### 5.1 数据风险
- spike 脚本只读（PRAGMA + ORM metadata 读取，不写 DB）→ 0 风险
- 修复阶段：写 alembic migration → 在 dev 库先跑 → 通过后才上 staging/prod

### 5.2 工具链
- 用 edu-cloud `.venv` 已装的 sqlalchemy + alembic
- 不引入新依赖

### 5.3 范围界限（unknown 推用户裁定）
- `unknown: column_only_in_db 类型 drift（DB 多 ORM 无映射）的处置`——保留 vs drop 由用户读 spike 报告后决定，本 design 不预设
- `unknown: 是否 worktree edu-cloud-t2 / edu-cloud-w2 也受影响`——w2 无 db，t2 db 状态待 spike 时再查

---

## 6. 实施步骤（写 plan 用，本 design 不展开 plan 细节）

| 阶段 | 动作 | 产物 |
|---|---|---|
| **S1** spike 脚本编写 | `scripts/check_alembic_drift.py`（约 100-150 LOC） | 脚本入 git |
| **S2** spike 跑 | dev db 上跑脚本 | drift 报告 JSON 入 docs/plans/ |
| **S3** 用户审报告 | 用户读报告，决定每个 drift 处置 | 标注表 |
| **S4** 增量 migration | 按 §3 策略写 alembic migration | migration 文件入 alembic/versions/ |
| **S5** 验证 | clean db 跑 upgrade head + 全量 pytest | 测试 baseline 维持 |
| **S6** 推后续 T3-02b | 单独提案：移除 create_all → alembic-only | 新 design |

---

## 7. 验收标准

- [ ] spike 脚本入 git；可幂等重跑
- [ ] drift 报告 JSON 出来后，用户审过并标注每个 drift 处置
- [ ] 所有 blocking drift 都有对应 alembic migration
- [ ] `alembic upgrade head` 在干净 dev db 上通过（无报错）
- [ ] 全量 pytest ≥ 2187 passed（baseline 维持，从今晚 P7 实测的 collect 数）
- [ ] 重跑 spike 脚本 → drift_count_by_type 全为 0

---

## 8. 与 edu-deep-scan design 的对应

- 解决 `edu-deep-scan §11.1 D-03` Alembic-ORM 列级 drift 未验证
- 解决 `§11.5 U-01` Alembic-ORM 列级 drift 具体分布
- 是 D-02 MANAGE_GRADING 回收（codex 优先）的**前置条件**（schema 稳后改权限更安全）
- 不解决 D-04 docker-compose 冲突 / D-05 db.bak / 49 空表（D-13）等其他 drift 类问题——这些是独立 T3 plan

---

## 9. 等用户 approve 后才进 writing-plans

按 brainstorming HARD-GATE：

> "Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it."

**用户起床后**：
- 看本 design
- 回复 `T3-02 approve` → 我（或新会话 Claude）走 writing-plans 出 plan.md
- 实际 spike 执行**必须独立新会话**（CLAUDE.md "T3/T4 设计→计划→独立新会话执行"）

---

**T3-02 design 草稿 v0 完 @ 2026-04-25 00:42**

**等 user approve 才进 writing-plans 阶段。本会话不执行任何 spike。**
