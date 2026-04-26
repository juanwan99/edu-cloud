# AI 阅卷 B 端改造设计

> 基于 AI 阅卷助手插件 v2.2.8 的 C 端逻辑，适配 edu-cloud B 端全链路。

## 背景

现有 AI 阅卷流程是科目级批量操作：教务创建 GradingTask → 后台 worker 批量评分。缺少：
- 题目内容和参考答案存储（Question 表无题干/答案字段）
- AI 自动生成评分细则（Rubric 需手动填写）
- 题目级阅卷入口（只有科目级批量）
- 逐空评分明细（AI 只返回总分+评语）

改造后：教务/备课组长录入原题+答案 → AI 生成 Rubric → 教师确认/编辑 → 逐题或批量阅卷 → 逐空评分明细。

## 数据模型变更

### Question 表新增字段（Alembic migration）

| 字段 | 类型 | 说明 |
|------|------|------|
| `content` | Text, nullable | 题干文本 |
| `content_images` | JSON, nullable | 题干图片路径列表 |
| `reference_answer` | Text, nullable | 参考答案文本 |
| `reference_answer_images` | JSON, nullable | 参考答案图片路径列表 |

图片存储复用 UPLOAD_DIR 体系，路径格式 `/uploads/questions/{question_id}/{uuid}.png`。

### GradingTask 表新增字段（Alembic migration）

| 字段 | 类型 | 说明 |
|------|------|------|
| `question_id` | String(36), nullable | NULL = 科目级阅卷（现有行为），有值 = 题目级阅卷 |

### Rubric criteria 结构升级（JSON 字段内部，无 migration）

```
旧: [{point: str, score: float, description: str}]
新: [{blankNo: str, score: float, answer: str, intent: str, coreRequirement: str}]
```

- `blankNo`: 得分点编号（"1", "2", ...）
- `score`: 该得分点满分
- `answer`: 该得分点标准答案
- `intent`: 考查意图
- `coreRequirement`: 核心要求（学生必须答到什么程度才给分）
- 所有 `score` 之和 = Question.max_score

### 不变的表

- **GradingResult**: `ai_raw_response` (JSON) 天然支持存逐空明细，`ai_score` 存总分，`ai_feedback` 存评语
- **StudentAnswer**: 不变
- **Rubric**: 表结构不变，criteria 字段内部结构升级

## 后端 API 端点

### 新增端点

#### PUT `/api/v1/questions/{id}/content`

权限: MANAGE_EXAMS
用途: 更新题干和参考答案

请求体:
```json
{
  "content": "已知函数f(x)=...",
  "content_images": ["/uploads/questions/xxx/1.png"],
  "reference_answer": "解：由题意可知...",
  "reference_answer_images": ["/uploads/questions/xxx/2.png"]
}
```

#### POST `/api/v1/questions/{id}/content/upload-image`

权限: MANAGE_EXAMS
用途: 上传题目相关图片（Multipart）
返回: `{"path": "/uploads/questions/{question_id}/{uuid}.png"}`

存储路径: `{UPLOAD_DIR}/questions/{question_id}/{uuid}.{ext}`

#### POST `/api/v1/grading/rubrics/generate`

权限: VIEW_GRADING
用途: AI 生成评分细则

请求体:
```json
{
  "question_id": "uuid",
  "max_score": 12
}
```

流程:
1. 从 DB 读 Question 的 content/content_images + reference_answer/reference_answer_images
2. 校验: content 和 reference_answer 至少有一个非空
3. 组装 prompt 调 llm-proxy（含图片 base64）
4. 解析返回的结构化评分细则
5. Upsert 到 Rubric 表（source = "ai_generated"）
6. 返回生成的 criteria

返回:
```json
{
  "id": "rubric-uuid",
  "question_id": "uuid",
  "criteria": [
    {"blankNo": "1", "score": 4, "answer": "...", "intent": "...", "coreRequirement": "..."}
  ],
  "source": "ai_generated"
}
```

### 改动端点

#### POST `/api/v1/grading/tasks`

新增可选参数 `question_id`:
- 省略或 null: 科目级阅卷（现有行为不变）
- 有值: 题目级阅卷，只处理该题的 StudentAnswer

