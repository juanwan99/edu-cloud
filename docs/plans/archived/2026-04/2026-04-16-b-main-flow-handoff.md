# HANDOVER — edu B 端阅卷主链路打通（2026-04-16）

> **读者**：接替本任务的新 Claude 会话。上一窗口已完成 Phase 0-A/0-B/0-C，剩 0-D → 1-A/B/C → 2-A/B/C → 3。本文件自含所有必要上下文，**无需回看历史对话**。

---

## 1. 项目范围与铁律（先读一次）

### 1.1 edu B 端专指四仓
- `/home/ops/projects/edu-cloud/` — **权威仓**，本机阿里云河源生产运行（systemd: `edu-cloud.service`, port 9000）
- `/home/ops/projects/paper-seg/` — 扫描工作站（FastAPI, port 8001）
- `/home/ops/projects/answer-card-editor/` — 答题卡模板编辑器
- `/home/ops/projects/exam-ai/` — **已归档（2026-04-16），只读**。根目录有 `ARCHIVED.md`，CLAUDE.md 顶部有 ⛔ 告示。任何改动**必须**在 edu-cloud 落地，禁止改 exam-ai。

**C 端扩展（`zhixue-auto-grader`/`zhixue-server`）与 edu 项目无关**，跑在另一台服务器，不涉及。

### 1.2 用户铁律（违反即返工）
1. **绝对禁止多版本并行**：同一功能不能有 v1+v2、新旧路由双挂、两张表同义。发现并行必须先合并再推进。
2. **不要积累技术债**：不留 TODO/FIXME/stub；若下一步依赖当前占位实现，就在当前任务内解决。
3. **调查清楚再动手**：大改动前先用 Explore agent 摸清读写点、测试、跨文件引用；避免改一点爆一片。

---

## 2. 已完成（2026-04-16）

### Phase 0-A — 后端单一分数源 ✅
合并 `AIGradingResult` + `TeacherReview` + `MarkingScore` + `MarkingAssignment` 4 张并行表为 **`GradingResult` + `GradingAssignment`**。

**GradingResult schema**（`src/edu_cloud/modules/grading/models.py`）：
```python
answer_id (UNIQUE)  question_id  school_id
ai_task_id (FK grading_tasks.id nullable)
ai_score  ai_confidence  ai_feedback  ai_raw_response    # AI 预评留痕
final_score  max_score                                    # 权威分数
status: ai_pending | ai_done | confirmed                  # 状态机
source: ai | ai_override | manual | None                  # 仅 confirmed 时有值
reviewer_id  reviewed_at  review_comment
version  (乐观锁)
```

**状态机**：
- AI 路径：worker 写 `status='ai_done', ai_score=X, final_score=X`
- 教师 approve：`status='confirmed', source='ai'`（final 不变）
- 教师 override：`status='confirmed', source='ai_override', final_score=adjusted`
- 纯人工：直接 `status='confirmed', source='manual', ai_score=None`

**读写迁移已完成**：`workers/grading.py`、`data/import_real_exam.py`、`modules/pipeline/service.py`、`modules/analytics/__init__.py`、`modules/marking/{router,scorer,exporter}.py`、`modules/grading/router.py`、`alembic/env.py`、`api/app.py` 全部切换，marking/models.py 清空。

**Alembic 迁移**：`alembic/versions/a7e9c4b8d123_merge_grading_marking_into_grading_result.py`。upgrade/downgrade 双向验证通过。包含旧表数据迁移逻辑（生产库零数据但保留健壮性）+ `grading_quality_checks.original_result_id` FK 改指向新表。

**测试**：15 个直接受影响的测试文件全部更新（`tests/test_services_exam/test_grading_{models,worker}.py`、`tests/test_services_exam/test_{analytics,data_pipeline,profile_pipeline,report_service}.py`、`tests/test_api_exam/test_{grading_review,dispatch_status,grading_task,analytics,analytics_class_filter,analytics_report,analytics_subject_id,grade_aggregates}.py`、`tests/test_ai/test_tools_analytics_report.py`、`tests/test_services_exam/test_all_models.py`），100+ 定向测试全绿。

