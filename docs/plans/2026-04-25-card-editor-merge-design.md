---
baseline_command: "cd ~/projects/edu-cloud && uv run python -m pytest --collect-only -q"
baseline_verified_at: "2026-04-25 00:55"
baseline_count: 2187
---

# T3-13 answer-card-editor 合入 edu-cloud design（U-07 落地）

<!-- key-start -->
## 0. 任务卡

| 项 | 值 |
|---|---|
| Topic | card-editor-merge |
| 父任务 | edu-deep-scan §11.1 D-01 旁支 / §10.5 U-07（用户 5(a) 裁定） |
| 触发 | 用户裁定 2026-04-25 选 (a) 合入 edu-cloud（继承原 exam-ai integration 目标） |
| 范围 | answer-card-editor → edu-cloud：11 端点迁移 + 后端合并 + 前端挂载 + card_editor.db 数据合并 |
| 形态 | brainstorming 产物；等 approve 进 writing-plans → 独立会话 executing |
| 前置 | T3-12 B0 build pipeline（前端挂载点稳定）+ T3-02 alembic drift（schema 稳）|
<!-- key-end -->

### 0.1 现状证据回顾

**answer-card-editor 现状**：
- 独立 8200 端口（node 进程，pid 1590097，待 verify Python or node）
- 后端 `backend/app/main.py` + `backend/app/api/templates.py`
- 前端 `frontend/src/` Vue + Vite，端口 3200
- 11 端点：
  - GET /api/spec/{subject} / /api/patch/{subject} / /api/render-vm/{subject} / /api/image/{subject}/{page}
  - PUT /api/patch/{subject}
  - POST /api/validate/{subject}
  - GET/POST/DELETE /api/templates(/{id}) + POST /api/templates/match
- 数据：`backend/data/card_editor.db`（运行时生成，含 card_templates 表）
- 非 git 仓库（解决 D-06 见 T3-05）

**edu-cloud 现状**：
- `src/edu_cloud/modules/card/` 已存在（22 文件，6134 LOC）— 但功能定位不同（应该是切图模板？）
- compat_router 有 `GET /api/templates/{subject_id}/{side}`（compat_router.py:136）
- card_editor 的 11 端点路径与 edu-cloud 现有 router 可能冲突（路径前缀同 /api/templates）

---

## 1. 设计目标

**核心**：把 answer-card-editor 的 11 端点 + Vue 前端 + card_editor.db 数据合并到 edu-cloud，answer-card-editor 仓退役（archive）。

**子目标**：
1. 解决 11 端点路径冲突（answer-card-editor /api/templates vs edu-cloud /api/templates）
2. 后端代码迁入 `src/edu_cloud/modules/card_editor/`（新模块）或合并到现有 `modules/card/`
3. card_editor.db 数据迁入 edu_cloud.db
4. 前端 SvgCardStage.vue 等组件迁入 frontend-nuxt（前提 T3-12 已完成）
5. answer-card-editor 仓加 ARCHIVED.md（同 exam-ai 模式）

**非目标**：
- ❌ 重写 GeometrySpec / GeometryPatch / TQL adapter（保留现状）
- ❌ 改 SVG 渲染算法（保留现状）

---

## 2. 端点路径冲突评估

| answer-card-editor 端点 | edu-cloud 现状 | 冲突级别 | 决策 |
|---|---|---|---|
| GET /api/spec/{subject} | 无 | 无 | 直接迁 |
| GET /api/patch/{subject} | 无 | 无 | 直接迁 |
| PUT /api/patch/{subject} | 无 | 无 | 直接迁 |
| GET /api/render-vm/{subject} | 无 | 无 | 直接迁 |
| GET /api/image/{subject}/{page} | 无 | 无 | 直接迁 |
| POST /api/validate/{subject} | 无 | 无 | 直接迁 |
| GET /api/templates | edu-cloud 现有 `/api/templates` 由 compat 提供（paper-seg 用）| **可能冲突** | 加 query param 区分 / 改路径前缀（/api/card-editor/templates）|
| GET /api/templates/{id} | 同上 | **可能冲突** | 同上 |
| POST /api/templates | 同上 | **可能冲突** | 同上 |
| DELETE /api/templates/{id} | 同上 | **可能冲突** | 同上 |
| POST /api/templates/match | 同上 | **可能冲突** | 同上 |

**决策（推荐）**：把 answer-card-editor 的端点全部加前缀 `/api/card-editor/*`，避免与 paper-seg 调用的 `/api/templates/{subject_id}/{side}` 混淆。

新前缀映射：
- `/api/card-editor/spec/{subject}`
- `/api/card-editor/patch/{subject}`
- `/api/card-editor/render-vm/{subject}`
- ...

answer-card-editor 前端代码同步更新 fetch 路径。

---

## 3. 后端代码合并

### 3.1 模块组织

`src/edu_cloud/modules/card_editor/`（新建）：
```
card_editor/
  __init__.py
  router.py               # 11 端点（迁自 backend/app/main.py + api/templates.py）
  models.py               # card_templates 表 ORM（迁自 backend/app/db.py）
  core/
    tpl_adapter.py        # 迁自 backend/app/core/
    geometry_builder.py
    patch_engine.py
    validator.py
    seed.py
  schemas/
    geometry_spec.py      # 迁自 backend/app/schemas/
    geometry_patch.py
    validation_report.py
  storage/                # 静态文件目录
    specs/
    images/
    patches/
  MODULE.md               # 治理（解决 D-14）
```

