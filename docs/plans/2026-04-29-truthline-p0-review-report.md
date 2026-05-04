# Truthline P0 Code Review Report

## 审查信息

| 字段 | 值 |
|------|-----|
| Plan | `docs/superpowers/plans/2026-04-29-truthline-p0.md` |
| Branch | `feat/truthline-p0` |
| Commit range | `e3e9aab..2757430` (9 commits) |
| Reviewer | GPT-5.4 via Codex MCP |
| Round | R2 (full template) |
| Handoff | `docs/plans/2026-04-29-truthline-p0-code-review-handoff.md` |
| Raw output | `.codex-raw-code_review_r2-20260429-2144.log` |
| Raw output hash | `94e16f262d1cd6fc6730724225e4d0eb6a718aa3f2f2396fc7636acd22c5835f` |

## 变更理解

本次变更在 edu-cloud 中引入 Truthline P0 真相可见化系统：

1. **前端 build 版本指纹**：vite.config.js 注入 4 个 define 常量 + closeBundle 生成 dist/version.json
2. **前端启动日志**：main.js 在 mount 前 console.log 版本信息
3. **后端版本端点扩展**：/api/v1/version 新增 git_hash/source_dirty/pid 三字段
4. **truth CLI 诊断工具**：truth status（四段真相链诊断）+ truth doctor（五段环境诊断）

核心目标：把"AI 改的和用户看到的不一样"从猜测变为秒级定位断在哪一步。全部只读诊断，不改工作流。

## 对抗性审查

GPT R2 审查覆盖了 4 个 phase，发现了 R1 遗漏的深层问题：

- **F001 dirty build 误报 aligned**：R1 修复了"后端 dirty 不设 BROKEN_AT"，但 R2 发现更微妙的场景——dirty build 产物（version.json source_dirty=true）在工作区恢复 clean 后仍被判为 aligned。这是 R1 未覆盖的路径。
- **F002/F003 pipefail 边界**：R1 只修了 grep LISTEN，R2 发现 pid 提取和 pgrep -fc 也有同类问题。说明 R1 的修复不够系统化。
- **F004 弱断言**：R1 快速审查未触及测试质量，R2 的 Phase 1 测试充分性检查正确捕获了"删除核心逻辑后测试仍 PASS"的 test-gap。

R2 的 4 个 findings 全部是 R1 遗漏的真实缺陷，验证了完整审查流程的必要性。

## 发现清单

### R1 快速审查（已修复，commit 6daceab）

| ID | Severity | Type | 问题 | 状态 |
|----|----------|------|------|------|
| R1-F002 | HIGH | defect_fix | backend dirty 时 truth status 报 ALL ALIGNED | resolved-correct |
| R1-F003 | HIGH | defect_fix | git diff --quiet 忽略 staged 变更 | resolved-correct |
| R1-F004 | MED | defect_fix | truth-doctor grep 空结果触发 pipefail | resolved-correct |

### R2 完整审查（已修复，commit 2757430）

## R2 Findings 与处置

| ID | Severity | Category | Type | 三态标注 | 处置 |
|----|----------|----------|------|---------|------|
| F001 | HIGH | code-bug | defect_fix | resolved-correct | truth-status.sh 消费 version.json source_dirty 字段，dirty build 不报 aligned |
| F002 | MED | code-bug | defect_fix | resolved-correct | truth-doctor.sh pid 提取加 `\|\| true` + 空 pid 时 warn 并 return |
| F003 | MED | code-bug | defect_fix | resolved-correct | pgrep -fc 改用隔离赋值 `VAR=0; VAR=$(...) \|\| VAR=0` |
| F004 | HIGH | test-gap | test_gap | resolved-correct | test_version 加 git_hash 格式 regex + pid > 0 断言 |

## ORC 验证

| ORC | 验证命令 | 结果 |
|-----|---------|------|
| ORC-1 | `curl -s https://mcu.asia/ \| head -1` | `<!DOCTYPE html>` PASS |
| ORC-3 | `pytest tests/test_api/test_health.py -v` | 2/2 PASS |
| ORC-4 | `truth doctor` dist 段 | www-data 可读，version.json 存在 PASS |
| ORC-5 | `curl -s localhost:9000/api/v1/version` | version + boot_time 存在 PASS |

## 结论

R2 PASS — 4 个 findings 全部 resolved-correct，修复 commit `2757430`。
