---
type: exploration-notes
created: 2026-04-11
project_dir: C:\Users\Administrator\edu-cloud
session: 全量管道测试（试卷制作→切割→阅卷）
tester: Claude (Playwright MCP)
---

# edu-cloud 全量管道测试笔记

## 目的
跑通 **试卷制作 → 扫描切割 → 人工阅卷** 完整管道，同时验证交接卡里记录的 3 个已识别问题。

## 测试环境
- 后端 :9000 健康
- 前端 :5273 健康
- 初始登录态：高睿皓 (subject_teacher)
- 测试用账号：admin_academic_director_2 / 123456（育才实验中学 李明华）
- 测试数据：D:\试卷数据\试卷图像\191871\A3722（9 科目 A+B 面完整）

## 子项进度

### S1 定位可测考试 ✅

- 账号: admin_academic_director_2 / 123456 (李明华，academic_director)
- 育才实验中学导航可见：教务概览/考试管理/阅卷调度/数据分析/分析报告/成绩趋势/文档中心/排课管理/选考组合/学校配置/知识图谱
- 使用考试：**2026第一次月考**（草稿态）
  - exam_id: `80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c`
  - 9 科齐全（地理/化学/历史/生物/数学/物理/语文/英语/政治）
  - 数学 subject_id: `1974216e-8aef-4a0b-b9c2-0432488d6b80`
- UX 观察：考试管理表格"创建时间"列全部显示 `-`，科目管理操作列缺失（科目只能添加不能删）

### S2 答题卡生成/布局 ✅

- 答题卡制作 tab：
  - 选择科目=数学 → 自动加载默认模板（11 选择题 + 6 解答题）
  - 纸张 A3（420mm），双面，满分 100
  - 默认题号序列：12/15/16/17/18/19（跳过 13/14，默认 `fillStart=12 fillCount=0`，属模板设计不是 bug）
- 点"直接编辑答题卡" → 进入 CardEditor 可视化
  - A 面：col0=header/info/notice/choices, col1=Q12, col2=Q15+Q16
  - B 面：col0=Q17, col1=Q18, col2=Q19
- **保存**：PUT `/api/v1/card/editor-layout/{subject_id}` 200 ✅
- **导出 Skeleton**：POST `/api/v1/card/export/skeleton` 下载 skeleton.json ✅

#### 🟡 F001 疑似 bug — Skeleton side 字段全为 A

导出的 skeleton.json 中 **所有 6 个 essay region 的 `side` 字段都是 "A"**，但 Q17/Q18/Q19 在编辑器界面明确显示在 B 面。

可能情景：
1. A3 双面扫一张大图时 side 只有一个值 → 设计意图，但字段命名具误导
2. 真 bug —— side 计算遗漏了 `_sideIdx=1` 的情况

影响面待评估：如果扫描管道按 skeleton.side 判定正反面，Q17-19 会全部被当成 A 面裁切 → 错位。需要看 `pipeline_service.py` 是否依赖 side 字段。

文件: `.playwright-mcp/skeleton.json` / CardEditor 导出逻辑位于 `frontend/src/card-editor/export/`

### S3 扫描目录发现 + tpl 导入 ✅

- POST `/api/v1/scan/pipeline/scan-dir` body=`{"dir_path":"D:\\试卷数据\\试卷图像\\191871\\A3722"}` → 200
- 返回 9 科目子文件夹（含图片数 / A 面 / B 面 / 学生数）：
  - 化学 464/232/232/232, 历史 216/108/108/108, 地理 254/127/127/127, 政治 328/164/164/164
  - 数学 734/367/367/367, 物理 510/255/255/255, 生物 402/201/201/201
  - 英语 730/365/365/365, 语文 726/363/363/363
- POST `/api/v1/scan/pipeline/import-tpl` body=`{"tpl_path":"D:\\...\\[141984002]数学A.tpl","subject_id":"...","side":"A"}` → 200
- 导入后预览/开始切割按钮启用 ✅

### S4 启动切割 pipeline（数学 A 面）✅

- POST `/api/v1/scan/pipeline/preview` 200 → 返回"4 个定位点"+ 标注图
  - 截图：`.playwright-mcp/pipeline-preview-math-a.png`
  - **观察**：tpl 预览图正确显示 anchor 检测 + 蓝色矩形切割区域。说明 anchor/affine 在 preview 路径中工作（**问题 3/F003 anchor/affine 在 preview 路径已生效**，pipeline/start 主路径待验证）
- POST `/api/v1/scan/pipeline/start` body=`{subject_id, side:"A", image_dir:"...数学", tpl_path:"...数学A.tpl"}` → 200
- 进度轮询（GET `/api/v1/scan/pipeline/progress`）：
  - T+0s: running 122/367
  - T+5s: running 318/367
  - T+10s: **completed 367/367 failed=0** ✅
- 实际处理速率: ~73 张/秒（含 anchor 检测 + 6 个 region 切割 + 落盘）

### S5 验证切图产物 ⚠️

- 切图存储路径：`storage/{school_id}/{exam_id}/{subject_id}/{student_number}/Q{N}.png`
  - 完整路径示例: `C:\Users\Administrator\edu-cloud\storage\31c17116-8182-429b-b38d-47c89eec39ef\80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c\1974216e-8aef-4a0b-b9c2-0432488d6b80\3722230101\Q01.png`
- **数量统计**：
  - 367 学生目录，2202 个 PNG 切图（= 367 × 6 题）✅
  - 学生 ID 命名分布：
    - **359 个**学生用真实学生号 (3722xxx)
    - **8 个**学生用 image_id fallback (I01xxx)
    - **失败率 2.2%**（条形码识别失败仍能完成切图，fallback 用 image_id）
- 单个学生切图：Q01-Q06.png（6 个解答题，分别 30KB-340KB）
- **DB 联动验证（致命问题）**：
  - GET `/api/v1/grading/progress/{exam_id}` → `{total_papers:0, graded_papers:0}`
  - GET `/api/v1/marking/subjects?exam_id=...` → 9 科目都返回，但**数学 questions 列表为空**（math_question_count=0, math_total_answers=0）

### S6 人工阅卷主观题打分 ⚠️

- 切换到考试 "2026第一次月考" 后看到 9 个科目段，5 个有 question (地理 19 题 / 化学 18 题 / 历史 19 题 / 生物 21 题 / 政治 20 题，全部从种子数据预创建)
- **4 个科目 question 完全为空**：数学/物理/语文/英语 (qcount=0, answers=0)
- **数学是我们刚跑完 pipeline 的科目** —— 切图 2202 张落盘但 question 表完全没数据，**与 F003 一致**
- 5 科有 question 也只有地理第 1 题有 1 个 answer（应是种子数据）
- 点入"地理 第1题"批改页 → 路由 `/marking/grade/{question_id}` 200，正确显示「全部批改完成 / 该题所有答卷已批改」空状态
- **结论**：阅卷 UI 路由 + 后端读取 + 空状态渲染都正常 ✅；但因为 pipeline 未注入 answer 数据，无法做端到端打分验证
- 截图: `marking-page-academic-director.png` (科目列表) + `marking-grade-empty-state.png` (空状态页)

### S7 科任教师权限过滤复现 🔴

- **找到真实科任教师账号**：`t_yw_001` (高睿皓 / 语文教师 / subject_teacher) 密码 `123456` ✅
  - **修正交接卡**：交接卡说"t_* 账号不存在"——实际是只查了 t_dl_001 + t_sx_001 + 等，但 **t_yw_001 ~ t_yw_005 是存在的**（有 5 个语文老师种子数据）
- 用 t_yw_001 token 调 `GET /api/v1/marking/subjects?exam_id=...` → status=200, **返回全部 9 科目**
- 预期：subject_teacher 应该只看到自己教的"语文"
- **🔴 问题 1 完全确认**：marking_subjects 后端没按 visible_subject_codes 过滤，违反交接卡描述

### S8 AI 阅卷流程 ⚠️

- 访问 `/grading/tasks` 阅卷调度页 ✅
- 弹出"创建批改任务"对话框 → 选 2026第一次月考 + 数学 → 点创建
- **后端 500 错误**：`POST /api/v1/grading/tasks → 500 (11861ms) unhandled exception, error: TimeoutError: Timeout connecting to server`
- 根因：`GET /api/v1/llm-config/slots` 显示所有 slot 的 `effective: null`（LLM 槽位未配置），创建任务时尝试连 LLM 服务超时 11 秒后报 500
- **F006**：grading/tasks 应在前置条件不满足（LLM 槽位为空、answer 数据为空）时返回 4xx，不应让请求转到 LLM 调用层后超时报 500
- AI 阅卷流程被两个前置依赖阻断：
  1. LLM 槽位未配置（环境问题）
  2. F003 切图未联动到 answer 表（代码问题）

---

## 总结