题目级前置校验:
1. Question 存在且属于该 subject
2. Question 是主观题（fill_blank 或 essay）
3. 该题有 Rubric
4. 该题有 StudentAnswer

#### POST `/api/v1/grading/rubrics`

criteria 字段适配新 5 字段结构。后端校验:
- 每个 item 必须有 blankNo, score, answer
- intent, coreRequirement 可选（手动录入时可省略，AI 生成时自动填充）
- 所有 score 之和 = Question.max_score

#### GET `/api/v1/grading/dispatch/status`

返回中新增每科的题目详情:
```json
{
  "subject_id": "...",
  "stage": "ready",
  "questions": [
    {
      "question_id": "...",
      "name": "第17题",
      "max_score": 4,
      "question_type": "essay",
      "has_content": true,
      "has_rubric": true,
      "answer_count": 368,
      "graded_count": 0
    }
  ]
}
```

### 权限对齐

`lesson_prep_leader` 新增权限（`core/permissions.py`）:
- `VIEW_GRADING` — 查看阅卷状态和结果
- `MANAGE_GRADING` — 创建阅卷任务、生成 Rubric、审核评分

与 `academic_director` 在阅卷方面权限一致。

## Worker 改造

### 题目级任务支持（`workers/grading.py`）

`process_grading_task` 判断 `task.question_id`:
- **为空**: 现有逻辑不变，加载全科主观题
- **有值**: 只加载该题的 Question + StudentAnswer + Rubric

### LLM Prompt 升级

评分 prompt（`grading/prompts.py`）要求 AI 返回逐空明细:

```
你是一位严谨的阅卷教师。根据评分细则对学生答案进行评分。

评分要求：
1. 逐个得分点评判，每个得分点独立给分
2. 得分点分值不可超过该点满分
3. 所有得分点分数之和为最终总分

返回 JSON 格式：
{
  "score": <总分>,
  "details": [
    {"blankNo": "1", "score": <得分>, "maxScore": <满分>, "reason": "<给分/扣分原因>"},
    ...
  ],
  "comment": "<整体评语，一句话>",
  "confidence": <0-1 置信度>
}
```

### Rubric 生成 Prompt（新增）

```
你是一位资深阅卷组长。根据以下原题和参考答案，拆分为逐空/逐得分点的评分细则。

【原题】
{content}

【参考答案】
{reference_answer}

【满分】{max_score}

要求：
1. 将答案拆分为独立的得分点，每个得分点有明确的判分标准
2. 所有得分点的分值之和必须等于满分
3. 每个得分点必须包含标准答案、考查意图、核心要求

返回 JSON 数组：
[
  {
    "blankNo": "1",
    "score": <分值>,
    "answer": "<该点标准答案>",
    "intent": "<考查意图>",
    "coreRequirement": "<核心要求，学生答到什么程度给分>"
  }
]
```

### 结果存储

`GradingResult` 字段映射:
- `ai_score` ← response.score（总分）
- `ai_feedback` ← response.comment（评语）
- `ai_confidence` ← response.confidence
- `ai_raw_response` ← 完整 response JSON（含 details 逐空明细）
- `final_score` ← response.score（初始等于 AI 分数，教师可覆盖）

## 前端设计

### 新增页面: AiGradingPage.vue

路由: `/exams/:examId/ai-grading/:subjectId`
入口: GradingDispatchPage 每科的"AI 阅卷"按钮
权限: VIEW_GRADING

左右分栏布局:

```
┌─ 顶栏 ─────────────────────────────────────────────┐
│ ← 返回调度中心    地理 · AI 阅卷    [批量阅卷全科]  │
├─ 左侧题目列表 (280px) ─┬─ 右侧详情面板 ────────────┤
│                         │                           │
│ ● 第17题 (4分) ✓✓      │ 【原题】                  │
│ ○ 第18题 (6分) ✓✗      │  文本 + 图片展示          │
│ ○ 第19题 (8分) ✗✗      │  [编辑]                   │
│                         │                           │
│ ✓✓ = 内容+Rubric就绪   │ 【参考答案】              │
│ ✓✗ = 有内容无Rubric     │  文本 + 图片展示          │
│ ✗✗ = 无内容             │  [编辑]                   │
│                         │                           │
│                         │ 【评分细则】              │
│                         │  空1: 4分 - 光合作用...   │
│                         │  空2: 2分 - CO₂转化...    │
│                         │  [AI 生成] [手动编辑]     │
│                         │                           │
│                         │ 【阅卷操作】              │
│                         │  待阅: 368份  已阅: 0份   │
│                         │  [开始阅卷本题]           │
│                         │  进度条 ████░░░░ 45%      │
│                         │                           │
├─────────────────────────┴───────────────────────────┤
│ 统计: 已阅 0/3题 | 总进度 0/1104份                   │
└─────────────────────────────────────────────────────┘
```

