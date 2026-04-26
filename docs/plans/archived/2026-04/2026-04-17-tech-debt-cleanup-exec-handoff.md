<!-- legacy-format -->
# edu-cloud 技术债清理 · 执行窗口交接卡（Phase 2 残余 + Phase 4-5）

> 状态：规划完成，待执行窗口接替
> 创建时间：2026-04-17（UTC+8）
> 规划窗口：Claude Opus 4.7 (1M)，本卡为规划产出，不含任何代码改动
> 前序交接卡：`docs/plans/2026-04-17-tech-debt-cleanup-handoff.md`（Phase 1 + P2 Task 1+2 + 等级 2 ORM 全闭环，1932 passed / 0 failed / 23 skipped）

## 0. 阅读顺序（执行窗口第一步）

```bash
cd /home/ops/projects/edu-cloud
# 1. 先读前序交接卡了解已落地范围
cat docs/plans/2026-04-17-tech-debt-cleanup-handoff.md
# 2. 再读本卡了解剩余 4 子项
cat docs/plans/2026-04-17-tech-debt-cleanup-exec-handoff.md
# 3. 必读规则
cat ~/.claude/rules/autonomy-boundary.md
cat ~/.claude/rules/bug-fix-discipline.md   # P5 行为变更需要
cat ~/.claude/rules/tdd-policy.md            # P5 TDD-lite 必走
# 4. 验证基线
git status --short | head -40
git log --oneline -5
```

## 1. 工作范围（4 子项 · 严格 checkpoint）

| # | 子项 | 类型 | T 级 | 风险 | 依赖 | 预计规模 |
|---|------|------|------|------|------|---------|
| 1 | Task 3 · `docs/arch/frontend-boundary.md` | 新增文档 | T1 | 低 | 无 | ~250 行 |
| 2 | Task 4 · `docs/plans/compat-router-deprecation.md` | 新增文档 | T1 | 低 | 无 | ~200 行 |
| 3 | Phase 5 首动作 · DeprecationWarning 注入 | 行为变更 | T2 | 中 | T4 文档定义退役日期 | ~50 行代码 + ~30 行测试 |
| 4 | Phase 4 · card 子目录化方案文档 | 新增文档 | T1 | 低 | 无（实施另起 session） | ~150 行 |

**关键澄清 ⚠️**：
- 子项 4（Phase 4）**只做方案文档，不做实施**。实施需用户批准方案 + 单独 session（135 处 card import 改动是 T3 大重构，需要独立 SVD 4-check 流程）
- 子项 3（Phase 5）只做"首动作 = 加 DeprecationWarning"，不做"paper-seg 客户端改造"（那是 Phase 5 后续 task，需 paper-seg 仓改动）
- **整包不可自治判定**：4 子项均非视觉、用户在线 → 不触发 autonomy-boundary 整包禁止；但**每子项完成必须 checkpoint 等用户确认**才进下一项。

## 2. 当前状态快照（2026-04-17 接替时）

### 2.1 git 状态
- HEAD: `00cfc3d takeover: sync ECS worktree as authoritative; retire legacy ai/* modules; untrack uploads/ and *.db`
- working tree：大量未 commit 改动（详见前序交接卡 §4.2），包括 12 个 `models/*.py` re-export stubs + 2 文档（`module-template.md`/`orm-placement.md`）+ 测试修复 + ORM 搬迁
- **执行窗口禁止 commit**，除非用户明确要求

### 2.2 测试基线
- pytest（最近一次，2026-04-17 19:07 启动）：**1932 passed / 0 failed / 23 skipped**（620s）
- 日志路径：`/tmp/edu_pytest_orm.log`
- 任何子项实施后都必须重跑 pytest 确认基线维持

### 2.3 关键事实（写文档时引用）
- `frontend/`：Vite 7 + Vue 3.5 + Naive UI 2.44 + vue-router 4 + ECharts，14 路由 + 72 Vitest，**生产主前端（阅卷平台）**
- `frontend-nuxt/`：Nuxt 3.17 + Element Plus 2.8 + Pinia 2 + Node ≥22.12，24 Vitest，**haofenshu Phase 1 复刻骨架**（Batch 2 R3 PASS，Batch 3 待启动）
- 后端**零引用** `frontend-nuxt/`，Dockerfile/docker-compose.yml 只构建 `frontend/`
- `compat_router.py`：343 行，8 端点，挂载点 `src/edu_cloud/api/app.py:270-271`
- `modules/card/` 16 业务文件（不计 `__init__.py`/`__pycache__`），Grep `from edu_cloud.modules.card` 在 `src/` + `tests/` 命中 **135 处 import**