| 子项 | 状态 | 说明 |
|------|------|------|
| S1 定位考试 | ✅ | 2026第一次月考 / 9 科齐全 |
| S2 答题卡生成 | ✅ + 🟡 | CardEditor 工作 / 发布按钮语义不对 |
| S3 扫描目录发现 + tpl | ✅ | scan-dir + import-tpl 完整 |
| S4 切割 pipeline | ✅ | 367 学生 100% 处理，0 失败 |
| S5 切图产物 | ⚠️ | 文件 2202 张落盘 / DB 0 记录 |
| S6 人工阅卷 | ⚠️ | UI 工作 / 无 answer 数据 |
| S7 权限过滤 | 🔴 | 问题 1 完全复现 |
| S8 AI 阅卷 | ⚠️ | 500 timeout / LLM + answer 双阻塞 |

**端到端管道结论**：试卷制作 ✅ → 切割 ✅（文件层）→ **管道断裂 🔴** → 阅卷 ❌（无数据）→ AI 阅卷 ❌（无依赖）

---

## 发现问题清单

### 🔴 F003 [HIGH] 答题卡发布流程不创建 Question/Answer 记录（管道断裂）

**症状**：
- 跑完 367 学生 × 6 题 = 2202 张切图全部落盘到 storage 目录 ✅
- 点"发布答题卡"完成 publishCard ✅（PDF 下载 + Template A 面写入）
- 但 `marking/subjects?exam_id=...` 数学 question_count=0, total_answers=0
- `grading/progress` total_papers=0
- 切图无法被任何阅卷模块消费

**根因**（已读源码）：
`frontend/src/card-editor/export.js:177-215 publishCard()` 只做了三件事：
1. POST `/api/v1/card/export/pdf` 生成 PDF blob
2. POST `/api/v1/card/export/skeleton` 提取 skeleton
3. **PUT `/api/v1/templates/{subjectId}/A`** —— 写入 Template 表（**仅 A 面**）

**完全没有调用**：
- POST `/api/v1/questions` 或类似端点写入题目
- POST `/api/v1/answers` 或类似端点关联学生切图
- 没有任何 Question/Answer ORM 写入路径

**衍生 bug F003a**：publishCard 只写 A 面 Template，B 面 Template 永远不会被写入。即使后续修复 Question 写入，B 面切割也会失败。

**影响**：scan-integration (T3) 完成的链路 paper-seg→edu-cloud 在切图存档后**完全断开**，整个阅卷管道无法继续。这是端到端不可用的阻塞 bug。

**关联交接卡问题**：
- 交接卡问题 2「选择题自动打分缺失」是 F003 的子症状（recognize_page 没调用是因为更上游的 Question 数据本来就没写入）
- 交接卡问题 1「权限过滤」是更下游的 UX 问题，被 F003 完全遮蔽

**修复方向（不在本次范围）**：T3-T4 起步，需 design→plan→handoff，可能要重新设计 Template + Question + Answer 之间的写入责任划分

#### R1 补充：源码层根因（2026-04-11 深挖）

1. **pipeline_router.py:147 显式注释**：
   ```python
   # 后台启动（只切图存储，不写 StudentAnswer — 入库由后续阅卷流程负责）
   asyncio.create_task(pipeline_service.run_pipeline(...))
   ```
   作者意图明确：pipeline 只存图，入库交给"后续阅卷流程"。但"后续阅卷流程"到底是谁没有在代码里定义。

2. **谁写 StudentAnswer**（grep `StudentAnswer(` / `db.add.*StudentAnswer`）：
   | 位置 | 路径 | 状态 |
   |------|------|------|
   | `data/seed_demo.py:306` | 启动时种子 | 工作中（explains 5 科有数据） |
   | `data/import_real_exam.py:252` | 一次性迁移脚本 | 非运行时路径 |
   | `api/compat_router.py:230/291/318` | paper-seg `/api/scan/upload{,-objective}` 兼容端点 | 旧路径 |
   | `modules/scan/router.py:68/149/336/383` | exam-ai 迁入的 scan router（不是 pipeline_router） | 旧路径 |
   | `modules/marking/importer.py:128` | `import_from_folder()` 目录扫描导入 | **目录结构不兼容 pipeline 输出** |

3. **目录结构不兼容**（F003 的具体技术形态）：
   - **pipeline 输出**: `storage/{school_id}/{exam_id}/{subject_id}/{student_number}/Q{NN}.png`
   - **importer 期望**: `{folder_path}/{科目名}/{题号}/{学生ID}.png`
   - 层级次序不同（pipeline 是 student/Q_NN，importer 是 Q_NN/student），目录命名不同（pipeline 用 UUID subject_id，importer 用中文科目名）

4. **谁在调用 importer**：`marking/router.py:183 POST /marking/import` → `import_from_folder(folder_path=...)`。用户在"人工阅卷"页上方的"导入试卷数据"按钮可能对接这里，但因为目录结构不匹配，即使用户手动指向 pipeline 的输出目录也无法成功导入。

5. **真正的断点**：scan-integration T3 迁入的是 paper-seg 的切图逻辑，但 paper-seg 原本是"客户端产生切图后 POST upload/upload-objective"的模式 —— compat_router.py 保留了这个入口并且**确实写 StudentAnswer**。但 edu-cloud 的新 pipeline_router.py 是"后端跑流水线"模式，跑完不触发 compat 路径，也不调 importer。

#### 修复方向选项（初步）

| 方案 | 描述 | 工作量 |
|------|------|--------|
| A | pipeline_service.run_pipeline 完成后自动创建 Question/StudentAnswer | MED (改 pipeline_service.py + 设计 Question 生成规则) |
| B | pipeline 输出改成 importer 兼容目录结构，再由 importer 导入 | LOW-MED (改 output_dir 层级) |
| C | 新增 `POST /api/v1/scan/pipeline/commit` 端点，pipeline 完成后前端显式调用提交入库 | MED (新端点 + UI 交互) |

任一方案都要先设计"Question 从哪来" —— 答题卡的题目清单需要从 CardEditor 的布局或 tpl 的 regions 解析出来。当前两套坐标系并存（F002）加剧了这个决策难度。

### 🟡 F009 [MED] marking/subjects 缺少权限过滤（F006 精确位置）

**位置**：`src/edu_cloud/modules/marking/scorer.py:12-18 get_subjects_with_progress()`

**源码**：
```python
subjects = (await db.execute(
    select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
)).scalars().all()
```

只按 `school_id` 过滤，没用 `get_visible_subject_codes(current_role)`。

**对比**：`src/edu_cloud/modules/marking/router.py:221 next_answer()` 在访问时**有**调 `get_visible_subject_codes` 做 403 拦截。

**结论**：同模块内"列表接口缺过滤但访问接口有过滤"是典型的 **后端过滤疏漏模式**（前端已显示的列表项在点击后才被 403 拒绝）—— 交接卡问题 1 描述的 UX 恶化根因就是这里。

**修复范围**：一行改动 — 在 `list_subjects` 或 `get_subjects_with_progress` 里注入 `visible_codes` 过滤，按 T2 起步。

---

## Round 2 测试（R1-R8）

### R1 深挖 F003 根因 ✅
见上方 F003/F009 段（源码层证据 + 修复方案 A/B/C）

### R2 知识图谱教师工作台 ⚠️

- `/knowledge-tree` 加载全模块概览：5 模块（分子与细胞 33/2、遗传与进化 26/2、稳态与调节 19/1、生态与环境 15/1、生物技术 15/4），模块间硬前置关系 7 条
- 点击"分子与细胞"进入 G6 图谱视图：4 canvas 渲染成功，节点+边密集网络 ✅
- 切换到"审查工作台" Tab：3 过滤器（模块/审核状态/优先级）+ 进度条 0% + 概念列表（33 项，含 HIGH/MED 警示）✅
- 截图：`knowledge-tree-molecular-cell.png`, `knowledge-tree-review-workbench.png`
- **局限**：Phase 2.5 焦点模式（节点 faded/edge dimmed + 跨模块徽标 hover）需要真实鼠标事件触发 G6 canvas，JS 模拟事件不生效，未独立验证

### R3 Analytics 3 页面 ✅

- `/analysis` → **AI 分析工作台**（考试/班级/日历/通知/文档 + 生成班级学情报告/学科分析报告按钮）
- `/analytics/report` → 多选考试 + 指标勾选 + 生成分析/导出 PDF
  - API 验证：POST `/api/v1/analytics/report/query` 200，返回 `metrics:{}` 空（因考试无 published 成绩数据）
- `/analytics/trend` → 选考试（≥2次）+ 维度（年级/班级/学生）+ 查看趋势
- 所有 3 页路由正常，UI 基础元素加载

### R4 AI 助手 SSE 对话 🎉

