# exam-ai → edu-cloud takeover index

> 本文档由 2026-04-24 edu-deep-scan 任务（`docs/plans/2026-04-24-edu-deep-scan-design.md`）产出。
> 用户裁定 2026-04-25：`answer-card-editor` 最终整合进 **edu-cloud**（继承原 exam-ai 目标）；前端战略选 **迁移路线**（element-plus 替换 naive-ui，`frontend/` 退役）。

## 1. 简介

2026-04-16 `exam-ai` 归档（见 `~/projects/exam-ai/ARCHIVED.md`），所有阅卷 / 模板 / 扫描 / AI Agent 功能迁入 `edu-cloud`。原 exam-ai 的 `/api` 对外接口在 edu-cloud 以**兼容层**形式保留，供下游仓（paper-seg）零改动对接。

## 2. 端点映射（paper-seg 对接面）

| 原 exam-ai 端点 | edu-cloud 实现 | 调用方 |
|---|---|---|
| POST /api/auth/login | `src/edu_cloud/api/compat_router.py:47` `compat_login` | paper-seg `app/client/api.py` |
| GET /api/exams | `:87` `compat_list_exams` | paper-seg |
| GET /api/exams/{id}/subjects | `:104` `compat_list_subjects` | paper-seg |
| GET /api/templates/{subject_id}/{side} | `:136` `compat_get_template` | paper-seg |
| POST /api/scan/tasks | `:185` `compat_create_scan_task` | paper-seg |
| PATCH /api/scan/tasks/{task_id} | `:215` `compat_update_scan_task` | paper-seg |
| POST /api/scan/upload | `:244` `compat_upload_image` | paper-seg |
| POST /api/scan/upload-objective | `:320` `compat_upload_objective` | paper-seg |

`APIRouter(prefix="/api", tags=["compat"])` @ `src/edu_cloud/api/compat_router.py:38`

## 3. 端口变更

| 原 exam-ai | 新 edu-cloud |
|---|---|
| 8000 | 9000 |

paper-seg 保持 8001；answer-card-editor 保持 8200。

## 4. 代码 provenance 保留点

以下**不改名**，是 takeover 历史痕迹（Claude 在 2026-04-24 brainstorming 原想统一抹除，codex integration review 指出违反 provenance 原则，予以保留）：

- `paper-seg/app/client/api.py:8` `class ExamAIClient` — 类名保留（代码命名 vs 文档叙述需一致）
- `answer-card-editor/backend/app/core/tpl_adapter.py` "TQL 解析器（从 exam-ai 复制）" — 历史来源说明
- `answer-card-editor/CLAUDE.md:95-97` `~/projects/exam-ai/docs/codex-card-editor-geom-consult.log` — 历史咨询日志路径（归档冻结，仅历史参考）

## 5. 前端战略（2026-04-25 裁定）

用户裁定：

- `frontend/`（Vite SPA + naive-ui，24.5k LOC，生产 serving @ https://mcu.asia）→ **迁移退役**
- `frontend-nuxt/`（Nuxt 3 + element-plus，4.4k LOC，dev only）→ **继任者**

迁移路线图待独立 T3 plan 展开（见 design §14.4 D-01 + D-11 + D-18，以及 §15.1 新增 T3-12）。

## 6. answer-card-editor 整合（2026-04-25 裁定）

用户裁定：answer-card-editor 最终整合进 edu-cloud（继承原 exam-ai 的整合目标）。

当前状态：answer-card-editor 独立 8200 端口运行，自有 `/api/*` 11 端点。整合时机与方式待独立 T3 plan 展开（见 design §10.5 U-07，§15.1 新增 T3-13）。

## 7. 归档禁区

- `~/projects/exam-ai/` — 归档冻结（`ARCHIVED.md:3` "禁止在本仓做任何改动"）。所有新指引写在 edu-cloud（本文档），不回写归档仓。

## 8. 参考文档

- `~/projects/exam-ai/ARCHIVED.md` — 13 行迁移映射表
- `~/projects/edu-cloud/CLAUDE.md` §exam-ai 兼容端点（L677-692）
- `~/projects/paper-seg/CLAUDE.md` §与 edu-cloud 的接口（/api 兼容层）
- `~/projects/answer-card-editor/CLAUDE.md` §关联项目
- `~/projects/edu-cloud/docs/plans/2026-04-24-edu-deep-scan-design.md` — 深度扫描 design（含 §13 codex 反馈 + §14 修正 + §15 用户裁定）