## 3. 子项 1 · Task 3 `docs/arch/frontend-boundary.md`

### 3.1 目标
固化双前端业务边界（Q3 决策 = B 共存），让任何新功能能照决策树判断"加到 frontend 还是 frontend-nuxt"，避免未来路由/权限重叠。

### 3.2 写作大纲（6 节，按此顺序）

```markdown
# 双前端业务边界规范

## 1. 现状定位
- frontend/ = 生产主前端（阅卷平台全功能 14 路由 / 72 Vitest）
  - 技术栈：Vite 7 + Vue 3.5 + Naive UI 2.44 + vue-router 4 + Pinia 3 + ECharts 6 + KaTeX
  - 端口：5273（dev）
  - 业务范围：登录/分析/考试管理/扫描/AI 阅卷/手工阅卷/通知/家长端/conduct/...（详见 CLAUDE.md "项目结构" frontend/src/pages/）
- frontend-nuxt/ = haofenshu 业务复刻 Phase 1（初始化阶段，Batch 2 R3 PASS）
  - 技术栈：Nuxt 3.17 + Vue 3.5 + Element Plus 2.8 + Pinia 2，Node ≥22.12
  - 端口：3000（dev，被 haofenshu-clone 占用时 fallback 3100）
  - 业务范围：仅首页 + 登录 + 模块卡片网格（Batch 2 完成）；Batch 3 拓展 PowerFilter + 45 页面 stub

## 2. 业务范围划分（不重叠原则）
- frontend：edu-cloud 原生平台所有功能（exam/grading/marking/analytics/knowledge/conduct/parent/...）
- frontend-nuxt：好分数复刻独立功能（学情看板、班级 Dashboard 等 8 模块 45 页面，详见 haofenshu-biz-replication-design.md "蓝图")
- **铁律**：同一业务功能不允许两前端各实现一遍。新需求触发归属决策树（§6）。

## 3. API 调用规约
- 两前端都走 `/api/v1/*` 统一后端
- frontend：Axios baseURL `/api/v1`
- frontend-nuxt：`composables/useApi.ts`（27 方法），代理 `/api` → `http://localhost:9000`
- 路由挂载互斥：后端不为某个前端定制路由；如需差异化，走 query 参数或 Accept header
- 认证：JWT 共享（同一 access_token 两边都认）；401/403 处理：useApi 抛 `AuthError` sentinel

## 4. 技术栈差异容忍度
- 列表为什么不强制统一（Q3 = B 务实理由）
  - 复刻骨架阶段，强推 Vue 生态会破坏 Nuxt SSR 路径
  - Element Plus vs Naive UI 互不兼容，迁移成本远超收益
  - frontend 已稳定 14 路由 / 72 测试，retro-fit 风险高
- 容忍清单
  - UI 库不同（Naive UI vs Element Plus）
  - 路由方式不同（vue-router 4 vs Nuxt file-based）
  - 状态管理小版本不同（Pinia 3 vs Pinia 2 + @pinia/nuxt）

## 5. 未来合并/取代决策条件
触发"启动 Phase N+1 合并"评审的硬条件（任一满足）：
- frontend-nuxt 业务范围 ≥ frontend 50%（功能等价度评估）
- 同一业务在两边各实现 → 进入维护双轨成本
- Nuxt 3 SSR 性能数据优于 frontend Vite SPA 2x 以上（生产观测）
- 用户决策："停 frontend，全量迁 Nuxt"
合并方案选项（待触发时再深化）：
- A：废 frontend，业务全迁 Nuxt
- B：废 frontend-nuxt，业务回迁 frontend
- C：拆为 frontend-admin（管理端）+ frontend-edu（教学端）

## 6. 新功能归属决策树
```
新需求来了：
├─ 复刻好分数已有功能？→ frontend-nuxt
├─ edu-cloud 原生功能（阅卷/conduct/分析/...）？→ frontend
├─ 跨域功能（既要复刻又要原生）？
│  ├─ 主用户角色 = 教师/管理员？→ frontend
│  └─ 主用户角色 = 学生/家长？→ frontend-nuxt
└─ 不确定？→ 默认 frontend（多数用户场景在主前端）
```

## 7. 端口/部署约束
| 资源 | frontend | frontend-nuxt |
|------|----------|---------------|
| Dev port | 5273 | 3000（fallback 3100） |
| Build 产物 | dist/ | .output/ |
| Dockerfile 包含 | ✅ | ❌（暂未纳入生产） |
| docker-compose | ✅ | ❌ |
| Node 要求 | 18+ | ≥22.12.0（lockfile 锁定） |
```

### 3.3 依据资料（执行窗口写时引用）
- `CLAUDE.md` § "技术栈" + "项目结构 frontend/src" + "端口约定"
- `docs/plans/2026-04-12-haofenshu-biz-replication-design.md`（蓝图：8 模块 45 页面）
- `docs/plans/2026-04-12-haofenshu-phase1-plan.md`（Batch 1-3 进度）
- `frontend/package.json` + `frontend-nuxt/package.json`（锁定版本）
- `Dockerfile` + `docker-compose.yml`（确认零 Nuxt 引用）

### 3.4 验收契约
- 文件落盘：`docs/arch/frontend-boundary.md`，~250 行（±50）
- 6 节齐全，§6 决策树是核心交付物
- §3 列出的 API 规约必须与实际代码一致（执行窗口必须 Grep 验证 `useApi.ts` 27 方法 + Axios baseURL）
- 不输出"已完成"标记，输出"待确认"

### 3.5 checkpoint 输出格式（必须严格遵守）
```
【Task 3 · 待确认】
- 文件路径：docs/arch/frontend-boundary.md
- 行数：实际行数
- 6 节标题：[列出实际标题]
- 引用资料 verify：[列出 Grep/Read 验证的资料]
- 已知偏差/未决问题：[列出，无则写"无"]
- 等用户查看：是否进入 Task 4 / 是否需要修改
```

## 4. 子项 2 · Task 4 `docs/plans/compat-router-deprecation.md`

### 4.1 目标
为 `compat_router.py` 8 端点制定退役计划：端点映射、客户端改造步骤、DeprecationWarning 方案、目标日期、风险监控。

### 4.2 写作大纲（6 节，按此顺序）

```markdown
# exam-ai 兼容路由退役计划

## 1. 现状
- 文件：src/edu_cloud/api/compat_router.py（343 行）
- 挂载点：src/edu_cloud/api/app.py:270-271（include_router）
- 用途：paper-seg 客户端零改动对接 edu-cloud（不必改 /api → /api/v1）

## 2. 端点清单与映射表
| compat 路径 | 方法 | 当前实现 | 替代 /api/v1 路径 | 客户端改造点 |
|------------|------|---------|-------------------|-------------|
| /api/auth/login | POST | compat_login（忽略 school_code） | /api/v1/auth/login | 去掉 school_code 字段 |
| /api/exams | GET | 列当前学校考试 | /api/v1/exams | 路径调整 |
| /api/exams/{id}/subjects | GET | 列科目 | /api/v1/exams/{id}/subjects | 路径调整 |
| /api/templates/{subject_id}/{side} | GET | 模板（image_size 兼容格式） | /api/v1/card/templates/{...}（待 verify） | 路径 + 字段格式 |
| /api/scan/tasks | POST | 创建扫描任务 | /api/v1/scan/tasks（待 verify） | 路径调整 |
| /api/scan/tasks/{id} | PATCH | 更新进度 | /api/v1/scan/tasks/{id} | 路径调整 |
| /api/scan/upload | POST | 上传切图（multipart） | /api/v1/scan/upload | 路径调整 |
| /api/scan/upload-objective | POST | 上传选择题 | /api/v1/scan/upload-objective | 路径调整 |

**执行窗口必须 Grep 验证**每个 /api/v1/* 替代路径在 modules/exam/router.py / modules/scan/router.py / modules/card/template_router.py 中真实存在。如果替代路径不存在，标注为"未实现，需新增"。

## 3. paper-seg 客户端改造步骤（逐端点）
- Step 1：盘点 paper-seg 调用 compat 端点的所有位置（执行窗口暂不做，给出 grep 命令模板）
- Step 2：8 端点逐个迁移到 /api/v1（按 §2 映射表）
- Step 3：去掉 school_code 字段（compat_login 唯一兼容点）
- Step 4：联调验证

## 4. DeprecationWarning 注入方案
- Python 端：每个 compat 路由 handler 内调用 warnings.warn(DeprecationWarning, ...)
- HTTP Response：加 header `Deprecation: true` + `Sunset: <date>` + `Link: </api/v1/...>; rel="successor-version"`
- 日志：每次调用 logger.warning(...) 计入计数（用 prometheus counter 或 logging metrics）
- 生效时间表：
  - T+0（立即）：DeprecationWarning + Response header
  - T+30 天：日志告警阈值（每天 >100 次调用触发告警）
  - T+60 天：开发环境默认拒绝（除非 X-Allow-Deprecated: true header）
  - T+90 天 = 退役日期：删除 compat_router.py + app.py:270-271 挂载

## 5. 目标退役日期
- 建议：2026-Q3（具体日期待 paper-seg 团队确认）
- 决策依据：paper-seg 是内部项目，可控；外部第三方 client 无（已 verify）

## 6. 风险与监控
- 风险 1：paper-seg 未及改造就到期 → 扫描断流，影响 N 所学校上传
  - 缓解：T+60 天前 weekly 推送调用次数报告给 paper-seg 团队
- 风险 2：替代 /api/v1 路径未实现 → 客户端无法迁移
  - 缓解：本文档 §2 必须先 verify 替代路径存在；不存在则升级为"先补 /api/v1，再退役 compat"
- 监控指标：
  - logs JSONL 中 path=/api/* 计数（按端点分组）
  - 按学校（school_id）分组的调用频次
  - 周报：发送给 paper-seg 团队 + edu-cloud owner
```

### 4.3 依据资料
- `src/edu_cloud/api/compat_router.py`（已读全文，343 行）
- `src/edu_cloud/api/app.py:270-271`（挂载验证）
- `CLAUDE.md` § "API 端点 / exam-ai 兼容端点"（清单核对）
- `modules/exam/router.py` + `modules/scan/router.py` + `modules/card/template_router.py`（替代路径 verify）

### 4.4 验收契约
- 文件落盘：`docs/plans/compat-router-deprecation.md`，~200 行（±50）
- §2 映射表 8 行齐全，每行替代路径都有"verify 状态"列（存在 / 不存在 / 部分）
- §4 时间表 4 个里程碑齐全
- §6 监控指标可执行（不写"加监控"这种空话，写具体 logger field）

### 4.5 checkpoint 输出格式
```
【Task 4 · 待确认】
- 文件路径：docs/plans/compat-router-deprecation.md
- 行数：实际行数
- §2 映射表 verify 结果：[N 个存在 / M 个不存在 / K 个部分]
- 不存在的替代路径清单：[列出，影响 §6 风险评估]
- 退役日期建议：YYYY-MM-DD
- 等用户查看：是否进入 P5 首动作 / 是否需要先补 /api/v1
```

## 5. 子项 3 · Phase 5 首动作 · DeprecationWarning 注入

### 5.1 目标
按 Task 4 文档 §4 的 T+0 阶段，在 8 个 compat 路由 handler 注入 DeprecationWarning + Response header + 日志计数。

### 5.2 前置条件
- Task 4 文档已落盘 + 用户确认退役日期
- 替代 /api/v1 路径已 verify（如有缺失，先停在 Task 4 不进 P5）

### 5.3 T2 行为变更声明（必须在动代码前输出）

```
**症状**: compat_router 8 端点对调用方无任何 deprecation 信号，paper-seg 不知道该迁移
**根因**: 缺少标准 deprecation 协议（DeprecationWarning / Response header / 日志告警）
**证据**: 通读 compat_router.py 343 行，所有 handler 仅 logger.info，无 warnings.warn 也无 Sunset header
**影响面 (scope check 三维度)**:
  - 同模式: 全项目其他 router 是否有应 deprecate 但未标记的？Grep "deprecated" / "legacy" 关键词
  - 同边界: 8 端点的 Response 模型是否会被 header 注入影响？(StreamingResponse vs JSONResponse)
  - 同不变量: paper-seg 现有调用是否依赖 Response header 缺失某字段？(rare 但需 verify)
**排除的假设**: 用户未要求"立即下线"——已排除"直接删 compat_router"方案；用户未要求"加 X-Allow-Deprecated 强制开关"——P5 首动作只做软提醒不做拦截
```

### 5.4 实施步骤
1. **TDD-lite 红测**：写 1-3 个失败测试断言：
   - 调用 `/api/auth/login` Response 含 `Deprecation: true` header
   - 调用任一 compat 端点产生 DeprecationWarning（pytest.warns 捕获）
   - logger.warning 含 "deprecated_compat_call" 关键字段
2. **最小实现**：定义 helper `_emit_deprecation(endpoint: str, response: Response)`，在每个 handler 调用
3. **绿测确认**：3 个测试通过
4. **全量回归**：`python -m pytest --tb=short -q` 必须仍 1932/0/23
5. **scope check verify**：Grep "@router.post|@router.get|@router.patch" 全项目，列出未带 v1 前缀的所有 router → 确认 compat 是唯一应 deprecate 的

### 5.5 验收契约
- 8 个 handler 全部加 `_emit_deprecation()` 调用（Grep "_emit_deprecation" 必须 ≥8 命中）
- 至少 3 个新测试 PASS（warning + header + log）
- 全量 pytest 回归仍 1932/0/23（**新增的 3 测试不算回归基线**，最终是 1935/0/23 或类似）
- Response header 三件套：`Deprecation` / `Sunset` / `Link`
- 不删除原 compat_router 任何业务代码

### 5.6 checkpoint 输出格式
```
【Phase 5 首动作 · 待确认】
- 修改文件：src/edu_cloud/api/compat_router.py（+N 行）
- 新增测试：tests/test_api/test_compat_deprecation.py（3 测试）
- pytest 结果：1935/0/23（含新增 3）
- Grep _emit_deprecation 命中：8（每端点 1）
- scope check 结论：compat 是项目内唯一未带 v1 前缀的 router（已 verify）
- 等用户查看：是否进入 Phase 4 方案文档 / 是否需要调整 Sunset 日期
```

## 6. 子项 4 · Phase 4 card 子目录化方案文档

### 6.1 目标
**只写方案，不动代码**。产出 `docs/plans/2026-04-17-card-subdir-plan.md`，让用户审批后再起新 session 实施。

### 6.2 理由（为什么拆分）
- 135 处 `from edu_cloud.modules.card` import，跨 src/ + tests/ 大范围影响
- T3 重构（按 SVD 分级）必须完整 4-check：git tag + inventory + 4-check
- 实施需 2-4 小时聚焦工作 + 全量 pytest 多次回归
- 用户必须先批准"子目录方案 + import 路径变动范围"才值得开工

### 6.3 方案文档大纲

```markdown
# Phase 4 · card 模块子目录化方案

## 1. 现状
- 文件：modules/card/ 16 业务文件平铺
  - 列出每个文件名 + 主要职责（一句话）
- import 影响面：Grep 命中 135 处

## 2. 子目录方案（建议）
```
card/
├── __init__.py
├── models.py              # 保留顶层（Template, CardSkeleton）
├── router.py              # 保留顶层（主路由）
├── template_router.py     # 保留顶层（模板子路由）
├── publish_service.py     # 保留顶层（跨子域服务）
├── rendering/
│   ├── __init__.py
│   ├── renderer.py
│   ├── layout.py
│   ├── tpl_parser.py
│   ├── subject_defaults.py
│   └── defaults.py
├── export/
│   ├── __init__.py
│   ├── export.py
│   ├── html_export.py
│   └── barcode_gen.py
├── parser/
│   ├── __init__.py
│   ├── answer_parser.py
│   ├── answer_standardizer.py
│   ├── word_parser.py
│   └── confidence.py
└── template/
    ├── __init__.py
    └── template_library.py
```

## 3. import 迁移策略（两选一）
- 方案 A · 全部硬迁移：135 处 import 路径全改，无兼容层
  - 优点：彻底干净，无 Task 22 类似 stub 债务
  - 缺点：跨 src/ + tests/ 一次性改 135 处，风险集中
- 方案 B · 加 re-export stub：modules/card/ 顶层保留 re-export，外部代码无需改
  - 优点：影响面缩到 modules/card/ 内部
  - 缺点：和 module-template.md "禁止新增 stub" 冲突；新增 4 个 __init__.py 实质做 stub 工作

**推荐方案 A**（与 ORM 搬迁等级 2 一致 — 用户明确"不留隐患"），但需用户确认。

## 4. 实施步骤（待批准后另起 session）
- Step 0：git tag svd-pre-card-subdir
- Step 1：创建 4 个子目录 + __init__.py + 移动 16 文件中的 12 个
- Step 2：批量 sed 替换 135 处 import（按子目录分批）
- Step 3：单元测试逐目录验证（rendering/ → export/ → parser/ → template/）
- Step 4：全量 pytest 回归（必须 1935/0/23 或与 P5 后基线一致）
- Step 5：caller_check_hook verify
- Step 6：4-check 完整流程

## 5. 风险与回滚
- 风险 1：sed 误改非 import 行（如字符串字面量）
  - 缓解：用 ast 重写，不用 sed
- 风险 2：部分文件之间循环依赖
  - 缓解：Step 1 后立即 import smoke test
- 回滚：git reset --hard svd-pre-card-subdir

## 6. 用户决策点
- 方案 A vs B
- 是否同意一次性改 135 处
- 是否同意删除"等级 2 妥协保留" — 例如 ai/models.py 是否同步搬？（建议本次只动 card，ai/ 维持现状）
```

### 6.4 验收契约
- 文件落盘：`docs/plans/2026-04-17-card-subdir-plan.md`，~150 行（±30）
- §2 子目录树准确（与 modules/card/ 实际 16 文件对齐）
- §3 两方案优缺点齐全
- §4 步骤可执行（不写"重构"这种空话）
- **不动任何代码**（git status 在 Phase 4 期间不应新增 card/* 改动）

### 6.5 checkpoint 输出格式
```
【Phase 4 方案文档 · 待确认】
- 文件路径：docs/plans/2026-04-17-card-subdir-plan.md
- 行数：实际行数
- card/ 文件清单 verify：16 文件名（与 ls 一致）
- 推荐方案：A 或 B + 推荐理由
- 等用户决策：方案 A/B 选择 + 是否进入实施 session
```

## 7. 执行纪律（必读，违反即停）

### 7.1 LESSONS 硬约束
- **L013**：自审盲区——擅长发现"没做什么"看不到"已做的是否一致"
  - **应用**：每子项 checkpoint 输出必须列"依据类型"（Grep 命中行号 / Read 文件路径 / pytest 输出哈希）
- **L015**：虚假完成声明与验收越权
  - **应用**：禁止自标 ✓，禁止"已完成/对齐/PASS"等裁定词；只能写"待确认"
- **L017**：局部最优覆盖全局最优
  - **应用**：写文档时如发现某节与 Phase 1-2 已落地结果矛盾，先停下来报告，不要"圆话"

### 7.2 autonomy-boundary
- 4 子项均非视觉、用户在线 → 不触发整包禁止
- 但每子项完成 checkpoint **必须等用户确认**才进下一项
- 同子项被纠正 ≥3 次 → 输出"超出能力边界"声明，主动放弃

### 7.3 bug-fix-discipline（仅 P5 适用）
- P5 是 T2 行为变更（注入 deprecation） → 必须先输出 §5.3 根因声明再动代码
- TDD-lite：先写测试再写实现

### 7.4 SVD 分级
- T3 / T4 = T1（仅文档新增） → 跳过 SVD
- P5 = T2 → git tag + marker check + caller_check_hook 自动检测
- P4 方案文档 = T1 → 跳过 SVD（实施另起 session 走 T3 完整 4-check）

### 7.5 不要做的事（明确禁区）
- ❌ commit 任何改动（用户未要求）
- ❌ 修改 docs/plans/2026-04-17-tech-debt-cleanup-handoff.md（前序交接卡，只读）
- ❌ 实施 Phase 4 子目录化（本卡只规划方案文档）
- ❌ 改造 paper-seg 客户端（不在本仓范围）
- ❌ 在 P5 删除 compat_router 业务代码（只加 deprecation 信号）
- ❌ 输出"全绿汇总表" / 自标 ✓ / 用"已完成"等词
- ❌ 跳过 P5 TDD-lite 红测直接写实现
- ❌ 改 ai/models.py 或 modules/ 其他 ORM 搬迁（前序交接卡 §3 已"务实妥协"决定保留）

## 8. 第一步指令（执行窗口收到本卡后做的第一件事）

```bash
# Step 1：阅读前序交接卡 + 本卡 + 必读规则（按 §0 顺序）
# Step 2：验证基线
cd /home/ops/projects/edu-cloud
git status --short | head -40
git log --oneline -5
tail -3 /tmp/edu_pytest_orm.log    # 确认 pytest 基线
ls docs/arch/                       # 应只有 module-template.md + orm-placement.md（frontend-boundary.md 待新增）
ls docs/plans/2026-04-17-*          # 应有 2 个交接卡（前序 + 本卡）

# Step 3：对用户报告"已接替 + 4 子项理解 + 拟从 Task 3 开始"
# Step 4：等用户说"开始 Task 3"再动手
```

**报告模板**：
```
已接替规划交接卡。
4 子项 + 风险/依赖确认：
1. Task 3 frontend-boundary.md（T1 文档，无依赖）
2. Task 4 compat-router-deprecation.md（T1 文档，无依赖）
3. Phase 5 DeprecationWarning 注入（T2 代码，依赖 T4）
4. Phase 4 card 子目录化方案文档（T1 文档，实施另 session）
基线 verify：git HEAD = 00cfc3d / pytest 1932-0-23 / docs/arch 现 2 文件
拟从 Task 3 开始。请确认。
```

## 9. 验收 gate 总览

| 子项 | 进入条件 | 退出条件（用户确认才能过） |
|------|---------|---------------------------|
| Task 3 | 用户说"开始 Task 3" | 文件落盘 + checkpoint 输出 + 用户说"OK 进 T4" |
| Task 4 | T3 已通过 | 文件落盘 + verify 8 端点替代路径 + checkpoint + 用户说"OK 进 P5" |
| Phase 5 | T4 已通过 + 用户确认退役日期 | 8 handler 改完 + 3 测试 PASS + pytest 1935/0/23 + checkpoint + 用户说"OK 进 P4 方案" |
| Phase 4 方案 | P5 已通过（或用户跳过 P5） | 方案文档落盘 + 不动代码 + checkpoint + 用户决策方案 A/B |

**全部完成后**：执行窗口输出最终汇总（用 Phase 1 / Phase 2 同款"差异说明"格式），不输出全绿表。

## 10. 兜底：执行窗口遇到歧义/阻塞怎么办

- **资料缺失**：本卡 §3.3/§4.3 列的资料路径必须真实存在；如有路径错，立即报告规划窗口（用 SendMessage 或新会话）
- **基线漂移**：如 git HEAD 已不是 `00cfc3d` 或 pytest 基线变化，立即停下报告
- **大幅偏离方案**：如发现 §2 现状快照与实际不符，停下报告，不要"自圆"
- **同子项被纠正 ≥3 次**：触发 L015 主动放弃声明 → "本任务超出我的能力边界，建议：(1) 调用 Codex 诊断 (2) 用户接管 (3) 换方案"
- **3 次以上 patch 失败**：升级 T 级别或触发 codex-review

## 11. 参考文档索引

| 文档 | 路径 | 用途 |
|------|------|------|
| 前序交接卡 | `docs/plans/2026-04-17-tech-debt-cleanup-handoff.md` | Phase 1 + P2 Task 1+2 已落地范围 |
| 本卡 | `docs/plans/2026-04-17-tech-debt-cleanup-exec-handoff.md` | Phase 2 残余 + P4 + P5 规划 |
| 模块模板规范 | `docs/arch/module-template.md` | T3 写 §6 决策树时参考"分层语义" |
| ORM 归属规范 | `docs/arch/orm-placement.md` | P4 方案文档 §3 stub 策略对齐 |
| haofenshu 复刻设计 | `docs/plans/2026-04-12-haofenshu-biz-replication-design.md` | T3 §1/§2 双前端业务范围依据 |
| haofenshu Phase 1 plan | `docs/plans/2026-04-12-haofenshu-phase1-plan.md` | T3 §1 进度依据 |
| 自治边界规则 | `~/.claude/rules/autonomy-boundary.md` | 必读 |
| Bug 修复纪律 | `~/.claude/rules/bug-fix-discipline.md` | P5 必读 |
| TDD 政策 | `~/.claude/rules/tdd-policy.md` | P5 必读 |
| SVD 分级 | `~/.claude/rules/svd-rules.md` | P5 / P4 实施时必读 |
| CLAUDE.md | `/home/ops/projects/edu-cloud/CLAUDE.md` | 项目总览，T3 / T4 写作时核对 |

---

**规划窗口签收**：本卡为静态规划文档，规划窗口已退出。执行窗口可直接按 §8 第一步指令开始。如有歧义，按 §10 兜底处理。
