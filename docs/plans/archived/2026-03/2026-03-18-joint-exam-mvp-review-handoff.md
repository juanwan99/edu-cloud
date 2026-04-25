[edu-cloud] Executor→Reviewer | 2026-03-18 19:35:04
## 审查交接单: Task 1-11
计划: docs/plans/2026-03-18-joint-exam-mvp-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | 5 个异常类 + 全局异常处理器 | commit 3b92154, 5 异常类 + 5 个 handler 注册 + middleware 穿透 | ✅ | |
| T2 | require_permission + conftest fixtures | commit a7f20b2, 工厂函数 + admin_user/admin_headers/seed_school/school_api_headers fixtures | ✅ | |
| T3 | SchoolService CRUD | commit 59af626, create/list/get/update/rotate 5 方法 + 7 tests | ✅ | |
| T4 | 学校管理 API 端点 | commit af9091f, POST/GET/PATCH/rotate-key + 6 tests | ✅ | |
| T5 | 数据模型改造 | commit c6c21c4, JointExam 新字段 + JointExamStudentResult 替代 JointExamScore + 3 tests | ✅ | |
| T6 | JointExamService 创建+参与校 | commit 7c86bdd, create_exam/add_participant/remove_participant/distribute/get_exam_detail + 5 tests | 🔀 | 将 Task 6+7 的 Service 实现合并到单一文件，Task 7 仅追加测试 |
| T7 | JointExamService 模板+成绩 | commit f82759a, upload_template/submit_scores/force_complete + 4 tests (upsert 测试修正了 auto-complete 逻辑) | ✅ | |
| T8 | 联考管理 API + sync 改造 | commit 4fedaf9, joint_exams.py(9 端点) + sync.py 重写(5 端点) + 9 tests | ✅ | |
| T9 | ResultsService + API | commit 985b1bf, 排名/对比/明细 3 方法 + 3 API 端点 + 8 tests | ✅ | |
| T10 | exam-ai CloudSyncService | commit 2c4064c(exam-ai), httpx 客户端 6 方法 + 4 API 端点 + 7 tests + CLAUDE.md 更新 | ✅ | |
| T11 | E2E 脚本 + CLAUDE.md | commit a3dbe21, 11 步 E2E 脚本 + CLAUDE.md 全面更新 | ✅ | |

> 状态: ✅一致 / ❌不一致 / 🔀改进

### 验证清单自检

**全局检查（计划末尾）：**
- ✅ 所有 Service 不导入 FastAPI — 已确认 school_service/joint_exam_service/results_service 无 FastAPI import
- ✅ 所有异常通过全局处理器映射（无 HTTPException 直抛）— Service 层仅抛自定义异常
- ✅ API Key 明文仅在 create/rotate 响应中返回一次 — POST /schools 和 POST rotate-key 返回后不可再获取
- ✅ JointExamScore 旧模型不再被引用 — Grep 确认 src/ 中零 import（仅 docstring 注释）
- ✅ CLOUD_ENABLED=false 时 exam-ai 无任何副作用 — 路由不注册，test_cloud_disabled_returns_404 验证
- ✅ 端口号统一: edu-cloud=9000, exam-ai=8000 — CLAUDE.md 和 config 一致
- ✅ CLAUDE.md 与实际 API/模型一致 — 已全面更新

**Per-Task 审查清单：**
- ✅ T1: 异常类不导入 FastAPI
- ✅ T3: bcrypt hash 存储，明文不持久化; rotate 旧 key 立即失效
- ✅ T4: POST /schools 返回 201 + 明文 key; 响应不含 api_key_hash
- ✅ T5: JointExamStudentResult 有唯一约束和排名索引
- ✅ T6: create_exam 自动添加出题校; remove_participant 不能移除出题校
- ✅ T7: 所有科目模板上传完自动 draft→templates_ready; upsert 不重复
- ✅ T8: /sync/templates POST 接收 multipart; /sync/joint-exams GET 返回 template_url
- ✅ T9: 排名使用 total_score 列; median 用 Python statistics.median
- ✅ T10: httpx.AsyncClient 用 base_url + X-API-Key header; CLOUD_ENABLED=false 路由不注册

### 自查（四要素格式）

- 新增文件的边界 case：
  构造输入: 不存在的 school_id 请求 GET /api/v1/schools/{id}
  运行命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_api/test_schools.py::test_get_nonexistent_school_404 -v`
  实际输出:
  ```
  tests/test_api/test_schools.py::test_get_nonexistent_school_404 PASSED
  ```
  结论: NotFoundError → 全局处理器 → 404 正确映射

- 状态变量/状态机的异常路径：
  构造输入: draft 状态联考直接 distribute（跳过模板上传）
  运行命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_joint_exam_service.py::test_distribute_requires_templates_ready -v`
  实际输出:
  ```
  tests/test_services/test_joint_exam_service.py::test_distribute_requires_templates_ready PASSED
  ```
  结论: StateError 正确阻止非法状态转换

- 字符串匹配/upsert 的数据完整性：
  构造输入: 同一学生同一科目二次提交成绩（upsert 场景）
  运行命令: `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_services/test_joint_exam_service.py::test_submit_scores_upsert -v`
  实际输出:
  ```
  tests/test_services/test_joint_exam_service.py::test_submit_scores_upsert PASSED
  ```
  结论: upsert 正确更新已有记录，数据库只有 1 条记录

使用 codex-review skill 进行 GPT 代码审查。