- GET `/api/v1/ai/health` → `{"status":"available","tools":53}`
- POST `/api/v1/ai/chat` body=`{"message":"你好，介绍一下本校的考试情况"}` → **SSE 200 正常**
  - Agent 主动调用 `get_exam_list` → 返回 5 考试
  - **发现**：2026第一次月考 status=**"scanning"**（证实 publishCard Step 4 成功更新 exam.status，尽管 Question 表仍空）
  - Agent 又调 `get_exam_overview(exam_id=...)` × 多次 → 返 `status:not_found "暂无分析快照"`
- **F007 修订**：AI Chat 能正常访问 LLM，说明 llm-config/slots 的 `effective:null` 不代表 LLM 不可达。grading/tasks 11s 超时的根因不是 LLM 未配置，需要进一步查 grading/router 的 LLM 调用路径

### R5 自适应学习 ⚠️

- OpenAPI 查询确认 **adaptive 模块没有 REST 端点**，只作为内部库 + AI Agent 工具暴露
- 通过 AI Chat 调 `diagnose_and_recommend(student_id=...)`:
  - 返回: `{"diagnosis":"暂无作答数据","learning_path":"所有知识点已掌握","recommended_questions":[]}`
  - 因 F003 + answer_logs 表为空
- 同次 Agent 自动调用 `get_student_learning_profile`:
  - 返回完整历史成绩（英 0.62/语 0.85/数 0.59 分率 + 班级排名）和 4 个弱知识点（mastery 0.3-0.58）
  - 数据来源是 exam_results 聚合，不是 BKT answer_logs
- **结论**：两套学情数据路径并存 —— (1) exam_results 聚合有数据 (2) BKT answer_logs 因 pipeline 断裂空

### R6 Studio 文档中心 🔴

- `/studio` 页面内容与 `/analysis` 完全相同 → 查源码 `router/index.js:57` 确认为 **Placeholder route**
- 源码注释：`// Placeholder routes (sidebar navigation targets)`
- 4 个占位路由（同一批 placeholder）：
  - `/studio` → AnalysisPage.vue
  - `/paper` → AnalysisPage.vue
  - `/calendar` → DashboardPage.vue
  - `/notifications` → DashboardPage.vue
- 后端 API 实现：GET `/api/v1/studio/templates` 200 返回 5 个模板（class_report / subject_analysis / parent_notification / holiday_safety / exam_notification），`/studio/documents` 200 返回 `[]`
- **结论**：Studio + 论文 + 校历 + 通知 **4 个侧栏导航项前端仅占位**，后端 API 完整但无独立 UI

### R7 教务管理 ✅

- `/assignments` 排课管理：UI 完整（新增排课/学期过滤/查询），列表空（No Data）
- `/selections` 选考组合：UI 完整（新增组合），列表空（暂无选考组合）
- `/school-settings` 学校配置：3 tab（功能模块 / 分数段 / 学校设置），功能模块 8 个（考试/阅卷/作业/学情分析/教研题库/教学管理/校历/文档中心）
- 3 页都有独立实现，数据层为空但 UI 工作

### R8 通知中心 ⚠️

- GET `/api/v1/notifications` 200 返回 `[]`
- 前端 `/notifications` 路由是 placeholder（见 R6 F012），顶栏 NotificationBell 是简单 badge，点击是占位 popover
- 后端实现完整，前端 UI 未落地

---

## Round 2 新增 Finding

### 🔴 F010 [MED] 考试列表状态显示 "(null)"

**症状**：在 `/analysis` 页面考试列表显示 "2026第一次月考 (null)"、"2026年春季期末考试 (null)" 等 —— 括号内应该显示状态（如"草稿"/"扫描中"/"已完成"），但显示为字面的 `null`

**对比**：考试管理页的状态列显示正常（"草稿"、"已完成"）

**位置**：`frontend/src/pages/AnalysisPage.vue` 的考试下拉渲染逻辑，可能绑的字段名和后端响应字段不一致

**优先级**：MED（前端数据绑定 bug，影响专业感）

### 🔴 F011 + F012 [HIGH-UX] 4 个侧栏导航项是占位路由

**症状**：用户点"文档中心"/"论文写作"/"校历"/"通知中心"→ 跳转到 AnalysisPage 或 DashboardPage，不是对应的独立 UI

**源码证据**：`frontend/src/router/index.js:56` 注释 `// Placeholder routes (sidebar navigation targets)`，行 57-60 定义：
```javascript
{ path: 'studio', name: 'Studio', component: () => import('../pages/AnalysisPage.vue'), ... },
{ path: 'calendar', ... DashboardPage ... },
{ path: 'notifications', ... DashboardPage ... },
{ path: 'paper', ... AnalysisPage ... },
```

**后端实现状态**：
- Studio: 5 模板 CRUD + 论文对接 paper-skill (9103) 均已实现，API 200
- Calendar: events CRUD 已实现
- Notifications: list API 已实现
- Paper: 经 Studio paper-skill 透传已实现

**影响**：4 个核心功能在侧栏看得见，点进去是错误页面。UX 严重违背"单一职责"。已完成的后端 API 对用户不可达。

**修复方向**：前端补齐 4 个页面组件。按每个页面 T3 起步（需要设计 UI）。总工作量大。

### 🟡 F013 [MED] AI Chat 能访问 LLM 但 grading/tasks 11s 超时

**背景**：R4 R5 确认 AI Chat 能完整调用工具并返回结果（证明 LLM 路径通），但 S8 阶段 POST `/grading/tasks` 返回 500 + 后端日志 `TimeoutError: Timeout connecting to server` 11 秒超时

**可能原因**：
1. grading 模块有独立的 LLM 配置（不走 llm-proxy 或 AI Agent 的 LLM Adapter）
2. grading worker 用 arq 异步调度，Redis 或 worker 进程未启动
3. grading 路径到的是另一个服务（如 paper-skill 或早期设定的 AI 服务端点）

**待确认**：读 `modules/grading/llm_client.py` 和 `modules/grading/router.py`（未在本次做）

**优先级**：MED（阻塞 AI 阅卷入口，但 F003 阻塞更根本，修 F003 后再挖 F013）

---

## 测试覆盖总结

**已测模块**（8 个主流程 + 8 个扩展）：
- 认证 + 角色切换（2 个账号，subject_teacher / academic_director）
- 考试管理（列表、详情、科目、答题卡编辑、扫描、发布）
- 扫描流水线（scan-dir / import-tpl / preview / start / progress）
- 切图文件落盘 + DB 联动（Question/StudentAnswer 表）
- 人工阅卷（subjects / grade / next）
- AI 阅卷（grading/tasks 创建）
- 知识图谱（模块概览 + G6 图谱 + 审查工作台）
- Analytics 3 页（分析/报告/趋势）
- AI Chat SSE + 工具调用
- 自适应学习（via Agent tool）
- Studio 后端 API
- 排课/选考/学校配置
- 通知 API
- Router 源码审计（发现占位路由）

**未测模块**（后续可扩展）:
- Homework 作业管理（Phase 2.2）
- Profile 学情画像（Phase 3.1）
- Bank 题库（Phase 3.1）
- Joint Exam 联考管理
- 学校管理（platform_admin）
- 教研工作流
- 家长入口

### 🟡 F002 [MED] CardEditor skeleton 与 pipeline tpl 不同源

**症状**：
- CardEditor 生成的 skeleton.json 用 1587×2245 标准化坐标 + region.id 形如 essay-Q12
- pipeline 实际跑切割时用 .tpl 文件中定义的 rect（真实试卷布局，与 skeleton 完全独立）
- 同一个 subject_id 在 storage 里得到的 6 张 Q01-Q06 是 tpl 的 region 顺序，跟 CardEditor 里的 Q12/Q15/Q16/Q17/Q18/Q19 题号毫无对应

**影响**：
- 用户在 CardEditor 里精心配置的题号、分值、布局 → 不影响实际切图
- 阅卷时即使能查到切图，题号映射也错位
- "发布答题卡"按钮含义模糊：到底用 CardEditor 还是 tpl

**待确认**：是否两套并存的设计意图（CardEditor 用于"自制答题卡 + 学校自打印"流程，tpl 用于"乐学尔扫描器 + 现成模板"流程）

### 🟡 F001 [MED-LOW] Skeleton 导出 side 字段全为 "A"

**症状**：CardEditor 在 A+B 双面布局下导出 skeleton.json，**所有 6 个 essay region 的 `side` 字段都是 "A"**，但 Q17/Q18/Q19 在编辑器里明确显示在 B 面（背面）。

**位置**：导出文件 `.playwright-mcp/skeleton.json` line 13/22/37/49/61/73 全是 `"side":"A"`

**可能影响**：如果 skeleton 真的被消费，B 面区域会被当成 A 面坐标处理 → 切图位置错乱。但由于 F002（pipeline 实际不用 skeleton，只用 tpl），当前实测下 F001 不会显式爆炸——属于隐藏 bug。

