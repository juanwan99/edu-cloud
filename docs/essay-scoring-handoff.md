# 作文评分优化交接文档

> 2026-05-04 | 14轮迭代 | 盲测已跑 | DeepSeek v4-flash 主评

## Goal

在 46 篇调参集上找到最优合成方案，在 50 篇新数据上盲测验证。

## Must Preserve

1. **3 锚对比 prompt**（score 0-42, above_boundary）—— 已验证有效，v7 融合实验证明不能替换
2. **5 锚 confirm prompt**（逐级比较）—— s1>=39 触发
3. **最终合成公式**（见下方 §3）
4. 锚点样本 5 篇（250136/250115/250112/250108/250101）在 `data/essay_51_test_input.json`

## Must Not Change

- 不能把整体印象定档法替代锚点对比法（v7 实验 MAE=3.15 失败）
- 不能按官方评分标准逐条检查（用户测试过，DS 缺乏整体感知）
- 不能用同一批 46 篇继续调参（过拟合警告）

---

## 1. 当前最优方案（冻结）

### 流程

```
字数 cap → Call 1 (3锚, score 0-42) → s1>=39 触发 Call 2 (5锚) → 合成公式 → 字数 cap 兜底
```

### 合成公式

```python
def synthesize_final(s1, s2):
    if s1 < 39: return s1
    if s1 == 39: return 39  # 不升
    # s1 >= 40
    if s2 is None or s2 < 40: return 39  # s2 否决
    if s1 == 40:
        if s2 <= 43: return 40  # 确认
        if s2 <= 45: return 41  # 强确认
        return 42               # 极强确认
    # s1 >= 41
    if s2 <= 45: return min(s1, 42)
    return min(s1 + 1, 42)
```

### 字数 cap（count_essay_chars 口径，含 OCR 补偿 ×1.08）

```python
CHAR_CAPS = [(20, 0), (150, 8), (200, 8), (350, 22), (450, 28), (500, 34)]
```

<500→34 来自官方评分标准四等上限（"不足500字"→30-34 分）。

---

## 2. 盲测结果（2026-05-04 23:36）

50 篇新作文，完整 OCR→评分 pipeline。

### OCR 正常样本（39 篇，字数>=400）

| 指标 | 目标 | 结果 |
|------|------|------|
| MAE | ≤2.6 | **2.21** ✓ |
| +-3 | ≥85% | 82% (接近) |
| >=5 | ≤10% | 8% (3/39) ✓ |
| 高分召回 | ≥40% | **80%** ✓ |
| bias | ~0 | **-0.05** ✓ |

分段：合格(36-39) MAE=2.00 | 较好(40-42) MAE=1.45 | 优秀(43+) MAE=4.00

### >=5 偏差（3 篇）

- 250513（人工33, final=40, +7）—— DS 给太高，可能人工偏低
- 252336（人工40, final=32, -8）—— DS 给太低
- 251836（人工46, final=41, -5）—— 42 分天花板限制（待调查 §5.2）

### OCR 异常样本（10 篇，字数<400）

全部被字数 cap 拦住（cap 22），人工分 37-42。根因：Gemini OCR 对双页拼接大图丢字严重（待调查 §5.1）。

### 日志

- 结果：`data/essay_blind_test_20260504_233615.json`
- JSONL 日志：`logs/essay_blind_test_20260504_233615.jsonl`

---

## 3. 迭代历史（14 轮）

| 版本 | 方案 | 全局MAE | 合格段 | 较好段 | 说明 |
|------|------|---------|--------|--------|------|
| v3.1 | 3锚+字数+Gemini复核 | 2.85 | 1.54 | 3.25 | 早期基线 |
| v5.3-A | 3锚+5锚简单平均 | 2.91 | 2.88 | 1.75 | s2 高分倾向污染 |
| v6-confirm | 3锚+5锚保守确认 | 2.52 | 2.23 | 1.50 | s2 做确认不平均 |
| v7-fusion | 整体定档+锚点校准 | 3.15 | 2.96 | 1.88 | **失败**：DS 无稳定尺度 |
| v8A-strict | v6+strict confirm | 2.37 | 2.08 | 1.75 | s1=39 需 s2>=42 |
| v8B-core | 更严格高分边界 | 2.11 | 1.50 | 2.00 | 召回 20% 太低 |
| **最终推荐** | v8B底座+40边界校准 | **2.30** | **1.96** | **1.75** | 召回 40%，bias+0.78 |
| **盲测(OCR正常)** | 同上 | **2.21** | **2.00** | **1.45** | bias -0.05，无过拟合 |