**文档同步**：`modules/grading/MODULE.md`、`modules/pipeline/MODULE.md`、`docs/governance/modules.yaml`。

### Phase 0-B — 前端两页合并 ✅
删除 `pages/MarkingPage.vue` 和 `pages/TeacherReviewPage.vue`，新建 `pages/ReviewPage.vue`（442 行）——图片查看 + AI 预测卡（条件显示）+ 评分输入 + 快捷键。

**核心逻辑**：`/marking/next` 现返回 `{answer_id, student_id, image_path, position, ai: {score,confidence,feedback,result_id}|null, max_score}`；前端若 `ai != null` 自动预填分数供校对，用户可改；统一 POST `/marking/score`，后端 `scorer.submit_score` 自动识别 source（ai/ai_override/manual）。

**路由变更**（`src/router/index.js`）：`/marking/grade/:questionId` 指向 `ReviewPage`；`/grading/review` 路由整条删除；`router.test.js` 断言 34→33。

**其它联动**：`GradingDispatchPage.vue` 的"去校对"按钮 `push({name:'TeacherReview'})` → `push({name:'MarkingSelect'})`；`api/grading.js` 移除 `getPending`+`submitReview`（已废）。

**验证**：`npm run build` 绿；`npm run test`（vitest）233/233 通过。

### Phase 0-C — 调度状态端点 ✅
`/api/v1/grading/dispatch/status` 后端已实现（`modules/grading/router.py` L391–521），前端 `getDispatchStatus` 对齐。本次仅确认无需新增工作。

---

## 3. 剩余任务（按推荐执行顺序）

### 3.1 Phase 0-D — paper-seg 本地模板 CRUD 清理（阵地：`/home/ops/projects/paper-seg/`）

**现状**：`app/routers/templates.py` 是一整套本地模板 CRUD（增/删/改/导入/导出/auto-match），与 edu-cloud 的 `Template` 表并行 —— 违反"禁止多版本并行"。但它通过 `_tpl_path` 和 `TEMPLATES_DIR` 被 `app/routers/pipeline.py` / `app/routers/segment.py` 紧耦合用来**读**本地缓存的模板文件。

**动作**：
1. 保留"**从 edu-cloud 拉取 + 本地缓存**"能力，删除本地 CRUD 接口。
2. 具体：
   - `app/routers/connect.py` 已有 `convert_server_template()`（把 edu-cloud 模板转为本地结构）。确认 pipeline 已走该路径 → 走了就把 `_tpl_path` 定义为只读的 cache 查找函数（不再对外暴露 CRUD）。
   - 删除 `app/routers/templates.py` 里的 POST/PUT/DELETE 端点；若 `_tpl_path` 继续保留，迁到 `app/tpl_cache.py`（新文件）。
   - `app/main.py` 的 `app.include_router(templates.router)` 删除。
   - 更新 `pipeline.py:79`、`segment.py:12` 的 import 指向新位置。
   - 更新测试：`tests/test_pipeline.py` L54/88/117、`tests/test_tpl_import.py` 改引用 `TEMPLATES_DIR` 从新位置。
3. 相关文件：`docs/plans/archived/2026-03-09-tpl-split-and-exam-list-plan.md`（旧文档，无需改）。

**验收**：`cd /home/ops/projects/paper-seg && pytest --tb=short -q`；paper-seg 作为"下游只读客户端"对 edu-cloud 的 `GET /api/templates/{subject_id}/{side}` 端点工作。

**风险**：paper-seg 的 CLAUDE.md 第 72 行注明 `TODO(cleanup): exam-ai 答题卡生成功能上线后删除本地模板全代码`——确认 edu-cloud 答题卡功能已稳定再动手（已稳定，可以做）。

### 3.2 Phase 1-A — 题型词汇表统一（阵地：edu-cloud + paper-seg + answer-card-editor）

**现状混乱**：
- `Question.question_type` (edu-cloud `modules/exam/models.py`) 仅 `objective`/`subjective` 二值
- `Template.regions[].type` (edu-cloud `modules/card/models.py`) 用 `choice_group` / `number_fill` / `subjective` / `absent_mark` 等
- `layout.py:185 / 320`、`renderer.py:1140` 已出现 `fill_blank` 但未持久化
- paper-seg 的 `pipeline.py:164-167` 按 `fillmark_types = {"choice_group", "number_fill", "absent_mark"}` 两路分支

