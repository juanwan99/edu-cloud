# Yuanqi 并行 registry + gate 用法

本目录提供 P0a 的并行任务 registry 与 gate。目标是让多个 Yuanqi
任务可以按模块并行推进，同时用文件锁和任务声明阻止交叉污染。

锁源来自 task 的 `allowed_paths`、实际变更的 `changed_paths`，以及
`exclusive_claims` 展开的独占范围。锁源不再依赖 import edge；当前 import
edge 基线已经为 0，不能作为并行锁判定依据。

本 README 只说明 P0a 自包含用法。把 registry 接入
`docs/context/PARALLEL_DEVELOPMENT.md` 等上下文 wiring 留给后续 P0b。

## 建立一个 task

每个并行任务登记为一个 YAML 文件：

```text
.yuanqi/tasks/<id>.yml
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `task_id` | 任务唯一 ID，通常与文件名一致。 |
| `mode` | 任务模式：`read_only_audit`、`planning_only`、`docs_local`、`frontend_only`、`module_writer`、`integration_writer`、`exclusive`。 |
| `owner` | 执行者：`claude`、`codex` 或 `human`。 |
| `branch` | 任务分支名。 |
| `worktree` | 任务工作树绝对路径。 |
| `allowed_paths` | 允许写入的路径 glob。`scope_gate` 用它拦截越界变更。 |
| `exclusive_claims` | 独占声明，例如 `db_migration`、`permissions`、`runtime`、`central_docs`、`foundation`。 |
| `registry_closeouts` | 可选。当前任务允许一并关闭的旧 task id 列表；只放行对应 `.yuanqi/tasks/<id>.yml`，用于清理已完成但未闭锁的 stale active lock。 |
| `ports` | 任务占用端口映射；无端口时写 `{}`。 |
| `status` | `active` 或 `closed`。只有 `active` 任务参与并行冲突检查。 |
| `created_at` | 创建时间，使用带时区 ISO 字符串。 |
| `expires_at` | 过期时间，`registry_doctor` 用它发现 stale lock。 |

参考示例：

- `.yuanqi/tasks/examples/module_writer.yml`
- `.yuanqi/tasks/examples/exclusive.yml`
- `.yuanqi/tasks/examples/read_only_audit.yml`

## 模块用法

### `lock_map`

`lock_map` 负责把模块和独占声明转换成锁范围。

- 模块路径来自 `docs/governance/modules.yaml`。
- 模块数据表来自同一文件的 `owns_tables`。
- `exclusive_claims` 会展开成对应文件路径，例如迁移、权限、运行时、
  中央文档或 foundation 边界。

示例：

```bash
uv run python - <<'PY'
from scripts.yuanqi.lock_map import expand_exclusive, module_paths, module_tables

print(module_paths("grading"))
print(module_tables("grading"))
print(expand_exclusive("db_migration"))
PY
```

### `task_schema`

`task_schema` 校验 `.yuanqi/tasks/<id>.yml` 是否符合 registry schema。
缺字段、非法 `mode`、非法 `owner`、非法 `status`，或
`allowed_paths` / `exclusive_claims` 类型错误都会报错。

示例：

```bash
uv run python - <<'PY'
from pathlib import Path
from scripts.yuanqi.task_schema import load_and_validate

task = load_and_validate(Path(".yuanqi/tasks/examples/module_writer.yml"))
print(task["task_id"])
PY
```

### `overlap_gate`

`overlap_gate` 比较候选 task 与当前 active tasks 的锁集。两边锁集相交时
返回 deny；无写锁的 `read_only_audit` / `planning_only` 可以并行。

锁集由三部分组成：

- `allowed_paths`
- `changed_paths`
- `exclusive_claims` 展开后的路径

`changed_paths` 是共享层覆盖的关键。即使两个任务都声明为模块任务，只要实际
变更同时触碰共享层，例如 `services/`、`src/edu_cloud/core/` 或
`src/edu_cloud/api/`，锁集也会相交并被 deny，避免模块任务借共享层互相污染。

示例：

```bash
uv run python - <<'PY'
from scripts.yuanqi.overlap_gate import check

candidate = {
    "task_id": "candidate",
    "mode": "module_writer",
    "allowed_paths": ["src/edu_cloud/modules/grading/**"],
    "changed_paths": ["src/edu_cloud/core/permissions.py"],
    "exclusive_claims": [],
}
active = [{
    "task_id": "active",
    "mode": "module_writer",
    "status": "active",
    "allowed_paths": ["src/edu_cloud/modules/knowledge/**"],
    "changed_paths": ["src/edu_cloud/core/**"],
    "exclusive_claims": [],
}]

print(check(candidate, active).allowed)
PY
```

### `scope_gate`

`scope_gate` 是 CI 用的越界检查。它读取 PR 的 changed files 和对应 task，
任何变更文件不在 `allowed_paths` 或 `exclusive_claims` 展开范围内都会 fail。

示例：

```bash
uv run python scripts/yuanqi/scope_gate.py \
  --task .yuanqi/tasks/<id>.yml \
  --changed changed-files.txt
```

### `registry_doctor`

`registry_doctor` 扫描 `.yuanqi/tasks/`，发现 `status: active` 且
`expires_at` 已过期的 stale lock。它只告警，不修改 registry。

示例：

```bash
uv run python scripts/yuanqi/registry_doctor.py
```

## 典型并行工作流

1. 建立 `.yuanqi/tasks/<id>.yml`，声明 `mode`、`allowed_paths`、
   `exclusive_claims`、分支和 worktree。
2. 用 `task_schema` 校验 task 文件。
3. 用 `overlap_gate` 对候选 task 与当前 active tasks 做冲突检查；
   allow 后才开工。
4. 为任务创建独立 worktree，在声明范围内施工。
5. PR 进入 CI 后由 `scope_gate` 用 changed files 把关，越界变更 fail。
6. 任务完成后提交 closeout，并把 task 状态改为 `closed`。
7. 定期运行 `registry_doctor`，清理或续期 stale active locks。

## P0a 验收标准

1. 构造 grading 与 knowledge 两个真实模块 task，`overlap_gate` 应 allow；
   构造两个 grading task，`overlap_gate` 应 deny。
2. 构造越界 changed file，例如 grading task 修改 scan 范围文件，
   `scope_gate` 应 fail。
3. 构造已过期 active task，`registry_doctor` 应输出 stale-lock warning。
4. 这些 gate 不依赖 `meta-check --write-state` 或 guardian 状态；
   判定只依赖 GitHub changed files 与 `.yuanqi/tasks/` 文件 registry。