### GPT（Codex）参与的 4 轮决策

1. 7 篇争议作文独立评分 → 确认 3 篇人工问题 + 2 篇 AI 问题 + 2 篇波动
2. v7 融合方案设计 → 推荐 A+B 融合（实验失败后回退）
3. v8A/v8B 对比 → 推荐 v8B-core 为底座
4. 最终方案选择 → 推荐"D方案：v8B-core + s1=40/s2>=40 保持 40 + guard shadow"

---

## 4. 关键发现（跨版本稳定）

### DS 能力边界

- 35-42 区间精确排序粒度约 5 分
- 无法识别"结尾否定主题"（250104 类）
- 无法识别"未写完"（250120 类）
- 高情绪叙事容易高估
- OCR 噪声重时波动大（4次跑全距最大 10 分）
- temperature=0 单次偏移均值 1.57，26% 偏移>=3

### 人工评分审计

- 89% 符合官方标准
- 250142（人工45）最大违规：缺"重拾"过程给一等
- 字数<500 人工偏低（给五等，标准说应四等 30-34）

### 过拟合教训

- 分布限制（"37-39占60%"）= 过拟合
- 门控阈值（base>=36 才进门控）= 拿人工标签调的
- v4.1 M2 默认指令 = 过拟合
- **生产能用的只有：锚点样本、字数门控、prompt 方法论、合成公式的结构性阈值**

---

## 5. 待调查（下个会话）

### 5.1 OCR 丢字问题

**现象**：50 篇盲测中 10 篇（20%）OCR 字数<400，人工分 37-42 说明原文正常。

**根因线索**：Q23.jpg 是左右两页拼接大图（~1.3MB）。OCR 正常的和异常的图片格式相同，差异可能在：
- 手写字体清晰度
- Gemini 对大图的处理（可能只读了部分区域）

**验证方向**：
1. 把 Q23.jpg 切成左右两半分别 OCR，对比字数
2. 降低 Gemini temperature / 增加 maxOutputTokens
3. 在 prompt 里强调"图片包含左右两页，请完整识别"
4. 对比生产 pipeline 的 OCR 方式（两步：先 Gemini OCR 再 DS 评分）

**影响**：如果 20% 的 OCR 丢字率在生产中也存在，MAE 会从 2.21 恶化到 4.59。

### 5.2 42 分天花板

**现象**：251836（人工46, s1=41, final=41, -5）被天花板限制。

**分析**：3 锚 prompt 最高只能给 42（above_boundary=true 标记但不直接加分）。盲测中 4 篇优秀段 MAE=4.00，主要因此。

**权衡**：
- 放开天花板（允许 43+）→ 会让更多普通文被错升（v7 教训）
- 保持 42 天花板 → 优秀段少数几篇会被压
- 中间方案：above_boundary=true 且 s2>=45 时允许 final=43（只放一分）

**建议**：不急于改，等更多优秀段样本（目前只有 4 篇）再决定。

---

## 6. 关键文件

| 文件 | 说明 |
|------|------|
| `data/essay_51_test_input.json` | 51篇调参集（含 OCR 文本+人工分+锚点） |
| `data/essay_blind_test_20260504_233615.json` | 盲测结果（50篇） |
| `data/essay_v53_results.json` | v5.3 三方案 s1/s2 数据（离线模拟用） |
| `data/essay_s1_stability.json` | s1 稳定性测试（4次跑数据） |
| `logs/essay_blind_test_20260504_233615.jsonl` | 盲测 JSONL 日志 |
| `scripts/essay_blind_test.py` | 盲测脚本（从 OCR 开始完整 pipeline） |
| `scripts/essay_v8b_offline.py` | v8A/v8B 离线对比脚本 |
| `scripts/essay_v6_offline_sim.py` | v6 离线模拟脚本 |
| `scripts/essay_v7_fusion.py` | v7 融合版（已失败） |
| `src/edu_cloud/modules/grading/prompts/chinese.py` | 生产评分 prompt |
| `src/edu_cloud/modules/grading/prompts/base.py` | count_essay_chars 函数 |
| `src/edu_cloud/workers/grading.py` | 生产阅卷 pipeline |
| `src/edu_cloud/modules/grading/rubric_formatter.py` | 锚点格式化 |
| `/home/ops/data/exam-comparison/景炎/01_语文.xlsx` | 人工成绩（col 68 作文分） |

