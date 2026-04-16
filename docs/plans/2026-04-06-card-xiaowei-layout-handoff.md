---
type: handoff
created: 2026-04-06 23:08:33
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-03-a4-card-editor-design.md
plan: null
---

# 小微答题卡智能排版 — 交接卡

## 当前状态

**代码已提交（cf9e2bc），功能完整但有 2 个未验证问题需要新窗口处理。**

### 已完成

1. **答案解析器** `src/edu_cloud/modules/card/answer_parser.py` — 解析 .docx 标准答案文件为结构化数据（已用 `D:\命题\2026一模\一模定稿\26年一模答案.docx` 验证，5 道大题全部正确解析）

2. **排版算法** `src/edu_cloud/ai/tools/card_layout.py` — 三个 Agent 工具：
   - `card_parse_answers`: 解析答案文件
   - `card_auto_layout`: 根据答案长度计算 heightRatio + blank 宽度(30%/48%/100%)，保存到编辑器布局
   - `card_adjust_layout`: 语义调整（resize/set_blank_width/balance）

3. **API 端点** `src/edu_cloud/modules/card/router.py`:
   - `POST /api/v1/card/upload-answer` — 上传 .docx 答案文件
   - `POST /api/v1/card/auto-layout/{subject_id}` — 解析+排版+保存一体化

4. **前端集成**:
   - `ExamDetailPage.vue` 工具栏"小微排版"按钮 — 选文件→上传→排版→刷新编辑器
   - `CardEditor.vue` `applyAutoLayout()` 方法 — 接收排版结果更新 layout regions

5. **排版数据已保存** — 生物科目（subject_id=`e1cc167b-d148-4cd4-8f3b-56db078a876f`）的排版已写入 `src/editor_layouts/31c17116..._e1cc167b...json`

### 未验证问题（需要新窗口处理）

**问题 1: PDF 导出 500 错误**
- 症状：前端点"导出 PDF"报 500
- 根因：`html_export.py` 的 `asyncio.Lock` 在 uvicorn `--reload` 后事件循环失配
- 已修复：改为延迟创建 Lock（`if _lock is None: _lock = asyncio.Lock()`）
- 状态：**代码已修复并提交，但后端需要重启才能生效**，重启后需验证 PDF 导出是否正常

**问题 2: 排版效果视觉验证**
- 排版数据已保存到正确的 subject_id，但用户尚未看到最终渲染效果
- 需要：重启后端 → 刷新浏览器 → 进入 `http://localhost:5273/exams/80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c` → 可视化编辑 → 选生物 → 查看效果
- 如果排版不理想（空间分配不合理、空宽度不对），需要调整 `calculate_layout()` 的参数

## 约束与偏好

**Tier: T2 流程**（验证+修复，不涉及架构变更）

- 用户是非开发者，需要直接看到可视化效果
- 后端启动命令：`cd C:\Users\Administrator\edu-cloud && python ~/.claude/scripts/serve.py python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 --reload`（后台运行）
- 前端已在运行：`http://localhost:5273`
- 测试答案文件：`D:\命题\2026一模\一模定稿\26年一模答案.docx`（生物 5 道大题 17-21）
- 答题卡编辑器代码在 `frontend/src/card-editor/`（5 模块：model/render/interact/panel/export）
- 排版算法的核心逻辑：按答案文本长度选空宽度 → 按预估行数等比分配 heightRatio
- 用户期望：排版后每道题空间合理、填满页面、不留大面积空白、空宽度匹配实际答案长度

## 启动 Prompt

```
[edu-cloud] 小微排版验证 | {timestamp}
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-06-card-xiaowei-layout-handoff.md 了解上下文。

任务：
1. 重启后端（端口 9000），确认 PDF 导出 500 错误已修复
2. 验证生物答题卡排版效果：打开 http://localhost:5273/exams/80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c → 可视化编辑 → 选生物，确认排版数据已加载（5 道题 heightRatio 不同）
3. 导出 PDF 验证渲染效果，如有问题修复
4. 如果排版效果不理想，调整 C:\Users\Administrator\edu-cloud\src\edu_cloud\ai\tools\card_layout.py 的 calculate_layout() 参数
```