**修复方向**：CardEditor export.js 在生成 region 时遗漏了 `_sideIdx=1` 的判断，应填入 'B'

### 🟢 F004 [LOW] 条形码识别失败率 2.2%（8/367 学生用 image_id fallback）

**症状**：8 个学生目录命名为 `I01...`（来源图片文件 ID），359 个用真实学号 `3722xxx`。
**可能原因**：扫描图条形码角度/破损/光照问题
**建议**：UI 应显示"识别失败学生"清单供人工补录学号；当前 fallback 是静默的

### 🟢 F005 [LOW] grading/progress 与 marking/subjects 接口语义割裂

GET `/api/v1/scan/tasks?exam_id=...` 返回 405 Method Not Allowed —— 端点存在但不接受 GET，前端无法用 GET 查扫描任务列表。

### 🔴 F006 [HIGH] 重新确认：人工阅卷选题页不按教师权限过滤（交接卡问题 1）

**复现**：登录 t_yw_001 (高睿皓 / 语文教师 / subject_teacher) → GET `/api/v1/marking/subjects?exam_id=80f4fc02-...` → status=200 → **返回 9 个科目**（地理/化学/历史/生物/数学/物理/语文/英语/政治）

**预期**：只应返回"语文"（高睿皓教的科目）

**位置**：`src/edu_cloud/modules/marking/router.py` § `list_subjects_with_progress` 应注入 `get_visible_subject_codes(current_role)` 过滤

**优先级**：HIGH —— 用户能看到无权限操作的科目，点击后才 403，体验恶劣（交接卡引用智学网比较）

### 🟡 F007 [MED] AI 阅卷创建任务在前置不满足时返回 500 而非 4xx

**症状**：POST `/api/v1/grading/tasks` 在 LLM 槽位未配置时不验证前置条件，直接转 LLM 调用，11 秒超时后报 500 `TimeoutError: Timeout connecting to server`

**预期**：
- 检测 LLM 槽位为空 → 400 "AI 槽位未配置，请联系管理员配置 LLM 槽位"
- 检测 answer 数据为空 → 400 "该科目无可批改答卷"
- 不应让请求等待 LLM 超时

**修复方向**：grading 任务创建端点入口加前置校验

### 🔴 F008 [HIGH] 交接卡问题 2/3（选择题填涂识别 + anchor/affine）当前管道下不可独立验证

**说明**：因 F003 主流水线已断在 ORM 写入这一步，问题 2（选择题识别）和问题 3（anchor/affine 集成）的实际行为被遮蔽。anchor 检测在 preview 路径有效（4 定位点），但 pipeline/start 主路径是否使用待源码确认。

**修复优先级**：F003 解决后才能独立验证 F008

### 🟢 UX 观察（不影响功能）

- 考试管理表格"创建时间"列全部 `-`（数据未填或前端不渲染）
- 科目管理表格无操作列（只能添加，不能编辑/删除）
- CardEditor 默认模板题号 12/15/16/17/18/19（跳 13/14）是模板设计选择，非 bug

---

## Round 3 根因深挖（2026-04-11 20:08 启动 / T1 只读模式）

> 目的：6 批修复策略确定后，用户要求"深度定位根因再动手"。本轮只读源码 + 追加 notes，不动代码。

### D1 F013 + F007 grading 模块根因（2026-04-11 20:08:48）

#### 调用链完整还原

```
POST /api/v1/grading/tasks { subject_id }
  │
  ▼
router.py:146 create_grading_task
  ├─ L152-160  校验 Subject 归属 current_role.school_id   ← 唯一前置校验
  ├─ L162-173  db.add(GradingTask) + commit              ← ★ 已落库，不可回滚
  └─ L177      await enqueue_grading_task(task.id)       ← ★ 11s 阻塞点
                │
                ▼
router.py:128 enqueue_grading_task
  ├─ L130  from arq import create_pool
  ├─ L131  from arq.connections import RedisSettings
  ├─ L133  redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
  │            │
  │            ▼
  │        config.py:14  REDIS_URL = "redis://localhost:6379/0"
  │            │
  │            ▼
  │        [Redis 未启动] → arq create_pool 默认 retry → 累计 ~11 秒 → TimeoutError
  ├─ L135  await redis.enqueue_job("process_grading_task", task_id)  ← 从未到达
  └─ L138  except Exception: logger.error(...); raise
                │
                ▼
FastAPI 冒泡 → 500 "TimeoutError: Timeout connecting to server"
```

#### F013 真相（颠覆原 R4 推断）

R4 原判："AI Chat 能用但 grading/tasks 11s 超时 → grading 模块独立 LLM 配置有问题"——**错**。

事实：
1. **`create_grading_task` API 路径完全不调 LLM**。API 进程只做 (a) 校验 subject (b) 落库 task (c) 把 task_id 扔 Redis 队列
2. **LLM 调用发生在 arq worker 进程**（`workers/grading.py:39 process_grading_task`）。worker 跟 API 是独立进程，通过 Redis 队列解耦
3. **11s 超时是 Redis 连接超时**：`arq.create_pool()` 默认 retry 行为 ≈ 11s。错误日志 "Timeout connecting to server" 里的 "server" 是 Redis `localhost:6379`，不是 LLM
4. **`llm-config/slots` 的 `effective:null` 跟本故障无关**：grading worker 根本不读 llm_slots 表，它读 `settings.LLM_API_URL/KEY/MODEL`（.env 直读）

#### 关键架构观察：grading LLM 路径与 AI Chat LLM 路径完全独立

| 项 | AI Chat（R4 已验证能用）| grading worker（F013 故障）|
|----|------------------------|---------------------------|
| LLM 入口 | `ai/llm_adapter.py LLMProxyAdapter` | `modules/grading/llm_client.py LLMClient` |
| 配置来源 | `llm_slots` 表 + llm-proxy（slot=ai-chat） | `settings.LLM_API_URL/KEY/MODEL`（.env） |
| 调用进程 | API 主进程（uvicorn）| arq worker 进程（独立）|
| 超时 | llm-proxy 转发 + 熔断 | `httpx.AsyncClient(timeout=60)` + max_retries=3 |
| 配置真源 | schools/{id}/llm-slots | `.env`（全局） |

这是**配置二元性**——两套 LLM 配置体系，一个用新的 slot 路由，一个还停留在旧 env 变量模式。修 F013 必须先决定：统一到 llm-proxy？还是 grading worker 保留旧路径？

#### F007 前置校验缺失清单

`router.py:146 create_grading_task` 共 4 个前置条件缺失：

| # | 缺失校验 | 失败后果 | 推荐返回 |
|---|---------|---------|---------|
| 1 | Redis 可达 | 11s TimeoutError → 500 | 503 "Queue unavailable" |
| 2 | Rubric 存在 | worker L120 `no rubric` → 全部 failed | 400 "Rubric not configured" |
| 3 | StudentAnswer 有数据 | worker L86 返回空 → task completed 但 total=0 | 400 "No answers to grade" |
| 4 | LLM 配置有效 | worker L98 ConnectError → L105 RuntimeError → 全部 failed | 400 "LLM not configured" |

更严重的问题：**task 在 enqueue 之前就已 commit**（L162-177），导致 Redis 挂时产生 orphan GradingTask 记录（DB 有行但永远不会被 worker 消费）。

#### F013 + F007 修复方向（3 候选）

| 方案 | 描述 | 成本 | 风险 |
|------|------|------|------|
| **A** | 启动 Redis（WSL 内 `apt install redis` + 启动服务），enqueue 加 try/except + timeout 参数 | LOW（运维）+ LOW（代码）| 未解决配置二元性 |
| **B** | 改 enqueue 流程：先 enqueue 成功才 commit GradingTask（反转顺序），防止 orphan task | MED（需要两阶段提交或 saga 模式）| 改动 DB 语义 |
| **C** | 统一到 llm-proxy：grading worker 改读 llm_slots 表，走 llm-proxy slot=grading；API 层加 LLM 健康检查 | HIGH（改 worker/grading.py + 新增 slot 配置 + 迁移 .env）| 触发大改 |

**推荐**：A + B 组合 = **快修**（A 解决故障）+ **结构修**（B 杜绝 orphan）。C 放到后续架构统一批次，不在本批次处理。

#### 未测问题（需要 B1 F003 解决后才能验证）

- worker 能跑通但 `questions` 为空（因 F003 Question 表空）→ worker L72 直接 `task.status=completed, total=0` 返回，看起来成功但实际啥都没做。这是 F003 的二阶效应，会被误判为"AI 阅卷正常"
- worker 能跑但 rubric 没配置 → L120 全部 failed。这是 F007 修复后暴露的下一层阻塞

### D2 F001 + F002 CardEditor 坐标系根因（2026-04-11 20:12:34）

#### F001 根因（一行改动）

