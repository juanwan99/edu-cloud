# Navigation Back Button — Startup Prompt

## 问题

前端页面缺少"返回上一级"按钮，用户进入子页面后无法方便地返回。

## 导航层级（已调查）

```
Dashboard (/)
├── ExamList (/exams) ← 一级，无需返回
│   ├── ExamDetail (/exams/:id) ← ❌ 需加返回 → /exams
│   │   └── CardEditorDev (/card-dev/:examId) ← ❌ 需加返回 → /exams/:id
├── AI 阅卷 (/grading/tasks) ← 一级，无需返回
│   ├── GradingResults (/grading/tasks/:id) ← ❌ 需加返回 → /grading/tasks
│   └── AiGrading (/exams/:examId/ai-grading/:subjectId) ← ✅ 已有
├── 阅卷 (/marking) ← 一级，无需返回
│   ├── ReviewPage (/marking/grade/:questionId) ← ✅ 已有
│   ├── MarkingAssign (/marking/assign) ← ❌ 需加返回 → /marking
│   └── MarkingProgress (/marking/progress) ← ❌ 需加返回 → /marking
├── conduct/* ← 德育模块内页 → /conduct/dashboard
└── analytics/* ← 分析模块内页互返
```

## 必须改的文件（按优先级）

| 文件 | 返回目标 | 改法 |
|------|---------|------|
| `frontend/src/pages/ExamDetailPage.vue` | `/exams` | 页面顶部加返回按钮 |
| `frontend/src/pages/CardEditorDevPage.vue` | `/exams/:examId`（从 route params 取） | 同上 |
| `frontend/src/pages/GradingResultsPage.vue` | `/grading/tasks` | 同上 |
| `frontend/src/pages/MarkingAssignPage.vue` | `/marking` | 同上 |
| `frontend/src/pages/MarkingProgressPage.vue` | `/marking` | 同上 |

## 可选改（改善体验但不紧急）

| 文件 | 返回目标 |
|------|---------|
| `frontend/src/pages/AnalyticsReportPage.vue` | `/analytics` |
| `frontend/src/pages/AnalyticsTrendPage.vue` | `/analytics` |
| conduct 模块 8 个子页面 | `/conduct/dashboard` |

## 不需改

- 一级导航页（Dashboard / ExamList / GradingDispatch / MarkingSelect 等）— 侧边栏直达
- 已有返回的页面（ReviewPage / AiGradingPage / KnowledgeTreePage）
- 家长端 — 底部 Tab 导航

## 实现规范

参考已有实现（AiGradingPage.vue line 4）:
```vue
<n-button text @click="$router.push('/exams')">← 返回考试列表</n-button>
```

统一用明确路径（不用 router.back()），避免用户从外部链接进入时 back() 跳出应用。

## 风险点

1. ExamDetailPage 很大（约 980 行），只加返回按钮不碰其他逻辑
2. CardEditorDevPage 需从 route.params.examId 构造返回路径
3. router.test.js 检查路由数量（17），不会变（不加新路由）

## 验证方式

- `cd frontend && npx vitest run` 全量通过
- `cd frontend && npx vite build` 无报错
- 浏览器验证每个改过的页面点返回按钮到达正确目标
