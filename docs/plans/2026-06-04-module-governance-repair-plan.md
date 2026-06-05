# 模块治理体系根因修复计划（2026-06-04 · v6.10）

> 性质：T3 级结构性修复。  
> 目标：让模块治理从"Claude PreToolUse 可能提醒"升级为"真实 commit staged index 上的强制闸门"。  
> 范围：跨两个仓库执行：`/home/ops/yuanshou` 修 hook 调度器，`/home/ops/projects/edu-cloud` 修模块治理真源、Git hook、CI、本地验证和当前债务。

> **设计锚点声明（回应 plan-review F-001）**：本任务为事故根因修复，无独立 design 阶段；
> 本计划即设计载体。设计锚点 = 「根因分层 R1-R6」+「总体原则 6 条」+「明确不做」+ 下方「Contract Pack」。
> 实现审查（code review）以这些段落 + Contract Pack 的 invariants/counter_examples 作为不变量基准，
> 不存在与本计划并列的独立 design 文档，无需核验外部设计一致性。

---

## 一句话结论

`exam_import` 没被拦，不是因为 `MODULE.md` 规则完全不存在，而是因为 `commit_guards` 没有在真实要提交的 repo/staged index 上运行模块治理检查。

必须先修"guard 能看到真实 staged index"，再清 `exam_import` 债务。否则只是把现场打扫干净，不能证明元守体系恢复。

---

## 事故链证据

### 证据 1：hook 运行但允许

`/home/ops/.claude/logs/hook-events.jsonl` 在 2026-05-19 22:45:51 记录：

```text
commit_guards | allow | all_pass
```

说明问题不是 hook 完全没运行，而是 hook 没看到真实风险。

### 证据 2：真实时间线显示 command repo 和 hook cwd 不一致

直接证据文件：

```text
/home/ops/.claude/projects/-home-ops/4da08d92-2802-4905-9efc-5e2ea7c1221d/subagents/agent-a4ea5dea4a16813f5.jsonl
```

该 JSONL 每条 Bash tool_use 的 `cwd` 字段均显示当时会话目录是：

```text
/home/ops/projects/edu-cloud/.claude/worktrees/agent-a4ea5dea4a16813f5
```

但 command 内部多次 `cd` 到主仓库：

```text
Step 1 · line 74 · 2026-05-19 22:44:46 +0800
command = cd /home/ops/projects/edu-cloud && git add ... && git commit -m "$(cat <<'EOF' ... EOF)"
结果：被 code_review_gate_guard 阻断，未形成事故提交。
注：Step 1 同时体现 R1（command 内 cd 到主仓库，与 hook cwd=worktree 不一致）和 R2（stage+commit 同命令）。
    commit message 是 heredoc 形态，任何 command normalizer 都不得破坏它。

Step 2 · line 101 · 2026-05-19 22:45:42 +0800
command = cd /home/ops/projects/edu-cloud && git commit ... # review-waiver...
结果：失败，nothing staged。

Step 3 · line 104 · 2026-05-19 22:45:47 +0800
command = cd /home/ops/projects/edu-cloud && git add ... && git diff --cached --stat
结果：在主仓库 staged 了 exam_import 文件。

Step 4 · line 106-107 · 2026-05-19 22:45:51 +0800
command = cd /home/ops/projects/edu-cloud && git commit ... # review-waiver...
结果：成功生成事故提交 5d85fd4。
```

最终成功命令是：

```bash
cd /home/ops/projects/edu-cloud && git commit -m "... # review-waiver: subagent-task1-parser-only-no-orm-no-api"
```

所以最终事故不是 hook 完全没运行，也不是同命令 `git add && git commit` 直接成功；真正命中的是：hook event `cwd` 留在 worktree，真实 staged index 在 command 内 `cd` 到的主仓库。

### 证据 3：commit_guards 当前读取 staged index 的方式

`/home/ops/yuanshou/hooks/commit_guards.py` 当前逻辑等价于：

```python
cwd = data.get('cwd', None)
subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=cwd)
subprocess.run(['git', 'diff', '--cached', '-U0'], cwd=cwd)
```

它读取的是 hook event 的 `cwd`，不是 Bash 命令里 `cd` 到的 repo。

### 证据 4：最小复现

构造：

```text
main repo: 已 staged 新模块 src/edu_cloud/modules/newmod/__init__.py，缺 MODULE.md
hook cwd: 另一个目录
tool command: cd <main repo> && git commit -m ...
```

当前 `/home/ops/yuanshou/hooks/commit_guards.py` 返回 0 且无输出，放行。

---

## 根因分层

### R1：真实 repo 定位错误（命中最终事故 5d85fd4）

`commit_guards` 用 hook event cwd 读取 staged index；实际 commit 可以通过 Bash 内部 `cd` 或 `git -C` 指向另一个 repo。Step 4 即为此场景：hook cwd 是 worktree，staged index 在主仓库，`git diff --cached` 返回空，放行。

### R2：PreToolUse 看不到同命令里的 stage 操作（并列高危旁路，Step 1 已观测）

如果命令是：

```bash
git add ... && git commit ...
```

PreToolUse 在命令执行前运行，看不到 `git add` 之后的 staged index。Step 1 使用了此形态（被 code_review_gate_guard 拦截，但若无该 guard 会直接绕过模块治理）。R1 和 R2 必须同级修复，但 R1 是最终成功提交的直接原因。

### R3：缺少 Git pre-commit 最终兜底

Claude hook 是工具层闸门，不是 Git 层闸门。没有 repo 内 `.githooks/pre-commit`，就没有"最终 staged index"的强制检查。

### R4：模块治理代码没有单一真源

当前测试从 `~/.claude/hooks` 导入，CI 无法复现；如果硬拷贝到 repo，又会产生双真源漂移。

### R5：CI 和本地收口缺失

`.github/workflows/test.yml` 只跑 `test_codex_scripts.py`，`scripts/codex-verify` 没有 `governance` 模式。

### R6：当前债务未清

`exam_import` 缺 `MODULE.md`，`docs/governance/` 过期，`exam_import/router.py` 仍有裸 `.school_id`。

---

## 总体原则

1. 先修"看见真实 staged index"，再修模块规则。
2. `yuanshou` 测 hook 调度器，`edu-cloud` 测模块治理规则，不能互相假装覆盖。
3. Claude PreToolUse 是第一道闸门，Git pre-commit 是第二道闸门。
4. repo 内脚本是真源，外部 hook 只做薄包装。
5. `aggregate_modules.py --check` 必须 fail on debt，不能只检查派生产物是否新鲜。
6. 每个 phase 独立 commit，可单独 revert。

---

## Phase 0：冻结契约和证据

### P0-T1：统一 ask/block 契约

`module_governance_guard` 属于 hard block，缺 `MODULE.md` 必须 block。

修改 `edu-cloud/tests/governance/test_module_governance_guard.py`：

```text
test_large_modification_without_module_md_asks: ask -> block
test_hook_entry_asks_on_large_legacy_touch: ask -> block
```

同时改测试名：

```text
test_large_modification_without_module_md_blocks
test_hook_entry_blocks_on_large_legacy_touch
```

### P0-T2：记录事故复现

在测试注释或计划证据中固定以下事实：

```text
hook cwd != effective commit repo
真实 staged index 在 command 内 cd 到的 repo
旧 commit_guards 读取 hook cwd，得到 staged_files=[]
```

### P0 验收

在 `edu-cloud`：

```bash
python3 -m pytest \
  tests/governance/test_module_governance_guard.py \
  tests/governance/test_aggregate_modules.py \
  -q
```

此阶段不跑 `test_tenant_static.py`，它属于 Phase 5。

---

## Phase 1：修 yuanshou 的 commit_guards 调度器

> 本 phase 在 `/home/ops/yuanshou` 执行，不在 edu-cloud 执行。

### P1-T0：命令级前置硬阻断（在 resolve / staged 读取之前）

> 关键时序：stage+commit 与 hook 绕过类命令，必须在 `_resolve_effective_repo()` 和任何 `git diff --cached` 之前，
> 由 command-only precheck 拦截。原因：dispatcher CHECKS 发生在 repo resolve 和 staged_info 读取之后，
> 那时再 block 已经晚了，且会与 resolve 失败路径相互纠缠。这是独立的命令文本检查，不读 index，不解析 repo。

在 `commit_guards.main()` 最前面（确认 `_is_git_commit_command(command)` 为真之后、resolve 之前）执行。
**时序（回应审查中-2）**：precheck 发生在 staged 读取之前，但 `dispatcher_emit` 需要 `ss`；
因此先初始化最小 `SessionState`，再跑 command-only precheck：

```python
ss = hook_lib.SessionState(hook_lib.current_session_id())   # 先于 precheck 初始化
precheck = _command_only_precheck(command)   # 只看命令文本，不读 index、不解析 repo
if precheck is not None:
    return hook_lib.dispatcher_emit(precheck, data, ss, ...)   # 直接 deny，不继续
```

`_command_only_precheck(command)` 必须 deny 以下两类：

**(a) 同命令 stage + commit**（R2）——至少覆盖：

```text
git add ... && git commit
git rm ... && git commit
git mv ... && git commit
git restore --staged ... && git commit
git reset <path> ... && git commit
git update-index ... && git commit
```

无论 stage 在 commit 前还是同复合命令内，一律 deny，提示拆成两条：先 stage，确认后再单独 commit。

**(b) Git hook 绕过类**（修复期间一律 deny，否则 Phase 4 的 pre-commit 兜底形同虚设）：