**目标枚举**：`choice | multi_choice | fill_blank | essay`（综合题拆 sub-region）

**动作**：
1. `modules/exam/models.py::Question.question_type` 支持 4 值（String(20) 已够，只改约束文档）
2. `modules/card/models.py::Template.regions[]` schema 统一字段名：将 JSON 里 `type` 重命名为 `question_type`，取值映射：
   - `choice_group` → `choice`
   - `number_fill` → `fill_blank`
   - `subjective` → `essay`
   - `absent_mark` 保留（不是题型，是"缺考标记区"，仍用 `type`）
3. Alembic 迁移：扫 `templates.regions` JSON 做 in-place update；扫 `questions.question_type` 做 `subjective`→`essay`/`objective`→`choice` 默认映射（需要更精细可按 Template region 反查）。
4. answer-card-editor：`/home/ops/projects/answer-card-editor/` 的 JSON schema（`schemas/` 或 `frontend/src/model.js`）同步新字段
5. paper-seg `pipeline.py` 的 `fillmark_types` 改为 `{"choice", "multi_choice"}`（选择题走填涂），其余走切图

**验收**：edu-cloud alembic upgrade/downgrade 双向通过；相关测试更新；seed_demo.py 用新取值。

### 3.3 Phase 1-B — 题型感知切割（阵地：paper-seg）

**依赖**：Phase 1-A 完成。

**现状**：`paper-seg/app/vision/segment.py::crop_region(img, rect)` 对所有区域用统一 bbox 裁切。

**动作**：
1. 签名改 `crop_region(img, rect, question_type='essay')`，按类型 margin：
   - `choice` / `multi_choice`：0px（这些 region 走 fillmark 不走 crop）
   - `fill_blank`：4px（紧凑，省 token）
   - `essay`：16px（保全笔迹末梢）
2. `pipeline.py` 的 `subjective_regions` 分支内根据 `region.question_type` 分派
3. 单元测试：`tests/test_segment.py` 参数化覆盖 4 种类型

**验收**：paper-seg pytest 绿；用真实扫描样本跑一次 pipeline，肉眼确认 fill_blank 与 essay 裁切差异。

### 3.4 Phase 1-C — 上传链路携带题型元数据（阵地：paper-seg + edu-cloud）

**依赖**：Phase 1-A 完成。

**动作**：
1. **paper-seg 侧**：`app/client/api.py::ExamAIClient.upload_image` 加 `question_type` 参数；`pipeline.py` 调用时传入 `region.question_type`。
2. **edu-cloud 侧**：
   - `modules/scan/models.py::StudentAnswer` 加 `question_type: Mapped[str | None]` 列（Alembic 迁移）
   - `modules/scan/router.py::POST /api/scan/upload` 加入参；落表
3. **AI 阅卷适配**：`workers/grading.py::_grade_single` 读 `answer.question_type`，按类型选不同 prompt：
   - `fill_blank`：短答 prompt（简洁评分，关注答案关键词）
   - `essay`：长答 prompt（分步给分，关注论证完整性）
   - Prompt 在 `modules/grading/prompts.py` 新建两套
4. 测试：`test_grading_worker.py` 加 fill_blank/essay 两类型分别的 prompt 验证

**验收**：端到端——上传一份 fill_blank + essay 混合答卷，AI 评分两类走不同 prompt；edu-cloud 完整测试绿。

### 3.5 Phase 2-A — 年级学科报告导出端点（阵地：edu-cloud）

**依赖**：Phase 0-A（有 `final_score`）。

**动作**：
1. `modules/analytics/router.py` 新增：
   ```
   GET /api/v1/analytics/report/grade/{exam_id}/{subject_id}/export?format=pdf|xlsx
   ```
