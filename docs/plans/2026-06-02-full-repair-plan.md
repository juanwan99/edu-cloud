# edu-cloud 全量修复计划（基于深度调查报告 20 条 + 依赖调查）

> 原则：每个修复独立可 revert，先调查再动手，绝不破坏正常功能。
> 依赖调查来源：8 个并行代理实证扫描 + Codex 5 轮交叉验证。

---

## 原报告修正（3 条误报/偏差）

| # | 原判定 | 修正 | 证据 |
|---|--------|------|------|
| F-07 | marking 僵尸模块 | **非僵尸**——13 端点运行中，前端 `marking.js` 调用，与 grading 分工明确（手动 vs AI） | `router.py` 543 行，frontend `getAnswerImageUrl` |
| F-12 | html2canvas 幽灵依赖 | **非幽灵**——`QuestionContentModal.vue:116` 动态 import 使用 | `await import('html2canvas')` |
| F-02 | 学生答题图片通过 /uploads 暴露 | **部分修正**——答题图在 `./storage`（不在 /uploads），但扫描件/题目图/文档页仍暴露 | `storage.py` vs `app.py:358` |

**实际需修复项：17 条**（20 - 3 修正 = 17）

---

## Phase 0：T1 速修（< 1 小时，零风险）

### Fix-A：exam_import 迁移应用（F-20）
**风险**：ZERO — 纯加表，不碰现有数据
**依赖调查**：5 个端点注册但底层表不存在 → 调用即 500
**操作**：`python scripts/db_migrate head`

### Fix-B：.env.example 补完（F-14）
**风险**：ZERO — 文档文件
**操作**：从 `config.py` Settings 类提取全部 35 字段，补注释

### Fix-C：死模型删除（F-17）
**风险**：ZERO — AgentMemory / ScoreSegmentConfig 全库零引用（仅 db_doctor schema 检查）
**操作**：删除 `models/agent_memory.py` + `models/score_segment.py`，更新 `app.py` 导入

### Fix-D：known-pytest-failures 刷新（F-16）
**风险**：ZERO — 文档文件
**操作**：跑全量测试，更新 `.quality/known-pytest-failures.txt`

### Fix-E：覆盖率依赖声明（F-13）
**风险**：ZERO — pyproject.toml dev 依赖
**操作**：加 `pytest-cov` + `diff-cover` 到 `[project.optional-dependencies] dev`

### Fix-F：主服务 systemd 文件（F-15）
**风险**：LOW — 新增文件，不改现有
**依赖调查**：guardian.service 依赖 `edu-cloud.service` 但该文件不在 repo
**操作**：从服务器 `ssh server 'cat /etc/systemd/system/edu-cloud.service'` 拉回纳入版本控制

---

## Phase 1：安全修复（已完成 + 待完成）

### ✅ 已完成（本会话）
- SEC2 时序攻击防护（3 登录端点 dummy bcrypt + 72 字节截断）
- SEC3 模拟登录 scope 全字段归属校验（class_ids / grade_ids / subject_codes）
- 匿名化失败安全哨兵（tool_wrapper except Exception）

### Fix-G：/uploads 鉴权（F-02）
**风险**：MEDIUM — 需确认前端所有消费点
**依赖调查结论**：
- `/uploads/questions/*` — 题目图片，前端 `<img>` 直接引用
- `/uploads/doc-pages/*` — 已有 proxy 端点 `/card/doc-pages-image`
- `/uploads/{school_id}/scan-input/*` — 已有 proxy 端点 `/scan/scan-image`
- 学生答题图在 `./storage`，不受影响

**修复方案（两步）**：
1. **Step 1**：为 `/uploads/questions/*` 新建 proxy 端点 `GET /api/v1/exam/question-image`（带 auth）
2. **Step 2**：确认前端全部切到 proxy 端点后，移除 `app.mount("/uploads", StaticFiles(...))`
3. **不能一步到位**——先加 proxy 再验证前端，最后删 mount

### Fix-H：CSP header（F-19）
**风险**：LOW — 纯增加响应头
**操作**：在 `app.py` 中间件加 `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'`
**注意**：需在浏览器实测确认不阻断正常功能（Vue 的 inline style 需要 `'unsafe-inline'`）

### Fix-I：Token 策略优化（F-03 + F-04）
**风险**：MEDIUM — 需产品决策
**依赖调查结论**（前轮）：
- 简单 fail-closed = Redis 故障时全员锁门（不可接受）
- JWT 共享 Redis（DB 0）与 arq worker，故障影响面大
- 进程内 LRU 缓存只覆盖同进程撤销（多进程限制已知）

**修复方案**：
1. 连接池替代每次 `from_url()`（降低开销）
2. 进程内 LRU 缓存写入撤销记录（同进程可靠，跨进程仍依赖 Redis）
3. **降低 JWT 有效期到 4 小时**（缩小 fail-open 窗口，需确认用户体验）
4. 加 refresh token 机制（可选，补偿缩短的有效期）

---

## Phase 2：数据完整性（T3 级，需设计审查）