```text
git commit --no-verify
git commit -n
git -c core.hooksPath=<任意> commit
git -c core.hooksPath=/dev/null commit
git --git-dir=<外部路径> commit
```

**(c) kill switch inline 注入**（回应审查 finding 1，HIGH）：

```text
EDU_GOVERNANCE_GUARD_DISABLED=1 git commit ...
EDU_GOVERNANCE_GUARD_DISABLED=1 cd <repo> && git commit ...
```

命令文本里出现 `EDU_GOVERNANCE_GUARD_DISABLED=` 赋值前缀 → deny。
注意：这只能拦 **inline 形式**；**继承形式**（shell 已 export 该变量）命令文本里没有，P1-T0 看不到——
继承形式的根治是 **P2-T1 在真源里移除 `_kill_switch()` 分支**（见下）。两手并用才闭环。

deny 文案要说明：模块治理修复期禁止绕过 commit 闸门；如确需 break-glass，另立显式机制，不在此通道放行。

**实现要求（结构化扫描，回应审查中-1，防误拦）**：

P1-T0 的匹配必须基于**命令结构**，不是裸字符串 grep：
- `--no-verify`/`-n`/`-c core.hooksPath`/`EDU_GOVERNANCE_GUARD_DISABLED=` 只在**命令选项/env 赋值位置**匹配；
- **绝不**扫描 commit message 内容（`-m` 之后的字符串、heredoc 体）——
  否则 `git commit -m "fix the -n flag"` 或 heredoc 里出现 `--no-verify` 会被误拦。
- 与 P1-T3 normalizer 同源：先识别 `git commit` 子命令边界，message 体视为不透明数据。

P1-T0 不依赖普通 CHECKS 列表，也不依赖 effective repo 解析结果。

### P1-T1：新增失败测试

扩展 `/home/ops/yuanshou/tests/test_commit_guards.py`（已存在，在现有测试基础上追加）：

```python
def test_resolve_effective_repo_from_cd_then_commit(tmp_path):
    """command = 'cd /repo && git commit' 时，effective repo 必须是 /repo。"""


def test_commit_guards_uses_effective_repo_for_staged_index(tmp_path):
    """hook cwd 和 command repo 不同时，staged_info 必须来自 command repo。"""


def test_commit_guards_passes_effective_cwd_to_subguards(tmp_path):
    """dispatcher 调用子 guard 时 data['cwd'] 必须替换为 effective repo root。"""


def test_commit_guards_blocks_stage_and_commit_same_command(tmp_path):
    """git add/rm/restore --staged 与 git commit 不得在同一 Bash 命令中。"""


def test_commit_guards_fail_closed_when_effective_repo_unresolvable(tmp_path):
    """命令含 git commit 但无法解析有效 repo 时必须 block。"""


def test_detects_git_dash_c_commit_as_commit_command(tmp_path):
    """git -C /repo commit 必须进入 commit_guards，不得被入口 regex 跳过。"""


def test_plain_git_commit_uses_hook_cwd_repo_root(tmp_path):
    """普通 git commit 必须解析为 hook cwd 所在 git repo root。"""


def test_commit_guards_uses_effective_repo_for_name_status_and_path_checks(tmp_path):
    """main() 内所有 git/index/文件存在性检查都必须使用 effective repo。"""


def test_effective_command_preserves_commit_args(tmp_path):
    """cd /repo && git commit -m 'msg' --no-edit 规范化后仍保留 -m 和 --no-edit。"""


def test_effective_command_preserves_heredoc_commit_message(tmp_path):
    """事故同款：git commit -m "$(cat <<'EOF' ... EOF)" 规范化后 message 不被破坏。"""


def test_review_waiver_survives_command_normalization(tmp_path):
    """commit message 含 # review-waiver: ... 时，规范化后 waiver 标记仍可被子 guard 识别。"""


def test_doc_commit_prefix_survives_command_normalization(tmp_path):
    """docs(...) / chore(docs) 等 doc commit 前缀规范化后仍可被 doc_sync_guard 识别。"""


def test_command_only_precheck_blocks_no_verify(tmp_path):
    """git commit --no-verify / -n 必须被 P1-T0 命令级 precheck deny。"""


def test_command_only_precheck_blocks_hookspath_bypass(tmp_path):
    """git -c core.hooksPath=/dev/null commit 必须被 P1-T0 deny。"""


def test_command_only_precheck_runs_before_repo_resolve(tmp_path):
    """stage+commit 在 _resolve_effective_repo / git diff --cached 之前就被 deny。"""


def test_command_only_precheck_blocks_kill_switch_inline(tmp_path):
    """EDU_GOVERNANCE_GUARD_DISABLED=1 git commit 必须被 P1-T0 deny（inline 形式）。"""


def test_precheck_does_not_falsely_match_flag_in_commit_message(tmp_path):
    """git commit -m 'fix the -n / --no-verify flag' 不得被误拦（结构化扫描，中-1）。"""


def test_precheck_does_not_falsely_match_flag_in_heredoc_body(tmp_path):
    """heredoc message 体里出现 --no-verify / EDU_GOVERNANCE_GUARD_DISABLED= 不得误拦。"""
```

这些测试必须先失败。

### P1-T2：实现 effective repo 解析

在 `/home/ops/yuanshou/hooks/commit_guards.py` 加：

```python
def _is_git_commit_command(command: str) -> bool:
    """识别所有 git commit 命令入口。
    
    必须匹配（返回 True）：
    - git commit ...
    - git -C <path> commit ...
    - cd <path> && git commit ...
    - git --git-dir=<path> commit ...（匹配后由 _resolve 做 fail-closed block）
    
    不匹配（返回 False）：
    - git log / git add / git push 等非 commit 命令
    - git commit-tree（底层命令，不是 porcelain commit）
    
    实现要求：
    不能只用 r'\bgit\s+commit\b'，必须覆盖 git 全局选项（-C / --git-dir / -c）
    穿插在 git 和 commit 子命令之间的情况。建议拆 token 后定位 'commit' 子命令位置。
    """


def _resolve_effective_repo(command: str, hook_cwd: str | None) -> str:
    """返回真实执行 git commit 的 repo root。失败时抛异常，由 main fail-closed。"""
```

解析规则：

1. `commit_guards.main()` 的入口判断必须调用 `_is_git_commit_command(command)`，不能继续使用 `re.search(r'\bgit\s+commit\b', command)`，否则 `git -C /repo commit` 会被跳过。
2. 同命令 stage + commit、`--no-verify`/`-n`、`-c core.hooksPath=...`、外部 `--git-dir` 已由 **P1-T0** 命令级 precheck 拦截，此处不再处理，也不在 resolve 内重复判断。
3. 支持普通明确的 `git commit ...`：candidate = hook cwd。
4. 支持简单明确的 `cd <path> && git commit ...`。
5. 支持简单明确的 `git -C <path> commit ...`。
6. 复杂 shell（多段 cd、变量、子 shell、函数、管道）一律 block，提示用户进入目标 repo 后单独执行 `git commit`。
7. 最终用 `git -C <candidate> rev-parse --show-toplevel` 规范化为 repo root。

不追求解析完整 shell。无法确定时 fail-closed。

### P1-T3：staged index 必须来自 effective repo

当前：

```python
cwd = data.get('cwd', None)
```

改为：

```python
hook_cwd = data.get('cwd', '')
command = data.get('tool_input', {}).get('command', '')
repo_root = _resolve_effective_repo(command, hook_cwd)
effective_data = dict(data)
effective_data['cwd'] = repo_root
effective_tool_input = dict(effective_data.get('tool_input') or {})
effective_tool_input['command'] = _normalize_to_git_commit_with_args(command)
effective_data['tool_input'] = effective_tool_input
```

**command 规范化规则（v6.2 修复）**：

`_normalize_to_git_commit_with_args(command)` 必须：

1. 去掉 `cd <path> &&` 前缀和 `git -C <path>` 前缀
2. 保留 `git commit` 之后的所有参数（`-m`、`--amend`、`--no-edit` 等）
3. 示例：`cd /repo && git commit -m "msg" --no-edit` → `git commit -m "msg" --no-edit`

**禁止**简单粗暴地设为 `'git commit'`——子 guard（如 `code_review_gate_guard`、`doc_sync_guard`）需要检查 commit message（`review-waiver`、`docs(...)` 前缀），丢参数会破坏其判断。

**heredoc 安全（v6.2 修复）**：事故命令是 `git commit -m "$(cat <<'EOF' ... EOF)"`。
normalizer **不得**用 `shlex.split` 粗暴拆 token——会破坏 heredoc message、`review-waiver` 标记、doc 前缀。
正确做法：只剥离 `git commit` 子命令之前的 `cd <path> &&` 和 `git -C <path>` / 全局选项前缀，
保留 `commit` 之后的原始字节串不动。无法安全剥离时 fail-closed（交由 P1-T0/复杂 shell 规则 block）。
注意：`--no-verify` 类标志本应在 P1-T0 已被 deny，不会走到 normalizer；normalizer 只处理合法 commit 的前缀剥离。

补测试（已加入 P1-T1）：`test_effective_command_preserves_commit_args`。

所有 staged 读取必须用 `repo_root`：

```python
git -C repo_root diff --cached --name-only
git -C repo_root diff --cached -U0
git -C repo_root diff --cached --name-status
```

`main()` 中所有 repo 相关操作都必须用 `repo_root`，包括：

```text
staged_files 读取
diff 读取
name-status 读取
os.path.exists(repo_root / test_file)
dispatcher_run_checks 的 data['cwd']
```

