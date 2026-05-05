---
name: card
status: active
owner: backend
layer: business

owns_tables:
  - templates
  - card_skeletons

owns_routes:
  - /api/v1/card
  - /api/v1/templates

exposes:
  services:
    - publish_card_atomic (publish_service)
    - upsert_questions_from_skeleton (publish_service)
    - render_card_v2 (rendering/renderer)
    - calculate_layout (ai/tools/card_layout)
    - html_to_pdf (export/html_export)
    - TemplateLibrary (template/template_library)
    - AnswerParser (parser/answer_parser)
  events: []

depends_on:
  modules:
    - exam
  services: []
  ai_tools:
    - card_parse_answers (card_layout.py)
    - card_auto_layout (card_layout.py)
    - card_adjust_layout (card_layout.py)

created: "2026-05-05"
last_reviewed: "2026-05-05"
design_docs:
  - docs/plans/2026-04-11-f003-question-writeback-design.md
---

# card 模块

## 职责

答题卡设计、排版、渲染和发布全链路：骨架管理（CardSkeleton）、扫描模板存储（Template）、可视化编辑器布局 CRUD、答案解析、PDF/HTML 渲染导出、条码生成、发布时原子 upsert Question+Template。

## 边界

- **做什么**：CardSkeleton CRUD、Template CRUD（A/B 面）、答题卡渲染（HTML→PDF，Playwright）、答案解析（Word/文本→结构化）、自动排版算法（card_layout AI 工具）、发布原子操作（publish_service）、条码贴纸生成
- **不做什么**：扫描切割（scan 读 Template 做检测）、考试管理（exam）、AI 阅卷（grading）

## 使用方式

前端通过 `/api/v1/card/*` 端点管理编辑器骨架和渲染；scan 模块 pipeline_router 通过 `Template` 模型读取模板做切割对齐；AI Agent 通过 3 个 card_layout 工具支持自然语言排版。publish_service 是答题卡发布的唯一入口（原子写 Question + Template）。

## 数据流

```
前端编辑器 → CardSkeleton（骨架数据）
    → card_auto_layout / card_adjust_layout（AI 排版）
    → render_card_v2（HTML→PDF 渲染）
    → publish_card_atomic → upsert Question + Template（原子事务）
scan pipeline → 读 Template.regions/anchors → 切割对齐
```
