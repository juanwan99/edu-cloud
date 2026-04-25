---
topic: analytics-deep-T5-frontend
tier: T2
handoff_type: executor
created: "2026-04-25 13:30:00"
blocked_by: [T1, T2, T3, T4]
blocks: [T6]
---

=== 生成块开始 ===

# T5 前端 analytics 页面填充（修正版）— 执行交接卡

**关键纠正**: 在 `frontend/`（主前端，mcu.asia 生产在用）中工作，**不碰 `frontend-nuxt/`**。

**现有资产盘点**:
- `pages/AnalyticsPage.vue` (209行) — 成绩分析主页
- `pages/AnalyticsReportPage.vue` (225行) — 分析报告
- `pages/AnalyticsTrendPage.vue` (154行) — 趋势分析
- `pages/AnalysisPage.vue` (23行) — AI 分析工作台
- `components/analytics/ScoreSegmentSettings.vue` — 分数段配置
- `api/analytics.js` (46行) — API 调用层
- 路由状态: **冻结中**（`router/index.js` 无 analytics 路由）

**执行步骤**:
1. 读 `frontend/src/router/_frozen/index.full.js` 找到原 analytics 路由定义
2. 解冻: 把 analytics 相关路由加回 `router/index.js`
3. 增强 `api/analytics.js`: 补全 T2-T4 新端点调用（class-diagnosis / layer-analysis / common-wrong-questions）
4. 增强已有页面: 接入新数据（三维诊断、分层学情、常错题）
5. `cd frontend && npx vite build` 让 mcu.asia 看到变更
6. 浏览器验证: https://mcu.asia 登录后访问分析页面

**交付路径**: nginx 443 → `frontend/dist/` → 用户直接看到。改代码后必须 `vite build`。

**验收**: mcu.asia 上能看到基于真实数据的分析图表（用户确认，非自审）

=== 生成块结束 ===

默认立场：增强已有 4 个页面 + 1 个 API 模块。只在确实需要时才新建组件。不在 frontend-nuxt/ 做任何工作。
