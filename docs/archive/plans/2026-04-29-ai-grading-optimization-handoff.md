# AI 阅卷成本优化 + 条码识别修复 — 交接文档

> 会话时间：2026-04-28 17:00 ~ 2026-04-29 07:20 (UTC+8)
> Commits: 7fa84f2..3ced8f5 (6 commits, 18 files, +863/-168)

## Goal

完成了两件事：
1. **AI 阅卷切换 Gemini 官方直连 + 双模式（实时/经济）**
2. **条码识别根因修复（模板坐标缩放）**

## 全局上下文（新窗口必须知道的）

### edu-cloud 是什么
多校协同云端平台，当前用户在测试 **景炎初级中学** 的考试流程：扫描→切割→AI 阅卷→人工复核。考试 ID `796f7c26`，三个科目（语文/生物/地理），1342 名学生。

### LLM 路由架构（关键！）
```
┌─ edu-cloud ─────────────────────────────────────────┐
│                                                      │
│  GEMINI_API_KEY 有值时：                              │
│    grade-single / worker → GeminiClient              │
│    (google-genai SDK 直连 Google，绕过 llm-proxy)      │
│                                                      │
│  GEMINI_API_KEY 空时（fallback）：                    │
│    → LLMClient (httpx) → llm-proxy:8100              │
│      → vecto/vecto2/aiberm (中转链)                   │
│                                                      │
│  其他 slot（ai-chat/agent 等）：                      │
│    仍走 llm-proxy，未改动                              │
└──────────────────────────────────────────────────────┘
```

- `.env` 已配 `GEMINI_API_KEY=AIzaSy...` + `GEMINI_MODEL=gemini-3-flash-preview`
- **两个模式都走官方直连**，区别在于：实时 = 标准计费 ~2分/份，经济(batch) = Batch API 半价 ~1分/份
- Batch API 的异步提交/轮询逻辑在 `gemini_client.py` 中已实现但 **worker 尚未实际走 Batch API 路径**——当前 batch 模式和 realtime 模式都是逐份实时调用，只是计费入口不同。真正的 Batch API 集成（提交 JSONL → 轮询 → 取结果）是后续优化项

### AI 阅卷 Pipeline
```
OCR (extract_text) → 文本评分 (grade_text) — 两步不可合并（用户铁律）
```
- `gemini_client.py`: Gemini 官方 SDK 客户端，支持 Context Caching
- `image_utils.py`: 图片缩放 max 768px（1 tile = 258 tokens）
- `detail_flatten.py`: LLM 嵌套输出→扁平逐空格式 + 术语净化（judgingRules→评分标准）
- `llm_client.py`: 原 httpx 代理客户端（GradeResponse 已扩展全字段）
- `scorer.py`: `_build_ai_info()` 统一 3 条读取路径的 AI 信息构建

### 前端
- `GradingPanel.vue`: 新增"实时模式/经济模式" radio group
- `AiGradingPage.vue`: 传递 mode 参数到 `/api/v1/grading/tasks`
- 已 `vite build`，线上可用 `https://mcu.asia`

### 条码识别
根因：扫描图 2481×1754 vs 模板 3307×2338，crop 坐标未按 0.75 缩放→裁切偏移→条码截断。
修复后：生物 100%、地理 100%、语文 99.4%（11 张条码被手写污损，极端 edge case）。
**但数据库中的旧数据（student_answers）还是错的——589+634 个假 student_id 没清理。** 需要用户决定是否重新跑 pipeline。

## Must Preserve

1. **两步 pipeline 不可合并**（OCR → 评分，用户明确禁止单步）
2. **GEMINI_API_KEY 优先级**：有值→官方直连，空→llm-proxy fallback（两条路都必须保留）
3. **阅卷质量不能降**：逐空评分 + reason + deductions + comment 全保留
4. **条码识别四层保障**：缩放→多策略重试→全图 fallback→格式校验

## Must Not Change

1. llm-proxy 的其他 slot（ai-chat/agent-reasoning 等）不动
2. `GradingResult` 的状态机（ai_pending→ai_done→confirmed）不动
3. 人工阅卷队列顺序（student_id ASC）不动
4. 已有的成功条码识别结果不动

## 待办（按优先级）

### P0 — 用户可能立即要求

1. **重新扫描/清理假数据**：生物 589 + 地理 634 个假 student_id 的 student_answers 需要清理或重跑 pipeline。等用户指令，不要自行操作
2. **前端 rubric 批量生成**：生物 5 题已有图片（content_images + reference_answer_images），rubric 生成校验已修复（`6f86a71`），可以重试
3. **arq worker 启动**：批量阅卷需要 arq worker 运行。Python 3.14 需要 monkey-patch `asyncio.get_event_loop()`，启动脚本见之前会话的 handoff（`docs/plans/2026-04-28-ai-grading-result-display-handoff.md`）

### P1 — 后续优化

4. **真正的 Batch API 集成**：当前 batch 模式仍是逐份调用，应改为 JSONL 批量提交→轮询→取结果，实现半价计费
5. **Context Caching 接入**：`gemini_client.py` 有 `_get_or_create_cache` 实现，但未在 worker 中调用（rubric+prompt 模板可缓存，省 ~80% 输入费）
6. **语文 11 张污损条码**：可用 OCR 读条码下方的数字文本作为终极 fallback（0.6% edge case）

### P2 — 技术债

7. **pipeline_router.py 有子代理遗留改动**（git diff 显示 `SubjectStatusCard.vue` + `pipeline_router.py` 未提交），需审查是否合理
8. **8 位误读过滤**：`_infer_barcode_pattern` 会在实际 pipeline 运行时自动过滤，但预扫描结果中 84 个 8 位读数仍在 mapping 中（不影响功能，pipeline 运行时的格式校验会拦截）

## 成本数据（实测）

| 指标 | 值 |
|------|-----|
| 模型 | gemini-3-flash-preview |
| OCR input | 1228 tokens (含 258 图片) |
| OCR output | 151 tokens |
| 评分 input | 769 tokens |
| 评分 output | 468 tokens |
| 实时模式 | 2.07 分/份 |
| 经济模式(Batch) | 1.04 分/份（理论，需 P1-4 落地） |
| 速度(官方直连) | ~6.7s/份（代理 30-98s） |

## 文件索引

| 文件 | 职责 |
|------|------|
| `src/edu_cloud/modules/grading/gemini_client.py` | Gemini 官方 SDK 客户端 |
| `src/edu_cloud/modules/grading/image_utils.py` | 图片预处理 max 768px |
| `src/edu_cloud/modules/grading/detail_flatten.py` | LLM 输出标准化 |
| `src/edu_cloud/modules/grading/llm_client.py` | httpx 代理客户端（fallback） |
| `src/edu_cloud/modules/grading/router.py` | grade-single + tasks API |
| `src/edu_cloud/modules/marking/scorer.py` | _build_ai_info 统一读取 |
| `src/edu_cloud/workers/grading.py` | 批量阅卷 worker |
| `src/edu_cloud/modules/scan/vision/barcode.py` | 条码识别（增强版） |
| `src/edu_cloud/modules/scan/pipeline_service.py` | 扫描切割 pipeline |
| `frontend/src/pages/ai-grading/GradingPanel.vue` | 模式选择器 UI |
