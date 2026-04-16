# paper-seg 整合到 edu-cloud — 扫描切割一体化设计

> [2026-04-09 16:51:21 实现完成] Commits: a9bc0e4..fb79600

## §0 背景

paper-seg 是独立的扫描切割客户端（port 8001），有自己的登录、前端、API。edu-cloud 刚完成 exam-ai 兼容层，paper-seg 可以连接 edu-cloud，但用户仍需操作两个系统。

**目标**：将 paper-seg 的核心视觉处理能力整合到 edu-cloud，用户在 edu-cloud 考试详情页内一站完成扫描切割全流程。paper-seg 退役。

## §1 后端整合

### §1.1 视觉处理模块迁移

将 `paper-seg/app/vision/` 的 6 个文件复制到 `edu-cloud/src/edu_cloud/modules/scan/vision/`：

| 源文件 | 目标文件 | 功能 |
|--------|---------|------|
| `app/vision/anchors.py` | `scan/vision/anchors.py` | 定位点检测（形态学） |
| `app/vision/transform.py` | `scan/vision/transform.py` | 仿射校正矩阵计算 |
| `app/vision/segment.py` | `scan/vision/segment.py` | 区域裁切（crop_region） |
| `app/vision/barcode.py` | `scan/vision/barcode.py` | 条码/二维码解码 |
| `app/vision/fillmark.py` | `scan/vision/fillmark.py` | 填涂区域识别 |
| `app/vision/lines.py` | `scan/vision/lines.py` | 横线检测（A3 分半） |

改动仅限 import 路径调整，不改逻辑。

新增 `scan/vision/__init__.py` 导出核心函数。

### §1.2 流水线服务

新建 `src/edu_cloud/modules/scan/pipeline_service.py`，核心流程：

```
start_pipeline(subject_id, side, image_dir, school_id, exam_id)
  │
  ├─ 1. 加载 Template（从 DB，含 anchors + regions）
  ├─ 2. 解析 .tpl 文件（如果 Template 无数据，从 tpl_path 导入）
  ├─ 3. 列出 image_dir 下的 PNG 文件（按文件名排序）
  ├─ 4. 逐张处理：
  │     ├─ 读条码 → student_id
  │     ├─ 灰度化 + 定位点检测
  │     ├─ 计算缩放比（模板尺寸 vs 扫描图尺寸）
  │     ├─ 逐区域裁切（按比例缩放坐标）
  │     ├─ 主观题切图 → StorageService.save() → StudentAnswer
  │     ├─ 选择题填涂识别 → StudentAnswer(detected_answer, score)
  │     └─ 更新 ScanTask 进度
  └─ 5. 完成：ScanTask.status = completed
```

**直接写库**：切图不走 HTTP 上传，直接调 StorageService + 写 StudentAnswer 表。

**进度追踪**：用内存字典 `_pipeline_progress: dict[str, PipelineProgress]` 存储进度，前端轮询。

**并发控制**：`asyncio.Lock` 保护，同一时刻只能运行一个流水线。

### §1.3 新增 API 端点