旧 `cwd` 只能保留为 `hook_cwd`，不得再用于 git/index/文件存在性判断。

dispatcher 必须使用 `effective_data`：

```python
result = hook_lib.dispatcher_run_checks(CHECKS, effective_data, ss, staged_info=staged_info)
```

否则 `_module_governance_if_edu()` 仍可能基于错误 cwd 跳过。

### P1-T4：确认 stage+commit 阻断由 P1-T0 统一负责

stage+commit 的真正阻断点是 **P1-T0 命令级 precheck**（通过 `hook_lib.dispatcher_emit` 输出 deny），
不是 dispatcher CHECKS 列表，也不是 `main()` 里裸 `return {"decision": "block"}`。

原因复述：

- `main()` 直接 `return {...}` 没有调用方处理，会被静默丢弃。
- 注册到 CHECKS 的 check 函数发生在 repo resolve 和 `git diff --cached` 读取之后，
  对"同命令 stage+commit / hook 绕过"这类**命令级**问题来说时序太晚，且会与 resolve 失败路径纠缠。

因此本计划只保留 P1-T0 一条阻断路径，**不再**新增 `_block_stage_and_commit` 这类 CHECKS 条目。
P1-T0 的 deny 必须经由 `dispatcher_emit`（或等价的标准 deny 输出函数）产出，确保 Claude 端真实拒绝。

实现自检：

```text
[ ] stage+commit / --no-verify / -n / -c core.hooksPath / 外部 --git-dir 全部在 P1-T0 deny
[ ] P1-T0 deny 走 dispatcher_emit，不是裸 return
[ ] P1-T0 检查的是【原始 command】，不是规范化后的 effective command
[ ] CHECKS 列表里没有重复的 stage+commit guard
```

### P1 验收

在 `/home/ops/yuanshou`：

```bash
python3 -m pytest tests/test_commit_guards.py -q
python3 -m pytest tests/ -q
```

并手工复现：

```text
hook cwd = temp worktree
command = cd temp-main-repo && git commit
main repo staged 缺 MODULE.md 新模块
期望：deny，不是 allow

command = git -C temp-main-repo commit
期望：进入 commit_guards 并使用 temp-main-repo 的 staged index

command = git commit
hook cwd = temp-main-repo/subdir
期望：解析到 temp-main-repo repo root，不误判 subdir

command = cd /repo && git commit -m "msg" --no-edit
期望：effective command 保留 -m "msg" --no-edit
```

---

## Phase 2：真源迁移工程（yuanshou hook → edu-cloud repo）

> 本 phase 在 `/home/ops/projects/edu-cloud` 执行。

> **前提**：当前 `~/.claude/hooks/module_governance_guard.py` 是真源（含完整治理逻辑，~330 行）。本 phase 目标是把真实逻辑迁入 edu-cloud repo，让 yuanshou hook 变成薄包装。这是一次完整代码迁移，不是新建空文件。

### P2-T1：将现有 hook 逻辑迁入 repo 真源

将 `~/.claude/hooks/module_governance_guard.py` 的完整逻辑复制到：

```text
scripts/governance/module_governance_guard.py
```

同时补充：

```text
check(data, session_state, staged_info=None)
--git-hook-mode CLI
```

迁移时必须同步修正两处：

**(1) 移除 kill switch（回应审查 finding 1，HIGH）**：

```text
当前真源 ~/.claude/hooks/module_governance_guard.py:19-20 有：
    def _kill_switch(): return os.environ.get("EDU_GOVERNANCE_GUARD_DISABLED") == "1"
迁移到 repo 真源时【彻底移除】该函数及其所有调用分支。
原因：环境变量可被继承，P1-T0 命令文本扫描看不到继承形式 → 唯一根治是真源里没有这个分支。
若未来确需 break-glass，另立【显式、审计、不可 inline 命令注入】的机制（见「明确不做」），不在本计划保留。
```

**(2) staged snapshot helper 必须用 git 判定，不用 .git 目录判定**：

```text
不得用 (repo / ".git").exists() 判断是否为 git repo。
必须用 git -C <repo> rev-parse --is-inside-work-tree / --show-toplevel。
原因：git worktree 的 .git 常常是文件，不是目录；目录判断会导致 checkout-index 失败后 fallback 到 worktree，破坏"只信 staged index"的核心契约。
```

**(3) 内部 aggregate 加载必须用 sibling，不从 target/snapshot 导入（回应审查 H2，HIGH）**：

```text
当前真源 _import_aggregate_module(repo) 从【被检查 repo】(real_repo) 的 scripts/governance 导入 aggregate
（~/.claude/hooks/module_governance_guard.py:95/124/278）。这会让 --repo <worktree> 悄悄用 worktree 的【旧 aggregate】，
或 target 无 scripts/governance 时失败/跳过——与方案 A「规则源全来自 canonical」直接冲突。

迁移时必须改成：module_governance_guard.py 加载【同目录 sibling】aggregate_modules.py，即：
    agg_dir = str(Path(__file__).resolve().parent)   # 规则源自身所在目录（canonical）
    sys.path.insert(0, agg_dir); import aggregate_modules
绝不从 real_repo/target/snapshot 的 scripts/governance 导入 aggregate。
导入失败或 frontmatter 生成失败 → fail-closed block（不静默跳过）。
```

> 解耦完整性：规则源是「module_governance_guard.py + 同目录 aggregate_modules.py」**整体**，都来自 canonical；
> 被检查对象（--repo / data['cwd']）只提供 staged index 内容，绝不提供任何规则代码（含 aggregate）。

**repo 真源的 command 判断契约（v6.2 修复）**：

repo 真源 `check()` 收到的 `data` 已经是 P1 规范化后的 `effective_data`——`data['cwd']` 是 effective repo root，`data['tool_input']['command']` 是规范化后的 `git commit ...`（含参数）。真源**信任调用方传入的 effective_data**，不再自行解析 `cd` / `-C` 前缀。

```python
# scripts/governance/module_governance_guard.py
def check(data, session_state, staged_info=None):
    # data['cwd'] = effective repo root（由 commit_guards 或 --git-hook-mode 设定）
    # data['tool_input']['command'] = 'git commit ...'（已规范化，含参数）
    # staged_info = 来自 effective repo 的 staged index
    # 直接使用以上字段，不再解析 cd / -C
    repo = Path(data.get('cwd', '.'))
    ...
```

这避免了 P1 规范化和真源自行解析的重复/矛盾。`--git-hook-mode` CLI 入口自行构造等价 data（`cwd=rev-parse --show-toplevel`, `command='git commit'`），走同一逻辑。

> **规则源 vs 被检查对象解耦（INV-8，方案 A）**：真源代码始终从 **canonical 主仓**加载——
> Claude 工具层由 wrapper 保证（EDU_CLOUD_REPO/固定路径）；Git 层由 pre-commit 用 `$EDU_CLOUD_REPO/scripts/governance` 保证，
> 并以 `--repo` 传入被检查对象。它**检查的对象**始终是 `--repo`/`data['cwd']`（effective repo）的 staged index。
> `git -C worktree commit` 时，用主仓最新规则检查 worktree 的 staged index，绝不用 worktree 里可能过期的规则。

`tests/governance/test_module_governance_guard.py` 必须从这里 import：

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "governance"))
import module_governance_guard as g
```

删除对 `~/.claude/hooks` 的 import。

### P2-T2：yuanshou hook 改成薄包装

`/home/ops/yuanshou/hooks/module_governance_guard.py` 改成 wrapper，只负责加载 repo 真源。

要求：

1. 模块名不要叫 `module_governance_guard`，避免和 wrapper 自己冲突。
2. 路径优先级：`EDU_CLOUD_REPO` 环境变量 → 固定 canonical 主仓 `/home/ops/projects/edu-cloud`。
   **不要**用 `data['cwd']` / `cwd.name == 'edu-cloud'` 推导源码位置（回应 plan-review R2-F-002）：
   治理源码版本必须统一来自 canonical 主仓，与被检查的 effective repo 解耦。详见 INV-8。
3. 找不到真源时 fail-closed，而不是静默 allow。
4. 必须 lazy load：不要在 wrapper 模块 import 阶段加载真源或抛异常。`commit_guards.py` 会顶层 import 此 wrapper，import 阶段崩溃不会经过 dispatcher，也不会产生标准 deny 输出。
5. **mtime 缓存（v6.2 修复）**：每次 `check()` 都 `spec_from_file_location` + `exec_module` 会拖慢 P95 延迟。wrapper 必须缓存已加载的 source module，仅在 source 文件 mtime 变更时重新加载。

wrapper 示例：

```python
import importlib.util
import os
from pathlib import Path

_cached_mod = None
_cached_mtime = None


_CANONICAL_REPO = "/home/ops/projects/edu-cloud"


def _resolve_rule_source_repo() -> str:
    """规则源 repo：默认固定 canonical；EDU_CLOUD_REPO 仅在 realpath allowlist 内才接受（回应审查 H1）。
    不在 allowlist → fail-closed raise（不静默 fallback，避免掩盖"指向旧仓/假仓/实验仓"的意图）。
    CI/测试通过 EDU_GOVERNANCE_REPO_ALLOWLIST(':' 分隔) 显式追加白名单。"""
    env = os.environ.get("EDU_CLOUD_REPO")
    if not env:
        return _CANONICAL_REPO
    rp = os.path.realpath(env)
    allowed = {os.path.realpath(_CANONICAL_REPO)}
    allowed |= {os.path.realpath(x) for x in
                os.environ.get("EDU_GOVERNANCE_REPO_ALLOWLIST", "").split(":") if x}
    if rp not in allowed:
        raise RuntimeError(f"EDU_CLOUD_REPO not in allowlist (rule-source spoofing blocked): {rp}")
    return rp


