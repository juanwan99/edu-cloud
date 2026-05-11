# edu-cloud 整体修复方案（Claude × GPT 共识）

> **日期**: 2026-05-08
> **共识方**: Claude Opus 4.6 + GPT 5.5
> **审计依据**: `docs/2026-05-08-health-audit-claude-gpt.md`
> **版本基线**: `faa185a` (master, 39 dirty + 17 untracked)

---

## 铁律：防版本劣化

### 不可回退变更（dirty state 中，任何修复必须保留）

| 变更 | 位置 | 回退后果 |
|------|------|---------|
| GradingResult UniqueConstraint → `(school_id, answer_id)` | `grading/models.py` | 跨校数据泄露 |
| auto_fix_ab_sides 废弃为 no-op | `scan/pipeline_service.py` | 作文页 A/B 配对损坏 |
| GRADING_DISPATCH_ROLES 收窄 | `frontend/src/config/roles.js` | 权限越权 |
| CardEditor TQL 视图移除 | `CardEditor.vue` | 废弃代码复活 |
| 3 新模块 | `questionSort.js`, `question_order.py`, `basic_report_service.py` | ImportError |

### 每阶段锚点检查（gate 前必跑）

```bash
# 5 项锚点存在性检查
grep -q "school_id.*answer_id" src/edu_cloud/modules/grading/models.py
grep -q "return 0" src/edu_cloud/modules/scan/pipeline_service.py  # auto_fix no-op
grep -q "SCHOOL_ADMIN_ROLES" frontend/src/config/roles.js
test ! -f frontend/src/components/CardEditor.vue || ! grep -q "switchToTql" frontend/src/components/CardEditor.vue
test -f frontend/src/utils/questionSort.js && test -f src/edu_cloud/modules/exam/question_order.py
```

### b0d314cc 只读文件（本方案禁止修改）

```
src/edu_cloud/api/deps.py
src/edu_cloud/api/ai.py
src/edu_cloud/api/impersonate.py
src/edu_cloud/modules/grading/router.py
src/edu_cloud/modules/grading/models.py
src/edu_cloud/modules/exam/results_router.py
src/edu_cloud/modules/exam/results_service.py
src/edu_cloud/modules/exam/joint_exam_router.py
src/edu_cloud/modules/exam/joint_exam_service.py
src/edu_cloud/modules/exam/router.py
```

---

## Dirty State 处理策略

**不做 blanket commit / stash / reset。** 当前 dirty state 含不可回退业务修复，保持原样叠加修复。

提交按可验证领域切分：
1. 权限安全修复 → 一次 commit
2. scan 安全封堵 → 一次 commit
3. 前端 XSS/fetch → 一次 commit
4. 性能修复 → 一次 commit
5. 架构重构 → 按模块各一次 commit
6. 清理 → 一次 commit

---

## Phase 0：现场冻结（不产生 diff）

| 步骤 | 命令 | 预期 |
|------|------|------|
| codex-check | `scripts/codex-check` | PASS |
| 锚点检查 | 上方 5 项 grep/test | 全通过 |
| 基线快照 | `pytest --co -q 2>&1 \| tail -3` | 收集当前测试数 |
| 基线快照 | `cd frontend && npx vitest run --reporter=verbose 2>&1 \| tail -5` | 收集前端测试数 |

**Gate**: 锚点全通过，基线数字记录。不产生任何文件变更。

---

## Phase 1：低冲突关键安全（不碰 b0d 文件）

### Task 1: N-C01 teacher 端点权限

| 字段 | 值 |
|------|-----|
| 改动文件 | `src/edu_cloud/modules/student/teacher_router.py` |
| 新增测试 | `tests/test_api_exam/test_teacher_permission.py` |
| 方案 | 所有 CUD 端点加 `require_permission(Permission.MANAGE_TEACHERS)` |
| 碰 b0d | 否 |
| diff 估算 | +100/-20 |

### Task 2: N-C02 card 端点权限

| 字段 | 值 |
|------|-----|
| 改动文件 | `card/router.py`, `card_export_router.py`, `card_template_router.py` |
| 新增测试 | `tests/test_api_exam/test_card_permission.py` |
| 方案 | 发布/导出/模板变更加 `require_permission(Permission.MANAGE_EXAMS)` |
| 碰 b0d | 否（card 不在 b0d 范围） |
| diff 估算 | +180/-40 |

### Task 3: N-H08 + N-L04 登录 rate limit

