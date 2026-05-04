# Truthline P0 Code Review Handoff

## 基本信息

| 字段 | 值 |
|------|-----|
| Plan | `docs/superpowers/plans/2026-04-29-truthline-p0.md` |
| Branch | `feat/truthline-p0` |
| Commit range | `e3e9aab..6daceab` (8 commits) |
| First commit | `e3e9aab` feat(truthline): inject build fingerprint via vite define |
| Last commit | `6daceab` fix(truthline): GPT code review F002-F004 |
| Files changed | 9 files, +438/-2 lines |
| Tier | T3 |

## 变更文件清单

| 文件 | 变更类型 | 职责 |
|------|---------|------|
| `frontend/vite.config.js` | Modify | 新增 4 个 define 常量 + `generateVersionJson` + `isSourceDirty` helper |
| `frontend/src/main.js` | Modify | app mount 前 console.log 版本指纹 |
| `frontend/eslint.config.js` | Modify | 新增 4 个 globals（`__BUILD_TIME__` 等）|
| `frontend/src/__tests__/version-fingerprint.test.js` | Create | 4 个 vitest 测试验证 define 常量 |
| `src/edu_cloud/api/app.py` | Modify | `/api/v1/version` 扩展 +3 字段（git_hash/source_dirty/pid）|
| `tests/test_api/test_health.py` | Modify | test_version 新增 3 个断言 |
| `scripts/truth` | Create | CLI 入口脚本，子命令分发 |
| `scripts/truth-status.sh` | Create | 四段诊断（Source/Build/Nginx/Backend）|
| `scripts/truth-doctor.sh` | Create | 五段诊断（Ports/Ghost/dist/systemd/Claude）|

## 设计意图

把"AI 改的和用户看到的不一样"变成"明确断在源码→build→dist→nginx 的第几步"。全部只读诊断，不改工作流。

## 已知 test_debt

- `truth-status.sh` / `truth-doctor.sh` 无自动化测试（bash CLI 依赖运行时环境）
- `version.json` 生成无独立测试（依赖 vite build 全流程，Task 7 集成验证覆盖）

## R1 快速审查 findings（已修复）

| ID | Severity | 问题 | 处置 |
|----|----------|------|------|
| F002 | HIGH | backend dirty 时 truth status 仍报 ALL ALIGNED | commit 6daceab: dirty 设 BROKEN_AT |
| F003 | HIGH | git diff --quiet 忽略 staged 变更 | commit 6daceab: 改为 git diff --quiet HEAD |
| F004 | MED | truth-doctor.sh grep 空结果触发 pipefail 退出 | commit 6daceab: 加 `|| true` |

## 逐 Task 自审

| Task | 意图 | 实际产出 | 一致？ |
|------|------|---------|--------|
| T1 vite define + version.json | 注入 4 个 build 常量 + closeBundle 生成 version.json | vite.config.js 新增 define 段 + generateVersionJson plugin，4 tests PASS | 是 |
| T2 main.js console.log | 启动时输出版本指纹 | main.js 在 mount 前 console.log，含 id/build/time/dirty | 是 |
| T3 /api/v1/version 扩展 | 新增 git_hash/source_dirty/pid | app.py 模块级缓存 + version 端点返回 5 字段，test_version 断言 5 字段 | 是 |
| T4 truth CLI 入口 | 子命令分发脚本 | scripts/truth 带 readlink -f 解析 symlink | 是 |
| T5 truth status | 四段诊断 Source/Build/Nginx/Backend | truth-status.sh 142 行，含 BROKEN_AT 定位 | 是 |
| T6 truth doctor | 五段诊断 Ports/Ghost/dist/systemd/Claude | truth-doctor.sh 153 行，含 issue 计数 | 是 |
| T7 安装 + 验证 | symlink + ESLint globals + P0 验证 | ~/.local/bin/truth + eslint.config.js 4 globals + ORC 全通过 | 是 |

## 验证清单自检

| 验证项 | 命令 | 结果 |
|--------|------|------|
| 前端指纹测试 | `npx vitest run src/__tests__/version-fingerprint.test.js` | 4/4 PASS |
| 后端 health 测试 | `.venv/bin/python -m pytest tests/test_api/test_health.py -v` | 2/2 PASS |
| vite build 成功 | `cd frontend && npm run build` | built in 19s，dist/version.json 生成 |
| ORC-1 nginx serve | `curl -s https://mcu.asia/ \| head -1` | `<!DOCTYPE html>` |
| ORC-5 向后兼容 | `curl -s localhost:9000/api/v1/version` | version + boot_time 仍存在 |
| truth status 运行 | `truth status` | 输出四段诊断，无报错 |
| truth doctor 运行 | `truth doctor` | 输出五段诊断，无报错 |
| dist/ 权限 | `truth doctor` dist 段 | www-data 可读 |

## 自查

1. **漏做了什么？** CLI 脚本无自动化测试（已记入 test_debt，P1 考虑 bats 框架）；前端全量测试有 4 个既有 failure（非本次引入，LoginPage/ReviewPage/GradingPanel）
2. **已做的和意图一致吗？** 逐 Task 对齐 plan，全部一致；GPT R1 发现的 3 个缺陷已修复（staged diff / dirty BROKEN_AT / grep pipefail）
3. **产出到达用户了吗？** vite build 已执行，mcu.asia 返回 200，version.json 可通过 nginx 访问；后端需重启才能加载最新 git_hash（uvicorn --reload 已自动处理）