def _source_path(data: dict) -> Path:
    # 治理源码（"用哪套规则"）始终来自 canonical 主仓，与 effective repo（"检查哪个 staged index"）解耦。
    # 不用 data['cwd'] 推导：worktree 是同项目的 checkout，跟随它会让旧 checkout 用旧规则（见 INV-8）。
    # H1：EDU_CLOUD_REPO 非任意覆盖，须 realpath allowlist，否则 fail-closed。
    repo = _resolve_rule_source_repo()
    return Path(repo) / "scripts" / "governance" / "module_governance_guard.py"


def _load_source(src: Path):
    spec = importlib.util.spec_from_file_location("_edu_cloud_module_governance_guard", src)
    if not spec or not spec.loader:
        raise RuntimeError(f"invalid module governance source spec: {src}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check(data, session_state, staged_info=None):
    global _cached_mod, _cached_mtime
    try:
        src = _source_path(data)   # H1: allowlist 不命中会 raise
    except Exception as e:
        return {"decision": "block", "reason": f"[module-governance-wrapper] rule source rejected: {e}"}
    if not src.exists():
        return {
            "decision": "block",
            "reason": f"[module-governance-wrapper] repo source missing: {src}",
        }
    st = src.stat()
    current_key = (str(src), st.st_mtime_ns, st.st_size)  # 用 ns + size，避免同秒两次编辑不刷新
    if _cached_mod is None or _cached_mtime != current_key:
        try:
            _cached_mod = _load_source(src)
            _cached_mtime = current_key
        except Exception as e:
            _cached_mod = None
            _cached_mtime = None
            return {
                "decision": "block",
                "reason": f"[module-governance-wrapper] repo source load failed: {e}",
            }
    return _cached_mod.check(data, session_state, staged_info=staged_info)
```

### P2-T3：增加 wrapper/source 测试

在 `yuanshou` 增加：

```python
def test_module_governance_wrapper_loads_repo_source(): ...
def test_module_governance_wrapper_missing_source_returns_block_not_import_crash(): ...
def test_module_governance_wrapper_caches_loaded_source_across_calls(): ...
def test_module_governance_wrapper_reloads_when_source_mtime_changes(): ...
def test_module_governance_wrapper_reloads_on_same_second_double_edit(): ...  # st_mtime_ns/size 才能捕获
```

在 `edu-cloud` 增加：

```python
def test_module_governance_source_importable_from_repo(): ...
def test_module_governance_source_trusts_effective_data_no_cd_reparse(): ...
def test_edu_cloud_repo_not_in_allowlist_fails_closed(): ...  # H1：fake/旧仓 EDU_CLOUD_REPO → block，不加载
def test_internal_aggregate_loads_from_sibling_not_target(): ...  # H2：--repo worktree 用 canonical 的 aggregate
def test_worktree_checkout_staged_index_does_not_fallback_to_worktree(): ...
def test_git_hook_mode_blocks_missing_module_md_inside_git_worktree(): ...
```

### P2 验收

```bash
cd /home/ops/projects/edu-cloud
python3 -m pytest tests/governance/test_module_governance_guard.py -q

cd /home/ops/yuanshou
python3 -m pytest tests/test_commit_guards.py -q
```

---

## Phase 3：补齐模块治理规则盲区

### P3-T1：存量模块缺 MODULE.md，任何触碰都 block

规则：

```text
如果模块目录在 HEAD 中存在，但 staged snapshot 中仍没有 MODULE.md，任何触碰都 block。
如果本次 staged 正在新增合法 MODULE.md，则允许继续校验 frontmatter 和派生产物。
```

### P3-T2：新增回归测试

在 `tests/governance/test_module_governance_guard.py` 加：

```python
def test_existing_module_without_module_md_any_touch_blocks(tmp_path): ...
def test_existing_module_without_module_md_allows_when_module_md_staged(tmp_path): ...
def test_new_module_without_module_md_blocks_from_git_hook_mode(tmp_path): ...
```

### P3-T3：派生产物检查保持 block

如果 `MODULE.md` 或模块目录有变更，而 `docs/governance/modules.yaml`、`dependency-graph.md`、`debt-report.md` 没刷新，必须 block。

同时更新 `debt-report.md` 文案：

```text
下次触碰时 hook 会 block
```

不能再写 ask。

### P3 验收

```bash
python3 -m pytest \
  tests/governance/test_module_governance_guard.py \
  tests/governance/test_aggregate_modules.py \
  -q
```

---

## Phase 4：Git pre-commit 层兜底（覆盖正常 commit；绕过形态见闸门矩阵）

> 依赖说明：`.githooks/pre-commit` 会调用 `aggregate_modules.py --check`。因此 P4-T2/P4-T3 的 hook 安装与本地安装检查，必须在 Phase 6 完成后执行。P4-T1 的 `--git-hook-mode` 可以先实现。

> **闸门覆盖矩阵（回应 plan-review R3-F-001 — 诚实边界，不夸大兜底）**：
>
> ```text
> 命令形态 \ 闸门        | Claude工具层(P1-T0/commit_guards) | Git层(.githooks/pre-commit)
> 正常 commit 缺 MODULE.md |  block（基于 effective staged）    |  block（基于 staged index）
> git add && commit        |  block（P1-T0）                    |  pre-commit 见最终 staged → block
> git commit --no-verify/-n|  block（P1-T0 命令文本）           |  ✗ 被 --no-verify 设计性跳过
> -c core.hooksPath=/dev/null commit | block（P1-T0 命令文本）  |  ✗ hooksPath 被改，pre-commit 不触发
> 外部 --git-dir commit    |  block（P1-T0）                    |  ✗ 可能不触发本 repo hook
> ```
>
> **关键诚实结论**：`--no-verify` / `core.hooksPath` / 外部 `--git-dir` 这三类绕过，**只有经 Claude 工具层时**
> 被 P1-T0 拦（它看的是命令文本，与 git 是否执行 hook 无关）。**终端直接敲、不经 Claude** 时，
> P1-T0 不触发、Git 层又被设计性跳过 → 两层皆漏，**对这些形态 fail-open**。
> 这是已知架构残留（见 test_debt TD-4 与「明确不做」），本计划范围内**不声称**能拦终端直接绕过；
> 根治需 server 端 receive hook 或远程 required check，另立计划。Phase 4 的 Git 层定位是
> "覆盖正常 commit 的本地兜底"，不是"绕过形态的兜底"。

### P4-T1：新增 `--git-hook-mode`

`edu-cloud/scripts/governance/module_governance_guard.py` 支持：

```bash
python3 scripts/governance/module_governance_guard.py --git-hook-mode
```

支持 `--repo <被检查 repo>` 参数（方案 A：规则源/对象分离）。

行为：

1. **规则源** = 本脚本自身所在 repo（始终由 canonical 主仓调用，见 P4-T2）。
2. **被检查对象** `target` = `--repo` 参数值；缺省回退 `git rev-parse --show-toplevel`。
3. 读取 target 的最终 staged index：`git -C <target> diff --cached --name-only` 和 `-U0`。
4. 调用 `check({"cwd": target, "tool_input": {"command": "git commit"}}, None, staged_info=...)`。
5. `decision == block` 时 stderr 打印 reason，exit 1；allow 时 exit 0。

`--repo` 信任边界：只接受 pre-commit 传入的 `git rev-parse` 结果，非用户可信输入面
（能改 pre-commit 的人本就能绕过 Git 层，见闸门矩阵 TD-4）。

### P4-T2：版本化 Git hook

新增：

```text
.githooks/pre-commit
scripts/install-governance-hooks
```

`.githooks/pre-commit`：

```bash
#!/usr/bin/env bash
set -euo pipefail
# 方案 A：规则源永远 canonical 主仓，被检查对象是当前 repo（贯彻 INV-8 到 Git 层）
canonical="/home/ops/projects/edu-cloud"
src="${EDU_CLOUD_REPO:-$canonical}"
# H1：EDU_CLOUD_REPO 仅当 realpath 命中 allowlist（canonical 或显式 EDU_GOVERNANCE_REPO_ALLOWLIST）才接受
if [ "$(realpath "$src")" != "$(realpath "$canonical")" ]; then
  case ":${EDU_GOVERNANCE_REPO_ALLOWLIST:-}:" in
    *":$(realpath "$src"):"*) : ;;  # 在白名单
    *) echo "[pre-commit] EDU_CLOUD_REPO not in allowlist: $src — refusing (fail-closed)" >&2; exit 1 ;;
  esac
fi
target="$(git rev-parse --show-toplevel)"
gov="$src/scripts/governance"

# fail-closed：canonical 规则源缺失/未 checkout 时，拒绝 commit（绝不静默放行）
if [ ! -f "$gov/module_governance_guard.py" ] || [ ! -f "$gov/aggregate_modules.py" ]; then
  echo "[pre-commit] canonical governance source missing under: $gov" >&2
  echo "[pre-commit] refusing commit (fail-closed). 检查 EDU_CLOUD_REPO 或主仓 checkout。" >&2
  exit 1
fi

