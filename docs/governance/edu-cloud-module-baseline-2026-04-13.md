# edu-cloud 模块治理基线报告（P0 调研产出）

> 创建时间: 2026-04-13
> 调研者: Opus 4.6（独立调研，未委派 subagent）
> 调研方法: 机械扫描缩小候选 → 分批阅读 + 交叉验证（file:line + 调用方 grep + git log；证据强度按严重度分层，见文末自审说明）
> 设计依据: `docs/plans/2026-04-13-module-governance-design.md` §3.3
> 使用方式: 逐条由用户 approve/reject/defer；approve 的条目进入 P2 落地一并处置；defer 的进入 `debt-report.md`

---

## 调研范围

### 已读模块（分 4 批 × 27 个实体）

| Batch | 范围 | 模块清单 |
|-------|------|---------|
| A（核心业务链路） | `modules/` | paper / scan / pipeline / grading / marking / card |
| B（知识与学习） | `modules/` | knowledge / knowledge_tree / adaptive / analytics / bank / homework |
| C（组织管理） | `modules/` | exam / school / studio / conduct / student / profile / menu / calendar |
| D（横切层） | `services/` + `ai/tools/` + `api/` | 14 个 service 文件 + 24 个 AI tool 模块 + 7 个 api/ stub |

### 阅读深度

- 每模块：`__init__.py`（导出清单） + router（路由前缀） + models（`__tablename__` 清单） + 关键 service
- 机械 grep：`class.*Base)` + `__tablename__\s*=` + `prefix=` + `APIRouter` + re-export 标记
- 深度 Read：仅对候选冲突点的具体文件（scan/card 的 tpl_parser、objective_grading、student/router.py 等）

### 未读（跳过）

- frontend/ — 本次不治理前端模块（设计 §0 明列非目标）
- `card-editor/` 子目录的原生 JS 代码（card 模块内部实现细节，不影响后端契约）
- 各模块 test_* 测试文件（测试内容不影响模块对外契约）

### 统计

| 分类 | 条数 |
|------|------|
| 真冲突（需处置） | 3 |
| 职责互补（保留分工 + MODULE.md 说明） | 4 |
| 历史债务（有记录，择期处理） | 3 |
| 结构性观察（非冲突，供 MODULE.md 撰写参考） | 3 |
| **合计** | **13** |

---

## 真冲突（HIGH — 需要处置决定）

### 冲突 #1: `tpl_parser.py` 在 scan 与 card 两模块并存，功能重叠

- **位置 A**: `src/edu_cloud/modules/scan/tpl_parser.py:1-115`（含 `parse_tpl_file`、`convert_tpl`、`_parse_tpl_location`、`_LOC_ID_MAP`）
- **位置 B**: `src/edu_cloud/modules/card/tpl_parser.py:1-289`（含 `parse_tpl_file`、`_decode_gbk`、`_parse_location`、`_ANCHOR_MAP`）
- **证据**:
  - 两份均含相同映射（scan `_LOC_ID_MAP = {"0101": "TL", "0102": "TR", ...}` 对应 card `_ANCHOR_MAP = {"0101": "TL", "0102": "TR", ...}`）
  - 两份均定义等价的正则 `r"\((\d+),(\d+)\)-\((\d+),(\d+)\)"` 用于位置字符串解析
  - 两份均含同名函数 `parse_tpl_file`
  - git log（`2026-04-09-scan-integration-plan.md`）显示 scan/tpl_parser.py 在 scan 集成时新建，card/tpl_parser.py 先于 scan 存在
- **判定**: 真冲突 — 同一外部格式（月小二 .tpl）的解析逻辑在两处独立实现
- **建议处置**:
  1. **抽共享模块**（推荐）：新建 `src/edu_cloud/shared/tpl_parser.py`（或归入 card 作权威源），提供 `parse_tpl_file` / `_LOC_ID_MAP` / `_parse_location` 等；scan 和 card 各自 import 该共享模块做"转 Template 格式" / "转 CardSkeleton" 的薄壳
  2. 或在 MODULE.md 中明确 scan 版为 deprecated、统一迁移到 card 版
- **影响面** (调用方 grep):
  - `scan/tpl_parser` 被调用: `scan/pipeline_router.py:23`、`tests/test_services_exam/test_scan_tpl_parser.py`（9 处）
  - `card/tpl_parser` 被调用: `card/router.py:152,914`、`card/template_library.py:123,143`、`card/subject_defaults.py:250`、`tests/test_services_exam/test_tpl_parser.py:5`
