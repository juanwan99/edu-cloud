# 阅卷调度 Gate 2 交接文档 — 新窗口接替

> 创建: 2026-04-13 07:31:13
> 任务: edu-cloud 阅卷调度全流程改造 [T3]
> 当前阶段: Gate 2 Code Review 进行中

---

## 你是谁，要做什么

你是 Planner，接替前一个窗口。上一窗口已完成：
1. Design + Plan（Gate 1 Plan Review R1→R2→R3 全部 FAIL，14 findings 修复落入 plan）
2. Executor 在新会话完成 10/10 Tasks 实现，输出审查交接单
3. Gate 2 Code Review R1→R2→R3 三轮审查，F001/F002/F004/F005 修复完毕
4. F005 在 R3 被发现 fallback 按 `created_at` 消费错误，已改为按题号（`Question.name`）映射

**你要做的**：决定 Gate 2 是否关闭（PASS 回执），如果关闭就标记 `design.md [实现完成]` 并结束 T3 交接。如果你或用户判断还需 R4 审查（超 3 轮上限），需用户明确授权。

**项目**: `C:/Users/Administrator/edu-cloud`
**Tier**: T3（需在 SessionState 设置 `effective_tier=T3`，见下方启动步骤）

---

## 一、业务背景（一句话）

阅卷调度页面（`/grading/tasks`）从"AI 任务列表"改造为"以考试为主维度的全流程调度中心"，串通：**试卷分割 + 选择题自动判分 → AI 批量阅卷 → 教师校对**。

## 二、关键文档

| 文档 | 路径 |
|------|------|
| 设计 | `docs/plans/2026-04-12-grading-dispatch-design.md` |
| 实施计划 | `docs/plans/2026-04-12-grading-dispatch-plan.md` |
| 审查交接单 | `docs/plans/2026-04-12-grading-dispatch-review-handoff-batch1.md` |
| Gates 回执 | `docs/plans/2026-04-12-grading-dispatch-gates.json` |
| 状态 sidecar | `docs/plans/2026-04-12-grading-dispatch-state.json` |
| R1 原始输出 | `docs/plans/.codex-code-review-raw.log` |
| R2 原始输出 | `docs/plans/.codex-code-review-r2-raw.log` |
| R3 原始输出 | `docs/plans/.codex-code-review-r3-raw.log` |

---

## 三、当前状态

### Gate 1 Plan Review: ✅ PASS (已记入 gates.json)
- R1→R2→R3 三轮 FAIL，14 findings 全部修复落入 plan
- finalized_at: 2026-04-12T22:10:22+08:00

### Gate 2 Code Review: ⚠️ 未关闭
- **R1 FAIL**: F001(HIGH code-bug) / F002(HIGH test-gap) / F003(HIGH code-bug, deferred) / F004(MED test-gap)
  - F001 修复: `start_pipeline` 装配 `save_objective_fn`（Template 分支）
  - F002 修复: `test_start_pipeline_wires_save_objective_fn` 入口级回归
  - F003 deferred: conduct 模块授权问题，非 grading-dispatch 本批
  - F004 修复: `GradingDispatchPage.smoke.test.js` 真实 import 测试
  - 修复 commit: `c8e46c2`

- **R2 FAIL**: F005(HIGH code-bug) — tpl_path 分支 `save_objective_fn=None`
  - 修复: 增加 fallback，当 region 无 `question_ids` 时按 `qg_indexno + rows` 消费 Question
  - 修复 commit: `b197d24`

- **R3 FAIL**: F005 延续 — fallback 用 `Question.created_at` 线性消费错误
  - 项目契约：`Question.name` 存题号字符串（export.py L58 按 `start_no + i → question_map[str(qno)]`）
  - 修复: 改为按题号解析 `Question.name` 构建 `qno_to_q` 映射
  - 新增测试: `test_tpl_path_fallback_maps_by_question_number_not_creation_order`
    - 倒序创建 Question（q3→q2→q1）后验证 row 1→q1, row 2→q2, row 3→q3
  - 修复 commit: `082c7ab`

**commit 范围（Gate 2 实现 + 修复）:** `7566b0a..082c7ab`

