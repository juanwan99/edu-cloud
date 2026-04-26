# Plan Review R3: 好分数业务复刻 Phase 1

> [edu-cloud] GPT Reviewer | 2026-04-13
> Raw output hash: e454c92929f1f5eaa85ca3a87a1cce6e5f8f21fb15d1a368ed2e3c3c9ff64393

## 审查报告

结论: **FAIL**

依据：R2 六项处置点全部通过（F002/F003/F007/F008/F009/F010 全 PASS）；但新扫描暴露 3 个 MED finding（2 test-gap + 1 design-concern）。按规则 test-gap MED 未修复即 FAIL。

## R2 已验证通过（GPT 复核结论）

| ID | GPT R3 结论 |
|----|-------------|
| F002 | PASS — Task 4/6/8/10/11/12 已补测试契约或标注非行为变更 |
| F003 | PASS — subject_teacher_headers 正确使用，placeholder 已删 |
| F007 | PASS — analytics 路径对齐真实路由，getPowerOptions stub 有效 |
| F008 | PASS — Batch 2 独立验证段不依赖 Task 12 |
| F009 | PASS — applyLoginResponse/applySwitchRoleResponse/restoreFromStorage 归一化正确 |
| F010 | PASS（仅 schema superseded 检查点） |

## Findings

### F011 — Task 2 测试契约命令引用旧测试名
- **Severity:** MED
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** 测试契约命令仍写旧名 `test_get_menus_role_filtering` / `test_get_menus_authenticated`，且"admin 看所有模块"边界与 platform_admin fail-closed 空菜单断言冲突
- **After-behavior:** 命令指向真实新名 `test_get_menus_subject_teacher` / `test_get_menus_platform_admin_structure`，边界语义一致
- **Evidence:** plan:L718, L730（旧名）vs plan:L595, L615（新测试函数）
- **Impact:** 执行者按契约跑会报 test not found 或被错误 admin 预期误导

### F012 — Task 5/6/10 测试命令退化为手动验证
- **Severity:** MED
- **Category:** test-gap
- **Type:** defect_fix
- **Before-behavior:** Task 5（auth store）、Task 6（useApi）、Task 10（usePowerOptions）测试命令为"手动验证/devtools/Phase 2 补 Vitest"
- **After-behavior:** Phase 1 核心行为（login 归一化/切角色/localStorage 恢复/空 stub 加载/级联 reset）需最小 Vitest 合约
- **Evidence:** plan:L1394, L1563, L2510, L2516
- **Impact:** Phase 1 最易出隐性回归的逻辑没有 CI 可执行的 falsifiable oracle

### F013 — 设计文档其余章节仍存在全局漂移
- **Severity:** MED
- **Category:** design-concern
- **Type:** defect_fix
- **Before-behavior:** §2 目录写 `edu-cloud/frontend/`，§4 useApi 示例用 `/analytics/power-options` 等不存在端点，§5 `RankComputeService → exam_scores`，§6 交付物 #9 "exam_scores 加 rank"
- **After-behavior:** 设计文档章节与 plan.md + 代码库一致
- **Evidence:** design:L32 / L239-243 / L440 / L474
- **Impact:** 若后续按 design 执行，仍可能回到错误目录、错误 API、错误表名

## 处置状态（R4 处置完成 2026-04-13）

| ID | 状态 | 处置 |
|----|------|------|
| F011 | resolved-correct | Task 2 测试契约第 1/3 条命令改为真实测试名；第 3 条边界从"admin 看全部模块"改为 platform_admin fail-closed |
| F012 | resolved-correct | Task 5/6/10 补最小 Vitest 合约（含 Vitest 骨架代码），命令指向具体测试文件和 `-t` 过滤 |
| F013 | resolved-correct | design.md §2 前添加全局漂移修正说明，列出所有 superseded 章节并明确 plan.md 为执行真源 |

## 补充判断（来自 GPT R3）

> R2 六项处置点本身没有发现"表面修了、实质没修"的回退；问题出在新一轮扫描里暴露出的"验证命令仍不可执行"和"设计文档其余章节继续漂移"。
