<!-- legacy-format -->
# T-G plan_baseline_guard Hook 设计 + 落地 · 2026-04-18

> 类型：Architect + Executor session（写 hook 代码 + plan frontmatter migration）
> 创建：2026-04-18 由 Planner (Opus 4.7 1M)
> 工作目录：`~/.claude/hooks/`（hook 文件）+ `/home/ops/projects/edu-cloud-t2`（plan frontmatter 示范）
> 估时：2h，独立 Executor session

## 1. 任务背景（实查事实）

W4-R8 Planner 暴露根因：plan 引用的"baseline 命令"在 ECS 上**根本跑不了**。

| 现象 | 证据 | 影响 |
|---|---|---|
| 30+ plan 含 `cd C:/Users/Administrator` | grep docs/plans → haofenshu/grading/migration/conduct/kg 多 plan | reviewer 看 plan 没法实跑 |
| ECS python3 无 pytest | `/usr/bin/python3` exists, `No module named pytest` | 即使路径改 ECS 也跑不了 |
| 7 轮 reviewer 全文字审 R7 PASS 是伪基线 | W4-R8 调查证据文档 | 系统性 plan-as-contract 失效 |
| 2026-04-17 起新 handoff 已隐性切 ECS path | grep W1/W3 exec handoff = 0 命中 | 切换无 lint 强制，新 plan 与旧 plan 双标 |

**根因**：缺少 plan-as-contract 的**环境锚定 + 时效校验**机制。

**本任务目标**：写 hook 阻止 Windows 路径再进 plan，强制 frontmatter 标注 baseline 三字段（command / verified_at / count），未来 reviewer 可机器校验。

## 2. 范围

**In scope**：
- 新建 `~/.claude/hooks/plan_baseline_guard.py`（fail-open，verbose log，dry-run 模式）
- 注册到 `~/.claude/settings.json` PreToolUse(Write, Edit) on `**/docs/plans/**.md`
- 给 W4 R8 plan (`docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md`) 加 frontmatter 示范
- 出 `~/.claude/hooks/README-plan-baseline-guard.md` 解释规则 + 例外路径

**Out of scope**（移交后续任务）：
- 大批量现存 plan frontmatter migration → T-F 任务
- ECS pytest 环境补全（venv/uv 装依赖）→ T-H 任务
- 修业务代码（src/ frontend/）

## 3. 红线

- hook 必须 **fail-open**：异常时 warning 不 block，避免 commit 雪崩
- 必须先 **dry-run 模式**测冲击面：现存 30+ plan 哪些会触发
- `update-config` skill 注册：走 `~/.claude/settings.json`（用户全局），**禁动 `.local` 或 project**
- 现存 plan frontmatter 检测**不能误伤已合规 yaml**（用 `python-frontmatter` 或简单分隔符 `---`）
- hook 文件 PEP 8 + UTF-8，**禁引入第三方依赖**（用标准库 + 已有 `python-frontmatter`）

## 4. 关键证据起点

| 项 | 命令 / 路径 |
|---|---|
| 已有 hook 体系 | `ls ~/.claude/hooks/*.py` 看现存格式 |
| settings.json 当前 hook 注册 | `jq '.hooks' ~/.claude/settings.json` |
| 受影响 plan 全清单 | `grep -rl "cd C:/Users/Administrator" /home/ops/projects/edu-cloud-t2/docs/plans/` |
| W4 R8 plan 路径 | `docs/plans/2026-04-14-conduct-roadmap-batch1-plan.md` |

## 5. Hook 规则设计

**触发**：PreToolUse(Write, Edit) on path matching `**/docs/plans/**.md`

**Block 条件**（任一命中即 block）：
1. 新内容含 `cd C:/Users/Administrator` (case-sensitive regex)
2. 新内容含 baseline 数字模式 (`\b\d+\s+passed\b`) 但前 100 行 frontmatter 缺 `baseline_verified_at` 字段
3. 文件名匹配 `*-plan.md` 但 frontmatter 缺 3 必填字段（baseline_command / baseline_verified_at / baseline_count）

**Warning 条件**（不 block）：
- `baseline_verified_at` 距今 > 7 天

**例外**（skip）：
- 文件首行包含 `<!-- legacy-format -->`（兼容现存交接卡）
- 文件路径含 `.codex-raw-` 前缀（codex 日志，禁修改）
- 文件名匹配 `*-handoff.md`（handoff 格式由 handoff_format_guard 管，本 hook 不重叠）

## 6. 步骤

1. **侦查**：读 `~/.claude/hooks/` 已有 hook 看代码风格 + 错误处理 + log 格式
2. **设计 dry-run**：先用 stdout 模式跑一遍现存 30+ plan，看冲击面
3. **写 hook**：`plan_baseline_guard.py` 含 §5 规则 + fail-open + 详 log
4. **注册**：用 `update-config` skill 加 PreToolUse hook 到 `~/.claude/settings.json`
5. **示范 migration**：给 W4 R8 plan `2026-04-14-conduct-roadmap-batch1-plan.md` 加 frontmatter（baseline 三字段，verified_at 用 W4-R8 当前订正后值）
6. **验证**：构造 3 个测试 case（含 Windows path / 缺字段 / 已合规）跑 hook 看 block 是否准确
7. **README**：`~/.claude/hooks/README-plan-baseline-guard.md` 含规则 + 例外 + 实例

## 7. 完成定义 (DoD)

- `~/.claude/hooks/plan_baseline_guard.py` 落地（≥ 100 行，含 fail-open + verbose log）
- `~/.claude/settings.json` 注册成功（jq 验证）
- W4 R8 plan 含 frontmatter 三字段
- README.md 落地，含 dry-run 冲击面统计（多少现存 plan 会被触发）
- 3 个测试 case 通过 + dry-run 冲击面报告

## 8. 启动 prompt（直接复制）

```
[meta-config] Executor | 2026-04-18 09:12:32 | T-G plan_baseline_guard hook
工作目录: ~/.claude/hooks/ + /home/ops/projects/edu-cloud-t2

读取交接卡: /home/ops/projects/edu-cloud-t2/docs/plans/2026-04-18-plan-baseline-guard-handoff.md
全文阅读后按 §6 步骤 1-7 推进。

红线 (§3):
- hook fail-open，禁打补丁式临时方案（用户偏好底层修复）
- update-config skill 走 ~/.claude/settings.json，禁动 local
- 不动业务代码（src/ frontend/）

完成后用 SendMessage 通知 Planner 当前 dry-run 冲击面 + 是否需启 T-F (plan 批量 migration)。
基于事实 + 实跑 dry-run 数字，禁猜测。L013/L015 严守。
```

## 9. 后续任务依赖（建议，待 Planner 决策）

- **T-F**（plan 批量清洗）：本 hook 落地后，按冲击面拆批次迁移现存 30+ plan，每批先跑 dry-run 看清单
- **T-H**（ECS pytest 环境）：venv/uv 装 pytest + 依赖，让 plan baseline 命令真能跑（这才是 reviewer 能实跑的根因修复）
- **路径**：T-G PASS → T-F 启动批量迁移；T-F 与 T-H 可并行