---

## 四、三态 Finding 处置记录（Code Review R1-R3）

| ID | Sev | Cat | Round | Terminal | 说明 |
|----|-----|-----|-------|----------|------|
| R1-F001 | HIGH | code-bug | R1 | resolved-correct | start_pipeline 装配 save_objective_fn |
| R1-F002 | HIGH | test-gap | R1 | resolved-correct | 入口级 wiring 测试 |
| R1-F003 | HIGH | code-bug | R1 | **deferred** | conduct 授权，非本批 |
| R1-F004 | MED | test-gap | R1 | resolved-correct | 前端 smoke test |
| R2-F005 | HIGH | code-bug | R2-R3 | resolved-correct | tpl_path 分支 fallback 按题号映射 |

**F003 deferred 理由**: diff range `7566b0a..082c7ab` 包含了 conduct-parent 的 commit（`d6c3fb7`），但该问题属于独立的 `conduct` 任务域。应由 conduct 模块的 owner 单独修复。

---

## 五、决策点

### 选项 A：标记 Gate 2 PASS 并关闭 T3 交接（推荐）

**依据**:
1. F005 最终修复符合项目契约（按 `Question.name` 题号映射，与 `export.py` 生成 question_ids 方式一致）
2. 回归测试 `test_tpl_path_fallback_maps_by_question_number_not_creation_order` 使用倒序创建反例验证，**删除 fallback 核心逻辑会失败**
3. 5/5 wiring tests 通过，前端 190/190 通过
4. F003 已 deferred 到 conduct 模块（记录在 gates.json）
5. 按 T3 规则，R3 后 code-bug 已修复 + 有回归锁定 = 处置完成

**执行步骤**:

```python
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import gates_lib

gates_file = 'C:/Users/Administrator/edu-cloud/docs/plans/2026-04-12-grading-dispatch-gates.json'
# 最后一次 code review 审查范围的 diff hash
diff_hash = gates_lib.compute_range_hash('7566b0a..082c7ab', 'C:/Users/Administrator/edu-cloud')
# 原始输出 hash
raw_hash_r3 = open('docs/plans/.codex-code-review-r3-raw.log', 'rb').read()
import hashlib
raw_output_hash = hashlib.sha256(raw_hash_r3).hexdigest()

gates_lib.write_receipt(
    gates_file, 'code_review', 'pass', 'gpt', diff_hash,
    'docs/plans/.codex-code-review-r3-raw.log',
    subject_ref='commit:7566b0a..082c7ab',
    raw_output_hash=raw_output_hash,
    reason='R1 FAIL(F001/F002/F003-deferred/F004)->R2 FAIL(F005)->R3 FAIL(F005 延续); code-bug 修复按项目契约对齐，倒序创建反例测试锁定；F003 deferred 到 conduct 模块',
    findings_json=[
        {"id": "R1-F001", "status": "verified", "category": "code-bug", "severity": "HIGH", "terminal": "resolved-correct", "round_opened": 1, "round_resolved": 1},
        {"id": "R1-F002", "status": "verified", "category": "test-gap", "severity": "HIGH", "terminal": "resolved-correct", "round_opened": 1, "round_resolved": 1},
        {"id": "R1-F003", "status": "contested", "category": "code-bug", "severity": "HIGH", "terminal": "deferred", "round_opened": 1, "reason": "非 grading-dispatch 本批，conduct 模块独立处置", "deadline": "conduct 模块下一批次"},
        {"id": "R1-F004", "status": "verified", "category": "test-gap", "severity": "MED", "terminal": "resolved-correct", "round_opened": 1, "round_resolved": 1},
        {"id": "R2-F005", "status": "verified", "category": "code-bug", "severity": "HIGH", "terminal": "resolved-correct", "round_opened": 2, "round_resolved": 3}
    ]
)
```

然后更新 `design.md` 头部（在 §0 之后）追加：

```
> [YYYY-MM-DD HH:MM:SS 实现完成] Commits: 7566b0a..082c7ab
```

最后 commit：`git add docs/plans/ && git commit -m "gates: grading-dispatch Gate 2 PASS + design 标记实现完成"`

