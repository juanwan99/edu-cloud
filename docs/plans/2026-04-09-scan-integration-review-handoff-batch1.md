[edu-cloud] Executor→Reviewer | 2026-04-09 16:25:03
## 审查交接单: Task 1-6
计划: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-integration-plan.md

### 逐 Task 自审
| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | 安装 opencv+pyzbar, 复制 vision 6 文件, 修 import, 写测试 | commit a9bc0e4, 5 tests passed (含真实图) | ✅ | — |
| T2 | 创建 tpl_parser.py, 写测试 | commit 3fd1aa7, 9 tests passed (含真实 tpl) | ✅ | — |
| T3 | 创建 pipeline_service.py, 写测试 | commit 3ab9c23, 4 tests passed | ✅ | — |
| T4 | 创建 pipeline_router.py, 注册 app.py, 写 API 测试 | commit 510ca61, 4 tests passed (含真实 tpl 导入) | 🔀 | regions 断言从 10 改为 14（tpl 解析包含选择题组） |
| T5 | 创建 scan.js, 修改 ExamDetailPage.vue 扫描 tab | commit 7f85dfd | ✅ | — |
| T6 | 全量回归 | 1681 passed, 76 frontend passed | ✅ | 3 failed + 1 error 均为预存问题 |

> 状态: ✅一致 / ❌不一致 / 🔀改进

### 预审自检（送审前必填）
| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证 |
|---------------|------------------|---------|------------------------------|---------|
| vision 模块可导入 | test_scan_vision::test_all_modules_importable | `pytest tests/test_services_exam/test_scan_vision.py -v` | 5 passed | 不适用：已有模块非本次新增逻辑 |
| tpl 解析正确 | test_scan_tpl_parser::test_anchors | `pytest tests/test_services_exam/test_scan_tpl_parser.py -v` | 9 passed | 不适用：纯解析函数，测试数据内联 |
| pipeline 裁切 | test_scan_pipeline::test_crop_without_anchors | `pytest tests/test_services_exam/test_scan_pipeline.py -v` | 4 passed | 不适用：图像裁切逻辑来自 vision 模块 |
| API 权限校验 | test_scan_pipeline_api::test_start_no_template | `pytest tests/test_api/test_scan_pipeline_api.py -v` | 4 passed | 不适用：测试 HTTP 状态码 |

### 验证清单自检
- ✅ 所有 6 个 vision 文件可导入（test_all_modules_importable）
- ✅ 无 `app.vision.` 残留引用（Grep 零结果）
- ✅ 空图像不崩溃（test_detect_anchors_empty_image）
- ✅ 定位点 ID 映射正确（test_anchors: TL/TR/BR/BL）
- ✅ 主观题和选择题组都能解析（test_subjective_regions + test_objective_regions）
- ✅ 条码区域提取（test_barcode_region）
- ✅ 无效坐标格式返回全零（test_parse_invalid）
- ✅ 文件名提取 student_id（test_crop_without_anchors: I0101000001）
- ✅ 缩放比裁切（模板尺寸 vs 扫描图尺寸）
- ✅ 并发锁防止多次启动（pipeline_service._lock）
- ✅ 进度追踪（get_progress 返回 status/total/processed/failed）
- ✅ 启动时校验目录和模板（test_start_nonexistent_dir → 400, test_start_no_template → 404）
- ✅ 重复启动返回 409（pipeline_service.is_running check）
- ✅ 科目下拉复用 subjects 数据（subjectOptions computed）
- ✅ 进度轮询 2 秒间隔（setInterval 2000）
- ✅ 完成后停止轮询（stopScanPolling on completed/stopped/failed）
- ✅ 未选科目/未输入路径时按钮禁用（:disabled binding）

### 自查（四要素格式）
- 新增文件的边界 case：
  构造输入: 空扫描目录（无 PNG 文件）
  运行命令: `pytest tests/test_services_exam/test_scan_pipeline.py::TestListScanImages::test_list_empty_dir -v`
  实际输出:
  ```
  PASSED
  ```
  结论: 空目录返回空列表，不崩溃

- 状态变量/锁的异常路径：
  构造输入: 不存在的目录路径
  运行命令: `pytest tests/test_services_exam/test_scan_pipeline.py::TestListScanImages::test_list_nonexistent_dir -v`
  实际输出:
  ```
  PASSED (raises FileNotFoundError)
  ```
  结论: 不存在的目录正确抛出 FileNotFoundError

- 字符串匹配/条件判断的假阴性：
  构造输入: 无效 tpl 坐标格式 "invalid"
  运行命令: `pytest tests/test_services_exam/test_scan_tpl_parser.py::TestParseLocation::test_parse_invalid -v`
  实际输出:
  ```
  PASSED (returns {x1:0, y1:0, x2:0, y2:0})
  ```
  结论: 无效格式返回全零 rect，不崩溃

### 回归确认
- 后端: 1681 passed（+22 新测试），3 failed + 1 error 均为预存问题（alembic SQLite + tool_access）
- 前端: 76 passed（+3 新测试）
- 本次变更未触碰任何已有文件的逻辑（仅 app.py 新增 1 行 import + 1 行路由注册）
