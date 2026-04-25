# AI 阅卷入口修复 — Startup Prompt

## 问题

侧边栏"AI 阅卷"指向 GradingDispatchPage（`/grading/tasks`），这是扫描切割调度页，不是 AI 阅卷。用户点进去看到的是扫描目录、模板检测、切割进度，不是 AI 阅卷功能。

## 现状

- `frontend/src/config/sidebarConfig.js`: `{ label: 'AI 阅卷', route: '/grading/tasks' }` → 指向 GradingDispatchPage
- `frontend/src/pages/GradingDispatchPage.vue`: 扫描调度页（选考试→显示科目扫描/切割/阅卷状态），标题被误改为"AI 阅卷"
- `frontend/src/pages/AiGradingPage.vue`: 真正的 AI 阅卷页（左右分栏：题目列表+内容编辑+AI评分细则+阅卷），路由 `/exams/:examId/ai-grading/:subjectId`，需要 examId+subjectId 参数

## 修复方案

### 1. AiGradingPage 增加考试/科目选择器

当前 AiGradingPage 从 route params 取 examId 和 subjectId。改为：
- 如果 URL 有 params → 直接加载（从 GradingDispatchPage 跳转过来的场景）
- 如果 URL 无 params → 页面顶部显示考试下拉框+科目下拉框，选完后加载

需要：
- 新增路由 `/ai-grading`（无 params），指向同一个 AiGradingPage
- AiGradingPage 内部判断：有 params 直接用，无 params 显示选择器
- 考试列表 API: `GET /exams`（已有）
- 科目列表 API: `GET /exams/{id}/subjects`（已有）

### 2. 侧边栏指向新路由

`sidebarConfig.js` 改为：`{ label: 'AI 阅卷', route: '/ai-grading' }`

### 3. GradingDispatchPage 恢复原名

- 页面标题改回"扫描调度"或"阅卷调度"
- 侧边栏可选是否保留这个入口（建议暂时保留在管理员角色下）

### 4. 路由注册

`router/index.js` 新增：
```javascript
{ path: 'ai-grading', name: 'AiGradingEntry', 
  component: () => import('../pages/AiGradingPage.vue'),
  meta: { roles: GRADING_DISPATCH_ROLES } },
```
原有路由保留：
```javascript
{ path: 'exams/:examId/ai-grading/:subjectId', name: 'AiGrading', ... }
```

## 关键文件

| 文件 | 改动 |
|------|------|
| `frontend/src/pages/AiGradingPage.vue` | 加考试/科目选择器（当 route params 缺失时） |
| `frontend/src/router/index.js` | 新增 `/ai-grading` 路由 |
| `frontend/src/config/sidebarConfig.js` | AI 阅卷 route 改为 `/ai-grading` |
| `frontend/src/pages/GradingDispatchPage.vue` | 标题改回"扫描调度" |

## 现有 AiGradingPage 结构（重要上下文）

- line 1-130: template（左右分栏）
- line 137: imports（getDispatchStatus, generateRubric, getRubric 等）
- line 140-150: route params 解构 `const examId = computed(() => route.params.examId)`
- line 155-190: onMounted 调 getDispatchStatus 加载科目题目列表
- line 196-208: selectQuestion 函数
- line 226-300: AI rubric 生成 + 阅卷任务创建 + 轮询

改动重点：line 140-190 区域，判断 params 存在性，缺失时渲染选择器。

## 风险点

1. AiGradingPage 两种入口模式（有 params / 无 params），确保切换考试/科目时状态正确重置
2. router.test.js 路由数量会从 17 变 18
3. GradingDispatchPage 标题改回后，其他引用"AI 阅卷"的文案检查
4. 前端 grading API 的 getDispatchStatus 需要 examId，确保选择器选完后才调用

## 验证

- `cd frontend && npx vitest run` 全量通过
- `cd frontend && npx vite build` 无报错
- 浏览器：侧边栏 AI 阅卷 → 选考试 → 选科目 → 看到题目列表+右侧操作区
- 浏览器：GradingDispatchPage 按钮"AI 阅卷"跳转仍正常