`frontend/src/card-editor/render.js` L641, L643, L689, L701 生成 .page DOM 时：
```js
<div class="page" data-paper="A3" id="pageA">...
<div class="page" data-paper="A3" id="pageB">...
```
**只有 `data-paper` 和 `id`，没有 `data-side` 属性**。

`src/edu_cloud/modules/card/html_export.py:101` 提取 skeleton 时：
```js
side: el.closest('[data-side]')?.dataset.side || 'A',
```
`closest('[data-side]')` 查找祖先 side 属性，DOM 里不存在任何 `data-side` 节点（仅 `divider-handle` 上有，但不是 region 的祖先），所以所有 region 都 fallback 到 'A'。

**修复方向**：render.js 4 处 `.page` 加 `data-side="A"` / `data-side="B"` 属性。T1 级别一行改动。

**盲区验证**：extract_skeleton 的 JS eval 在 Playwright 无头浏览器里跑，DOM 结构和实时 CardEditor 一致。不存在"开发模式看到 side 但导出时丢失"的情况。

#### F002 双坐标系根因（设计意图，不是 bug）

- **CardEditor skeleton 坐标系**: html_export.py:95-100 用 Playwright `el.getBoundingClientRect()` 取**页面渲染坐标**。A3 viewport 固定 `1587×1123 px`（html_export.py:47），region 的 x1/y1/x2/y2 在这个坐标系下
- **pipeline tpl 坐标系**: tpl 文件是真实扫描图像的像素坐标（4960×3508 或类似），由 .tpl 文件里的 rect 定义，与 CardEditor 完全独立
- **两套坐标系并存的设计意图**（推测，需向用户确认）：
  - CardEditor + skeleton 是 **自制答题卡流** —— 老师在前端画布拖拽排版，后端 Playwright 渲染 PDF 给学校打印，扫描回来 skeleton 可以做 region 对齐
  - tpl + pipeline 是 **乐学尔扫描器兼容流** —— 使用预定义的行业模板（[141984002]数学A.tpl），没有 CardEditor 介入，直接扫描切割

**关键问题**：两套流里 skeleton 用 1587×1123 像素，tpl 用真实扫描像素（数量级完全不同）。如果 skeleton 最终要对齐到扫描图像，中间必须有 anchor 仿射变换把 skeleton 坐标映射到扫描坐标。publish_card (router.py:1232-1243) 的 `skeleton_to_paperseg_json` 可能包含这个映射，但我未读完。

**影响**：F002 不直接崩溃，但用户体验上 CardEditor 设置的题号/分值（Q12 5分 Q15 10分…）**不会映射到 tpl 流产出的切图**。这是 F003 的另一个维度表现。

#### F003 真相重大修订

原 R1 深挖结论"方案 A/B/C"全部失效。证据：

1. **CardEditor 布局是文件存储，不走 DB**：
   - `router.py:39` `_EDITOR_LAYOUT_DIR = editor_layouts/`
   - `router.py:157 PUT /card/editor-layout/{subject_id}` 只调 `_editor_layout_path(...).write_text(...)`
   - `router.py:47 GET /card/editor-layout/{subject_id}` 只从文件 JSON 读
   - 没有任何 Question/Answer 表操作

2. **前端 `createQuestion` 是死代码**：
   - `frontend/src/api/questions.js:5` 定义 `createQuestion`
   - grep 全前端代码库只有这 1 个结果（定义本身）—— **从未被调用**

3. **后端 `POST /api/v1/card/publish` 是僵尸端点**：
   - `router.py:1189` 定义了一站式 publish（含 question_map 构建）
   - grep 前端代码库 `card/publish` 或 `/publish` 零匹配
   - `ExamDetailPage.vue:868` 只调 `exportModule.publishCard(subjectId, filename)`（前端 export.js 的函数）
   - 前端 publishCard 手工走 3 步：`/export/pdf` + `/export/skeleton` + `PUT /templates/{subjectId}/A`，**不碰 /card/publish**

4. **publish 端点即使被调用也不创建 Question**：
   - router.py:1223-1229 从**已有的** Question 表读取构建 `question_map={q.name: q.id}`
   - 如果 Question 表是空的（我们的情况），question_map 永远为空
   - Template 写入时 regions 里的 question_id 全是 None（取决于 `skeleton_to_paperseg_json` 的处理方式）

**F003 真相**：**Question 的创建入口从未被接通**。CardEditor 里老师填题号/分值 → 写 editor_layouts 文件 → 没人把这些数据同步到 Question 表 → publish 读不到 Question → Template 没有 question_id → pipeline 切图也没有 question 关联 → 整条阅卷链路从源头就没有 Question 主键。

#### 新修复方案 D（替代方案 A/B/C）

**核心思路**：让 CardEditor 保存/发布动作在后端同步 upsert Question 表。

| 步骤 | 修改点 | 内容 |
|------|--------|------|
| 1 | CardEditor 布局 JSON schema | 规范化 regions 的 `qno/name/type/max_score` 字段语义，从布局 JSON 可明确抽取一个题目列表 |
| 2 | `PUT /card/editor-layout/{subject_id}` | 保存 layout 时同步 upsert Question 表（by subject_id+name）。删除题目时 soft-delete Question |
| 3 | `POST /card/publish` 或 `publishCard` | **接通一条路径**（推荐走后端 /publish，废弃前端手写三步）。保证 skeleton region.qno 能对应 Question.name |
| 4 | Template 写入 | skeleton_to_paperseg_json 的 question_map 非空，regions[].question_id 能赋值 |
| 5 | Template 双面 | publish 端点要支持 A+B 双 side，当前 L1247 硬编码 `side="A"` 是 F003a |
| 6 | pipeline_service.run_pipeline | 切图落盘时 insert StudentAnswer，关联 question_id（从 Template region 反查） |

**Tier 评估**：**T4**。理由：
- 跨前后端数据契约变更（布局 JSON schema → Question 表）
- 跨模块改动（card + exam + scan + pipeline）
- 接口语义变更（/card/publish 从僵尸变主路径）
- 数据模型约束（soft delete vs hard delete 的语义设计）
- 回归风险高（可能影响既有 editor_layouts/ 文件和 5 科种子 Question 数据）

**次要清理**：
- F003a: publish 端点 L1247 硬编码 A 面 → 改为 A/B 双面循环
- 僵尸代码清理：api/questions.js createQuestion 死代码可删（或接通），publishCard 前端三步改调 /card/publish

#### F001 与 F003 独立性

F001 是 DOM 属性遗漏（一行改动 T1），**不依赖 F003**，可以独立修复。修复后 skeleton.json 的 side 字段才有参考价值，但当前 F002 说明 skeleton 并不影响 pipeline 实际切图——所以 F001 修复的**唯一价值**是：当未来 F003 接通 publish 路径后，skeleton region 的 side 字段才能被正确消费。

**结论**：F001 可以立刻独立修，但修之前要先判断 F003 是否会改变 skeleton 消费方式。建议与 F003 合批处理。

### D3 F004 barcode fallback 静默路径（2026-04-11 20:14）

`src/edu_cloud/modules/scan/pipeline_service.py:85-93 process_one_image`:

```python
# 条码识别
student_id = None
if barcode_region:
    try:
        student_id = read_barcode(image_path, barcode_region)
    except Exception:
        pass                                      # ← 吞异常，零日志
if not student_id:
    student_id = _extract_student_id(image_path.name)   # ← 静默 fallback 到文件名
```

**静默点清单**：
1. `except Exception: pass`：吞掉 `read_barcode()` 抛出的所有异常（pyzbar 解码失败/图像损坏/region 越界）
2. `if not student_id` 分支：`read_barcode()` 返回 None 时，没有 logger.warning
3. `progress.warnings` (L179) 只填充 crops[].errors（region 切割错误），不包含 barcode 识别错误
4. `results` dict（L162）只有 `total/processed/failed/students`，没有 `barcode_failed` 计数
5. 前端进度面板只显示"已处理 N/M"，没有"条码识别失败 K 个学生"

**唯一能看到 fallback 的痕迹**：学生目录命名（真实学号 `3722xxx` vs 文件名派生 `I01xxx`）。需要用户事后 ls 目录才能发现，UI 零反馈。

**实测数据**：2202 张切图里 8 个学生用 image_id fallback（2.2% 失败率）。老师在 UI 上看不到这个数字。

**修复方向**（T2 级别）:
1. `except Exception as e: logger.warning("barcode_read_failed: file=%s, error=%s", image_path.name, e, exc_info=True)`
2. fallback 生效时另外 log：`logger.warning("barcode_fallback: file=%s, using filename stem=%s", image_path.name, student_id)`
3. `PipelineProgress` 新增 `barcode_failed: int = 0` 字段
4. `results` dict 新增 `barcode_failed_students: list[str]`（学生目录名列表）
5. 前端 PipelineProgressPanel 新增"条码识别失败清单"展示 + CSV 导出供人工补录

