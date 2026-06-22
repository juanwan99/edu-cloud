---
name: scan
status: active
owner: backend
layer: business

owns_tables:
  - scan_tasks
  - student_answers

owns_routes:
  - /api/v1/scan
structure_pattern: multi-router
max_router_loc: 1300
routers: [router.py, pipeline_router.py]

exposes:
  services:
    - StorageService
    - PipelineProgress
    - auto_detect_cv_regions
    - grade_objective_answer
    - parse_tpl_file
  events: []

depends_on:
  modules: []
  services:
    - scan_workflow
  ai_tools: []

created: "2026-05-05"
last_reviewed: "2026-06-22"
design_docs:
  - docs/plans/2026-04-12-grading-dispatch-design.md
---

# scan 模块

## 职责

扫描图采集与切割全流程：接收 paper-seg 上传的扫描图、批量流水线切割（vision 子包：定位点检测/裁切/条码识别/选择题识别）、客观题自动判分、tpl 模板解析、OpenCV+LLM 混合区域检测、StudentAnswer 写入。

## 边界

- **做什么**：扫描图上传/存储、ScanTask 进度管理、流水线批量切割、选择题自动判分（objective_grading）、答题卡区域 CV 检测 + LLM 语义标注（auto_detect_cv）、tpl 文件解析导入
- **不做什么**：主观题 AI 评分（grading）、成绩统计（analytics）、答题卡设计/渲染（card）

## 使用方式

paper-seg 客户端通过兼容 API 或 `/api/v1/scan/*` 上传切图；前端通过 pipeline 端点控制批量切割流程；grading 模块和 analytics 模块读取 StudentAnswer 表获取学生作答数据。

## 数据流

```
paper-seg / 前端上传 → StorageService 存储图片
    → pipeline_service 批量切割（vision 定位+裁切+条码）
        → StudentAnswer 写入（含 objective_grading 自动判分）
    → grading 读 StudentAnswer 做 AI 评分
    → analytics 读 StudentAnswer 做统计
```