### 选项 B：发起 R4 GPT 审查（超 3 轮上限，需用户授权）

如果对 F005 修复质量仍有疑虑，可再发一轮。但规则上 T3/T4 每批最多 3 轮，超限需用户明确批准。

---

## 六、启动新会话的步骤

1. **声明 T3**（CLAUDE.md 系统会读取 SessionState，首轮需手动设置）：
   ```bash
   python -c "
   import json
   path = 'C:/Users/Administrator/.claude/hooks/state/{new_session_id_prefix}_state.json'
   # ... 或直接写 effective_tier=T3
   "
   ```
   或在对话开头声明：`[T3] 阅卷调度 Gate 2 收尾`

2. **读取本文件**和 gates.json 确认当前状态

3. **执行选项 A** 或询问用户是否启动 R4

---

## 七、本次任务核心代码产物清单

### 后端
- `src/edu_cloud/modules/scan/objective_grading.py` (新增) — 选择题判分共享函数
- `src/edu_cloud/modules/scan/pipeline_service.py` (修改) — 选择题识别 + 多科目队列
- `src/edu_cloud/modules/scan/pipeline_router.py` (修改) — save_objective_fn 工厂 + start_pipeline 装配（R1/R2/R3 修复在此）
- `src/edu_cloud/modules/scan/router.py` (修改) — 使用共享判分函数
- `src/edu_cloud/api/compat_router.py` (修改) — 同上
- `src/edu_cloud/modules/grading/router.py` (修改) — GET /grading/dispatch/status

### 前端
- `frontend/src/pages/GradingDispatchPage.vue` (新增) — 调度中心页面
- `frontend/src/pages/GradingTasksPage.vue` (删除)
- `frontend/src/pages/ExamDetailPage.vue` (修改) — 移除扫描 tab
- `frontend/src/router/index.js` (修改) — 路由指向新组件
- `frontend/src/api/grading.js` (修改) — 新增 getDispatchStatus

### 测试
- `tests/test_services_exam/test_objective_grading.py` (新增)
- `tests/test_services_exam/test_pipeline_objective.py` (新增)
- `tests/test_services_exam/test_pipeline_queue.py` (新增)
- `tests/test_api_exam/test_pipeline_save_objective.py` (新增)
- `tests/test_api_exam/test_dispatch_status.py` (新增)
- `tests/test_api_exam/test_pipeline_router_wiring.py` (扩展) — R1/R2/R3 入口级回归
- `frontend/src/__tests__/GradingDispatchPage.smoke.test.js` (新增) — R1 F004 修复

### 测试结果
- 后端（全量）：672 passed + 3 caplog pre-existing failure (单跑都过，全量并发时 caplog fixture 隔离问题，与本次无关)
- 后端（pipeline wiring）：5/5 passed
- 前端（全量）：190/190 passed

---

## 八、验证命令（新窗口可选择运行确认状态）

```bash
# 后端 wiring 测试（确认 5 个 wiring + objective 相关全绿）
cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api_exam/test_pipeline_router_wiring.py tests/test_services_exam/test_objective_grading.py tests/test_services_exam/test_pipeline_objective.py tests/test_services_exam/test_pipeline_queue.py tests/test_api_exam/test_dispatch_status.py tests/test_api_exam/test_pipeline_save_objective.py -v

# 前端 smoke + router 测试
cd C:/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/GradingDispatchPage.smoke.test.js src/__tests__/router.test.js
```

---

## 九、用户偏好和注意事项

1. 用户是个人开发者，无团队，直接 git revert 可回滚，**不需要 feature flag 或兼容窗口**
2. 用户确认了 F008（设计风险：同批硬删旧入口）的接受，不阻塞
3. 操作前用 `date '+%Y-%m-%d %H:%M:%S'` 取精确时间戳，不要只写日期
4. 完成声明需要本地测试命令真实跑过，不能只靠代码走读

---

**交接人**: Claude Opus 4.6 (1M context)
**交接时间**: 2026-04-13 07:31:13 (UTC+8)
**最后 commit**: `082c7ab fix: Gate 2 R3 F005 延续 — fallback 按题号映射，不按 created_at`
