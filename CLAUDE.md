# edu-cloud — 教育云平台

> 多校协同云端平台，学校端（exam-ai）的上游调度中心。
> 架构边界：ECS 单一权威开发环境，与原 Windows/WSL 环境完全切断。

## 交付合同

| 字段 | 值 |
|------|-----|
| 权威代码 | `frontend/src/` → `vite build` → `frontend/dist/` |
| 用户消费 URL | `https://mcu.asia`（nginx 443 → `frontend/dist/`） |
| 验证目标 | `https://mcu.asia`（唯一完成证据 URL） |
| dev server | `localhost:8080/5173`（仅调试，不可验收） |
| 后端验证 | `.venv/bin/python -m pytest --tb=short -q` |

## 启动命令

```bash
# 后端
cd /home/ops/projects/edu-cloud
.venv/bin/python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 --reload

# 前端（Vite dev server）
cd frontend && npm run dev

# 测试
.venv/bin/python -m pytest --tb=short -q       # 后端
cd frontend && npx vitest run                    # 前端
```

## 硬禁令

- 前端改代码必须 `vite build` 才能让用户看到
- Migration 唯一路径：`python scripts/db_migrate [target]`（直接 alembic 命令被 guard 阻断）
- `/var/www/website/` SPA 产物禁止服务器编辑（查 `.SPA_MANAGED`）
- 禁止 `print()`/`console.log()` 用于业务日志
- 不得用 `cp`/`rsync` 复制活跃 SQLite（用 `.dump` 或 `.backup`）

## 模块治理设施（2026-06-05 Phase -1 收口 · commit 时 staged index 强制校验）

| 维度 | 真源 | 守卫脚本 |
|------|------|---------|
| 模块定义/结构 | `docs/governance/modules.yaml` + 各模块 `MODULE.md`（模板 `docs/governance/MODULE-template.md`） | `scripts/governance/module_governance_guard.py`（聚合器 `aggregate_modules.py`） |
| 运行时路由门控（Phase 0.6） | `frontend/src/config/routeAccess.js`（静态 route↔moduleCode）∪ `to.meta.moduleCode`（动态路由 `/exams/:id` 等） | `frontend/src/router/index.js` `authGuard`：roles/permissions 通过后按学校 `enabledModules` 对直达 URL（含动态详情页）二次门控；有 `school_id` 用户 fail-closed（模块态须已加载且 moduleCode 在启用列表，否则 `next('/')`），admin 无校豁免；`loadModules` API 失败给空列表（非默认模块）使门控真 fail-closed |

> Phase 0.5（模块语义统一，设计 v4 + plan-review R1/R2 处置 + v4 必修6项处置，待实施）：将新增 `docs/governance/module-semantics.yaml`（逐入口期望表：架构模块/后端 prefix/前端 route/portal service ↔ 9 学校开关码；backend_routes 36 条 == `app.routes` 实测顶层 segment，方向 A）+ `scripts/governance/check_module_semantics.py`（6 个 check：守卫用 FastAPI `app.routes` 展开逐路由比对，前端 routeAccess/sidebar/dashboard 均做 route 级 fail-closed+一致性，行为不变、known_drift 按四元组精确豁免、frontend drift 实际探测禁过期）。已登记 11 处 known_drift = 9 backend（4 fail-open: academic/conduct/exam-imports/profile + 5 hygiene: menus/portal/grades/teachers/client-logs）+ 2 frontend（studio/teaching），只登记不修复；`schoolSettings.js` 设置写入消费点纳入零 diff gate。CI 接入 backend job（重依赖）。设计见 `docs/superpowers/specs/2026-06-05-module-semantics-design.md`、计划见 `docs/superpowers/plans/2026-06-05-module-semantics-implementation.md`。

## 按需上下文（需要时 Read）

| 信息 | 路径 |
|------|------|
| 项目结构 + 模块列表 | `docs/reference/REPO_MAP.md` |
| API 端点完整表（320 路由） | `docs/reference/API_ENDPOINTS.md` |
| 角色体系 + 权限映射 | `docs/reference/ROLES.md` |
| 数据模型（88 表） | `docs/reference/DATA_MODELS.md` |
| 技术栈 + 部署 + 端口 | `docs/reference/TECH_STACK.md` |
| 活跃设计/计划索引 | `docs/context/ACTIVE_INDEX.md` |
| 日志查询工具 | `scripts/edu-log <command> --help` |

## 测试基线（2026-05-19）

- 后端：2314 passed / 12 failed / 23 skipped
- 前端：2373 passed / 3 failed
