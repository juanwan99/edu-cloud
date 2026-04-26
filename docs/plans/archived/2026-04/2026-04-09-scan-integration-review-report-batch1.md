[edu-cloud] GPT Reviewer | 2026-04-09 16:25:03
## 审查报告: Task 1-6 (R1)
结论: FAIL

### 第一段：测试充分性（Test Adequacy）
- vision/tpl_parser 单元测试充分，能在错误实现下失败
- pipeline 测试只覆盖 list_scan_images 和 process_one_image 的 happy path
- run_pipeline 成功路径、持久化、进度、停止逻辑无入口级测试（F002）
- API 测试只覆盖错误分支（404/400），缺少成功路径覆盖

### 第二段：行为正确性（Behavioral Correctness）
#### 变更理解
GPT 理解：将 paper-seg 的 6 个 vision 文件迁入 edu-cloud scan 模块，新建 tpl_parser（解析 .tpl JSON）和 pipeline_service（批量切割），新建 pipeline_router（5 个 API 端点），前端在 ExamDetailPage 扫描 tab 实现操作界面。

#### 对抗性审查
- F001: save_answer 回调使用 region_id（Q01）作为 question_id，但 StudentAnswer 有 FK 到 questions.id，会导致 IntegrityError 被静默吞掉
- F003: process_one_image 只做线性缩放裁切，未使用已迁入的 anchor/affine 路径
- F004: 前端预览按钮声明了状态但未接线，preview API 是死代码

### 第三段：未测试风险（Non-tested Risks）
- 全局 _running/_progress 对多考试并行场景的隔离
- image_dir/tpl_path 任意服务器路径输入的安全风险
- 前端轮询在组件销毁时的清理

### 发现清单

**F001**
- ID: F001
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Before-behavior: 流水线把 region_id（Q01）当 question_id 写入 StudentAnswer，FK 失败被 IntegrityError 静默吞掉
- After-behavior: 流水线只负责切图存储，不写 StudentAnswer
- Evidence: pipeline_router.py:103-115
- Impact: StudentAnswer 入库失败但统计为 processed
- Status: verified → ✅ 已修复 (commit 320df26)

**F002**
- ID: F002
- Severity: HIGH
- Category: test-gap
- Type: defect_fix
- Before-behavior: run_pipeline 成功路径、save_fn 调用、stop 语义无测试
- After-behavior: 新增 3 个入口级测试覆盖 success/save_fn/stop
- Evidence: test_scan_pipeline.py 只有 4 个测试
- Impact: 删除 run_pipeline 核心逻辑后测试仍全绿
- Status: verified → ✅ 已修复 (commit 320df26)

**F003**
- ID: F003
- Severity: HIGH
- Category: code-bug
- Type: defect_fix
- Before-behavior: process_one_image 只做线性缩放裁切，不使用 anchor/affine
- After-behavior: GPT 建议有 anchor 时走仿射变换路径
- Evidence: pipeline_service.py:70-94
- Impact: 扫描件倾斜时裁切不准
- Status: contested → accepted-risk（reason: Plan 明确定义 MVP scope 为缩放比裁切，anchor 对齐为后续增强阶段。真实扫描图定位点检测测试通过，vision 模块已迁入待集成。）

**F004**
- ID: F004
- Severity: MED
- Category: code-bug
- Type: defect_fix
- Before-behavior: 前端预览按钮未接线，scanPreviewImage 是死状态
- After-behavior: 预览按钮接线，支持 image_dir 自动取第一张图
- Evidence: ExamDetailPage.vue:301-313
- Impact: 用户无法在批量切割前预览确认
- Status: verified → ✅ 已修复 (commit 320df26)

### Process Findings（不阻塞）
- PF-001: Contract Pack 缺失（plan 未包含）— 记录，不阻塞
- PF-002: Commit range 包含 knowledge-tree 提交 — 审查只针对 scan-integration 相关文件