2. 数据 = 现有 analytics service 聚合：总平均 / 分数段分布 / 班级对比 / 每题得分率 top&bottom
3. PDF 实现：`reportlab` 已在 `pyproject.toml` 依赖（见第 5 节清单）。渲染可复用 `modules/card/html_export.py` 的 HTML→PDF 模式，或者直接用 reportlab Platypus 拼表格
4. XLSX 实现：`openpyxl` 已装。多 sheet（总览 / 班级对比 / 题目分析）
5. 权限：用现有 `get_visible_class_ids(role)` / `get_visible_subject_codes(role)` 过滤
6. 模板：在 `templates/document_templates.py` 新增 `grade_subject_report` 模板

**参考已存在实现**：
- `modules/conduct/export_service.py::export_records_excel` —— openpyxl 多 sheet 写法
- `modules/card/html_export.py::html_to_pdf` —— HTML→PDF（依赖 playwright，该依赖是 pre-existing 缺装问题，可改为 reportlab 纯 Python 实现规避）

**验收**：端点返回 200 + `Content-Type: application/pdf`/xlsx；单元测试覆盖 3 种角色（principal/班主任/任课老师）权限隔离。

### 3.6 Phase 2-B — 个人学科报告导出端点（阵地：edu-cloud）

**依赖**：Phase 2-A（复用 PDF/XLSX 基础）。

**动作**：
1. `modules/analytics/router.py` 新增：
   ```
   GET /api/v1/analytics/report/student/{student_id}/{exam_id}/{subject_id}/export?format=pdf|xlsx
   ```
2. 数据：总分 / 各题得失分 / 班级均分对比 / 薄弱题 top3（得分率 <60%）
3. 权限：本人 / 家长（cp_token） / 班主任 / 任课老师
4. 数据源：`StudentAnswer` JOIN `GradingResult.final_score` + `StudentExamSnapshot`

**验收**：非授权角色 403；授权角色下载 PDF 内容含 4 个维度。

### 3.7 Phase 2-C — 前端报告页真实下载（阵地：edu-cloud/frontend）

**依赖**：2-A + 2-B。

**动作**：
1. `pages/AnalyticsReportPage.vue` 的"导出 PDF"按钮改调新端点：
   ```js
   const resp = await client.get(endpoint, { responseType: 'blob' })
   const url = URL.createObjectURL(resp.data); ...
   ```
   删除跳转 Studio 的假实现（当前 `exportReport` 方法）
2. `pages/AnalyticsPage.vue` 的学生行加"查看学生报告"入口，跳转到新建的 `StudentReportPage.vue` 或直接下载
3. `api/analytics.js` 加 `exportGradeReport`/`exportStudentReport` 封装

**验收**：前端点击按钮实际下载 PDF/XLSX，浏览器保存不报错。

### 3.8 Phase 3 — 端到端验证（全局）

**依赖**：所有 Phase 完成。

**动作**：
1. 用 seed 数据（`data/seed_demo.py`）+ 样本扫描图（paper-seg 的 `test_data/`）跑完整链路：
   - 扫描 → paper-seg 切图（题型感知）→ 上传到 edu-cloud（带 question_type）
   - 选择题自动判 + AI 评主观题（fill_blank/essay 走不同 prompt）
   - 教师在 `/marking/grade/:questionId` 校对 1 份
   - `/api/v1/analytics/report/grade/...` 导出 PDF，`/api/v1/analytics/report/student/...` 导出 XLSX
2. 跑全量测试：`cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=line -q --no-header --ignore=tests/governance --ignore=tests/test_services_exam/test_card_e2e.py --ignore=tests/test_services_exam/test_card_word_parser.py`
3. paper-seg：`cd /home/ops/projects/paper-seg && pytest --tb=short -q`
4. 前端：`cd /home/ops/projects/edu-cloud/frontend && npm run build && npm run test`
5. 确认：**零新增** TODO/FIXME、全绿（除 pre-existing 见第 6 节）、无多版本并行痕迹

---

## 4. 任务看板（Task Tool 里已登记，沿用）