python3 "$gov/module_governance_guard.py" --git-hook-mode --repo "$target"
python3 "$gov/aggregate_modules.py" --check --staged --repo "$target"
```

> 方案 A 取舍（已知并接受）：
> - pre-commit 不再自包含，硬依赖 canonical 主仓路径 → 上面 fail-closed 兜底（缺失即拒绝，不放行）。
> - canonical 主仓必须保持权威分支最新（A 的前提；主仓即开发主线，成立）。
> - worktree 基于旧 base 的改动会被主仓最新规则检查 → 规则统一最新（INV-8 设计意图），体感上更严，属预期。
>
> pre-commit 只信 staged index：`--git-hook-mode` 与 `--check --staged` 都不读 working tree。
> CI 阶段（Phase 7）规则源==checkout==canonical，三者等价，用普通 `--check`。

`scripts/install-governance-hooks`：

```bash
#!/usr/bin/env bash
set -euo pipefail
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
printf 'governance hooks installed: core.hooksPath=.githooks\n'
```

### P4-T3：安装状态检查

`codex-verify governance` 本地模式检查：

```bash
git config --get core.hooksPath
```

如果不是 `.githooks`，本地失败并提示运行：

```bash
scripts/install-governance-hooks
```

CI 不要求本地 git config 已设置，但必须直接运行 `.githooks/pre-commit` 的等价检查。

### P4 验收

> 前置（回应审查 finding 3）：pre-commit 内含 `aggregate --check --staged`，对 clean 的期望必须在
> Phase 5 债务清理之后；在此之前 pre-commit 对"缺 MODULE.md"返回非 0 是**预期正确**（正是它该拦的）。

```bash
scripts/install-governance-hooks
python3 scripts/governance/module_governance_guard.py --git-hook-mode --repo "$(git rev-parse --show-toplevel)"
```

并手工验证：

```text
staged 新模块缺 MODULE.md
执行 git commit
期望：Git pre-commit 阻断
```

---

## Phase 5：清理当前 exam_import 债务

### P5-T1：修复裸 `.school_id`

当前位置：

```text
src/edu_cloud/modules/exam_import/router.py:32
src/edu_cloud/modules/exam_import/router.py:46
```

推荐修法：端点注入 `TenantContext`。

```python
from edu_cloud.core.auth import get_tenant_context
from edu_cloud.core.tenant import TenantContext

async def create_import(..., tenant: TenantContext = Depends(get_tenant_context)):
    school_id = tenant.require_school()
```

要求：

1. 所有入口用 `tenant.require_school()`。
2. 保留 `ExamImportSession.school_id == school_id` 查询过滤。
3. 对 platform_admin / district_admin 这种 `school_id is None` 场景返回 403。
4. 增加行为测试覆盖 403。
5. `tests/governance/test_tenant_static.py` 必须通过。

### P5-T2：补 `exam_import/MODULE.md`

新增：

```text
src/edu_cloud/modules/exam_import/MODULE.md
```

frontmatter：

```yaml
---
name: exam_import
status: active
owner: backend
layer: business
owns_tables:
  - exam_import_sessions
owns_routes:
  - /api/v1/exam-imports
exposes:
  services:
    - match_students
    - commit_import
    - run_post_import_pipeline
depends_on:
  modules:
    - exam
    - student
    - scan
    - grading
    - profile
  services: []
  ai_tools: []
structure_pattern: standard
max_router_loc: 400
routers:
  - router.py
created: 2026-05-19
last_reviewed: 2026-06-04
design_docs:
  - docs/plans/2026-05-19-exam-import-pipeline-design.md
---

# exam_import

## 职责

导入外部联考 Excel/ZIP 成绩数据，完成解析、学生匹配、考试写入、导入状态追踪和导入后快照处理。
```

### P5-T3：刷新派生产物

```bash
python3 scripts/governance/aggregate_modules.py
```

必须更新：

```text
docs/governance/modules.yaml
docs/governance/dependency-graph.md
docs/governance/debt-report.md
```

### P5 验收

```bash
python3 -m pytest tests/governance/ -q
python3 scripts/governance/aggregate_modules.py --check
```

---

## Phase 6：`aggregate_modules.py --check` 强制模式

### P6-T1：行为规格

`--check` 生成临时输出，不写磁盘。

**staged-aware（v6.2 修复）**：必须支持 `--check --staged`。

```text
--check          基于 working tree 聚合 MODULE.md，与已落盘派生产物比对（CI / 本地手动用）。
--check --staged 基于 staged index（git diff --cached / git show :<path>）聚合，
                 与 staged 的派生产物比对。pre-commit 必须用此模式。
--repo <path>    指定被检查/被聚合的目标 repo（缺省=git rev-parse --show-toplevel）。
                 方案 A：脚本本体（规则源）由 canonical 主仓调用，--repo 只定位被检查对象。
```

原因：pre-commit 阶段 working tree 可能和 staged index 不一致（部分 stage、stage 后又改）。
若 pre-commit 跑 working-tree `--check`，会基于未提交的 working tree 误判，放过或错杀。
`--staged` 模式只信 staged 内容，与 `module_governance_guard.py --git-hook-mode` 的"只信 staged index"契约一致。

退出码：

```text
0: clean，派生产物新鲜，无冲突，无债务
1: stale，派生产物与生成结果不同
2: parse error，MODULE.md frontmatter 非法
3: conflict，owns_tables / owns_routes 冲突
4: debt，仍有模块缺 MODULE.md
```

优先级：

```text
parse error > conflict > debt > stale > clean
```

### P6-T2：测试

在 `tests/governance/test_aggregate_modules.py` 加：

```python
def test_check_exit_0_clean(tmp_path): ...
def test_check_exit_1_stale(tmp_path): ...
def test_check_exit_2_parse_error(tmp_path): ...
def test_check_exit_3_conflict(tmp_path): ...
def test_check_exit_4_debt(tmp_path): ...
def test_check_no_write(tmp_path): ...
def test_check_staged_uses_index_not_working_tree(tmp_path): ...  # working tree 脏时仍只看 staged
```

### P6-T3：更新 CLI 文档

更新 `scripts/governance/aggregate_modules.py` 顶部退出码说明，避免旧语义误导。

### P6 验收

> 分两段（回应审查 finding 3）：
> - **能力验收**（P6 自身完成时）：exit 4 / 1 / 2 / 3 / 0 各分支有测试证明（见 P6-T2）。
>   此时 exam_import 债务可能仍在 → `--check` 返回 exit 4 是**预期正确行为**，不算 P6 失败。
> - **clean 验收**（仅在 Phase 5 债务清理后）：`--check` 返回 exit 0。

```bash
# 能力验收（P6 完成即可跑）
python3 -m pytest tests/governance/test_aggregate_modules.py -q
# clean 验收（必须在 Phase 5 清 exam_import 之后才期望 exit 0）
python3 scripts/governance/aggregate_modules.py --check   # 债务清理前=exit4(预期)；清理后=exit0
```

---

## Phase 7：CI 与本地收口

### P7-T1：GitHub Actions governance（追加，不替换）

> **严禁替换现有 `governance` job（v6.2 修复）**。当前 `.github/workflows/test.yml` 的 `governance` job
> 已经跑：`test_codex_scripts.py`、`codex-check --no-network`、`meta-check --json --strict`、
> `codex-context --no-network`、`codex-consult-claude --dry-run`、`codex-verify safety --repo-wide`、
> `codex-verify full --dry-run`。这些是元守/安全 CI，**一条都不能删**。
>
> 正确做法二选一：
> (a) 新增独立 `module-governance` job（推荐，隔离清晰）；
> (b) 在现有 `governance` job 末尾**追加**模块治理步骤。
>
> 不论哪种，diff 必须是纯增量；review 时确认原有 7 条 codex/meta/safety 步骤一字未动。

新增 job 示例（方案 a）。优先保持轻量；如果根 `tests/conftest.py` 拉起 app/native 依赖导致失败，再按实际报错补系统库：

```yaml
module-governance:        # 新增，与现有 governance job 并存
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    # 系统库（libgl1/libzbar 等）仅在实测因 conftest 拉起 native 依赖时补充安装
    # 当前治理测试不涉及 pymupdf/cv2，优先保持轻量；如 CI 失败再按实际报错补
    - run: pip install -e ".[dev]"
    - run: python -m py_compile scripts/governance/aggregate_modules.py scripts/governance/module_governance_guard.py scripts/codex-verify
    - run: python -m pytest tests/governance/ -q
    - run: python scripts/governance/aggregate_modules.py --check
    # pre-commit 等价 smoke（回应审查 finding 2）：CI 必须真跑 pre-commit 实际执行的两条命令，
    # 否则"CI 验证 pre-commit 等价"是空话。构造 staged 负例，断言缺 MODULE.md 会失败。
    - name: pre-commit equivalence smoke (negative + positive)
      run: |
        set -eu
        export EDU_CLOUD_REPO="$PWD"   # 规则源=canonical(=checkout)，命中 H1 allowlist
        tmp="$(mktemp -d)"; git -C "$tmp" init -q
        # H3：用【不带下划线】的模块名，否则 aggregate _render_debt 跳过 _ 开头目录 → 假阴性
        mod="$tmp/src/edu_cloud/modules/ci_newmod"
        mkdir -p "$mod"; echo "x=1" > "$mod/__init__.py"
        git -C "$tmp" add -A

        # --- 负例：缺 MODULE.md，必须以【确定的失败语义】被拦，不能用裸 ! 吞崩溃 ---
        set +e
        python scripts/governance/aggregate_modules.py --check --staged --repo "$tmp"; agg_rc=$?
        guard_out="$(python scripts/governance/module_governance_guard.py --git-hook-mode --repo "$tmp" 2>&1)"; guard_rc=$?
        set -e
        test "$agg_rc" -eq 4    || { echo "expected aggregate exit 4 (debt), got $agg_rc"; exit 1; }
        test "$guard_rc" -ne 0  || { echo "expected guard non-zero on missing MODULE.md"; exit 1; }
        echo "$guard_out" | grep -qi "MODULE.md" || { echo "guard reason must mention MODULE.md; got: $guard_out"; exit 1; }

        # --- 正例：补合法 MODULE.md + staged 派生产物后，两条命令必须 exit 0 ---
        # （MODULE.md 内容用最小合法 frontmatter；派生产物用 canonical aggregate 生成到 $tmp 后 stage）
        cat > "$mod/MODULE.md" <<'MD'