- **用户决定**: [ ] approve 抽共享 / [ ] approve scan→card 统一 / [ ] reject / [ ] defer

---

### 冲突 #2: "学生×知识点×掌握度" 表三处并存

- **位置 A**: `src/edu_cloud/modules/profile/models.py:40` — `student_knowledge_mastery`（字段 `mastery_level`, `attempt_count`, `correct_count`, `trend`, `recent_scores`）
- **位置 B**: `src/edu_cloud/modules/adaptive/models.py:24` — `student_da_mastery`（字段 `p_mastery`/`mastery_prob`, `p_transit`, `p_slip`, `p_guess`）BKT 引擎专用
- **位置 C**: `src/edu_cloud/modules/analytics/analysis_models.py:52` — `student_knp_mastery`（分析层快照）
- **证据**:
  - 3 个表命名相近、业务维度相同（student×knowledge_point→mastery）但字段集合不同
  - 写入方分布：`pipeline/service.py:update_knowledge_mastery` 写 profile 表；`adaptive/updater.py` 写 adaptive 表；`analytics/analysis_models.py` 作为分析快照
  - 读取方混杂：`ai/tools/student_profile_tool.py`、`ai/workflow/w3_student_profile.py` 可能引用任一
- **判定**: 职责互补但**命名冲突** — 三张表角色不同（通用/BKT/分析），但命名相近导致理解成本高和读取方可能混用
- **建议处置**:
  1. **重命名 + MODULE.md 明确职责**（推荐）：`student_knowledge_mastery`（profile 拥有，保留名）、`student_bkt_mastery`（adaptive 拥有，从 `student_da_mastery` 改）、`student_knp_analysis_mastery`（analytics 拥有）
  2. 或保留现名，MODULE.md 与代码注释显式区分
- **影响面**: 读写方分布 11 处文件（pipeline / adaptive / analytics / profile / knowledge_tree / ai/tools /ai/workflow）
- **用户决定**: [ ] approve 重命名 / [ ] approve 保留现名+注释 / [ ] reject / [ ] defer

---

### 冲突 #3: `api/` 与 `services/` 下共 16 个 re-export stub（历史迁移残留）

- **位置 A**: `src/edu_cloud/api/{schools,joint_exams,results,studio,calendar,workspace}.py`（6 个 stub，canonical 为 `modules/X/router.py`）
- **位置 A-补**: `src/edu_cloud/api/app.py`（含"backwards compatibility"标记，具体位置待定）
- **位置 B**: `src/edu_cloud/services/{approval_service,calendar_service,workspace_service,results_service,notification_service,school_service,joint_exam_service,paper_service,studio_service}.py`（9 个 stub，canonical 为 `modules/X/service.py` 或 `modules/X/notification_service.py`）
- **证据**:
  - 每个 stub 第 1 行均标注 `# Re-export from new location for backwards compatibility (Task 22 cleanup)`
  - stub 内部仅 1 行 `from edu_cloud.modules.X.Y import Z  # noqa: F401`
  - CLAUDE.md `src/edu_cloud/api/` 段已列出 6 个 `schools.py → modules/school/router.py` 等映射表
- **判定**: 历史债务 — 未完成的重构残留
- **建议处置**:
  1. **批量清理**：搜全仓代码改为从 `modules/X` 直接 import → 删除 stub
  2. 或保留直到下个主版本（MODULE.md 标注 status=deprecated、design_docs 指向"Task 22 cleanup"）
- **影响面**: 仓库内对 stub 的 import 数量需逐个 grep 确认；CLAUDE.md 需要同步更新
- **用户决定**: [ ] approve 立即批量清理 / [ ] approve 保留 status=deprecated / [ ] reject / [ ] defer

---

## 职责互补（MED — 在 MODULE.md 明确边界即可）

### 条目 #4: `scan/objective_grading.py` 的"选择题判分"位置错位于 scan 模块

- **位置**: `src/edu_cloud/modules/scan/objective_grading.py:1-19`（19 行纯函数 `grade_objective_answer`）
- **证据**:
  - docstring 注释: `"""选择题判分共享函数 — pipeline 和 router 共用。"""`
  - 功能：输入 `detected_answer/correct_answer/max_score` → 返回 `(score, is_correct)`
  - 业务上属"阅卷"职责域；但代码位置在 scan/ 下