**风险**：如果大批量 fallback 但 student_id 巧合匹配到已有学生（同校不同班同号），会静默覆盖。当前零检测。新增一条：fallback 生效后必须与 `students` 表做匹配校验，命中 fallback 且学号不在 students 表 → progress.errors，不是 warnings。

### D4 F011 + F012 exam-ai 可迁入页面探查（2026-04-11 20:16）

#### exam-ai 页面清单（全部 14 个）

```
DashboardPage / GradingResultsPage / TeacherReviewPage / AnalyticsPage / SchoolsPage /
LoginPage / GradingTasksPage / MarkingSelectPage / MarkingPage / MarkingProgressPage /
MarkingAssignPage / ExamListPage / ExamDetailPage / CardEditorDevPage
```

**无 Studio/Paper/Calendar/Notification 任何一个页面**。exam-ai 是单校阅卷端，天然没有 Studio 文档中心 / 校历 / 通知中心这类平台级功能的前端。4 个页面必须从零设计。

#### edu-cloud 后端实现度核对

| 模块 | 代码体量 | 完整度 | 坑 |
|------|---------|-------|----|
| `modules/studio` | 437 行（router 221 + service 122 + approval_service 94）| 完整 CRUD + 状态流转 + 审批流 | 无 |
| `modules/calendar` | 232 行（router 78 + service 102 + notification_service 52）| 完整 CRUD + 通知触发规则 | **dispatch 是 stub**：`notification_service.py:14-42` 只标记 status=sent，`channel="stub"`，`note="企业微信未接入，仅标记状态"`，**不真发消息** |
| `api/notifications_api.py` | 列表 API | list + status/since 过滤 | 依赖 calendar 的 stub dispatch |
| Paper | 无独立模块 | `studio/paper/create` + `/status` 2 端点透传 paper-skill :9103 | paper-skill 服务可用性决定此入口 |

#### F011/F012 修复工作量评估

| 页面 | 前端工作量 | 依赖 | Tier |
|------|-----------|------|------|
| `/paper` 论文写作 | **最轻** — 表单提交 + 进度轮询 + 结果下载 | paper-skill 可达 | T3 |
| `/notifications` 通知中心 | 轻 — 列表 + 已读/未读切换 | 后端 list API | T3 |
| `/calendar` 校历 | 中 — 月视图 + 事件 CRUD + 触发规则编辑 | 后端完整 | T3 |
| `/studio` 文档中心 | **最重** — 5 模板选择 + 内容编辑器 + 状态机流转 + 审批流 UI | 后端完整 | T3（但接近 T4）|

**总工作量**：4 × T3 ≈ 一个 T4 级别的项目（类似知识图谱可视化的规模）。

**建议拆单**：不要把 4 个页面当成一个批次。按优先级拆：
- **B4a**: Paper（最轻，解锁现有 paper-skill 投资）
- **B4b**: Notifications（用户影响面最大，阅卷/考试发布/作业批改都会触发通知）
- **B4c**: Calendar（依赖 Notifications 的 UI 复用）
- **B4d**: Studio（最重，可以独立成 T4 项目）

**额外发现**：calendar notification_service 的 stub dispatch 是**隐藏的 F014**。用户配置通知规则 → 触发事件 → notification 记录 status=sent → **实际收件人一封消息都没收到**。这是比 UI 占位更严重的"虚假 sent"。notifications 页面补齐之后，如果没解决 stub，用户会看到一堆"已发送"的通知但从没人收到。

**F014 升级**：把 "notification_service.dispatch stub 模式" 作为独立 finding 记录，severity = MED-HIGH（没 UI 也能触发，属业务背刺）。

### D5 F010 AnalysisPage "(null)" 字段绑定根因（2026-04-11 20:18）

#### 调用链还原

```
AnalysisPage.vue（壳，23 行）
  ↓
ContextPanel.vue:28-33 examOptions
  ↓
computed(() => contextStore.exams.map(e => ({
  label: `${e.name} (${e.subject_code})`,    // ← ★ 字段绑错
  key: e.id,
})))
  ↓
context.js store.loadContext()
  ↓
GET /api/v1/workspace/context
  ↓
workspace_service.py:44-50
  exams: [{id, name, subject_code, semester}, ...]
  ↓
数据库 exams.subject_code（nullable） → 多科考试创建时默认 NULL
  ↓
JSON 返回 e.subject_code = null
  ↓
JS 模板字符串 `${null}` → 字符串 "null"
  ↓
"2026第一次月考 (null)"
```

#### 两层 bug

**Bug 1: 字段绑错（主因）** — `ContextPanel.vue:30`

```js
label: `${e.name} (${e.subject_code})`,
```

用户期望（交接卡原记录）：显示"草稿/扫描中/已完成"等状态，用于快速识别考试阶段。
实际代码：绑到 `subject_code`（学科代码，legacy 字段）。

**Bug 2: Exam 表 subject_code 是 legacy 字段（次因）** — `modules/exam/models.py:33`

```python
# edu-cloud 原有字段（sync 用）
subject_code: Mapped[str | None] = mapped_column(String(50), default=None)
subject_name: Mapped[str | None] = mapped_column(String(100), default=None)
max_score: Mapped[float | None] = mapped_column(Float, default=None)
exam_date: Mapped[datetime | None] = mapped_column(DateTime, default=None)
```

注释自述"edu-cloud 原有字段（sync 用）"——这些字段是 edu-cloud 作为联考后端时的历史遗物，当时 Exam 建模为"单科考试"（一个 exam 一个 subject）。迁入 exam-ai 后 Exam 改成多科容器（Subject 表存每科），但 subject_code/subject_name 字段没删。

`workspace_service.py:47` 仍然把 `e.subject_code` 返回给前端，前端拿到 null。

#### 修复方向

**方案 A（最小改动 T1）**：`ContextPanel.vue:30` 改为 `label: \`${e.name} (${e.status || '未知'})\``。但 status 值是英文 `draft/scanning/grading/reviewing/completed`，用户看不懂。

**方案 B（推荐 T2）**：
1. 前端新增 `utils/examStatus.js` 映射函数 `STATUS_LABELS = { draft: '草稿', scanning: '扫描中', grading: '阅卷中', reviewing: '审核中', completed: '已完成' }`
2. `ContextPanel.vue:30` 改为 `label: \`${e.name} (${STATUS_LABELS[e.status] || e.status || ''})\``
3. `workspace_service.py:44-50` 在返回数据中加 `"status": e.status` 字段
4. 覆盖其他同样被 bug 困扰的地方（grep `${e.subject_code}` / `${e.subject_name}` 看是否还有引用）

**方案 C（彻底清理 T3）**：
1. 方案 B 全部做完
2. 调研 Exam.subject_code / subject_name / max_score / exam_date 这 4 个 legacy 字段还有谁引用
3. 如果只有 workspace_service 一处引用 → safe-delete model 字段 + migration
4. 如果有 sync pipeline 还在用 → 保留字段但加字段注释"仅联考同步链路使用，不是多科考试场景"

**推荐走方案 B**：解决 UX bug，暴露 legacy 字段真实使用范围，不动 schema。

#### 次要影响面

`${e.subject_code}` 的 legacy 字段依赖可能还出现在其他地方：
- grep 结果显示 `modules/exam/workspace_service.py:47` 是唯一直接引用点
- 不排除 dashboard/analytics/report 等模块可能通过 `Exam.subject_code` 做查询
- 方案 B 只修 UI 不动 model 是安全的（nullable 字段保持原状）

### D6 F003 方案 A/B/C 可行性反验 + 方案 D 细化（2026-04-11 20:20）

#### 原 R1 三个方案失效证据