---
name: ci_newmod
status: active
owner: backend
layer: business
owns_tables: []
owns_routes: []
exposes: {services: []}
depends_on: {modules: [], services: [], ai_tools: []}
---
# ci_newmod
## 职责
CI smoke 正例模块。
MD
        # 在 $tmp 内用 canonical 规则生成派生产物（aggregate 支持 --repo 写盘到 target）后 stage
        python scripts/governance/aggregate_modules.py --repo "$tmp" || true
        git -C "$tmp" add -A
        python scripts/governance/aggregate_modules.py --check --staged --repo "$tmp"
        python scripts/governance/module_governance_guard.py --git-hook-mode --repo "$tmp"
```

### P7-T2：`scripts/codex-verify governance`

新增子命令：

```bash
scripts/codex-verify governance
```

执行（必须与 pre-commit 实际命令同口径 — 回应审查 finding 2）：

```bash
python3 -m pytest tests/governance/ -q
python3 scripts/governance/aggregate_modules.py --check
python3 scripts/governance/aggregate_modules.py --check --staged --repo "$(git rev-parse --show-toplevel)"
python3 scripts/governance/module_governance_guard.py --git-hook-mode --repo "$(git rev-parse --show-toplevel)"
```

本地默认检查：

```bash
git config --get core.hooksPath == .githooks
```

允许 CI 跳过本地 hook 安装检查：

```bash
scripts/codex-verify governance --ci
```

### P7 验收

```bash
scripts/codex-verify governance
scripts/codex-verify governance --ci
```

CI push 后 governance job 必须变绿。

---

## Phase 8：MODULE.md schema hardening + 历史数据迁移（回应审查 M1）

> 目标：让"有 MODULE.md"等于"治理语义完整"，而不是"字段存在但是空的"。
> **硬约束**：schema 加严会让 20 个历史 `owns_routes` 空值/`""` 立即校验失败，
> 因此**历史迁移必须与加严同批提交**，否则一加严全仓 `--check` 返回 exit 2（parse error）。

### P8-T1：parse_module_md schema hardening

在 `scripts/governance/aggregate_modules.py` 的 `parse_module_md` 增加（在现有枚举/nested 校验之后）：

```text
1. name == 目录名：meta['name'] 必须等于 MODULE.md 所在模块目录名，否则 ModuleGovernanceError。
2. 必填列表字段必须是 list[str]：owns_tables / owns_routes /
   depends_on.modules / depends_on.services / depends_on.ai_tools
   —— 不是 list 或元素非 str → error（杜绝 owns_routes: "" / None / 标量）。
