<!-- no-projectctl -->

=== 生成块开始 ===

task_id: T4-ui-theme-migration
topic: 冷暖撞色UI全系统迁移
project_dir: ~/projects/edu-cloud
effective_tier: T4
gate_status: plan_review=pass, code_review=pass
last_verified_evidence: vite build 20.25s + grep旧色值=0 + vitest 2375passed/18failed
subject_hash: d4f39f4
raw_output_hashes: N/A
timestamp: 2026-05-03 22:45:00

=== 生成块结束 ===

=== 自由备注开始 ===

## Goal
色值迁移+视觉风格落地。DashboardPage/AppHeader已对齐demo。剩余：其他页面视觉微调。

## Must Preserve
- variables.css新token（surface-stat-*、page-gradient、shadow-stat-*）
- theme.js完整Naive UI覆盖（18组件+全状态色）
- global.css统计卡nth-child彩色浅底+Naive组件覆盖
- AppHeader pill导航+DashboardPage统计卡（GPT重写版）
- chartTheme.js+heatmapUtils.js新色板

## Must Not Change
- 侧栏布局（44页面依赖）/路由/后端/测试基线(2375/18)

## Status
Commits b14a041..d4f39f4 | Plan v2 GPT PASS | 用户确认方向正确 | 待逐页确认

=== 自由备注结束 ===