**方案 A（pipeline 完成后自动创建 Question）失效**：
- pipeline_service 拿不到 Question 元数据（题号/分值/类型）
- 这些元数据的权威源是 CardEditor 的 editor_layouts/*.json 文件
- pipeline 是切图环节，没有题目语义上下文
- 让 pipeline 反向读 editor_layouts 违反模块边界（scan 不应依赖 card）

**方案 B（pipeline 输出改兼容 importer 目录）失效**：
- `marking/importer.import_from_folder()` 只处理 **已有 Question** 后的 StudentAnswer 关联
- Question 本身还是没人创建，规避症状不根治

**方案 C（新增 pipeline/commit 端点）失效**：
- 同样依赖 Question 表非空，和 A/B 一样堵在根因

#### 方案 D 完整技术闭环

```
[user] CardEditor 拖拽排版 + 填题号/分值
  ↓
PUT /api/v1/card/editor-layout/{subject_id}  (router.py:157)
  ├─ editor_layout_path.write_text(layout)           # 原有
  └─ ★ 新增：upsert_questions_from_layout(db, ...)   # 关键
       解析 layout.sides[].columns[].regions[] →
       upsert Question(subject_id, name=qno, max_score, type)
  ↓
[user] 点击"发布答题卡"
  ↓
POST /api/v1/card/publish  ★ 改前端走此路径（废弃 publishCard 手工三步）
  ├─ L1218 html_to_pdf
  ├─ L1221 extract_skeleton (F001 修后 side 正确)
  ├─ L1225 SELECT Question → question_map 非空
  ├─ L1232 skeleton_to_paperseg_json → regions 带 question_id
  ├─ ★ 修：循环写 A/B 双面 Template（当前 L1247 硬编码 "A"）
  └─ L1263 exam.status → scanning
  ↓
POST /api/v1/scan/pipeline/start
  ↓
pipeline_service.run_pipeline
  ├─ process_one_image 切图保存
  └─ ★ 新增：save_answer_fn 接通（参数已预留但 router.py:172 未传）
       insert StudentAnswer(
         exam_id, subject_id, student_id,
         question_id=<Template region_id 反查>,
         image_path, school_id
       )
```

#### 方案 D 6 个关键设计点（design 阶段必须澄清）

1. **Question.name ↔ skeleton slot.name 命名约定**
   - `export.py:97` 要求 `sr["name"] in question_map`
   - 全链路统一：CardEditor qno → layout JSON → Question.name → skeleton slot.name
   - 对现有 5 科种子 Question 做 migration 核对

2. **选择题 group 展开粒度**
   - CardEditor 的 objective_group = 11 题一组
   - DB Question 是**逐题 11 条**还是**组 1 条 + count 字段**？
   - 影响 marking/统计/mastery 计算
   - `export.py:62-67` 已经有 `per_question_ids` 逻辑，暗示应该逐题

3. **editor_layouts 文件 vs Question 表同步策略**
   - 幂等 upsert by (subject_id, name)
   - 删除题目：soft-delete (Question.is_deleted) vs hard-delete + CASCADE
   - 推荐 soft-delete，阅卷流程加过滤

4. **Template 双面写入**
   - 当前 L1247 硬编码 `side="A"`
   - 需按 skeleton region.side 分组写入两条 Template
   - 确认 Template 唯一约束是否支持 `(subject_id, side)` 复合键

5. **pipeline.save_answer_fn 反向查找**
   - pipeline 切图只有 tpl region_id
   - region_id → question_id 在 Template.regions[].question_id 里
   - pipeline_service 需接受 Template 参数构建查找表
   - `pipeline_service.py:142` 已有 `save_answer_fn=None` 参数但 router.py:172 未传

6. **既有 5 科种子数据兼容**
   - 地理/化学/历史/生物/政治已有种子 Question（S6）
   - 方案 D 启用后，与 editor_layouts 不一致会冲突
   - 推荐：第一阶段只处理新创建考试，老考试保持现状

#### 方案 D Tier 最终评估: **T4**

- **跨模块**：card + exam + scan + pipeline + marking + grading
- **跨层**：前后端数据契约 + DB schema + JSON schema + UI 流程
- **回归面**：5 科种子数据 / editor_layouts / Template / StudentAnswer / marking/importer
- **接口变更**：deprecate publishCard 前端三步，/publish 支持双面，save_editor_layout 副作用升级
- **流程要求**：brainstorming → writing-plans → Gate 1 (codex-review plan) → 新会话执行 → 多批次 code review → 集成 review → reconciliation

---

## Round 3 根因清单汇总 + 批次建议调整（2026-04-11 20:22）

### 全量 Finding 清单（14 项）

| ID | Severity | 类型 | 根因简述 | 精确位置 | Tier | 原批次 | 新批次 |
|----|----------|------|---------|---------|------|-------|-------|
| F001 | MED-LOW | UI DOM | render.js `.page` 元素缺 `data-side` 属性 → skeleton fallback 全 A | `frontend/src/card-editor/render.js:641,643,689,701` | T1 | B5 | **B1-f1**（合并 F003） |
| F002 | MED | 设计意图 | CardEditor 1587×1123 vs tpl 真实扫描尺寸双坐标系，设计并存但用户混淆 | `html_export.py:47` + `.tpl` 文件 | T3 | B5 | **B5**（独立）|
| F003 | HIGH | 架构断裂 | Question 创建入口从未接通；editor_layouts 文件不同步 DB，publish 读空 Question 表 | `card/router.py:157,1189-1270` + `export.js:177` | **T4** | B1 | **B1**（核心）|
| F003a | HIGH | Schema | publish 端点 L1247 硬编码 side="A"，B 面 Template 永不写入 | `card/router.py:1247` | T2 | B1 子项 | **B1-s5**（合并）|
| F004 | LOW | 观测缺失 | barcode 识别失败静默 fallback 文件名，无 log/计数/UI | `scan/pipeline_service.py:85-93` | **T2** | B6 | **B6a**（独立）|
| F005 | LOW | 接口 | `GET /api/v1/scan/tasks?exam_id` 返回 405 | scan/router.py（未读）| T1-T2 | B6 | **B6b** |
| F006 | HIGH | UX 权限 | 科任教师看到全部 9 科（F009 的症状）| 同 F009 | T2 | B2 | **B2**（同 F009）|
| F007 | MED | 错误分类 | grading/tasks 前置校验缺 4 项（Redis/Rubric/Answer/LLM）+ orphan task | `grading/router.py:146-179` | T2 | B3 | **B3a** |
| F008 | HIGH | 被遮蔽 | 选择题识别 + anchor/affine 被 F003 遮蔽不可独立验证 | 需 F003 解决后验证 | - | - | **依赖 B1 完成**|
| F009 | HIGH | 权限 | `get_subjects_with_progress` 无 visible_subject_codes 过滤 | `marking/scorer.py:12-18` | T2 | B2 | **B2**（一行改）|
| F010 | MED | 字段绑定 | ContextPanel 绑 `subject_code` 应绑 `status`，Exam.subject_code 是 legacy NULL | `ContextPanel.vue:30` + `workspace_service.py:47` | **T2** | B6 | **B6c** |
| F011 | HIGH-UX | 前端占位 | 4 个侧栏路由全 placeholder（studio/paper/calendar/notifications）| `router/index.js:56-60` | 4×T3 | B4 | **B4a-d** 拆 4 批 |
| F012 | HIGH-UX | 前端占位 | 同 F011（归并项）| 同 F011 | - | B4 | 同 F011 |
| F013 | MED | 根因误判 | 不是 LLM 超时，是 Redis 连接超时（R4 原判错）| `grading/router.py:128-141` + `config.py:14` | T2 运维 + T3 代码 | B3 | **B3b** |
| **F014** | MED-HIGH | 隐藏业务 | calendar `notification_service.dispatch` 是 stub，只标记 sent 不发消息 | `calendar/notification_service.py:14-42` | T3 | — | **新增批次 B7** |

### 批次建议调整（从 6 批扩到 7 批 + 依赖关系）

```
B1 F003 架构重设（T4，核心阻塞）
├─ s1 Question.name 命名约定 + 种子数据 migration
├─ s2 save_editor_layout 同步 upsert Question
├─ s3 前端 publishCard 切换到后端 /card/publish
├─ s4 publish 端点支持 A/B 双面 Template (合并 F003a)
├─ s5 pipeline 接通 save_answer_fn 写 StudentAnswer
└─ f1 合并 F001 render.js .page 加 data-side
     依赖：无（B1 是所有 HIGH finding 的上游）
     解锁：F008 可验证；marking/grading/adaptive 全链路通；F013/F007 修复后端到端可用

B2 权限过滤一行改（T2）
└─ marking/scorer.py:12-18 注入 visible_subject_codes 过滤（含 F006 + F009）
     依赖：无（独立，可和 B1 并行）

B3 grading 前置校验 + Redis（T2 运维 + T3 代码）
├─ a F007 router.py:146 加 4 项前置校验 + orphan task 防御
└─ b F013 启动 Redis + enqueue try/except + LLM 路径统一决策（延后到 B7）
     依赖：Redis 可达（运维）+ B1 完成（否则 worker 跑到 Question 空就 trivially completed）

B4 前端 4 页面（4 × T3 ≈ T4 规模）
├─ a Paper 论文写作（最轻）
├─ b Notifications 通知中心（依赖 B7 F014 解除 stub）
├─ c Calendar 校历（依赖 b）
└─ d Studio 文档中心（最重）
     依赖：B7 的 F014 必须修，否则 Notifications UI 显示虚假 sent

B5 CardEditor 坐标系清理（T3）
└─ F002 double coordinate system 设计意图文档化 + UI 警示
     依赖：B1 完成后再决定是合并 tpl 与 skeleton 还是保持双轨

B6 零散 UX 修（T1-T2 混合，可并行）
├─ a F004 barcode fallback 加日志 + 计数 + UI 核对面板
├─ b F005 scan/tasks 405 调查
└─ c F010 ContextPanel 字段绑定 + status 中文映射

B7 ★ 新增：通知分发 + LLM 路径统一（T3）
├─ a F014 calendar notification_service.dispatch 接入真实渠道（企微 / 邮件 / WebSocket）
└─ b 决策：grading worker 是否统一到 llm-proxy（原 F013 方案 C）
     依赖：B4b (Notifications UI) 的上游基础
```

### 依赖图（修复顺序）

```
时间 →
[B1 核心]───────────────────────────────────────┐
   ↓                                            │
   ├──→ F008 可验证                             │
   └──→ 阅卷/grading/adaptive 链路通  ──────────┤
                                                │
[B2] 独立并行                                   │
[B3a] F007 前置校验（独立）                     │
[B3b] F013 Redis 运维 ─────────────────┐        │
                                        │        │
[B5] F002 依赖 B1 完成后决策 ───────────┼────────┤
                                        │        │
[B6a/b/c] 独立并行                      │        │
                                        │        │
[B7a] F014 通知分发 ────────────────────┼────────┤
[B7b] LLM 路径统一（延后）              │        │
                                        │        │
[B4a] Paper 独立                        │        │
[B4b] Notifications 依赖 B7a ───────────┘        │
[B4c] Calendar 依赖 B4b                          │
[B4d] Studio 独立（最重，可单独 T4 项目）        │
                                                 ↓
                                            全部完成
```

### 推荐启动顺序

1. **立刻可做**（T1-T2，低风险，独立）:
   - B2 权限过滤（一行改）
   - B3a F007 前置校验
   - B6c F010 字段绑定
   - B6a F004 barcode 观测

2. **需要 design 阶段**（T3+，有设计决策）:
   - **B1 F003 架构重设（最优先）** — 是所有 HIGH finding 的上游
   - B7a F014 通知分发
   - B4a Paper 论文页面
   - B5 F002 坐标系文档化

3. **延后**（依赖上游）:
   - B4b/c/d Notifications/Calendar/Studio
   - B3b F013 Redis + LLM 统一

4. **运维修复**（并行，不阻塞代码流程）:
   - B3b-part1 启动 Redis
   - 配置 LLM_API_URL 等 .env 变量

### 工作量估算（粗估）

| 批次 | Tier | 代码工作量 | 测试工作量 | 审查轮次估算 |
|------|------|-----------|-----------|-------------|
| B1 | T4 | 2-3 周（5 个子任务）| 高（全链路 E2E）| 3-5 轮 |
| B2 | T2 | 0.5 天 | 低 | t2-review 1 轮 |
| B3a | T2 | 1 天 | 中 | t2-review 1-2 轮 |
| B3b | T3 | 1-2 天 | 中 | 1-2 轮 |
| B4a | T3 | 3-5 天 | 中 | 1-2 轮 |
| B4b | T3 | 3-5 天 | 中 | 1-2 轮 |
| B4c | T3 | 5-7 天 | 中 | 1-2 轮 |
| B4d | T3-T4 | 1-2 周 | 高 | 2-3 轮 |
| B5 | T3 | 1 天（文档为主）| 低 | 1 轮 |
| B6a | T2 | 1 天 | 中 | 1 轮 |
| B6b | T1 | 0.5 天 | 低 | - |
| B6c | T2 | 0.5 天 | 低 | 1 轮 |
| B7a | T3 | 3-5 天 | 中 | 1-2 轮 |
| B7b | T3-T4 | 1-2 周 | 高 | 2-3 轮 |

**总计**: ~1.5-2 个月全量修复工作（按每日 6 小时有效开发估算）

---

## Round 3 T2 快修执行记录（2026-04-11 20:51）

### 4 批 T2 完成清单（本会话内独立 commit）

| 批 | Commit | Finding | 修复范围 | 新增测试 | 广域回归 |
|---|--------|---------|---------|---------|---------|
| B2 | `d5cedb4` | F006+F009 | `marking/scorer.py` + `router.py` + `exporter.py` 3 端点（subjects/progress/**export**）注入 visible_subject_codes | 4 回归（admin 全量 / subject_teacher 过滤 / 空 codes / CSV 表头不泄漏）| 421/421 exam 广域 PASS |
| B3a | `bbeeb8f` | F007 | `grading/router.py` 创建端点加 4 项前置校验 + enqueue 失败清理 orphan task 返回 503 | 4 回归（no subjective / no rubric / no answer / enqueue ConnectionError）| 39/39 grading+marking+worker PASS |
| B6a | `2ce070b` | F004 | `scan/pipeline_service.py` — barcode_status 状态机 + logger.warning + PipelineProgress 聚合 barcode_failed 计数器 | 4 回归（exception / none / success / 3 次混合聚合）| 11/11 scan_pipeline PASS |
| B6c | `75922c7` | F010 | `workspace_service.py` 返回 status 字段 + `ContextPanel.vue` 改绑 status + 新增 `utils/examStatus.js` 中文映射 | 1 回归（test_get_context_tree_returns_status_field）| 10/10 workspace + 182/182 前端 vitest PASS |

**合计**: 13 个新回归测试 / 4 commit / 零 card 模块触碰

### B2 scope 扩展决策（L001 同模式全覆盖）

原 B2 计划仅修 `/marking/subjects` + `/marking/progress`。scope check 时发现 `marking/exporter.py:24` 同模式漏改（`/marking/export` 也会给 subject_teacher 导出全科成绩 → 数据泄漏）。按 L001 bug-fix-discipline 要求同批次修复，扩展 B2 至 3 端点。

### 新发现 finding（不在本批次范围）

#### 🟡 F015 [MED] analytics/service.py 同类权限过滤缺失

**症状**：`src/edu_cloud/modules/analytics/service.py:62` 同样是 `select(Subject).where(Subject.exam_id, Subject.school_id)` 模式，同样没注入 visible_subject_codes 过滤。subject_teacher 调 `/api/v1/analytics/*` 端点（analytics 模块约 10+ 端点）可能看到不该看的其他科目统计数据。

**为什么不并入 B2**：
1. analytics 是独立模块，影响面远大于 marking（10+ 端点，含 report/trend/summary 等多个分析入口）
2. B2 严格限定在 marking 模块同模式修复，扩到 analytics 会触发 scope creep
3. 需要系统性评估 analytics 的所有 endpoint 哪些需要按 subject 过滤，哪些是全局（如跨校对比）
4. 跑完 B2 的 3 个 marking 端点修复已经证明方案可行，F015 可沿用相同模板

**待做**：记入本文件清单，等 B2 commit 后再决定是否作为独立批次 B8

#### F013 根因已修订（R4 原判断错误）

本次 D1 调查发现 F013 "grading/tasks 11s 超时" 真相不是 LLM 超时，是 **Redis 连接超时**（arq.create_pool）。notes 原始 F013 描述（grading 模块独立 LLM 配置问题）已在 D1 段颠覆。B3a 的 F007 前置校验 + orphan task 防御间接缓解了 F013（enqueue 失败快速 503 而非 11s 超时），但 Redis 运维和 LLM 路径统一（B7）仍待处置。

### 执行过程中的 card 模块 WIP 发现

git status 检测到 edu-cloud 有 4 个未 commit 修改文件在 card 模块。通过后台 Agent 调查确认：

**归属任务**: "小微排版引擎 v2 视觉验收"
**Handoff 文档**: `docs/plans/2026-04-08-card-xiaowei-layout-v2-handoff.md`
**影响文件**:
- `frontend/src/card-editor/render.js`（essay-row 布局重构 + 标点分组 + 视觉定额高度 `targetHeight_mm`）
- `frontend/public/card-editor/styles.css`（grid 驱动 v2 排版引擎）
- `src/edu_cloud/modules/card/answer_parser.py`（①②③ 圈数创建新 sub + 标点清理）
- `src/edu_cloud/modules/card/answer_standardizer.py`（LLM 配置迁移，副作用）
- `src/edu_cloud/ai/tools/card_layout.py`（视觉行数 + 最优分割装箱 + targetHeight_mm）

**完成度**: 70-80%（代码重构完成，未视觉验收）
**与 F003 修复冲突风险**: 无直接冲突，但 B1 F003 方案 D 会触碰 card 模块的 Template/Question/publish 路径，必须先完成小微排版验收，WIP 回主线后才能启动 B1

### B1 启动前置条件

B1 F003 design（方案 D）阻塞在：
1. **小微排版 v2 视觉验收完成** — card 模块 WIP 收尾后才能动（用户决策 Q1=C）
2. **Question 命名约定决策** — D6 列出的 6 个设计决策点，需要用户在 design 阶段明确
3. **既有 5 科种子 Question 兼容策略** — migration 方案
- "发布答题卡"按钮触发 dialog confirm（带"答题卡锁定为只读"警告），但 confirm 内部调用的实际是 export.js 的 publishCard——名实不符