3. owner 必须是非空 str。
4. 重复 module name：aggregate_all 聚合时若两个目录 name 相同 → 冲突 error（exit 3 类）。
```

### P8-T2：历史数据迁移（与 P8-T1 同批）

```text
扫描 src/edu_cloud/modules/*/MODULE.md，把 owns_routes / owns_tables / depends_on.* 的
空值（"" / None / 缺省标量）规范化为 []：当前已知 20 处 owns_routes 空值（含 adaptive 的 owns_routes: ""）。
迁移脚本一次性改写，人工核对 diff（确认这些模块确实无 owns_routes，不是漏填）。
```

### P8-T3：测试

在 `tests/governance/test_aggregate_modules.py` 加（每条新校验正反例）：

```python
def test_name_must_equal_dirname(tmp_path): ...
def test_name_mismatch_dirname_raises(tmp_path): ...
def test_owns_routes_empty_string_raises(tmp_path): ...        # owns_routes: "" → error
def test_owns_routes_none_raises(tmp_path): ...
def test_list_fields_must_be_list_of_str(tmp_path): ...
def test_owner_must_be_nonempty_str(tmp_path): ...
def test_duplicate_module_name_conflicts(tmp_path): ...
def test_migrated_history_all_parse_clean(tmp_path): ...        # 迁移后全仓 parse 无 error
```

### P8 验收

```bash
python3 -m pytest tests/governance/test_aggregate_modules.py -q
# 迁移 + 加严后，全仓 parse 干净（无 exit 2）；债务清理后整体 clean
python3 scripts/governance/aggregate_modules.py --check
```

---

## 执行顺序

以下顺序以依赖关系为准，不按 phase 编号机械执行。

> **顺序铁律（回应审查 finding 3）**：先实现 `--check` 能正确返回 exit 4（用测试证明 debt 检测能力，
> 此阶段**不要求** clean）；guard 修好后**立刻清 exam_import 债务并刷新派生产物**；
> **最后**才要求 `--check` / pre-commit **clean**。否则债务还在时要求 clean 必然失败（exam_import 缺 MODULE.md）。

```text
1. yuanshou: 修 commit_guards P1-T0 命令级前置硬阻断(stage+commit/--no-verify/hooksPath/kill-switch inline) + effective repo 解析 + 测试
2. edu-cloud: 建 module_governance_guard repo 真源(移除 _kill_switch) + yuanshou wrapper
3. edu-cloud: 补模块治理规则盲区和 --git-hook-mode --repo
4. edu-cloud: 实现 aggregate --check / --check --staged --repo 的 exit 4 能力 + 测试证明（不要求 clean）
5. edu-cloud: 清 exam_import 债务（school_id + MODULE.md）+ 刷新 docs/governance（此后才可能 clean）
6. edu-cloud: 增加 .githooks/pre-commit 和安装脚本（依赖第 4 步 --check + 第 5 步 clean）
7. edu-cloud: MODULE.md schema hardening + 历史 owns_routes 空值迁移（同批，Phase 8）；迁移后全仓 parse 干净
8. edu-cloud: CI governance(含 pre-commit 等价 smoke 正反例) + codex-verify governance；要求全链路 clean
```

> Phase 8（schema hardening）排在 guard 修好（1-3）、--check 能力（4）、债务清理（5）之后：
> 加严 + 历史迁移同批，先让全仓 parse 干净，再要求 CI/pre-commit 全链路 clean（第 8 步）。

不要先清 `exam_import` 债务于 guard 之前。必须先让 guard 能在真实 commit repo 上看见 staged index；
但 `--check` 的 **clean 验收**必须排在债务清理（第 5 步）**之后**，第 4 步只证明 exit 4 能力。

---

## 最终验收清单

### yuanshou 验收

```bash
cd /home/ops/yuanshou
python3 -m pytest tests/test_commit_guards.py -q
```

必须覆盖：

```text
cd /repo && git commit 使用 /repo staged index
git -C /repo commit 使用 /repo staged index
普通 git commit 使用 hook cwd 所在 repo root
hook cwd 与 effective repo 不一致时仍 block
同命令 stage+commit 被 block（add/rm/mv/restore --staged/reset/update-index 六类，参数化覆盖）
git commit --no-verify / -n 被 block
git -c core.hooksPath=/dev/null commit 被 block
无法解析 effective repo 时 fail-closed
cd /repo && git commit -m "msg" 规范化后保留 -m "msg"（heredoc message 不被破坏）
```

### edu-cloud 验收

```bash
cd /home/ops/projects/edu-cloud
python3 -m pytest tests/governance/ -q
python3 scripts/governance/aggregate_modules.py --check
scripts/install-governance-hooks
scripts/codex-verify governance
```

### 运行时 hook 路径验收（回应 plan-review R4-F-003）

仓内 wrapper/source 测试通过 ≠ 真实 PreToolUse 已加载新 wrapper。必须验证运行时实际生效路径：

```text
1. 确认 ~/.claude/hooks/module_governance_guard.py 已是 wrapper 版本（symlink→yuanshou，git status 在 yuanshou 仓核对）。
2. python3 -c "import importlib.util,sys; \
     spec=importlib.util.spec_from_file_location('w','/home/ops/.claude/hooks/module_governance_guard.py'); \
     m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); \
     print('check loaded:', hasattr(m,'check'))"   # 必须 True 且不抛异常
3. 真实触发一次：在 edu-cloud staged 缺 MODULE.md 新模块，经 Claude 走 git commit，
   确认 hook-events.jsonl 记录 commit_guards 链路命中 module_governance（deny），且来源是 repo 真源（非旧 ~/.claude/hooks 内联逻辑）。
4. 确认 commit_guards.py 顶层 import wrapper 不崩溃（P2-T2 lazy load 要求的运行时证据）。
```

### 事故回归验收

构造以下场景必须 block：

```text
hook cwd = /home/ops/projects/edu-cloud/.claude/worktrees/some-agent
command = cd /home/ops/projects/edu-cloud && git commit -m ...
/home/ops/projects/edu-cloud staged 新模块缺 MODULE.md
```

### 当前债务验收

```text
exam_import 有合法 MODULE.md
docs/governance/modules.yaml 包含 exam_import
docs/governance/debt-report.md 无债务
test_tenant_static.py 通过
```

---

## 明确不做

| 项目 | 理由 |
|------|------|
| 重写整个 dispatcher | 当前根因可由 effective repo + fail-closed 策略解决 |
| 继续依赖手动 hard copy | 会制造双真源漂移 |
| 只靠 CI 事后检查 | CI 太晚，必须有 Git pre-commit 本地兜底 |
| 先清 exam_import 债务 | 会破坏事故回归证据，必须先补 guard |
| release-prod 统一闸门 | 可另立结构性安全计划，本计划只收口模块治理 |
| 根治终端直接绕过（--no-verify/hooksPath，不经 Claude） | 需 server 端 receive hook 或远程 required check；本计划只在 Claude 工具层拦（TD-4） |
| 保留 EDU_GOVERNANCE_GUARD_DISABLED kill switch 作 break-glass | 环境变量可继承、可 inline 注入、无审计 → 修复期移除；未来 break-glass 须显式+审计+不可命令注入，另立 |

---

## 风险与回滚

### 风险 1：effective repo 解析误伤复杂命令

策略：复杂命令 fail-closed，提示用户进入目标 repo 后单独执行 `git commit`。

### 风险 2：Git hook 安装影响本地开发

策略：`.githooks` 版本化，`scripts/install-governance-hooks` 显式安装；必要时可 `git config --unset core.hooksPath` 回滚。

### 风险 3：yuanshou 和 edu-cloud 分仓导致测试割裂

策略：

```text
yuanshou 测调度器行为
edu-cloud 测模块治理规则
wrapper 测加载 repo 真源
```

不允许用 edu-cloud CI 假装覆盖 yuanshou hook 调度器。

### 风险 4：yuanshou 命令级 guard / wrapper 跨仓改动误伤（回应 plan-review F-004）

P1 改 `/home/ops/yuanshou/hooks/commit_guards.py`、P2 改 `~/.claude/hooks/module_governance_guard.py`（薄包装），
这两处不在 edu-cloud 仓，`.githooks`/`core.hooksPath` 回滚覆盖不到。跨仓回滚边界：

```text
RM-1 commit_guards 误伤（误拦合法 commit / 解析崩溃）：
  在 yuanshou 仓 git revert 对应 commit，或 git checkout 上个版本的 hooks/commit_guards.py。
  紧急可临时注释 main() 中 P1-T0 的 _command_only_precheck 调用，保留其余链路。

RM-2/RM-3 wrapper / 真源迁移误伤（import 崩溃 / 真源找不到 / fail-closed 全拦）：
  ~/.claude/ 核心目录 symlink → ~/yuanshou，wrapper 实际位于 yuanshou 仓。
  在 yuanshou 仓 git revert 迁移 commit，即恢复迁移前的 module_governance_guard.py。
  edu-cloud 侧 scripts/governance/ 为新增文件，revert 对应 commit 后这些新增文件随之消失，不影响存量。
```

回滚顺序：先恢复 yuanshou（commit 通道立即恢复），再处理 edu-cloud 新增文件。
每个 phase 独立 commit（总体原则 6）是跨仓回滚的前提——确保可逐 phase revert。

---

## Contract Pack（机器可审计 — 回应 plan-review F-002/F-003）

### invariants（不变量，实现/审查逐条映射）

```text
INV-1  commit_guards 永远基于 effective repo 的 staged index 判定，绝不基于 hook cwd。
INV-2  能绕过 commit 闸门的命令形态（stage+commit / --no-verify / -n / -c core.hooksPath / 外部 --git-dir /
       EDU_GOVERNANCE_GUARD_DISABLED= inline）在 P1-T0 命令级 precheck 被 deny，发生在 resolve 与任何
       git diff --cached 之前；其中 kill switch 的【继承形式】由 P2-T1 在真源移除 _kill_switch() 根治。
       P1-T0 扫描基于命令结构（选项/env 赋值位置），绝不扫 commit message 体，避免误拦。
INV-3  staged snapshot 只信 git index；worktree 的 .git 是文件时不 fallback 到 worktree。
INV-4  模块治理逻辑单一真源在 edu-cloud/scripts/governance/，yuanshou hook 仅薄包装。
INV-5  pre-commit（--git-hook-mode）与 aggregate --check --staged 只读 staged index，不读 working tree。
INV-6  CI 模块治理为纯增量；原有 codex/meta/safety 7 步一字不删。
INV-7  command normalizer 保留 commit 后原始字节（heredoc/review-waiver/doc 前缀不破坏）。
INV-8  治理「规则源」与「被检查对象」全层解耦（方案 A）：**两道闸门的规则源都来自 canonical 主仓**——
       Claude 工具层 wrapper 从 EDU_CLOUD_REPO/固定路径加载；Git 层 pre-commit 用 $EDU_CLOUD_REPO/scripts/governance
       并以 --repo 指定被检查对象。effective repo / --repo 只决定读哪个 staged index，绝不决定用哪套规则。
       worktree（同项目 checkout）即便过期也不得决定规则版本；规则统一最新，对象按 effective repo 定位。
       前提：canonical 主仓保持权威分支最新；规则源缺失时 fail-closed（pre-commit 拒绝 commit）。
       规则源是「module_governance_guard.py + 同目录 aggregate_modules.py」整体（H2）：内部 aggregate 必须从
       sibling(Path(__file__).parent) 加载，绝不从 target/worktree 导入。EDU_CLOUD_REPO 非任意覆盖（H1）：
       须 realpath 命中 allowlist（canonical 或显式 EDU_GOVERNANCE_REPO_ALLOWLIST），否则 fail-closed，
       防止指向旧仓/假仓/实验仓加载错误规则。
```

### counter_examples（反例 — 每条必须被对应机制拦截 / 保持）

```text
CE-1  hook cwd=worktree, command=cd <main> && git commit, main staged 缺 MODULE.md
        => commit_guards block（事故回归，对应 INV-1）
CE-2  git add X && git commit                       => P1-T0 deny（INV-2）
CE-3  git commit --no-verify / git commit -n        => P1-T0 deny（INV-2）
CE-4  git -c core.hooksPath=/dev/null commit         => P1-T0 deny（INV-2）
CE-5  git -C <main> commit（缺 MODULE.md）            => 进入 commit_guards 并用 <main> staged（INV-1）
CE-6  worktree 内 git commit，.git 为文件             => staged snapshot 不 fallback 到 worktree（INV-3）
CE-7  git commit -m "$(cat <<'EOF' ...review-waiver... EOF)"
        => normalizer 不破坏 message，子 guard 仍识别 waiver（INV-7）
CE-8  working tree 脏但 staged 干净的派生产物          => aggregate --check --staged 只看 staged（INV-5）
CE-9  EDU_GOVERNANCE_GUARD_DISABLED=1 git commit（inline）=> P1-T0 deny；且真源已无 _kill_switch()，
        继承形式（已 export）也不放空 guard（INV-2 / INV-4）
CE-10 git commit -m "...含 -n / --no-verify 字样..."      => 不被误拦（结构化扫描，INV-2）
```

### risk_modules（高风险改动面 — 审查重点 + 回滚边界见风险段）

```text
RM-1  /home/ops/yuanshou/hooks/commit_guards.py        新增 P1-T0 precheck + effective repo 解析（改动核心）
RM-2  ~/.claude/hooks/module_governance_guard.py        改薄包装（symlink→yuanshou；import 时序 + lazy load 风险）
RM-3  edu-cloud/scripts/governance/module_governance_guard.py  新真源（330 行迁移 + git rev-parse 替换 .git 目录判断）
RM-4  edu-cloud/scripts/governance/aggregate_modules.py  新增 --check --staged（staged 读取分支）
RM-5  edu-cloud/.githooks/pre-commit                     新兜底（绕过类命令在此层无效，依赖 P1-T0）
RM-6  edu-cloud/.github/workflows/test.yml               CI 追加（误删原 7 步的风险）
RM-7  edu-cloud/scripts/install-governance-hooks           改本地 git core.hooksPath（误伤开发环境风险；回滚 git config --unset）
RM-8  edu-cloud/scripts/codex-verify（governance 子命令）  完成证据入口（误报 PASS 的风险；须与 pre-commit/CI 同口径）
RM-9  scripts/governance/aggregate_modules.py:parse_module_md  schema hardening（加严会使历史空值失败，须同批迁移）
RM-10 src/edu_cloud/modules/*/MODULE.md（20 处 owns_routes 空值）  历史迁移面（改写空值→[]，人工核对非漏填）
```

### test_debt（已知未覆盖 / 显式接受的边界）

```text
TD-1  复杂 shell（变量 / 子 shell / 函数 / 管道 / 多段 cd）只 fail-closed，不追求解析全语法。
TD-2  yuanshou 与 edu-cloud 分仓，无单一 CI 同时覆盖二者；靠两仓各自测试 + wrapper 加载测试组合保证。
TD-3  break-glass（合法绕过 commit 闸门）本计划不实现，见「明确不做」；修复期一律 deny。
      旧 EDU_GOVERNANCE_GUARD_DISABLED kill switch 已在 P2-T1 移除，不保留为 break-glass 通道。
TD-4  终端直接（不经 Claude）执行 git commit --no-verify / -n / -c core.hooksPath=/dev/null / 外部 --git-dir：
      P1-T0 不触发 + Git 层被设计性跳过 → 两层皆漏，fail-open。本计划不解决，根治需
      server 端 receive hook 或远程 CI required check（见「明确不做」）。