在 `scan/router.py` 扩展（或新建 `scan/pipeline_router.py`）：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/scan/pipeline/start` | 启动切割流水线。参数：`{subject_id, side, image_dir, tpl_path?}` |
| `GET` | `/api/v1/scan/pipeline/progress` | 轮询进度。返回：`{status, total, processed, failed, current_file, warnings[]}` |
| `POST` | `/api/v1/scan/pipeline/stop` | 停止流水线 |
| `POST` | `/api/v1/scan/preview` | 单张预览。参数：`{image_path, subject_id, side}`。返回：标注了定位点和切割区域的图片（base64） |
| `POST` | `/api/v1/scan/import-tpl` | 导入 .tpl 模板文件。参数：`{tpl_path, subject_id, side}`。解析后写入 Template 表 |

### §1.4 tpl 解析

从 paper-seg 的 `routers/templates.py` 提取 tpl 解析逻辑到 `scan/tpl_parser.py`：
- `parse_tpl_file(path)` → 解析定位点 + 选择题组 + 主观题区域 + 条码区域
- `tpl_to_template(tpl_data)` → 转换为 Template 模型格式（anchors + regions）

### §1.5 依赖

pyproject.toml 新增：
- `opencv-python-headless`（不需要 GUI）
- `pyzbar`（条码识别）

已有的 `numpy`、`Pillow` 不变。

## §2 前端整合

### §2.1 扫描状态 Tab 改造

在 `ExamDetailPage.vue` 的"扫描状态"tab 内，替换当前的空白内容：

**布局**：
```
┌─────────────────────────────────────────┐
│ 科目: [下拉选择]   面: [A/B]            │
│ 模板: ✅ 已发布 / ❌ 未发布 [导入.tpl]   │
├─────────────────────────────────────────┤
│ 扫描目录: [___________________] [浏览]  │
│ 图片数: 127 张 A面 + 127 张 B面          │
├─────────────────────────────────────────┤
│ [预览切割]  [开始扫描]  [停止]           │
├─────────────────────────────────────────┤
│ 进度: ████████░░ 89/127  失败: 2        │
│ 当前: I0101000089A.png                  │
│ 警告: 3 张条码未识别（文件名兜底）        │
├─────────────────────────────────────────┤
│ 预览区（选一张图展示定位点+切割框）       │
└─────────────────────────────────────────┘
```

### §2.2 API 调用

新增 `frontend/src/api/scan.js`：
- `startPipeline(subjectId, side, imageDir, tplPath?)`
- `getPipelineProgress()`
- `stopPipeline()`
- `previewScan(imagePath, subjectId, side)`
- `importTpl(tplPath, subjectId, side)`

### §2.3 预览功能

用户选一张扫描图后点"预览切割"：
- 后端返回标注图（定位点红框 + 切割区域蓝框 + 区域名称标签）
- 前端用 `<img>` 显示 base64 图片
- 确认定位准确后再开始批量处理

## §3 数据流

```
考试详情页 → 选科目 → 扫描状态 tab
  │
  ├─ 模板来源：Template 表（答题卡发布时写入）
  │              或 .tpl 文件导入
  │
  ├─ POST /api/v1/scan/pipeline/start
  │     │
  │     ├─ 读本地目录 PNG
  │     ├─ 定位点检测 + 缩放裁切
  │     ├─ 主观题 → StorageService → StudentAnswer(image_path)
  │     ├─ 选择题 → fillmark → StudentAnswer(detected_answer, score)
  │     └─ 条码 → student_id
  │
  ├─ GET /api/v1/scan/pipeline/progress (轮询)
  │
  └─ 完成 → 考试可进入 grading 阶段
```

## §4 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/edu_cloud/modules/scan/vision/__init__.py` | 新建 | 包入口 |
| `src/edu_cloud/modules/scan/vision/anchors.py` | 新建 | 定位点检测（从 paper-seg 复制） |
| `src/edu_cloud/modules/scan/vision/transform.py` | 新建 | 仿射校正（从 paper-seg 复制） |
| `src/edu_cloud/modules/scan/vision/segment.py` | 新建 | 区域裁切（从 paper-seg 复制） |
| `src/edu_cloud/modules/scan/vision/barcode.py` | 新建 | 条码解码（从 paper-seg 复制） |
| `src/edu_cloud/modules/scan/vision/fillmark.py` | 新建 | 填涂识别（从 paper-seg 复制） |
| `src/edu_cloud/modules/scan/vision/lines.py` | 新建 | 横线检测（从 paper-seg 复制） |
| `src/edu_cloud/modules/scan/tpl_parser.py` | 新建 | tpl 文件解析 + 转 Template |
| `src/edu_cloud/modules/scan/pipeline_service.py` | 新建 | 流水线核心逻辑 |
| `src/edu_cloud/modules/scan/pipeline_router.py` | 新建 | 流水线 API 端点 |
| `src/edu_cloud/api/app.py` | 修改 | 注册 pipeline_router |
| `frontend/src/api/scan.js` | 新建 | 扫描 API 调用层 |
| `frontend/src/pages/ExamDetailPage.vue` | 修改 | 扫描状态 tab 内容 |
| `pyproject.toml` | 修改 | 新增 opencv-python-headless, pyzbar |
| `tests/test_services_exam/test_scan_pipeline.py` | 新建 | 流水线测试 |
| `tests/test_services_exam/test_tpl_parser.py` | 新建 | tpl 解析测试 |

## §5 不做的事

- 不做浏览器文件上传（当前是本地场景，YAGNI）
- 不做模板可视化编辑器（用 .tpl 导入 + 答题卡编辑器发布覆盖）
- 不删除 paper-seg 项目（保留但不再维护）
- 不删除 compat 兼容层（保留向后兼容）
- 不做 A3 自动分半处理（扫描仪已输出单面 PNG）

## §6 风险

| 风险 | 缓解 |
|------|------|
| OpenCV 依赖增大 Docker 镜像 | 用 headless 版（~50MB），edu-cloud 已有 Playwright Chromium 所以影响不大 |
| pyzbar 需要 zbar 系统库 | Dockerfile 加 `apt-get install libzbar0` |
| 流水线处理慢（200+ 张图） | 异步处理 + 进度轮询，不阻塞前端 |
| 本地路径安全性 | 校验路径存在 + 仅允许读取图片文件 + 不执行任何动态代码 |