## 7. 数据源映射

```
xlsx 学号(25xxxx) = student_answers.student_id = storage 子目录名
作文切图: storage/{school_id}/{exam_id}/{subject_id}/{student_id}/Q23.jpg
question_id: 1ef2a5ba-561a-45bb-8655-c43c75267f47 (name=23, max=50)
exam_id: 796f7c26-77d6-4606-ba42-a1c2de2aa4f7
db: /home/ops/projects/edu-cloud/edu_cloud.db (SQLite)
可用盲测样本: 1290 篇（排除已有 51 篇）
```

## 8. 生产落地改动（2026-05-05 已实现）

### 已完成

| 文件 | 改动 | 状态 |
|------|------|------|
| `workers/grading.py` | 新字数 cap 6 档 + `_synthesize_essay_score` 合成公式 + essay_anchor pipeline（OCR→3锚→5锚confirm→合成→cap） | ✅ 已实现+单元测试 |
| `modules/grading/gemini_client.py` | `extract_essay_text` 方法（跳过 resize + maxOutputTokens=8192）+ `extract_text` 增加 `skip_resize`/`max_tokens` 参数 | ✅ 已实现 |
| `modules/grading/prompts/base.py` | `ESSAY_OCR_PROMPT`（纯文本 OCR，强调双页识别） | ✅ 已实现 |
| `modules/grading/rubric_formatter.py` | `split_essay_anchors` + `build_essay_anchor_prompt`（3锚/5锚 prompt 构建） | ✅ 已实现+单元测试 |
| `frontend/.../GradingPanel.vue` | 锚点从 3 档扩展到 5 档（优秀46/良好43/中等42/合格38/偏弱35） | ✅ 已实现 |

### 验证结果

- Worker 测试：20 passed（0 新增 failure）
- 合成公式与盲测 48 篇结果完全匹配（0 mismatch）
- Grading API 测试：34 passed（2 known failures，非本次引入）

### 激活条件

essay_anchor pipeline 自动激活，需满足：
1. `question_type == "essay"` 且 `max_score >= 40`
2. rubric criteria 中有 `essayAnchors` 且至少 3 个有 summary
3. 使用 Gemini 官方 API（`use_gemini_official=True`）

不满足以上任一条件时，fallback 到原有的整体印象定档法。

### OCR 丢字根因与修复

**根因**：生产 OCR 对双页拼接作文图片（~3000×2000px）做 resize 到 768px，手写字变成 ~5px 高无法辨认。加上 maxOutputTokens=2048 对长文不够。

**修复**：
- 作文 OCR 跳过 resize，发送原图（`extract_essay_text`）
- maxOutputTokens 提高到 8192
- 专用纯文本 prompt（避免 JSON 结构浪费 token）

### 待验证（用户操作）

1. 在 AI 阅卷页面为作文题配置 5 个锚点样本（至少填 3 个：42/38/35 分）
2. 跑一批真实作文验证 OCR 字数是否恢复正常（预期字数 >500）
3. 验证评分 MAE 与盲测一致（≤2.6）

## 9. 官方评分标准（参考，不注入 prompt）

一等(45-50)：紧扣重拾核心 + 真情实感 + 较强感染力 + 语言流畅
二等(40-44)：符合题目要求 + 内容具体 + 比较有感染力
三等(35-39)：符合题目要求 + 有中心 + 语言基本通顺
四等(30-34)：语病5句以上 / 内容空泛 / 层次不清 / 不足500字
五等(0-29)：文不对题 / 观点错误 / 文理不通 / 抄袭

用户已测试：直接喂给 DS 效果反而差。当前方案通过锚点隐式传递尺度，不用显式标准。