```

### plan-review WONTFIX 记录（设计者裁定 — L017 全局优先）

```text
R4-F-001（模块覆盖 1/22，要求 Phase -1 手抄 22 模块全集）→ WONTFIX
  证据反驳：
  - aggregate_modules.py 遍历 src/edu_cloud/modules/* 全量，--check fail on debt（P6）对所有模块生效；
  - 22 模块中 21 已有 MODULE.md，唯一债务 exam_import 已由 P5 清理 + Phase 3 规则盲区覆盖；
  - 「逐个模块基线」由 aggregate --check 机械保证，无需在计划文本手抄模块名（手抄反而引入漂移源）。
  - 此 finding 连续多轮以形式覆盖率口径重复提出，判定为形式要求，不纳入。
```

### test_contracts（核心回归 5 字段契约 — 防弱 oracle 蒙混）

> 仅对最高危反例展开 5 字段；其余测试以函数名 + docstring + 上述 counter_examples 为准。

```text
TC-CE1（事故回归）
  setup:      临时 main repo staged 新模块缺 MODULE.md；hook cwd 设为另一 worktree 目录
  action:     commit_guards.main(data={cwd:worktree, command:'cd <main> && git commit'})
  assertion:  decision == 'block' 且 reason 含 module-governance
  neg_oracle: 把 MODULE.md 一并 staged 后，同输入必须 allow（证明不是无脑 block）
  entrypoint: yuanshou/tests/test_commit_guards.py

TC-CE3（--no-verify）
  setup:      任意 git commit 命令文本附 --no-verify / -n
  action:     commit_guards.main(command='git commit --no-verify')
  assertion:  decision == 'block'，且阻断发生在 _resolve_effective_repo 调用之前（mock 断言未被调用）
  neg_oracle: 去掉 --no-verify 的普通 commit 不被 P1-T0 拦（证明只拦绕过形态）
  entrypoint: yuanshou/tests/test_commit_guards.py

TC-CE7（heredoc + waiver）
  setup:      command = git commit -m "$(cat <<'EOF'\n...# review-waiver: x\nEOF\n)"
  action:     _normalize_to_git_commit_with_args(command)
  assertion:  返回串含完整 heredoc message 与 review-waiver 标记（字节级保留）
  neg_oracle: 不得退化为 'git commit'；shlex.split 实现会破坏，必须失败
  entrypoint: yuanshou/tests/test_commit_guards.py

TC-CE8（staged-aware）
  setup:      repo working tree 改脏派生产物，但 staged 的派生产物与 staged MODULE.md 一致
  action:     aggregate_modules.py --check --staged
  assertion:  exit 0（clean）——只看 staged
  neg_oracle: 同 repo 跑 --check（无 --staged）因 working tree 脏返回非 0，证明两模式确有差异
  entrypoint: edu-cloud/tests/governance/test_aggregate_modules.py

TC-CE5（git -C 定位 effective repo）
  setup:      temp main repo staged 新模块缺 MODULE.md；hook cwd 设为不相关的第三目录
  action:     commit_guards.main(data={cwd:<第三目录>, command:'git -C <main> commit'})
  assertion:  _is_git_commit_command 判 True；effective repo == <main>；staged_info 来自 <main>；decision=='block'
  neg_oracle: <main> 补 MODULE.md 后同输入 allow——证明用的是 <main> 的 staged index，不是 hook cwd 也不是第三目录
  entrypoint: yuanshou/tests/test_commit_guards.py

TC-A（方案 A：Git 层规则源=canonical，对象=--repo）
  setup:      canonical 主仓含【新版】规则（如新增一条 frontmatter 校验）；worktree checkout 旧版规则（无该校验）；
              worktree staged 一个违反【新版】规则的 MODULE.md
  action:     在 canonical 跑 module_governance_guard.py --git-hook-mode --repo <worktree>
  assertion:  用【新版】规则检查 <worktree> staged → block（证明规则源来自 canonical 非 worktree）
  neg_oracle: 若实现用 $target/scripts/governance（worktree 旧规则）→ 漏掉新校验 → allow；该错误实现必须使测试失败
              fail-closed 验收：EDU_CLOUD_REPO 指向不存在路径时 pre-commit exit 1（不放行）
  entrypoint: edu-cloud/tests/governance/test_module_governance_guard.py

TC-CE6（worktree .git 为文件，不 fallback 到 worktree）
  setup:      git worktree add 建一个 worktree（其 .git 是【文件】，内容为 gitdir: 指针）；
              worktree 内 staged 新模块缺 MODULE.md
  action:     真源 staged snapshot helper 读取该 worktree（data['cwd']=worktree）
  assertion:  用 git -C <wt> rev-parse --is-inside-work-tree/--show-toplevel 正确识别；
              staged snapshot 来自 git index（checkout-index/git show :path），decision=='block'
  neg_oracle: 若实现用 (repo/'.git').exists() 目录判断 → worktree 的 .git 是文件 → 判非 repo → 错误 fallback 到
              worktree 文件树；该错误实现必须使本测试失败（断言 snapshot 来源是 index 而非 worktree readdir）
  entrypoint: edu-cloud/tests/governance/test_module_governance_guard.py

TC-CE2（stage+commit 同命令 — 参数化覆盖全部 6 类 staged mutation）
  setup:      pytest.mark.parametrize 覆盖 6 类 stage 动作与 commit 组成同命令：
                'git add <p> && git commit -m m'
                'git rm <p> && git commit -m m'
                'git mv <a> <b> && git commit -m m'
                'git restore --staged <p> && git commit -m m'
                'git reset <p> && git commit -m m'
                'git update-index --add <p> && git commit -m m'
  action:     commit_guards.main(command=每个参数)
  assertion:  6 个参数全部 decision=='block'；阻断由 P1-T0 经 dispatcher_emit；早于 _resolve_effective_repo
  neg_oracle: 拆成两条（先单独 stage，再单独 git commit）后，单独 git commit 不被 stage+commit 规则拦；
              且仅含 commit、不含上述 stage 动词的命令不误伤
  entrypoint: yuanshou/tests/test_commit_guards.py

TC-CE4（core.hooksPath 绕过）
  setup:      command = 'git -c core.hooksPath=/dev/null commit -m m'
  action:     commit_guards.main(command=上述)
  assertion:  decision=='block'（P1-T0 命令文本匹配 -c core.hooksPath）；早于 resolve
  neg_oracle: 不含 -c core.hooksPath 的普通 git commit 不被该规则拦（只拦绕过形态）
  entrypoint: yuanshou/tests/test_commit_guards.py

TC-CE9（kill switch — inline 拦 + 真源根治）
  setup:      (a) command='EDU_GOVERNANCE_GUARD_DISABLED=1 git commit -m m'
              (b) 迁移后的 repo 真源代码
  action:     (a) commit_guards.main(command=上述)；(b) grep 真源源码
  assertion:  (a) decision=='block'（P1-T0 inline 前缀匹配）；
              (b) 真源【不含】_kill_switch / EDU_GOVERNANCE_GUARD_DISABLED 分支（继承形式无放空通道）
  neg_oracle: 不含该 env 前缀的普通 commit 不被该规则拦；message 体含该字样不误拦（见 CE-10）
  entrypoint: yuanshou/tests/test_commit_guards.py + edu-cloud/tests/governance/test_module_governance_guard.py
```

---

## 计划完成判定

只有同时满足以下条件，才算修复完成：

1. 事故回归场景被 `commit_guards` block。
2. `git -C /repo commit` 进入 `commit_guards`，并使用 `/repo` 的 staged index。
3. 同命令 `git add && git commit` 被 block（由 P1-T0，经 dispatcher_emit）。
4. 经 Claude 工具层的 `git commit --no-verify` / `-n` / `-c core.hooksPath=...` /
   `EDU_GOVERNANCE_GUARD_DISABLED=1`（inline）被 P1-T0 block；且 repo 真源已移除 `_kill_switch()`，
   继承形式的 kill switch 也不放空 guard。终端直接绕过为已知残留（TD-4），本判定不声称覆盖。
5. Git worktree 中的 staged snapshot 不 fallback 到 worktree。
6. Git pre-commit 用 `--git-hook-mode --repo` + `aggregate --check --staged --repo`，规则源=canonical 主仓、
   对象=当前 repo，只信 staged index，能 block 缺 MODULE.md；canonical 源缺失时 fail-closed 拒绝 commit。
7. `tests/governance/` 全绿。
8. `aggregate_modules.py --check` / `--check --staged` clean，且 fail on debt 已有测试。
9. `exam_import` 债务清零。
10. CI 新增 module-governance 步骤运行完整治理测试和 `--check`，且**包含 pre-commit 等价 smoke**：
    负例（不带下划线模块名、缺 MODULE.md）断言 `aggregate --check --staged --repo` exit==4、
    guard 非 0 且 reason 含 "MODULE.md"；正例（补合法 MODULE.md + staged 派生产物）断言两条命令 exit 0。
    且原有 codex/meta/safety CI 一条未删。
11. `scripts/codex-verify governance`（含 `--check --staged --repo` 同口径）可作为本地完成声明前的统一收口。
12. `--check` 的 clean 验收在 exam_import 债务清理（Phase 5）之后才要求 exit 0；
    清理前返回 exit 4 是预期正确行为（finding 3）。
13. MODULE.md schema hardening 生效（name==dirname / 必填列表 list[str] / owner 非空 / 重复 name 冲突），
    且 20 处历史 owns_routes 空值已迁移为 []，迁移后全仓 parse 无 exit 2（M1）。