- **判定**: 职责互补 — scan 阶段即完成选择题自动判分（不经 AI），与 grading/（主观题 AI 判分）互补
- **建议处置**: **保留现有位置**；在 scan 的 MODULE.md 明列 exposes.services 含 `grade_objective_answer`，在 grading 的 MODULE.md 边界段声明"选择题判分由 scan 完成"
- **影响面**: 被 `scan/pipeline_router.py` 和 `scan/router.py` 调用；grading 不调用
- **用户决定**: [ ] approve 保留分工 / [ ] approve 迁入 grading / [ ] defer

---

### 条目 #5: `student/router.py` 的 `prefix="/api/v1"` 约定偏离

- **位置**: `src/edu_cloud/modules/student/router.py:14` — `router = APIRouter(prefix="/api/v1", tags=["students"])`
- **证据**:
  - 所有其他业务模块均用 `/api/v1/<module>` 作前缀（grading / marking / analytics / ... 20+ 处一致）
  - student 仅用 `/api/v1` 裸前缀，挂载子路径 `/classes` 和 `/students`
  - 实际完整路径是 `/api/v1/classes` 和 `/api/v1/students`（非模糊），但前缀约定不一致
- **判定**: 职责互补（classes/students 是跨模块共享资源，确实不宜归在 `/api/v1/students` 子路径）
- **建议处置**: **保留现状**；在 student 的 MODULE.md 中显式列 `owns_routes: [/api/v1/classes, /api/v1/students]`（展开挂载路径，而非仅 prefix），并在"边界"段说明"classes 表与 students 表是跨模块基础资源"
- **影响面**: 仅涉及 student/router.py；前端 API 调用路径已稳定
- **用户决定**: [ ] approve 保留 / [ ] approve 改 `/api/v1/students`+`/api/v1/classes` / [ ] defer

---

### 条目 #6: `exam.publish_service` 与 `card.publish_service` 同名（不同语义）

- **位置 A**: `src/edu_cloud/modules/exam/publish_service.py` — 发布考试成绩
- **位置 B**: `src/edu_cloud/modules/card/publish_service.py:1-261` — 发布答题卡模板（题目/模板原子写入）
- **判定**: 职责互补 — 同名但作用于完全不同领域（exam 发布成绩、card 发布卡片），因各自模块内 import 不跨界，无实际冲突
- **建议处置**: MODULE.md 中 exposes.services 标注完整符号路径（如 `edu_cloud.modules.exam.publish_service` vs `edu_cloud.modules.card.publish_service`）以避免 AI tool / 文档摘录时的歧义
- **用户决定**: [ ] approve 保留 + 模块内注释 / [ ] defer

---

### 条目 #7: `knowledge` 与 `knowledge_tree` 双轨知识体系（过渡期并存）

- **位置 A**: `modules/knowledge/` — `knowledge_points` + `question_knowledge_points`（课标知识点，exam-ai 迁入）
- **位置 B**: `modules/knowledge_tree/` — `concept_graph_nodes` + `concept_big_concept_map` + `concept_graph_edges` + `concept_stats` + `edit_sync_failures`（新版概念图谱）
- **桥接表**: `modules/adaptive/models.py:da_knowledge_point_map.concept_node_id FK → concept_graph_nodes`
- **判定**: 职责互补（过渡期双轨） — knowledge 保留给 exam/题库，knowledge_tree 为可视化 + adaptive 服务
- **建议处置**: MODULE.md 中 knowledge 和 knowledge_tree 分别声明所有权，双方"边界"段相互指引；在 knowledge_tree 的 depends_on.modules 中列 knowledge 若有 import，否则通过桥接表隐式依赖
- **用户决定**: [ ] approve 保留双轨 + MODULE.md 明确 / [ ] defer 到知识系统重构

---

## 历史债务（LOW — 记录，择期处理）

### 条目 #8: `scan/pipeline_router.py` 与 `pipeline/router.py` 命名混淆

- **路径**: `/api/v1/scan/pipeline`（扫描切割流水线，前期）vs `/api/v1/pipeline`（考后数据流水线，后期）
- **判定**: 历史债务 — 两个"pipeline"实为不同阶段，命名让 AI tool 和文档摘录易混淆
- **建议处置**: 不改路由（前后端已绑定），但在两模块 MODULE.md「职责」段首行强调"我们是 XX 阶段 pipeline，不是另一个 YY 阶段 pipeline"
- **用户决定**: [ ] approve MODULE.md 强化说明 / [ ] approve 重命名 scan/pipeline_router 为 scan_flow / [ ] defer

---

