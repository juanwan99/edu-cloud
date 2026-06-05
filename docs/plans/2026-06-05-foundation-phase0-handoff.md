# edu-cloud 地基治理 Phase 0/0.5 接手交接卡（2026-06-05）

> 给新 Claude/Codex 窗口阅读。  
> 项目：`/home/ops/projects/edu-cloud`  
> 分支：`feat/module-governance-repair`  
> Phase -1 收口基线 HEAD：`ab4c740`  
> 当前状态：Phase -1 已收口完成，工作区在写入本交接卡前为 clean，下一步进入 Phase 0 / Phase 0.5。

---

## 1. 一句话任务

继续执行地基治理总纲：先冻结当前治理基线（Phase 0），再做模块语义统一（Phase 0.5），为后续 Portal 首页聚合合同落地和成熟门户功能吸收打地基。

不要从 Portal 功能实现直接开始。当前正确入口是 Phase 0 / Phase 0.5。

---

## 2. 必读文档

请先按顺序阅读：

1. `docs/plans/2026-06-05-foundation-governance-master-plan.md`
   - 总纲。尤其看：
     - §3 统一治理范式
     - §3.1 Contract Pack
     - §4 Phase -1 / Phase 0 / Phase 0.5
     - §6 执行顺序与 gate 要求
2. `docs/governance/foundation-boundaries.md`
   - 当前治理事实基线。
3. `docs/governance/module-dependencies.yaml`
   - 当前 55 条跨模块边 / 30 个历史循环基线。
4. `docs/governance/ai-tool-module-codes.yaml`
   - 当前 67 个 AI 工具模块归属基线。
5. `docs/governance/portal-aggregation-contract.md`
   - 后续 Portal 聚合合同。
6. `docs/reviews/2026-06-05-foundation-plan-global-review.md`
   - 上一轮全局审查。注意其中“没有开关可关”的推断已在 master plan §0 / §4.0.5 订正。

---

## 3. Phase -1 已完成

原先工作区里约 50 个未提交 governance 改动，因为另一个 Claude Code 窗口 `sid:305ef04a` 的 tool call 解析失败和提交闸门阻断，无法继续。

已由当前窗口接手并拆成 5 个小提交：

```text
ab4c740 ci: 将模块治理检查纳入测试流水线
b030275 feat(portal): 增加门户聚合 API 底座
30936f0 governance: 增加依赖 AI 权限基线检查
0f37bff governance: 增加模块合同聚合器与提交守卫
b1c35c7 docs: 固定地基治理总纲与模块合同基线
```

这 5 个提交完成了：

- 固定地基治理总纲、计划、审查和模块合同基线。
- 加入 `exam_import` / `portal` 的 `MODULE.md`。
- 增强 `aggregate_modules.py`。
- 新增 `module_governance_guard.py`。
- 新增依赖循环、AI 工具归属、权限镜像三个治理检查脚本。
- 新增后端 Portal 聚合 API 底座：`/api/v1/portal/*`。
- 将治理检查加入 `.github/workflows/test.yml`。

---

## 4. 当前验证结果

最后一次验证命令：

```bash
cd /home/ops/projects/edu-cloud
.venv/bin/python scripts/governance/aggregate_modules.py --check
.venv/bin/python scripts/governance/check_module_dependencies.py --check
.venv/bin/python scripts/governance/check_ai_tool_modules.py
.venv/bin/python scripts/governance/check_permission_mirror.py
.venv/bin/python -m pytest tests/governance tests/test_modules/test_portal tests/test_modules/test_exam_import/test_router.py --tb=short -q
```

验证结果：

```text
Check: {'modules': 23, 'conflicts': 0, 'debt': 0, 'stale': [], 'mode': 'working-tree'}
Module dependency baseline clean: 55 edges, 30 cycles
AI tool module baseline clean: 67 tools, counts={'conduct': 9, 'exam': 46, 'grading': 3, 'homework': 6, 'research': 3}
Permission mirror clean
129 passed, 5 warnings
```

接手后先确认：

```bash
git status --short
git log --oneline -8
```

---

## 5. 不要继续使用的坏窗口

坏窗口信息：

```text
sid: 305ef04a-ab01-471f-9889-9f31420ba745
session log: /home/ops/.claude/projects/-home-ops/305ef04a-ab01-471f-9889-9f31420ba745.jsonl
```

它的问题：

- 连续出现 `The model's tool call could not be parsed (retry also failed)`。
- 卡在 commit 阶段，先后被：
  - `doc_sync_guard`
  - `command_only_precheck`
  - `module_governance_guard`
  - `derivation_scale_guard`
  拦截。
- 最后主要阻断是一次大提交触发：14 个代码文件、2073 行变更，超过 L014 阈值。

现在不要再让该窗口接手本任务。它可以关闭或忽略。

---

## 6. 下一步：Phase 0

### 目标

冻结治理基线，确认当前地基从“已提交”变成“可验证、可审查、可回滚”的基线。

### 建议动作

1. 先复核工作区：

```bash
cd /home/ops/projects/edu-cloud
git status --short
git log --oneline -8
```

2. 跑治理检查：

