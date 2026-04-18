<!-- legacy-format -->
# T-E Takeover 影响面全景 Audit · 2026-04-18

> 类型：Researcher session（只读，不写代码）
> 创建：2026-04-18 由 Planner (Opus 4.7 1M)
> 工作目录：/home/ops/projects/edu-cloud-t2 (master @ 6490dea)
> 唯一输出：`docs/plans/2026-04-18-takeover-impact-audit-report.md`
> 估时：1-2h，独立 Researcher session（不是 Executor）

## 1. 任务背景（实查事实，禁演绎）

W4-R8 Planner 调查 conduct 测试漂移时假设"takeover 遗失 40 测试"。Planner 实查后**校准结论**：

| 假设 | git 全历史实证 | 真相 |
|---|---|---|
| Windows 108 → ECS 68 是 takeover 漏 sync | `git log --all --diff-filter=A -- 'src/edu_cloud/modules/conduct/__init__.py'` 唯一命中 = `00cfc3d` | conduct 模块在 git 全历史中**第一次出现就是 takeover**，Windows 108 测试从未进 git |
| takeover 是技术故障 | message: `sync ECS worktree as authoritative; retire legacy ai/* modules; untrack uploads/ and *.db`；删除的 5 个 tests 文件全是 `tests/test_ai/test_*.py` legacy | takeover 是**有意的"ECS-as-authority 重置基线"事件**（3492 files, +356697/-54790），不是漏 sync |
| 只 conduct 一处漂移 | grep `cd C:/Users/Administrator` docs/plans → 30+ 文件命中 | 漂移系统性扩散到 W2 KG-phase1 / haofenshu / grading-dispatch / migration-gate-repair 多 plan |

**核心 audit 问题（本任务待回答）**：
1. takeover 之外，还有哪些**Windows-era 开发未进 ECS**？
2. 当前 ECS 与 Windows 历史快照（如有可达 source）的真实差异面是多少？
3. 哪些"漂移"是有意 retire（同 ai/*）/ 哪些是误漏？

## 2. 范围

**In scope**：
- git diff 全量对比 takeover 前后（00cfc3d~1 vs 00cfc3d）按目录分桶
- 横向 grep 所有 docs/plans/*.md 中的 baseline 数字 vs 当前 ECS 实测
- 列 plan × baseline 命令 × ECS 可执行性 三栏表
- 输出 audit-report.md（commit-anchored 证据 + 归类决策建议）

**Out of scope**（红线）：
- 禁修任何代码
- 禁修任何 plan / handoff
- 禁触发 codex-review
- 禁试图"恢复" Windows 历史测试（决策权在用户）

## 3. 红线

- 只读 git / file / pytest collect-only，**禁 commit 任何改动**
- 禁触 `src/`、`frontend/`、`alembic/`
- **禁动 W4-R8 Planner 在跑的文件**：`docs/plans/2026-04-18-w4-r8-planner-handoff.md` + `docs/plans/2026-04-18-batch1-baseline-evidence.md`
- **禁动 T-D 在跑的文件**：`docs/plans/2026-04-18-w2-batch3b-iii-handoff.md`
- ECS python3 现状：`/usr/bin/python3` 存在但 `No module named pytest` → 用 `git ls-files | grep test_ | xargs grep -c "^def test_\|^async def test_"` 统计实查

## 4. 关键证据起点（已 verify）

| 证据 | 命令 | 结果 |
|---|---|---|
| takeover commit | `git log --all --grep="takeover"` | `00cfc3d 2026-04-16 21:21:23 +0800` |
| takeover 规模 | `git show --shortstat 00cfc3d` | `3492 files changed, +356697/-54790` |
| takeover 删除的 test | `git show --name-status 00cfc3d \| grep -E "^D\s+tests/"` | 5 文件，**全是 ai/* legacy** |
| takeover 新增的 test | `git show --name-status 00cfc3d \| grep -E "^A\s+tests/" \| wc -l` | ≥ 266（grep -A 标记） |
| ECS conduct 实测 | `grep -c "^def test_\|^async def test_" tests/test_conduct/*.py` | 7 文件 / 68 函数（admin_api 13+admin_crud_api 14+agent_tools 9+crypto 4+models 4+parent_api 19+permissions 5）|
| W4-R8 Planner 池 | `2026-04-18-batch1-baseline-evidence.md` (W4 worktree feat/conduct-roadmap-batch1) | 不在 master，需 `cd /home/ops/projects/edu-cloud && cat docs/plans/2026-04-18-batch1-baseline-evidence.md` |

## 5. 步骤

1. **takeover 文件分桶**
   - `git show --name-status 00cfc3d > /tmp/takeover-files.txt`
   - 按 src/ / tests/ / docs/ / alembic/ / frontend/ / scripts/ 分类
   - 输出每桶 A/M/D 数量
2. **plan baseline 全量盘点**
   - grep 所有 `docs/plans/*.md` 中的 `cd C:/Users/Administrator` 命中文件清单
   - grep 所有 `docs/plans/*.md` 中"X passed"格式的数字与对应文件
   - 输出 plan × baseline 数字 × baseline 命令 三栏表
3. **ECS 可执行性核查**
   - 对每个 baseline 命令，去掉 cd 路径后能否 grep 出对应测试文件
   - 找出 plan 引用但 ECS 仓内不存在的测试目录
4. **conduct 模块特例对账**
   - 用 `git log --all --oneline -- tests/test_conduct/` 看 ECS 上 68 测试的"诞生时间"
   - 用 `git log --all -- 'src/edu_cloud/modules/conduct/'` 看 conduct 模块 commit 链
5. **归类决策矩阵**（每个差异 1 行）
   - 类 A：Windows-only 历史扩展（git 无源头，可 retire 或重新实现）
   - 类 B：git 历史有 commit 但未 sync 到 ECS（可 cherry-pick 恢复）
   - 类 C：takeover 主动 retire（同 ai/*，无需操作）
   - 类 D：plan 引用但代码从未存在（plan 错误，需修订）
6. **输出 audit-report.md**
   - 包含：§1 结论 / §2 takeover 全景 / §3 plan 漂移清单 / §4 conduct 特例 / §5 归类决策 / §6 followup 建议
   - 每个论断必带 commit hash 或 grep 输出锚定

## 6. 完成定义 (DoD)

- `docs/plans/2026-04-18-takeover-impact-audit-report.md` 落地（≥ 6 节）
- 列至少 **5 个 plan 的 baseline 真伪**（W4-R8 已自行处理 conduct，本任务覆盖其他 plan）
- 对 W4-R8 "40 测试遗失"假设给出权威结论（A/B/C/D 类归属）
- followup 建议：T-F (plan 清洗) / T-G (hook) / T-H (pytest 环境) 的优先级与依赖关系

## 7. 启动 prompt（直接复制）

```
[edu-cloud] Researcher | 2026-04-18 09:12:32 | T-E Takeover Audit
工作目录: /home/ops/projects/edu-cloud-t2 (master @ 6490dea)

读取交接卡: docs/plans/2026-04-18-takeover-audit-handoff.md
全文阅读后按 §5 步骤 1-6 推进，输出 §6 DoD 中的 audit-report.md。

红线 (§3):
- 只读 git/file，禁 commit 代码
- 禁动 W4-R8 / T-D 在跑的 handoff
- 禁修 plan，只产 audit 报告

完成后用 SendMessage 通知 Planner，不擅自启 followup 任务。
基于事实 + commit anchor，禁猜测。L013/L015 严守。
```