### 新增组件

#### QuestionContentModal.vue

编辑题干或参考答案的弹窗:
- NInput(type=textarea) 文本输入
- NUpload 多图上传（调 `/questions/{id}/content/upload-image`）
- 图片预览列表（支持删除、排序）
- 保存调 `PUT /questions/{id}/content`

#### RubricEditor.vue

评分细则展示与编辑:
- 列表展示每个得分点（blankNo / score / answer / intent / coreRequirement）
- 行内编辑模式（点击可修改）
- "AI 生成"按钮（调 `/grading/rubrics/generate`，loading 状态）
- 分值合计校验（实时显示总分 vs 满分，不等时警告）
- 保存调 `POST /grading/rubrics`

### API 层新增（`frontend/src/api/grading.js`）

```javascript
generateRubric(questionId, maxScore)   // POST /grading/rubrics/generate
updateQuestionContent(questionId, data) // PUT /questions/{id}/content
uploadQuestionImage(questionId, file)   // POST /questions/{id}/content/upload-image
```

### 路由注册

`router/index.js` 新增:
```javascript
{
  path: '/exams/:examId/ai-grading/:subjectId',
  name: 'AiGrading',
  component: () => import('../pages/AiGradingPage.vue'),
  meta: { permission: 'view_grading' }
}
```

## 测试策略

### 后端测试

| 测试文件 | 覆盖内容 |
|---------|---------|
| `test_api_exam/test_question_content.py` | Question content CRUD + 图片上传 |
| `test_api_exam/test_rubric_generate.py` | AI Rubric 生成端点（mock LLM） |
| `test_api_exam/test_grading_task_question.py` | 题目级 GradingTask 创建 + 前置校验 |
| `test_workers/test_grading_question.py` | 题目级 worker 分支 + 逐空明细解析 |
| `test_api/test_permissions_grading.py` | lesson_prep_leader 权限验证 |

### 前端测试

| 测试文件 | 覆盖内容 |
|---------|---------|
| `frontend/src/pages/__tests__/AiGradingPage.spec.js` | 页面挂载 + 题目选择 + 状态切换 |
| `frontend/src/components/__tests__/RubricEditor.spec.js` | 分值校验 + 编辑交互 |

## 明确排除

- **阅卷暂停/恢复**: 需 Redis 信号机制，复杂度高，后续迭代
- **统计面板**: 数据结构已支持（details 在 ai_raw_response），UI 后续迭代
- **自定义 API Key**: B 端统一走 llm-proxy
- **批量题目内容导入**: 首版手动录入，后续可加 Excel/Word 导入

## 变更清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `modules/exam/models.py` | 修改 | Question 加 4 字段 |
| `modules/grading/models.py` | 修改 | GradingTask 加 question_id |
| `alembic/versions/xxx.py` | 新增 | Migration: Question + GradingTask 字段 |
| `modules/exam/router.py` 或新文件 | 修改 | Question content 端点 |
| `modules/grading/router.py` | 修改 | Rubric generate + Task question_id 支持 |
| `modules/grading/prompts.py` | 修改 | 评分 prompt 升级 + Rubric 生成 prompt |
| `workers/grading.py` | 修改 | 题目级分支 + 逐空明细 |
| `core/permissions.py` | 修改 | lesson_prep_leader 权限 |
| `frontend/src/pages/AiGradingPage.vue` | 新增 | AI 阅卷页面 |
| `frontend/src/components/QuestionContentModal.vue` | 新增 | 题目内容编辑弹窗 |
| `frontend/src/components/RubricEditor.vue` | 新增 | 评分细则编辑器 |
| `frontend/src/api/grading.js` | 修改 | 新增 API 方法 |
| `frontend/src/router/index.js` | 修改 | 新增路由 |