### Fix-J：SQLite FK 启用（F-01）
**风险**：HIGH — 调查确认直接开 PRAGMA 会炸掉 64+ 删除操作
**依赖调查结论**：
- 161 FK 全部 NO ACTION（0 CASCADE、0 RESTRICT 声明）
- 关键删除路径：exam(14 子表) / student(8 子表) / question(9 子表) / class(10 子表)
- `exam/service.py:119-124` 先删 Question → 删 Subject → 删 Exam，FK 开启后 Question 删不掉（有 student_answers）
- `knowledge_tree/sync_service.py:195-197` 已意识到问题——注释说"直接 DELETE ALL nodes 会触发 FK violation"

**修复方案（三阶段，不可跳步）**：

**Stage 1 — 审计（不改代码）**：
1. 在生产 DB 跑孤儿记录检测 SQL（列出所有 FK 违反）
2. 为每个 FK 标注期望语义：CASCADE / RESTRICT / SET NULL
3. 输出 FK 策略表

**Stage 2 — 迁移准备**：
1. 写 Alembic 迁移批量添加 `ondelete=` 声明
2. 修改 64+ 删除操作为"先删子后删父"或用 CASCADE
3. 清理孤儿数据

**Stage 3 — 启用 PRAGMA**：
1. `database.py` 添加 `@event.listens_for(engine.sync_engine, "connect")` 设置 `PRAGMA foreign_keys=ON`
2. `alembic/env.py` 同步添加
3. 全量测试验证

### Fix-K：租户隔离 enforce（F-05）
**风险**：HIGH — 调查确认直接切 enforce 会破坏 seed 脚本、worker、pipeline
**依赖调查结论**（前轮）：
- `tenant_bypass` 定义了但全库零使用
- 36 个表受影响
- 登录路径安全（tenant=None 时 listener 跳过）
- JointExam 表无 school_id（安全）

**修复方案（同 Fix-J 三阶段）**：
1. 先给 seed/worker/pipeline 的跨校查询标记 `tenant_bypass`
2. 收集 audit 日志确认所有合法跨校查询已标记
3. 切 enforce + 全量测试

---

## Phase 3：代码结构优化（T2 级，渐进重构）

### Fix-L：N+1 查询修复（F-11 剩余）
**风险**：LOW-MEDIUM — 纯查询优化，不改数据

| 位置 | 模式 | 修复 |
|------|------|------|
| `homework/service.py:337-346` | per-student 循环查 HomeworkSubmission | 批量 `WHERE student_id IN (...)` |
| `pipeline/service.py:520-526` | per-question 循环查 KnowledgePoint | 批量 `WHERE question_id IN (...)` |
| `marking/scorer.py:223,328,452` | per-child-answer 循环查 GradingResult | 批量 `WHERE answer_id IN (...)` |

### Fix-M：大文件拆分（F-08 + F-09）
**风险**：MEDIUM — 纯重构，不改行为
**需独立 design + plan + review 流程**

### Fix-N：向后兼容垫片（F-18）
**风险**：HIGH — 38 个垫片被 48+ 测试文件和 scripts 引用
**依赖调查**：全部垫片都在被使用，不能直接删
**方案**：渐进迁移——新代码直接 import modules，旧引用逐步更新，最后删垫片
**不急**——垫片不影响功能，只是代码组织问题

---

## 不修的项目

| # | 原发现 | 决定 | 理由 |
|---|--------|------|------|
| F-06 | AI 会话部分纯内存 | **WONTFIX** | confirmation/artifact 丢失可接受（重启后用户重发即可），消息已持久化 |
| F-07 | marking 僵尸 | **不是问题** | 调查确认 marking 与 grading 分工明确 |
| F-10 | 零 relationship() | **WONTFIX** | 设计选择，显式查询可控性更好 |
| F-12 | html2canvas 幽灵 | **不是问题** | 调查确认 `QuestionContentModal.vue` 在用 |

---

## 执行优先级汇总

```
Phase 0（T1，本周内）:
  Fix-A(迁移) → Fix-B(env) → Fix-C(死模型) → Fix-D(failures) → Fix-E(cov) → Fix-F(systemd)
  ↓ 全量 pytest 回归

Phase 1（安全，1-2 周）:
  Fix-G(/uploads 鉴权，两步) → Fix-H(CSP) → Fix-I(token 策略)
  ↓ Codex 审查 + 浏览器验证

Phase 2（数据完整性，2-4 周，T3 流程）:
  Fix-J(FK 三阶段) → Fix-K(租户 enforce)
  ↓ design + plan + codex-review gate

Phase 3（代码结构，按需）:
  Fix-L(N+1) → Fix-M(大文件拆分) → Fix-N(垫片迁移)
```

## 铁律

1. **每个 Fix 独立 commit**，可单独 revert
2. **Phase 2 必须走 T3 流程**（design → plan → codex-review gate）
3. **FK 启用和 tenant enforce 不可在同一批次**
4. **不碰 marking 模块**（调查确认不是问题）
5. **不删 html2canvas**（调查确认在用）
6. **垫片删除必须先确认所有引用已迁移**