| 字段 | 值 |
|------|-----|
| 改动文件 | `api/auth.py`, `conduct/parent_router.py`, `api/client_logs.py` |
| 新增文件 | `src/edu_cloud/core/rate_limit.py`（可选，或用 slowapi） |
| 方案 | 登录 5 次/分钟/IP；client_logs 用服务端 session 而非客户端传入 |
| 碰 b0d | 否 |
| diff 估算 | +220/-40 |

### Task 4: N-H04 grading worker 吞错

| 字段 | 值 |
|------|-----|
| 改动文件 | `workers/grading.py` |
| 方案 | `except Exception: pass` → `except Exception: logger.error("...", exc_info=True)` |
| 碰 b0d | 否（b0d 碰的是 grading/router.py 不是 workers/） |
| diff 估算 | +35/-4 |

**Phase 1 Gate**:
```bash
# 锚点检查
# targeted pytest
.venv/bin/python -m pytest tests/test_api_exam/test_teacher_permission.py tests/test_api_exam/test_card_permission.py -v
# safety
scripts/codex-verify safety
```

---

## Phase 2：scan 安全封堵

### Task 5: N-C03 browse-directory 目录限制

| 字段 | 值 |
|------|-----|
| 改动文件 | `scan/pipeline_router.py` (~line 292-320) |
| 方案 | 限制根目录为 `settings.UPLOAD_DIR` 或 `settings.STORAGE_DIR`；校验 `resolved.is_relative_to(allowed_root)` |
| 碰 b0d | 否 |
| diff 估算 | +70/-20 |

### Task 6: N-M06 scan 资源关闭

| 字段 | 值 |
|------|-----|
| 改动文件 | `scan/pipeline_service.py`, `scan/auto_detect_cv.py` |
| 方案 | `Image.open()` / `fitz.open()` 用 `with` 或 try/finally 确保关闭 |
| 碰 b0d | 否 |
| diff 估算 | +80/-35 |

**Phase 2 Gate**:
```bash
.venv/bin/python -m pytest tests/test_api/test_scan_pipeline_api.py -v
# 新增目录遍历测试
```

---

## Phase 3：前端 XSS / fetch / token

### Task 7: N-H03 DOMPurify innerHTML

| 字段 | 值 |
|------|-----|
| 改动文件 | `CardEditor.vue`, `QuestionContentModal.vue`, `render.js`, `interact.js` |
| 方案 | 所有 innerHTML 赋值前经 `DOMPurify.sanitize()` |
| 碰 b0d | 否 |
| diff 估算 | +60/-25 |
| 注意 | **保留 CardEditor TQL 删除**，不恢复 switchToTql |

### Task 8: N-M02/03 fetch → Axios

| 字段 | 值 |
|------|-----|
| 改动文件 | `CardEditor.vue`, `card-editor/export.js`, `stores/aiChat.js`, `pages/exam-detail/VisualEditorTab.vue` |
| 方案 | 替换 `fetch()` 为 `client.get/post()`，保留 `localStorage.getItem('token')` 读取点统一 |
| 碰 b0d | 否 |
| diff 估算 | +160/-120 |

### Task 9: N-M05 + N-H07 路由守卫加固

| 字段 | 值 |
|------|-----|
| 改动文件 | `router/index.js`, 可选 `api/client.js` |
| 方案 | 路由守卫增加 token 有效性 pre-check（解码检查过期，非仅 truthy）；Axios 拦截器增加 token 过期主动 logout |
| 碰 b0d | 否 |
| diff 估算 | +120/-70 |

**Phase 3 Gate**:
```bash
cd frontend && npx vitest run
npm run lint
npm run build
scripts/truth-status.sh /home/ops/projects/edu-cloud
```

---

## Phase 4：性能修复（等 b0d checkpoint）

### Task 10: N-H09 + N-H10 阅卷分页与 N+1

| 字段 | 值 |
|------|-----|
| 改动文件 | `grading/grading_review_router.py` |
| 前置 | **等 b0d314cc 提交 grading 相关修改后再动** |
| 方案 | `.all()` 加 `limit/offset` 参数；dispatch/status 改批量 count 查询 |
| 碰 b0d | **间接协调** — b0d 可能改 grading_review_router 的权限 |
| diff 估算 | +220/-90 |

**Phase 4 Gate**:
```bash
.venv/bin/python -m pytest tests/test_api_exam/ -k "grading" -v
```

---

## Phase 5：scan async 与 router 拆分

### Task 11: N-H06 scan async offload