router 注册在 `src/edu_cloud/api/app.py` lifespan 区。

### 3.2 数据迁移（card_editor.db → edu_cloud.db）

`card_editor.db` 含 `card_templates` 表。**注意：edu-cloud 已有 `templates` 表（27 行）**，名称冲突。

**决策**：
- 把 card_editor.db 的 `card_templates` 表数据 export → 转换 → import 到 edu_cloud.db 新表 `card_editor_templates`（重命名避冲突）
- 写一个 alembic migration `<rev>_create_card_editor_templates.py` 建新表
- 写一个一次性脚本 `scripts/migrate_card_editor_db.py` 跑数据迁移

### 3.3 静态文件迁移

`backend/storage/{specs,images,patches}/` → edu-cloud `storage/card-editor/{specs,images,patches}/`

`POST /api/card-editor/image/{subject}/{page}` 改读 edu-cloud `storage/card-editor/images/`。

### 3.4 依赖整合

answer-card-editor 后端依赖（5 个）：fastapi, uvicorn, pydantic, playwright, orjson
- fastapi/uvicorn/pydantic/orjson：已在 edu-cloud
- **playwright**：edu-cloud Dockerfile 已装（用于 card PDF 生成）→ 已有

→ 无新增依赖。

---

## 4. 前端合并（前提 T3-12 完成）

answer-card-editor 前端：
- `frontend/src/main.js` Vue 入口
- `frontend/src/App.vue` 科目选择 + 页面容器
- `frontend/src/components/SvgCardStage.vue` SVG 渲染（核心组件）

**决策**：
- 等 T3-12 frontend-nuxt 上线后，把 SvgCardStage.vue 迁入 `frontend-nuxt/components/card-editor/`
- 新建 `frontend-nuxt/pages/card-editor/index.vue` 作为入口
- naive-ui → element-plus 适配（如有依赖）— 实测看 SvgCardStage.vue 主要是 SVG，UI 库依赖应较低

**风险**：T3-13 强依赖 T3-12，时序需协调。

---

## 5. 退役 answer-card-editor 仓

合并完成后：
- 写 `~/projects/answer-card-editor/ARCHIVED.md`（同 exam-ai 模式，含端点 → edu-cloud 映射表）
- 删除 8200 端口的进程（pid 1590097 之类）
- 在 takeover-index.md 加新一节"answer-card-editor → edu-cloud"
- 更新 paper-seg CLAUDE.md（如有引用 answer-card-editor 仓的话——P3 调研时未发现 paper-seg 直接调 card-editor，无需改）

---

## 6. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 端点前缀变更（card-editor）破坏现有 vue 前端 | answer-card-editor 自身 UI 报 404 | 同步改前端 fetch 路径 |
| card_templates 表数据格式与 edu-cloud `templates` 不同 | 数据迁移失败 | export → manual schema mapping → import；先 dry-run |
| `playwright` 在 edu-cloud lifespan 启动时机 | 内存翻倍（双 chromium） | 评估 lazy load |
| TQL adapter 代码 provenance（"从 exam-ai 复制"）需保留注释 | 历史信息丢失 | 迁移时保留注释，加日期标 "@ T3-13 commit migrated" |

---

## 7. 实施步骤（写 plan 用）

| 阶段 | 动作 |
|---|---|
| **S1** 后端模块迁入 | `src/edu_cloud/modules/card_editor/` 建模 + 迁代码 + alembic migration 建表 |
| **S2** 路径前缀改 | 11 端点加 `/api/card-editor/` 前缀 |
| **S3** 数据迁移脚本 | `scripts/migrate_card_editor_db.py` + dry-run + run |
| **S4** 静态文件迁移 | `storage/card-editor/` |
| **S5** 集成测试 | 全量 pytest + 端到端 e2e |
| **S6** 前端迁移 | 等 T3-12 完成后再做（依赖 frontend-nuxt 上线）|
| **S7** answer-card-editor 退役 | ARCHIVED.md + 进程关停 + takeover-index 更新 |

---

## 8. 验收标准

- [ ] 11 端点在 edu-cloud 9000 上以 `/api/card-editor/*` 前缀提供
- [ ] card_editor.db 数据 100% 迁入 edu_cloud.db `card_editor_templates` 表
- [ ] 静态文件全迁
- [ ] 全量 pytest ≥ 2187 + 新增 card-editor 模块测试
- [ ] answer-card-editor 仓有 ARCHIVED.md
- [ ] 8200 端口不再有 answer-card-editor 进程
- [ ] takeover-index.md 增 "answer-card-editor → edu-cloud" 节

---

## 9. 与其他 T3 的关系

- **T3-12**（前端迁移）：S6 前端迁移依赖 frontend-nuxt 完成（强前置）
- **T3-02**（alembic drift）：建 `card_editor_templates` 表的 migration 须在 T3-02 后写（schema 稳）
- **T3-05**（非 git 仓库 git 化）：answer-card-editor 退役后无需再 git 化，与 T3-05 范围调整

---

**T3-13 design 草稿 v0 完 @ 2026-04-25**
**等 approve 进 writing-plans；执行强依赖 T3-02 + T3-12，时序协调**
