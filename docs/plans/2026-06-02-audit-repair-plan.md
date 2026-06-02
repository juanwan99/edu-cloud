# edu-cloud 审计修复计划（初稿）

> 原则：每个修复独立可 revert，不改变正常路径行为，先测后改。

---

## Phase 1：安全修复（纯增量，零行为变化正常路径）

### Fix-1: 登录时序攻击防护（SEC2）
**风险**：LOW — 仅在用户不存在时增加一次 bcrypt 空跑，不影响成功登录

**依赖调查结论**：
- 两个登录端点受影响：`api/auth.py:84` 和 `api/compat_router.py:65`
- `conduct/parent_service.py` 有独立的家长登录（同样模式，一并修）
- `user.verify_password()` 用 bcrypt（`models/user.py:35-38`）
- 现有测试只检查 status code，不量时间，不会被破坏

**修复方式**：用户不存在时跑一次 `bcrypt.checkpw` 空 hash，使两条路径耗时一致

**修改文件**：
1. `src/edu_cloud/api/auth.py:84-87` — 登录端点
2. `src/edu_cloud/api/compat_router.py:62-65` — 兼容登录端点
3. `src/edu_cloud/modules/conduct/parent_service.py` — 家长登录

**验证**：全量 pytest 回归 + 手动测两端点响应时间无显著差异

---

### Fix-2: 模拟登录 scope 补全校验（SEC3）
**风险**：LOW — 纯增加验证，只拒绝非法输入，不影响合法使用

**依赖调查结论**：
- `grade_ids` 和 `subject_codes` 都缺学校归属校验
- Grade 模型有 `school_id` FK（`models/grade.py:17`），可校验
- 下游消费点：`ai/data_scope.py:153`、`api/permissions.py:55` 的 `grade_predicate()`
- 现有测试只测 "缺字段→422"，不测归属，不会被破坏
- subject_codes 是枚举字符串（语文/数学等），无 school_id FK，暂不校验

**修复方式**：在 `impersonate.py:103` 后面加 grade_ids 归属检查（与 class_ids 同模式）

**修改文件**：
1. `src/edu_cloud/api/impersonate.py:91-117` — 在 class_ids 校验块后加 grade_ids 校验块

**验证**：全量 pytest + 新增测试验证跨校 grade_ids 被拒绝

---

### Fix-3: tool_wrapper 匿名化失败不静默（S5 安全子项）
**风险**：LOW — 仅加 logger.error + 返回安全值，不改正常路径

**依赖调查结论**：
- `ai/engine/tool_wrapper.py:106` — 匿名化/artifact 处理失败时 `except: pass`
- 失败后原始未脱敏数据被返回（隐私泄漏风险）
- 应 log error 并返回安全哨兵值（空字符串或错误标记）

**修改文件**：
1. `src/edu_cloud/ai/engine/tool_wrapper.py:106` — 加 logger.error + 安全回退

**验证**：AI 工具相关测试回归

---

## Phase 2：可靠性修复（渐进增强，有行为约束）

### Fix-4: Token 撤销进程内缓存兜底（SEC1）
**风险**：MEDIUM — 引入新组件（LRU 缓存），但 fail-open 行为不变

**依赖调查结论**（关键）：
- **不能简单改 fail-closed**：Redis 故障时 `is_revoked()` 返回 True → 全员 401 锁门
- Redis 同时服务 auth + arq worker 队列（同实例 DB 0）
- JWT 签名校验在 `is_revoked()` 之前（`core/auth.py:52-55`）
- 启动时 Redis 必须可用（`startup_checks.py:46`），运行时才降级
- 现有测试 `tests/test_core/test_token_store.py` 测的就是 fail-open 行为

**修复方式（三层策略）**：
1. 新建全局 Redis 连接池（替代每次 `from_url()`），降低连接开销
2. 撤销操作成功时同步写入进程内 LRU 缓存（TTL = token 有效期）
3. `is_revoked()` 查询顺序：进程内缓存 → Redis → 异常时查缓存（不再裸 False）
4. 进程内缓存命中 = 已撤销（确定性结论）；缓存未命中 + Redis 异常 = 仍 fail-open（保守）

**效果**：只要撤销操作成功写入过缓存，即使 Redis 后续故障，已撤销的 token 仍被拦截。未经本进程撤销的 token 在 Redis 故障时仍 fail-open（可接受——跨进程撤销场景极少）。

**修改文件**：
1. `src/edu_cloud/core/token_store.py` — 全部重写（连接池 + LRU 缓存）
2. `tests/test_core/test_token_store.py` — 更新测试