| ID | 状态 | 任务 |
|----|------|------|
| 1 | ✅ completed | Phase 0-A 合并三张分数表为 GradingResult |
| 2 | ✅ completed | Phase 0-B 合并前端 MarkingPage 与 TeacherReviewPage |
| 3 | ✅ completed | Phase 0-C 补齐 /grading/dispatch/status 端点并修正前端契约 |
| 4 | ⏸ pending | Phase 0-D 删除 paper-seg 本地模板 CRUD |
| 5 | ⏸ pending | Phase 1-A 统一题型词汇表 |
| 6 | ⏸ pending | Phase 1-B 题型感知切割策略（blockedBy 5） |
| 7 | ⏸ pending | Phase 1-C 上传链路携带题型元数据（blockedBy 5） |
| 8 | ⏸ pending | Phase 2-A 年级学科报告导出端点 |
| 9 | ⏸ pending | Phase 2-B 个人学科报告导出端点（blockedBy 8 in实际上我写的 blockedBy 是 1，可放宽） |
| 10 | ⏸ pending | Phase 2-C 前端报告页真实下载（blockedBy 8,9） |
| 11 | ⏸ pending | Phase 3 端到端验证 |

**推荐并行度**：0-D 独立；1-A 完成后 1-B 和 1-C 并行；2-A 完成后 2-B 可并行（都是 backend 导出），2-C 等两者。

---

## 5. 关键架构知识（必读）

### 5.1 仓间调用路径
```
paper-seg (8001) ──httpx──▶ edu-cloud (9000)
  上传切图        /api/scan/upload
  拉取模板        /api/templates/{subject_id}/{side}
  拉取考试列表    /api/exams
  登录           /api/auth/login   (edu-cloud compat_router 兼容层)

edu-cloud 内部：
  阅卷任务        modules/grading/router.py
  人工校对        modules/marking/router.py  （前缀 /api/v1/marking/*）
  分析聚合        modules/analytics/router.py
  考后流水线      modules/pipeline/service.py (arq worker 或 API)
  AI Agent       api/ai.py → ai/agent_loop.py （23 工具，已升级为状态机架构）
```

### 5.2 edu-cloud 已装依赖（用于 Phase 2 导出）
- `reportlab >= 4.4.10` ✅
- `openpyxl >= 3.1.5` ✅
- `python-docx` ❌ 未装（prod 没需要；部分测试因此 fail，pre-existing 问题）
- `playwright` ❌ 未装（同上；card/html_export.py 依赖它，Phase 2 PDF 建议纯 reportlab 规避）
- `weasyprint` ❌ 未装

### 5.3 数据库
- 生产：`edu_cloud.db`（SQLite，`sqlite+aiosqlite:///./edu_cloud.db`）
- 头版本：`alembic/versions/a7e9c4b8d123_merge_grading_marking_into_grading_result.py`（Phase 0-A 新加的）
- 该库在零数据状态下，`grading_results` 等表都已创建
- 生产 `grading_tasks` 有 5 行历史数据（与 Phase 0-A 迁移兼容）

### 5.4 systemd 服务
- `edu-cloud.service` 生产运行；改后 `sudo systemctl restart edu-cloud`
- `paper-seg` 无 systemd（本地跑）

---

## 6. Pre-existing 问题清单（不要踩坑，不是你的 bug）

全量 pytest 有 **37 failed / 1829 passed / 23 skipped**（~10 分钟）。失败全部 pre-existing：

| 文件 | 数量 | 根因 |
|---|---|---|
| test_publish_service.py | 14 | `playwright` 未装（card/html_export.py import） |
| test_cards.py | 3 | `playwright` / `docx` 未装 |
| test_card_publish.py | 2 | `playwright` 未装 |
| test_tql_renderer.py | 2 | 字体缺致 PDF < 30KB |
| test_finalize_skeleton.py | 1 | `docx` 未装 |
| test_answer_standardizer.py | 2 | （未细查，类似 docx/pdf 依赖） |
| test_scan_pipeline.py | 2 | **flaky**（独立跑绿），全局测试顺序致失败 |
| test_pipeline_save_answer.py | 1 | **flaky**（独立跑绿） |
| test_compat.py | 2 | `playwright` 未装（compat_router 调用 card publish） |
| test_tool_access_fail_closed.py | 2 | event loop 问题（pre-existing） |
| test_registry.py | 1 | event loop |
| test_workspace/profile_api/bank_api/deps.py | 4 | auth fixture 问题（pre-existing） |

**这些失败与 Phase 0-A/0-B 无关**；我已把 `test_all_models.py` 原本第 37 项的失败修好。