```bash
.venv/bin/python scripts/governance/aggregate_modules.py --check
.venv/bin/python scripts/governance/check_module_dependencies.py --check
.venv/bin/python scripts/governance/check_ai_tool_modules.py
.venv/bin/python scripts/governance/check_permission_mirror.py
```

3. 跑重点测试：

```bash
.venv/bin/python -m pytest tests/governance tests/test_modules/test_portal tests/test_modules/test_exam_import/test_router.py --tb=short -q
```

4. 如果都绿，不需要再改代码。Phase 0 可以记录为完成。

### Phase 0 不做

- 不新增 Portal 功能。
- 不重构依赖循环。
- 不改 AI 工具归属。
- 不改权限/模块开关语义。

---

## 7. 下一步：Phase 0.5 模块语义统一

这是当前最重要的新工作。

### 背景

代码库存在两套模块概念：

| 类型 | 数量 | 真源 |
|---|---:|---|
| 架构模块 | 23 | `src/edu_cloud/modules/*/MODULE.md` |
| 学校开关模块 | 9 | `src/edu_cloud/models/school_settings.py::MODULE_CODES` |

真实问题不是“没有映射”，而是映射隐式、分散、无守卫。

当前映射散落在：

- `src/edu_cloud/api/module_middleware.py::ROUTE_MODULE_MAP`
- `frontend/src/config/routeAccess.js::ROUTE_ACCESS_REQUIREMENTS`
- `frontend/src/config/sidebarConfig.js::SIDEBAR_GROUPS`
- `src/edu_cloud/modules/portal/service.py::SERVICE_CATALOG`

### Phase 0.5 目标

建立单一声明式映射真源，并让四方消费者对齐它。

建议新增：

```text
docs/governance/module-semantics.yaml
scripts/governance/check_module_semantics.py
tests/governance/test_module_semantics.py
```

### 映射建议口径

`module_code` 在 Portal / 前端入口 / AI 工具里统一表示“学校功能开关码”，不是代码架构 owner。

示例：

```yaml
architecture_to_school_module:
  analytics: study_analytics
  profile: study_analytics
  adaptive: study_analytics
  bank: research
  knowledge: research
  knowledge_tree: research
  marking: grading
  scan: exam
  card: exam
  pipeline: exam
  exam_import: exam
  portal: null        # cross-cutting aggregation; does not own school switch
  school: null        # core/admin infrastructure
  student: null       # base info / shared identity, define explicitly
  menu: null          # navigation infrastructure
  paper: exam         # verify before finalizing
  academic: teaching  # verify before finalizing
```

注意：上面是建议起点，不是最终事实。实施前必须对照当前路由、菜单、服务目录和业务语义核实。

### 关键验收

- `module-semantics.yaml` 覆盖 23 个架构模块和 9 个学校开关码。
- `teaching` 空壳状态被显式登记。
- `check_module_semantics.py` 能校验：
  - 后端 `ROUTE_MODULE_MAP` 与真源一致。
  - 前端 `routeAccess.js` 与真源一致。
  - `sidebarConfig.js` 与真源一致。
  - Portal `SERVICE_CATALOG` 的 `module_code` 全部属于 `MODULE_CODES`，且能解释到架构模块/服务入口。
- 故意漂移时测试会红。
- 对受模块治理的业务入口 fail-closed；但必须保留明确 exempt list，避免误伤 auth / health / schools / students / classes 等基础接口。

---

## 8. 重要风险

1. 不要把 Phase 0.5 做成行为大改。先声明映射和加守卫，行为尽量不变。
2. 不要把 Portal 当超级模块。Portal 只能聚合 source service/adapter，不拥有业务表。
3. 不要把 `module_code` 和架构模块 owner 混为一谈。`module_code` 当前应表示学校功能开关码。
4. 不要先做 Phase 1 Portal 前端迁移。Phase 0.5 没完成前，入口和模块开关语义仍会漂。
5. 不要在一个 commit 里塞太多代码文件。之前 `derivation_scale_guard` 因 14 个代码文件 / 2073 行阻断过。每批尽量小于 8 个代码文件、500 行变更。

---

## 9. 推荐提交策略

Phase 0.5 建议至少拆成两批：

### Commit 1：声明映射真源

- `docs/governance/module-semantics.yaml`
- 如需补充：`docs/governance/foundation-boundaries.md`

### Commit 2：检查脚本 + 测试

- `scripts/governance/check_module_semantics.py`
- `tests/governance/test_module_semantics.py`
- `.github/workflows/test.yml` 如需纳入 CI

如果后续要改四方消费者以派生自真源，再另开 Commit 3，不要和脚本测试混一起。

---

## 10. 接手后的第一句建议

建议新窗口先做：

```text
我先复核 HEAD/工作区/治理检查，然后只做 Phase 0.5 的模块语义统一计划与最小实现，不进入 Portal 功能迁移。
```

然后执行：

```bash
cd /home/ops/projects/edu-cloud
git status --short
git log --oneline -8
.venv/bin/python scripts/governance/aggregate_modules.py --check
.venv/bin/python scripts/governance/check_module_dependencies.py --check
.venv/bin/python scripts/governance/check_ai_tool_modules.py
.venv/bin/python scripts/governance/check_permission_mirror.py
```