**验证**：全量 pytest + 手动测 Redis 故障场景

---

### Fix-5: 异常吞没批量加日志（S5 安全子项外的 16 处）
**风险**：LOW — 纯加 logger.warning/debug，零行为变化

**依赖调查结论**：36 处分三类：
- 10 处 INTENTIONAL → 不动
- 16 处 SAFE TO LOG → 加 warning（本 Fix）
- 9 处 NEEDS DEEPER FIX → 逐个评估（不在本轮）

**注意事项**：
- `scan/pipeline_service.py:401` 在批量场景可能高频触发 → 用 `logger.debug` 而非 warning
- `json_parser.py:122,202` 是紧循环 → 不加日志（INTENTIONAL 分类）
- `client_logs.py:52` → 用 `logger.debug`（JWT 解码失败是正常场景）

**修改文件**（16 个）：
1. `ai/engine/tools/actions.py:98`
2. `modules/grading/router.py:166`
3. `modules/grading/router.py:707`
4. `modules/knowledge_tree/detail_service.py:116`
5. `modules/knowledge_tree/course_map_service.py:141`
6. `modules/knowledge_tree/course_map_service.py:400`
7. `modules/scan/pipeline_service.py:401` → debug 级别
8. `modules/scan/cv_detect_router.py:110`
9. `modules/scan/auto_detect_cv.py:438`
10. `modules/card/parser/answer_standardizer.py:210`
11. `modules/card/parser/answer_standardizer.py:227` → error 级别（最终失败）
12. `modules/scan/router.py:88`
13. `modules/scan/router.py:140`
14. `modules/scan/router.py:170`
15. `modules/card/layout_helpers.py:369`
16. `api/client_logs.py:52` → debug 级别

**验证**：全量 pytest 回归

---

## Phase 3：结构性修复（风险较高，需单独评估）

### Fix-6: 租户隔离走向 enforce（S1）
**风险**：HIGH — 调查结论明确：**当前不能直接切 enforce**

**依赖调查结论**（关键）：
- 36 个表有 school_id（被 audit listener 覆盖）
- `tenant_bypass` 逃逸机制已定义（`database.py:44`）但全代码库**零使用**
- 直接切 enforce 会破坏：seed 脚本、worker upsert、pipeline ON CONFLICT、部分 analytics
- JointExam 表无 school_id（安全，但 JointExamParticipant 有）
- 登录路径安全（tenant=None 时 listener 跳过）

**本轮只做准备工作**（不切 enforce）：
1. 在 seed/migration 脚本中标记 `tenant_bypass`
2. 在 worker/pipeline 的跨学校查询中标记 `tenant_bypass`
3. 在测试中验证 bypass 机制生效
4. 收集一段时间的 audit 日志，确认所有合法跨校查询都已标记
5. 切 enforce 作为独立任务（需要完整回归测试 + 灰度上线）

**本轮修改文件**：无代码修改，只做调查记录。切 enforce 另开 task。

---

### Fix-7: FK ondelete 声明（S2）
**风险**：MEDIUM — 需逐表审计删除语义，Alembic 迁移

**本轮只做第一步**：审计 197 个 FK 的期望 ondelete 策略，输出 FK 策略表。
实际迁移作为独立任务（涉及 52 个 migration 文件的增量迁移）。

---

### Fix-8: 大文件拆分（S4）
**风险**：MEDIUM — 纯重构，不改行为但改文件结构

**本轮不做**。grading/router.py 和 workers/grading.py 的拆分属于重构，
需要独立的 design + plan + review 流程。记录为后续任务。

---

## 执行顺序与 Gate

```
Phase 1（安全修复，可立即执行）:
  Fix-1 (SEC2 时序) → Fix-2 (SEC3 scope) → Fix-3 (tool_wrapper)
  ↓ 全量 pytest 基线对比
  
Phase 2（可靠性，需更多测试）:
  Fix-4 (token 缓存) → Fix-5 (异常日志)
  ↓ 全量 pytest + Redis 故障手动测试

Phase 3（结构性，本轮只调查不动代码）:
  Fix-6 调查 → Fix-7 审计 → Fix-8 记录
```

## 铁律

1. **每个 Fix 独立 commit**，可单独 revert
2. **先跑基线测试，记录 passed/failed/skipped 数字**
3. **每个 Fix 完成后重跑全量测试，对比基线**
4. **不改正常路径的返回值/状态码/数据结构**
5. **不新建文件除非必要**（优先改现有文件）
6. **不碰 Phase 3 的代码**（本轮只记录）
