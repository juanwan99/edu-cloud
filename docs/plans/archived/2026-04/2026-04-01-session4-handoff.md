---
type: handoff
created: 2026-04-01 16:22:09
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-03-29-business-logic-backfill-design.md
---

# 项目总规划师交接卡 — Session 4 → Session 5

## 已完成（本会话）

| 工作 | 级别 | 状态 | Commits |
|------|------|------|---------|
| Phase 2.3 examids 统一 | T2 | 完成，t2-review PASS | bbba5db |
| CLAUDE.md 全面更新 | — | 完成 | 6e254bf |
| 前端启动修复（7 项） | T1 | 完成 | 8aa42e9 |

### 前端修复明细（8aa42e9）

| 问题 | 根因 | 修复 |
|------|------|------|
| 答题卡预览只有纯文本无排版 | `public/card-editor/styles.css` platform-merge 遗漏 | 从 exam-ai 复制 977 行 CSS |
| ExamDetailPage useDialog() 崩溃 | App.vue 缺少 NDialogProvider | 添加包裹 |
| Vue Router 重复 key 警告 | sidebarConfig 多功能项共用 `/analysis` 占位路由 | 各功能用独立路由（/studio /calendar /notifications /paper /settings） |
| Vue Router "No match" 警告 | 5 个侧栏路由未在 router 注册 | 注册占位路由 |
| Vite 5173 端口 EACCES | Hyper-V 排除范围 5147-5246 | 改为 5273 |
| 种子数据不完整（空考试） | seed_school 只建组织架构不建考试 | app.py lifespan 接入 seed_demo（育才实验中学） |
| seed_demo CLASS_PROFILES KeyError | 育才 36 班超出 4 班 profile 定义 | `.get()` fallback |

## 当前状态快照（2026-04-01 16:22）

- **分支**: master
- **测试**: ~1043 后端 + 68 前端
- **表**: 51 / **路由**: 152 / **AI 工具**: 39 / **权限**: 25 / **角色**: 8
- **种子数据**: 育才实验中学（YCSY2026）— 36 班 / 1500 学生 / 200 教师 / 2 次考试（期中+月考，各 3 科）
- **登录账号**: `admin_principal_1` / `123456`（校长，王建国）
- **前端端口**: 5273（Vite dev server）

## 路线图

```
Phase 1: 数据基底 + 权限引擎 + Agent 基础设施  ← 100% 完成
Phase 1e: 常驻巡检 Agent                       ← 未开始（T3）
Phase 2: 核心流程层                              ← 100% 完成
Phase 3: 价值输出层                              ← 70% 完成
  ├── 3.1 学情分析      ✅
  ├── 3.2 考后流水线    ✅
  └── 3.3 分析报告      ← 未开始（T3）
Phase 4: 高级功能层                              ← 未开始
```

## 下一步：答题卡制作工具攻关

### 背景

答题卡制作工具从 exam-ai 迁入时代码 100% 一致（74959 行），但存在以下问题：

1. **样式遗漏已修复**: `public/card-editor/styles.css` 已补回（本会话）
2. **用户反馈"完全没法用"**: 需要实际操作验证完整流程（选科目→配置→预览→导出 PDF）
3. **后端依赖**: 答题卡 PDF 导出需要 Playwright Chromium（Docker 部署时已内置，本地开发需确认）

### 已知答题卡相关端点

```
POST /api/v1/card/parse-answers         — 答案解析（图片上传）
POST /api/v1/card/barcode               — 条码生成
POST /api/v1/card/preview-by-weights    — 权重预览
POST /api/v1/card/export/pdf            — PDF 导出（需 Playwright）
POST /api/v1/card/export/skeleton       — Skeleton JSON 导出
GET  /api/v1/card/tql-reference/{id}    — TQL 模板对照
GET  /api/v1/card/editor-layout/{id}    — 编辑器布局加载
PUT  /api/v1/card/editor-layout/{id}    — 编辑器布局保存
```

### 关键文件

| 文件 | 位置 | 说明 |
|------|------|------|
| CardEditor.vue | `frontend/src/components/CardEditor.vue` | 674 行，可视化编辑器组件 |
| ExamDetailPage.vue | `frontend/src/pages/ExamDetailPage.vue` | 812 行，考试详情（含答题卡 tab） |
| card-editor/ | `frontend/src/card-editor/` | 5 原生 JS 模块（model/render/interact/panel/export） |
| styles.css | `frontend/public/card-editor/styles.css` | 977 行，渲染样式（本会话补回） |
| cards.py | `src/edu_cloud/modules/card/` | 后端答题卡路由+服务 |

### 建议攻关步骤

1. **端到端验证**: 用 `admin_principal_1` 登录，选期中考试→答题卡制作→选语文→走完整流程
2. **识别断点**: 哪些操作失败（预览？PDF 导出？答案解析？条码？）
3. **逐个修复**: 按用户实际使用路径修复
4. **PDF 导出**: 确认本地 Playwright 可用性（`python -m playwright install chromium`）

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-01 16:22:09
项目: C:\Users\Administrator\edu-cloud  读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-01-session4-handoff.md 了解上下文。重点攻关答题卡制作工具——端到端验证并修复所有断点。先启动前后端（后端 port 9000，前端 port 5273），用 admin_principal_1/123456 登录，选 2026年春季期中考试→答题卡制作→完整操作流程，记录每个失败点并修复。
```
