---
baseline_command: ".venv/bin/python -m pytest --tb=no -q"
baseline_verified_at: "2026-04-26T10:17:07+08:00"
baseline_count: "2219 passed / 23 skipped / 2 failed"
---

# edu 项目群技术债系统性修复设计

> **审计来源**: `docs/2026-04-26-tech-debt-audit.md`（Claude 6 路 + GPT 3 路并行审计）
> **修复范围**: 21 条（6 Critical + 15 High），Medium 级排除
> **分批策略**: 按风险层分 3 Phase（安全 → 稳定性 → 架构）
> **验证机制**: 全量测试 + codex-review code + Phase 间 handoff

---

## 现有资产盘点

| 层 | 已有 | 位置 | 证据 |
|----|------|------|------|
| 后端测试 | 2219 passed / 23 skipped / 2 failed | `tests/` 300 文件 | ECS pytest 实测 2026-04-26 |
| 前端测试 | 348 vitest | `frontend/src/__tests__/` | vitest run 实测 |
| 审计报告 | 42 条发现 | `docs/2026-04-26-tech-debt-audit.md` | Claude + GPT 双模型 |
| 配置中枢 | Settings(BaseSettings) | `src/edu_cloud/config.py` | pydantic-settings |
| CI | 无 | — | 三仓均无 GitHub Actions |

## 增量 vs 新建论证

全部 21 条修复均为**增量修改**，不新建平行系统。最大的结构变更是 H-01 路由文件拆分，但仅拆文件不改 API 签名，`app.py` 注册入口同步更新即可。

## 交付路径

代码层修复，不涉及前端产物构建部署（H-09 Bundle 优化除外，需 `vite build` 验证）。生产部署由用户决定时机。

---

## Phase 0 — 安全修复（8 条，~4h）

**目标**: 消除所有可被外部利用的安全风险。

| ID | 问题 | 仓库 | 修复方式 |
|----|------|------|---------|
| C-01 | 硬编码密码 "123456" × 5 处种子 | edu-cloud | 环境变量 `SEED_DEFAULT_PASSWORD` + 启动校验非默认值 |
| GPT-01 | teacher_router 业务 API 硬编码 123456 | edu-cloud | 统一引用 `settings.SEED_DEFAULT_PASSWORD` |
| C-03 | .env 在 git 中 | edu-cloud | `git rm --cached .env` |
| C-05 | ExamAIClient 默认端口 8000 | paper-seg | 默认值改 `None`，强制显式传入 |
| GPT-02 | module_middleware JWT 异常绕过 | edu-cloud | except 后返回 403 而非 call_next |
| H-03 | JWT 明文存 localStorage | edu-cloud | 本 Phase 仅加 token 过期清理 + 标记；完整 httpOnly cookie 迁移降级跟踪 |
| H-04 | v-html 渲染 AI 内容未防护 | edu-cloud | 引入 DOMPurify，ChatPanel.vue 用 `DOMPurify.sanitize()` |
| H-05 | card-editor innerHTML 多处 | edu-cloud | 对 innerHTML 赋值数据源做 sanitize |

**验证覆盖**: pytest 全量 / vitest 全量 / codex-review code / git diff 确认无计划外变更
**验证未覆盖**: 浏览器 UI 视觉验证 / 安全渗透测试 / 生产环境验证

---

## Phase 1 — 稳定性修复（8 条，~6h）

**目标**: 消除运行时故障风险和开发环境腐化。

| ID | 问题 | 仓库 | 修复方式 |
|----|------|------|---------|
| C-02 | Alembic-ORM 双轨漂移 | edu-cloud | 移除 `app.py:70` 的 `create_all()`，验证 `alembic upgrade head` 从空库完整建表 |
| C-04 | .db + 日志在 git 中 | edu-cloud | `git rm --cached edu_cloud.db* logs/app.jsonl.*`，补 .gitignore |
| C-06 | Pillow/numpy 依赖未声明 | ace | pyproject.toml 补 `Pillow>=10.0, numpy>=1.24` |
| H-06 | npm 6 HIGH 安全漏洞 | edu-cloud + ace | `npm audit fix --audit-level=high` |
| H-07 | N+1 查询 analytics.grade_aggregates | edu-cloud | `selectinload()` 预加载关系 |
| H-08 | workers/grading.py 裸 except | edu-cloud | `logger.error(..., exc_info=True)` + raise |
| GPT-03 | audit_service 吞审计写入失败 | edu-cloud | except 内加 `logger.error()` 保留失败记录 |
| H-12 | .venv pip 破损 | edu-cloud + paper-seg | 重建虚拟环境 |