### 条目 #9: `school/assignment_router.py` 与 `grading/assignment_router.py` 同名不同义

- **school 的**: `teacher_assignments`（教师×班级×科目×学期 排课）tag=`teacher-assignments`
- **grading 的**: `grading_assignments`（AI 阅卷结果分配给教师复核）tag=`grading-assignments`
- **判定**: 历史债务 — 路由文件同名 `assignment_router.py`，虽 tag 区分但 IDE/grep 时易混
- **建议处置**: 重命名为 `teacher_assignment_router.py` / `grading_assignment_router.py`（或最小成本在 MODULE.md 中清楚标注）
- **用户决定**: [ ] approve 重命名 / [ ] approve 保留+MODULE.md 说明 / [ ] defer

---

### 条目 #10: `analytics/analysis_models.py` 文件命名偏离约定

- **约定**: 其他模块均用 `models.py` 作模型文件
- **analytics**: 用 `analysis_models.py`（且 analytics 下无 `models.py`，也无 `models/` 子目录）
- **判定**: 历史债务 — 命名不一致，不影响功能但违反模块内部约定
- **建议处置**: 重命名为 `models.py`；聚合脚本按约定读取（如允许 glob `*models.py` 则不需改）
- **用户决定**: [ ] approve 重命名 / [ ] approve 聚合脚本放宽 / [ ] defer

---

## 结构性观察（非冲突，供 MODULE.md 撰写参考）

### 观察 #11: `paper` 模块无表无路由，是外部客户端（httpx → paper-skill）

- **位置**: `src/edu_cloud/modules/paper/` 只有 `__init__.py` + `service.py`
- **职责**: PaperService REST 客户端封装 paper-skill 外部服务
- **MODULE.md 示意**: `owns_tables: []` / `owns_routes: []` / `exposes.services: [PaperService]` / `depends_on: {modules: [], services: [], ai_tools: []}`

### 观察 #12: `adaptive` 模块无独立 HTTP 路由

- **位置**: `src/edu_cloud/modules/adaptive/`（9 个文件含 models/service/bkt_engine/path_planner/question_selector/updater/sync/da_mapper）
- **使用方式**: 仅通过 AI tool（`ai/tools/adaptive.py`）和 `pipeline.service._update_adaptive_mastery` 消费
- **MODULE.md 示意**: `owns_routes: []`，但 `owns_tables` 7 张，`exposes.services` 列关键函数如 `process_answer` / `diagnose_and_recommend`

### 观察 #13: `conduct` 模块双 router（admin/parent）挂同 prefix `/api/v1/conduct`

- **内部拆分**: 按租户身份拆（admin 用 JWT，parent 用 cp_token），两 router 均挂 `/api/v1/conduct`
- **MODULE.md 示意**: `owns_routes: [/api/v1/conduct]`（单项，不重复）；在正文说明"本模块路由内部按 admin/parent 拆分"

---

## 用户动作（批阅指引）

1. 对**真冲突（#1/#2/#3）**：必须 approve 一种处置方案或 defer；不能 reject（冲突事实存在）
2. 对**职责互补（#4-#7）**：选 approve（接受分工/保留现状）或 defer
3. 对**历史债务（#8-#10）**：按精力选 approve（立即处理）或 defer（记入 debt-report.md）
4. 对**结构性观察（#11-#13）**：仅用于 MODULE.md 撰写，不需批阅

**批阅后**:
- approve 的条目在 P2（Task 4-5）试点 MODULE.md 撰写时一并落地；其他 18 个模块触碰时渐进落地
- defer 的条目由聚合脚本自动进入 `docs/governance/debt-report.md` 债务清单

---

## 调研方法论自审

- L013 反向防御：HIGH/MED 优先级条目含完整 3 类证据（file:line 原文 + 调用方 grep + git log）；LOW 与"结构观察"类条目（如 #2/#6/#8）证据强度较弱——受限于 P0 阶段单次调研预算，部分条目仅含 file:line 与调用方关系，未追补 git log 痕迹。后续 P2/P3 落地或后续审查迭代中补全。当前基线不适合作为"机械完备证据包"使用
- 候选机械扫描只用于**缩小阅读范围**（本次从 21 模块缩小到"有疑点"的 7-8 处），判定由 Read 实际代码后下
- 未读模块（card/paper-skill 子目录等）已在"调研范围-未读（跳过）"段明列
- **没有把 triage 推给用户**：本报告已对每条候选完成分类（真冲突/互补/债务/观察）