验收新 phase 时：
- 只看**新增**的 FAILED（对比 pre-existing 清单）
- 若 failure count 仍为 37 且面貌一致，说明没破坏
- 若 count 变大，差异就是新引入的 bug

---

## 7. 调试命令速查

```bash
# edu-cloud 后端
cd /home/ops/projects/edu-cloud
.venv/bin/python -m pytest tests/test_api_exam/test_grading_review.py -v         # 特定测试
.venv/bin/python -m pytest --tb=line -q --no-header \
  --ignore=tests/governance \
  --ignore=tests/test_services_exam/test_card_e2e.py \
  --ignore=tests/test_services_exam/test_card_word_parser.py                       # 全量（~10min）
.venv/bin/alembic heads                                                             # 当前迁移头
.venv/bin/alembic upgrade head                                                      # 应用迁移
.venv/bin/alembic downgrade -1                                                      # 回滚一步

# 前端
cd /home/ops/projects/edu-cloud/frontend
npm run build                                                                        # 构建（16s）
npm run test                                                                         # vitest（8s）

# paper-seg
cd /home/ops/projects/paper-seg
pytest --tb=short -q

# 生产进程
systemctl status edu-cloud
sudo systemctl restart edu-cloud
curl http://127.0.0.1:9000/api/v1/health

# 本机信息：阿里云河源 ECS，主机名 iZf8z2piigunrk8ixto7hnZ，工作目录 /home/ops
```

### 常见检查：摸新 task 前先跑这一串
```bash
cd /home/ops/projects/edu-cloud
ls src/edu_cloud/modules/grading/models.py        # GradingResult 定义位置
.venv/bin/python -c "from edu_cloud.modules.grading.models import GradingResult; print([c.name for c in GradingResult.__table__.columns])"
.venv/bin/python -m pytest tests/test_services_exam/test_grading_models.py -v  # 冒烟 4 个 case
```

---

## 8. 记忆系统（会话级持久化）

本机 Claude Code 开启了 auto memory：`/home/ops/.claude/projects/-home-ops/memory/`

关键文件：
- `MEMORY.md` — 索引
- `project_edu_scope.md` — 项目范围定义（已更新为四仓口径 + exam-ai 已归档）

**新会话加载时会自动注入 MEMORY.md 内容**。已记录的要点：
- edu 项目 = edu-cloud / paper-seg / answer-card-editor（exam-ai 归档）
- edu-cloud 是权威仓，本机阿里云河源运行

---

## 9. 本次会话未解问题（非阻塞，但建议跟进）

1. **`docx` 和 `playwright` 依赖缺失**：导致 17+ 测试 fail。建议在 Phase 2 做 PDF 导出时**不要**依赖 playwright，用 reportlab 纯 Python 路径，规避这块债。如果后续有时间，推动装这两个依赖并修复测试，属于独立小任务。
2. **test_scan_pipeline.py 等 flaky**：独立跑绿、全局跑黄，提示有共享状态污染（可能是 sys.modules 缓存或 DB fixture）。独立任务，非主链路阻塞。
3. **GradingResult.version 乐观锁未被任何代码用到**：Phase 0-A 加的字段，后续若需要防并发覆盖，在 `submit_score` / `submit_review` 里加 `.where(GradingResult.version == expected)` 即可。目前单用户场景不阻塞。

---

## 10. 动手前最后 checklist

- [ ] 确认 working directory `/home/ops/projects/edu-cloud`（改后端）或 `/home/ops/projects/paper-seg`（改扫描）
- [ ] **先读 `TaskList`** 确认待办
- [ ] 改前用 Explore agent 或 Grep 摸读写点（"调查清楚再动手"）
- [ ] 改中每个文件 Edit 后跑该模块对应的 pytest，早发现早修
- [ ] Alembic 迁移要 upgrade+downgrade 双向验证
- [ ] 前端改后 `npm run build && npm run test`
- [ ] 完成后 TaskUpdate 标 completed；发现新问题 TaskCreate 追加
- [ ] **不要改 exam-ai 任何代码** — 已归档

祝顺利。有问题找不到答案，先 grep 代码，别从零设计。