**关键风险**: C-02 移除 `create_all()` 后需确认 31 个 migration 的 upgrade 链能从空库建出 88 表。测试 conftest.py 仍可用 `create_all()` 做 in-memory fixture，只禁生产启动路径。

**验证覆盖**: pytest 全量 / vitest 全量 / Alembic upgrade head 空库建表 / npm audit 零 HIGH / codex-review code / git diff
**验证未覆盖**: Alembic downgrade 反向链（已知 2 个债务）/ PostgreSQL 方言兼容 / 生产部署 / N+1 性能基准

---

## Phase 2 — 架构修复（5 条，~12.5h，拆 2 个会话）

**目标**: 降低维护成本和未来开发摩擦。

### Phase 2a — 后端路由拆分 + Bundle + CI + ace（~4.5h）

| ID | 问题 | 仓库 | 修复方式 |
|----|------|------|---------|
| H-01 | God Module 3 个超大路由 | edu-cloud | `card/router.py` 拆 3 文件 / `grading/router.py` 拆 2 文件 / `analytics/router.py` 拆 2 文件，app.py 注册同步 |
| H-09 | Bundle 未优化 | edu-cloud | vite.config.js 添加 manualChunks（echarts / marked-katex / ui-vendor） |
| H-10 | SQLite 并发安全 | ace | connection-per-request + FastAPI Depends，移除 check_same_thread=False |
| H-11 | 三仓无 CI | 三仓 | `.github/workflows/test.yml`（pytest + vitest + npm audit） |

### Phase 2b — 前端组件拆分 Top 3（~4h）

| ID | 问题 | 仓库 | 修复方式 |
|----|------|------|---------|
| H-02 | 25 个巨型前端组件（本 Phase 仅 Top 3） | edu-cloud | ExamDetailPage(1368行) / AiGradingPage(838行) / GradingDispatchPage(826行) 各拆 3-5 子组件 |

**H-02 降级说明**: 25 个组件全拆是 T4 工作量（40h+）。只拆 Top 3 覆盖 3032 行（债务 ~45%），剩余 22 个降级到 Medium 后续迭代。

**验证覆盖**: pytest 全量 / vitest 全量 / vite build + 产物体积对比 / CI dry-run / codex-review code / git diff
**验证未覆盖**: 22 个未拆中型组件 / 浏览器 UI 验证 / CI GitHub Actions 实际运行 / Bundle 性能实测

---

## 跨 Phase 协调

### 会话结构

| 会话 | 内容 | 前置条件 |
|------|------|---------|
| 当前 | design + plan | — |
| Phase 0 | 安全修复 | plan 已 commit |
| Phase 1 | 稳定性修复 | Phase 0 handoff |
| Phase 2a | 后端架构 + CI | Phase 1 handoff |
| Phase 2b | 前端组件拆分 | Phase 2a handoff |

### codex-review 门控

- 每个 Phase/子 Phase 完成后 codex-review code
- GPT finding 三分类（L017）：`defect_fix` 直接修 / `test_gap` 补测试 / `design_concern` 报不修
- R1 FAIL → 修复 → R2；R2 FAIL → 拆子 batch 或 WONTFIX

### 完成标准

- 21 条 C+H 发现全部 resolved 或有明确 WONTFIX 理由
- pytest ≥ 2219 passed（不低于基线）
- vitest ≥ 348 passed（不低于基线）
- npm audit 零 HIGH
- 审计报告更新每条 fix 的 commit SHA

### 显式排除

- 21 条 Medium 级发现
- H-03 完整 httpOnly cookie 迁移
- H-02 剩余 22 个中型组件拆分
- 生产部署
- 新功能开发