| 字段 | 值 |
|------|-----|
| 改动文件 | `scan/pipeline_router.py`, `scan/pipeline_service.py`, `scan/auto_detect_cv.py` |
| 方案 | CPU-bound CV 操作用 `asyncio.to_thread()` 包装 |
| diff 估算 | +160/-80 |

### Task 12: N-H05 pipeline router 拆分

| 字段 | 值 |
|------|-----|
| 改动文件 | `scan/pipeline_router.py` → 拆出 `scan/pipeline_browse_router.py` + `scan/pipeline_detect_router.py` |
| 前置 | Task 11 完成 |
| diff 估算 | +260/-260（总行数守恒） |

---

## Phase 6：前端结构优化

### Task 13: N-H02 Naive UI 按需导入

| 改动文件 | `frontend/src/main.js`, 可选新增 `plugins/naive.js` |
| 方案 | 移除 `app.use(naive)`，改用 `unplugin-vue-components` 或手动按需注册 |

### Task 14: N-H01 ReviewPage 拆分

| 改动文件 | `ReviewPage.vue` → 拆出 `pages/review/ImageViewer.vue` + `ScoringPanel.vue` + `FloatingReview.vue` |
| 注意 | **保留悬浮阅卷模式功能**，只拆结构不改行为 |

### Task 15: N-M01 analytics 拆分

| 改动文件 | `analytics/` 模块内部重组 |
| 注意 | **保留 basic_report_service.py（新模块）**，不回退 |

### Task 16: N-M04 + N-M10 + N-L07 前端清理

| 改动 | 删 5 死组件 + 移除 `marked` 依赖 + 提取 `randomHex12` 到共享工具 |

---

## Phase 7：后端清理与测试债

### Task 17: N-M07 create_all 清理

| 改动文件 | `data/seed_school.py`, `data/seed_highschool_supplement.py`, `data/import_exam_xlsx.py` |
| 方案 | 改用 `alembic upgrade head` 或从已有 engine 获取 session |

### Task 18: N-M09 + N-L08 依赖清理

| 改动 | pyproject.toml 移除 `qrcode`, `python-dateutil`, `lxml`；评估 python-jose → PyJWT |

### Task 19: N-L01/02/03 测试更新

| 改动 | 按模块逐批更新 44 个过时测试 + paper 模块补 smoke test |
| 注意 | **不改变测试对应的生产代码行为** |

---

## Phase 8：最终验证（等 b0d 合并后）

```bash
# 锚点检查
# 全量后端
.venv/bin/python -m pytest --tb=short -q
# 全量前端
cd frontend && npx vitest run
# 构建
npm run build
# 交付链路
scripts/truth-status.sh /home/ops/projects/edu-cloud
# 安全全扫
scripts/codex-verify safety --repo-wide
```

**最终基线目标**: 后端 ≥2468 passed（当前基线不降）、前端 ≥2495 passed、npm audit 0 HIGH。

---

## 文件冲突矩阵

| 文件 | 涉及 Task | 冲突策略 |
|------|----------|---------|
| `scan/pipeline_router.py` | T5, T11, T12 | 严格按顺序：封堵→async→拆分 |
| `CardEditor.vue` | T7, T8 | T7(sanitize) 先做，T8(fetch) 后做 |
| `card/router.py` | T2 | 仅加权限，不改业务逻辑 |
| `grading_review_router.py` | T10 | 等 b0d checkpoint |
| `ReviewPage.vue` | T14 | Phase 6 最后做，保留 dirty 功能 |
| `analytics/router.py` | T15 | 保护 dirty import |
| `workers/grading.py` | T4 | 仅改 except 行，不碰业务逻辑 |

---

## 工时估算

| Phase | 工时 | 累计 |
|-------|------|------|
| Phase 0 | 0.5h | 0.5h |
| Phase 1 (安全) | 4h | 4.5h |
| Phase 2 (scan 封堵) | 2h | 6.5h |
| Phase 3 (前端安全) | 3h | 9.5h |
| Phase 4 (性能) | 3h | 12.5h |
| Phase 5 (scan 重构) | 4h | 16.5h |
| Phase 6 (前端结构) | 6h | 22.5h |
| Phase 7 (清理) | 4h | 26.5h |
| Phase 8 (验证) | 1h | 27.5h |

**总计约 27.5h，预计 3-4 个工作日。**

---

*Claude × GPT 共识达成。方案核心：安全先行、逐阶段 gate、锚点守恒、b0d 只读协调。*
