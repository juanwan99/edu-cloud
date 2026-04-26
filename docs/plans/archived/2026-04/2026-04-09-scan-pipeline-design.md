# 试卷全链路打通 — exam-ai 兼容层设计

> [2026-04-09 12:57:51 实现完成] Commits: f7ea5a1..8184e79
> 状态：实现完成 | 创建：2026-04-09

## §0 背景

edu-cloud 已整合答题卡编辑器、扫描接收、AI 阅卷、教师审核、成绩发布全部模块。paper-seg 是学校端扫描客户端，通过 `ExamAIClient`（httpx）调用服务端 API。

当前 paper-seg 硬编码连接 exam-ai（已弃用），API 路径前缀为 `/api/`。edu-cloud 的等价端点在 `/api/v1/`。两个系统的数据模型和字段名已对齐，只差路由层的桥接。

**目标**：在 edu-cloud 内新增一组 exam-ai 兼容路由（`/api/` 前缀），paper-seg 只需把服务器地址从 `localhost:8000` 改为 `localhost:9000`，零代码改动即可完成全链路对接。

## §1 兼容路由清单

在 `src/edu_cloud/api/compat_router.py` 新建路由，挂载到 `/api`（无 `/v1`）。

| paper-seg 调用 | 兼容端点 | 实现方式 |
|---------------|---------|---------|
| `POST /api/auth/login` | 接受 `{school_code, username, password}`，忽略 `school_code`，转发到 edu-cloud 登录逻辑 | 直接复用 `auth.py` 的 `authenticate_user` |
| `GET /api/exams` | 查 Exam 表，按 JWT school_id 过滤 | 直接查库 |
| `GET /api/exams/{id}/subjects` | 查 Subject 表 | 直接查库 |
| `GET /api/templates/{subject_id}/{side}` | 查 Template 表，返回 paper-seg 兼容 JSON | 包装 `_template_response` + `image_size` 字段 |
| `POST /api/scan/tasks` | 创建 ScanTask | 转发到 scan 模块 |
| `POST /api/scan/upload` | Multipart 接收切图 | 转发到 scan upload_single |
| `POST /api/scan/upload-objective` | JSON 接收选择题结果 | 转发到 scan upload_objective |
| `PATCH /api/scan/tasks/{id}` | 更新扫描进度 | 转发到 scan update_task |

### §1.1 登录兼容

paper-seg 发送：
```json
{"school_code": "YCSY2026", "username": "admin_principal_1", "password": "123456"}
```

兼容端点：忽略 `school_code`，用 `username + password` 走 edu-cloud 标准登录，返回 `{"access_token": "..."}` 格式。

### §1.2 模板格式兼容

paper-seg 期望的模板响应：
```json
{
  "id": "...",
  "subject_id": "...",
  "side": "A",
  "image_size": {"width": 3308, "height": 2308},
  "anchors": [{"id": "TL", "cx": 102, "cy": 97, ...}],
  "regions": [{"id": "Q01", "type": "subjective", "rect": {...}, "question_id": "..."}]
}
```

edu-cloud Template 表已有 `image_width/height/anchors/regions` 字段。兼容端点需要：
- 将 `image_width/image_height` 包装为 `image_size: {width, height}`
- 其余字段直接透传

### §1.3 切图上传兼容

paper-seg 发送 Multipart：
```
exam_id: "uuid"
subject_id: "uuid"
student_id: "20230101"
question_id: "uuid"
image: <binary PNG>
```

edu-cloud `/api/v1/scan/upload` 接受完全相同的字段名。兼容端点直接转发。

### §1.4 选择题上传兼容

paper-seg 发送 JSON：
```json
{
  "exam_id": "uuid",
  "subject_id": "uuid",
  "student_id": "20230101",
  "is_absent": false,
  "answers": [{"question_id": "uuid", "detected_answer": "A", "fill_ratios": {...}, "anomaly": false}]
}
```

edu-cloud `UploadObjectiveRequest` 完全匹配。兼容端点直接转发。

## §2 发布流程增强

### §2.1 现有 publish 端点修改

当前 `POST /api/v1/card/publish` 的问题：
1. `exam.status` 检查 `!= "draft"` 就拒绝 → 改为允许 `draft` 或 `scanning`（支持重新发布）
2. 发布时强制设 `exam.status = "scanning"` → 改为仅当 `draft` 时设为 `scanning`，`scanning` 状态保持不变
3. PDF 只返回不持久化 → 增加持久化到 storage（可选，供打印下载）

### §2.2 Question→Region 映射

发布时 `question_map = {q.name: q.id}`，将题号映射到 question_id 写入 regions。这要求 Question 已经创建且 `name` 与编辑器里的题号一致（如 "17"）。

目前 "小微排版" 上传答案时会自动创建 Question（`parse-answers` 端点）。所以正确的用户流程是：
1. 上传答案 → 自动创建 Question
2. 在编辑器里排版
3. 点"发布答题卡" → Question name 映射到 region

## §3 数据流总览

```
                    edu-cloud (port 9000)
┌─────────────────────────────────────────────────────┐
│                                                     │
│  [答题卡编辑器]                                       │
│       │                                             │
│       ▼ POST /api/v1/card/publish                   │
│  [Template 表]  ←── anchors + regions + question_id │
│       │                                             │
│       ▼ GET /api/templates/{sid}/{side}              │
│  ─────┼──────────────────────────────── 兼容层 ──── │
│       │                                             │
└───────┼─────────────────────────────────────────────┘
        │
        ▼
   [paper-seg] (port 8001)
        │
        ├─ 拉模板 → 定位点检测 → 仿射校正 → 区域裁切
        │
        ├─ POST /api/scan/upload         → [StudentAnswer 表]
        ├─ POST /api/scan/upload-objective → [StudentAnswer 表]
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  [AI 阅卷 Worker]                                    │
│       │ 读切图 → LLM 评分 → AIGradingResult          │
│       ▼                                             │
│  [教师审核] → [成绩发布] → EventBus pipeline         │
└─────────────────────────────────────────────────────┘
```

## §4 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/edu_cloud/api/compat_router.py` | 新建 | 兼容路由（8 个端点） |
| `src/edu_cloud/api/app.py` | 修改 | 注册 compat_router |
| `src/edu_cloud/modules/card/router.py` | 修改 | publish 端点放宽 status 检查 |
| `tests/test_api/test_compat.py` | 新建 | 兼容层测试 |

## §5 不做的事

- 不改 paper-seg 代码（用户手动改服务器地址即可）
- 不改 exam-ai 代码（已弃用）
- 不新增模板推送/通知机制（paper-seg 主动拉取即可）
- 不改已有的 `/api/v1/` 端点（兼容层是独立路由）

## §6 风险

| 风险 | 缓解 |
|------|------|
| paper-seg 期望的响应字段与兼容层不完全匹配 | 用 paper-seg 的 ExamAIClient 作为测试基准，逐个端点验证 |
| publish 生成的 regions 缺 question_id | 要求先上传答案创建 Question，再发布（前端可加校验提示） |
| 扫描大量图片时上传性能 | 已有重试机制，storage 用本地文件系统够用 |
