[edu-cloud] Executor→Reviewer | 2026-04-14 09:06:54

## 审查交接单: Batch 2 Gate 2 Code Review Round 3 — B2-F001 Node floor 升级 + B2-F003 根因定论收窄

**Plan**: `docs/plans/2026-04-12-haofenshu-phase1-plan.md`
**R3 交接卡**: `docs/plans/2026-04-14-haofenshu-phase1-batch2-r3-handoff.md`
**R2 FAIL 报告**: `docs/plans/2026-04-12-haofenshu-phase1-review-report-batch2-r2.md`
**R2 Executor 自审**: `docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md`
**Tier**: T4（延续 Batch 2 R1→R2→R3 同一 T4 轨道）

---

### 逐 Task 自审

| Task / Finding | R3 交接卡要求 | 实际执行 | 状态 | 说明 |
|---------------|--------------|---------|------|------|
| B2-F001 方案 A (Node floor 升级) | `frontend-nuxt/package.json` 追加 `"engines": {"node": ">=22.12.0"}` | 已添加 engines 段（L4-6，type 之后、scripts 之前）；`frontend-nuxt/.nvmrc` 新建内容 `22.12.0` | ✅ | 与 handoff §1.2/§1.3 一致。behavior_change，user approved 2026-04-14 |
| B2-F001 runtime 切换 | Node 环境升到 `>=22.12.0` | Portable `node-v22.22.2-win-x64` 解压至 `~/bin/`，SHA256 官方匹配 `7c93e9d9...`；`~/.bashrc` 追加 PATH 前置；验证 `which node` = portable 路径，`node --version` = v22.22.2；系统 Node 20.18 保留未覆盖 | 🔀 | 改进记录：winget 方案 1603 失败（MsiSystemRebootPending=1 + 17+ node.exe 占用 `C:/Program Files/nodejs/node.exe`，Claude Code 自身为 Node 进程无法释放）；改走 portable zip + `~/.bashrc` PATH 前置，实现等价 ≥22.12 效果且不需重启/不污染系统 Node。**非仓库改动**：`~/.bashrc` 与 `~/bin/node-v22.22.2-win-x64/` 均在 edu-cloud 仓库外（`git ls-files --error-unmatch ../.bashrc` 报 outside repository） |
| B2-F003 顺手清理 (根因定论) | 删除 R2 handoff §6 "原表述"段，消除 `hot-reload` 引用 | 重写 §6 标题为「B2-F003 根因定论」，删除 "原表述 (R1 交接单 Step 3/4)" + block quote + "新表述 (R2 收窄)" 对比结构，改为直接陈述根因为 9000 进程陈旧 + GPT 取证段。同时改写 "根因范围修正" 段去除 `hot-reload` 字样 | ✅ | 两处 `hot-reload` 实体全删（L171 + L176），`grep -c "hot-reload"` = 0 |
| CLAUDE.md 技术栈 + 进度行 | 追加 Node 运行时约束 + Batch 2 R3 进度描述 | 技术栈段首行插入 `- Node >=22.12.0 运行时约束...`；695 行状态从 "R3 待修" 改为 "R3 修复完成待审"；条目末尾追加 **R3 Executor 修复完成** 段 | ✅ | 符合 handoff §1.6 + doc-writeback hook 要求（package.json engines 变更同步技术栈） |

> 状态注：✅一致 / ❌不一致 / 🔀改进（实现优于/替代计划，必须记录具体变更）

---

### 预审自检（测试契约 slice）

| 测试契约 slice | 对应测试命令 | 验证命令 | 实际输出（pass/fail + 关键行） | 反证验证（删除核心修改后测试是否 fail） |
|---------------|-------------|---------|------------------------------|---------------------------------------|
| ORC-NODE-01 clean `npm ci --ignore-scripts` 在 ≥22.12 环境下 stdout/stderr 零 EBADENGINE warning | N/A（非单测，属 env-level oracle） | `cd frontend-nuxt && rm -rf node_modules && npm ci --ignore-scripts 2>&1 \| tee /tmp/npm-ci-r3.log && grep -c EBADENGINE /tmp/npm-ci-r3.log` | PASS：npm ci exit 0，`added 706 packages, and audited 708 packages in 32s`；EBADENGINE 计数 = **0**（R2 基线在 Node 20.18 下 ≥6 条 EBADENGINE；R3 在 Node 22.22.2 下 0 条） | 反证：若退回 Node 20.18 跑同命令，R2 Authoritative FAIL 报告已证会出现 `EBADENGINE Unsupported engine` 针对 nitropack/unplugin/rollup-plugin-visualizer 等 6+ 条。当前环境因 ~/.bashrc 前置 Node 22.22.2，反证需临时 unset PATH 前缀复现，但 R2 authoritative 日志 `docs/plans/.codex-raw-code_review-batch2-r2-20260410-203333.log` 已有反面证据，不重复触发 |
| ORC-NODE-02 forbidden_strategy：不得通过降级 dep 达成零警告 | N/A（策略级 oracle） | `cd frontend-nuxt && git diff --stat package-lock.json` | PASS：`git diff --stat frontend-nuxt/package-lock.json` 无变化（本次 R3 未触碰 lockfile）；R3 scope 明确禁止 dep 降级，实际 diff 证实仅 engines 字段新增 | 反证：若 R3 改为降 nitropack@2.x 至 <2.13（方案 B），则 lockfile `resolved`/`integrity` 必然变化、package.json 的 dep 版本也会动。diff 零变化反证修复路径是升 runtime 而非降 dep |

---

### 语义回归自检（semantic_risk=true）

B2-F001 handoff §1.2 声明 `semantic_risk: true`，两条 ORC：

| Oracle ID | Type | 验证命令 | 实际输出 | 结论 |
|-----------|------|----------|----------|------|
| ORC-NODE-01 | temporal_trace（clean `npm ci` 零 EBADENGINE） | `rm -rf frontend-nuxt/node_modules && cd frontend-nuxt && npm ci --ignore-scripts 2>&1 \| tee /tmp/npm-ci-r3.log; echo "ci exit=$?"; grep -c EBADENGINE /tmp/npm-ci-r3.log` | `ci exit=0` + `added 706 packages, and audited 708 packages in 32s` + EBADENGINE count = `0`（仅剩 unplugin-vue-router + glob 两条 `deprecated` 警告，非 engine 错误） | ✅ |
| ORC-NODE-02 | forbidden_strategy（禁止降级 dep） | `cd C:/Users/Administrator/edu-cloud && git diff --stat frontend-nuxt/package-lock.json frontend-nuxt/node_modules 2>/dev/null; git diff frontend-nuxt/package.json \| grep -E "\"(@nuxt\|nitropack\|unplugin\|vite\|nuxt)\":.+\^" ` | `git diff --stat` 对 package-lock.json 零变化；`git diff package.json` 仅显示新增 `"engines": {"node": ">=22.12.0"}` 块，无 dep 版本改动 | ✅ |

---

### Fix Card（B2-F001）

```yaml
root_cause: frontend-nuxt/package-lock.json 锁定的多个 dep（nitropack@2.13.3 / unplugin / yargs / yargs-parser / nitropack/rollup-plugin-visualizer 等）要求 Node >=20.19.0 或 >=22.12.0（部分硬门槛 >=22）；仓库缺 engines 声明 + .nvmrc；执行环境 Node v20.18.0 不满足 → `npm ci --ignore-scripts` 稳定产生 EBADENGINE 警告 6+ 条
preserved_invariants:
  - INV-01: 不修改 frontend/（✅ git status 确认未触碰 frontend-nuxt 外的 frontend/*）
  - INV-02: 不碰 src/edu_cloud/ 和 alembic/（✅ git status 中 src/edu_cloud 下的 M 标记是外部任务遗留，非本 R3 改动）
  - INV-AUTH-01~04: B2-F002 已过的 4 ORC（auth-fail-closed / menu-degrade / auth-state-consistency / no-double-logout）不得回归（✅ Vitest 24/24 PASS，tests/composables/useMenus.test.ts 8 + tests/layouts/default.test.ts 4 全绿）
  - package-lock.json 当前 dep 版本不变（✅ git diff --stat package-lock.json 零变化）
non_goals:
  - 不降级任何 dep（方案 B rejected）— 验证：git diff package.json 仅 engines 新增
  - 不新增任何 dep — 验证：dependencies / devDependencies 块无改动
  - 不改 AuthError / useMenus / default.vue / auth.ts 任何逻辑 — 验证：git status 中 composables/ layouts/ stores/ tests/ 下零 M
  - 不启动 Batch 3 — 验证：Task 10-12 相关文件零改动
allowed_change_surface:
  - frontend-nuxt/package.json（新增 "engines": {"node": ">=22.12.0"}）✅
  - frontend-nuxt/.nvmrc（新建，内容 22.12.0）✅
  - CLAUDE.md（追加 Node 运行时约束 + Batch 2 R3 进度段）✅
  - docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md（B2-F003 §6 重写）✅
  - docs/plans/2026-04-14-haofenshu-phase1-review-handoff-batch2-r3.md（本文件新建）✅
非 scope 但属 env setup（不进 git）:
  - ~/.bashrc（PATH 前置 portable Node）— 用户家目录，git ls-files 确认 outside repo
  - ~/bin/node-v22.22.2-win-x64/（portable 解压目录）— 同上 outside repo
verification:
  - Node ≥22.12.0 环境下 `npm ci --ignore-scripts` exit 0 ∧ EBADENGINE 0 ✅
  - `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2` 零 invalid ∧ 零 extraneous ✅
  - `npx nuxt prepare` exit 0 ✅
  - `./node_modules/.bin/vitest.cmd run` = 24/24 PASS ✅
  - handoff hot-reload grep count = 0 ✅
semantic_risk: true
oracle:
  - ORC-NODE-01 temporal_trace: 验证已通过
  - ORC-NODE-02 forbidden_strategy: 验证已通过
```

---

### 验证清单自检（handoff §1.8 七项断言）

| # | 断言 | 命令 | 实测输出 | 结论 |
|---|------|------|---------|------|
| 1 | Node 版本 ≥ v22.12.0 | `which node && node --version && npm --version` | `which=/c/Users/Administrator/bin/node-v22.22.2-win-x64/node`; `node=v22.22.2`; `npm=10.9.7` | ✅ 22.22.2 > 22.12.0 |
| 2 | clean `npm ci --ignore-scripts` exit 0 | `cd frontend-nuxt && rm -rf node_modules && npm ci --ignore-scripts 2>&1 \| tee /tmp/npm-ci-r3.log` | exit code=0；`added 706 packages, and audited 708 packages in 32s` | ✅ |
| 3 | EBADENGINE 计数 = 0 | `grep -c EBADENGINE /tmp/npm-ci-r3.log` | `0` | ✅ |
| 4 | `npm ls ... invalid\|extraneous` = 0 | `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2 2>&1 \| tee /tmp/npm-ls-r3.log && grep -cE "invalid\|extraneous" /tmp/npm-ls-r3.log` | `0`（npm ls 打印的是 `@nuxt/kit@3.17.7 / 3.21.2 / 4.4.2` 等 deduped 分层，无 invalid 标签） | ✅ |
| 5 | `npx nuxt prepare` exit 0 | `cd frontend-nuxt && npx nuxt prepare 2>&1 \| tee /tmp/nuxt-prepare-r3.log` | exit code=0；尾部 `◆ Types generated in .nuxt.` | ✅ |
| 6 | Vitest 24/24 PASS | `cd frontend-nuxt && ./node_modules/.bin/vitest.cmd run 2>&1 \| tee /tmp/vitest-r3.log` | `Test Files  4 passed (4)` + `Tests  24 passed (24)`；分组 `useApi.test.ts 4` + `auth.test.ts 8` + `useMenus.test.ts 8` + `default.test.ts 4` = 24 | ✅ 与 R2 基线一致，无回归 |
| 7 | handoff hot-reload grep = 0 | `grep -c "hot-reload" docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md` | `0` | ✅ 两处原 hot-reload 文本（L171 block quote + L176 "R1 未验证假设"引用）全部重写 |

---

### 根因分析（B2-F001 bug-fix-discipline 四要素）

- **症状**: R2 Authoritative FAIL 报告显示 `npm ci --ignore-scripts` 在 Node v20.18.0 下稳定产生 ≥6 条 `EBADENGINE Unsupported engine` 警告（nitropack/unplugin/rollup-plugin-visualizer 等）。虽然 npm ci exit 0，但 lockfile dep 的 engines 声明与运行环境不匹配，违反 plan Task 4（frontend-nuxt 骨架）隐含的"本地跑得通且无环境警告"契约
- **根因**: 仓库缺 Node 版本声明基线（package.json 无 engines / 无 .nvmrc / 无仓库根 .nvmrc），而 Node 22 线 dep（nitropack@2.13.3 等）的 runtime 门槛与主机默认 Node 20.18 之间有未声明的"隐形合同"。单纯升级 dep 或降级 dep 都只是局部治标
- **证据**:
  - R2 Authoritative FAIL 报告 `docs/plans/2026-04-12-haofenshu-phase1-review-report-batch2-r2.md` 第一段粘贴了 6+ 条 EBADENGINE 原文
  - 本会话对 lockfile 的 engines 字段做 Python 扫描：4 个包硬要 `^20.19.0 || >=22.12.0`（nitropack/unplugin/yargs/yargs-parser），`nitropack/rollup-plugin-visualizer` 硬要 `>=22`（20.x 不能满足），另 40+ 个 dep 要求 `>=20.19.0 || >=22.0.0` —— 即当前 v20.18.0 环境下必违反
  - 本 R3 在 Node 22.22.2 下同命令 EBADENGINE = 0，证明根因正确
- **影响面** (scope check):
  - 同模式：frontend/（Vite 7+Vue 3.5）理论上也应有 Node 版本约束，但非本 R3 scope（INV-01 禁止触碰）；R3 仅在 frontend-nuxt 下声明 engines，不波及 frontend/
  - 同边界：后端 src/edu_cloud Python venv 与 Node 无关；CI（若有）将来应读 frontend-nuxt/.nvmrc，属 Batch 3 或后续 Phase 治理范围
  - 同不变量：`INV-AUTH-01~04` 是 B2-F002 的核心不变量，Vitest 24/24 未退证明 R3 不触发 auth lifecycle 回归
- **排除的假设**:
  - 假设 "降级 nitropack 至 ≤2.12（要求 Node 20）"：rejected by user（方案 B），且会传染到 `@nuxt/kit`（3.17.7）与 nuxt@3.17.7 的内部依赖图，lockfile 大规模重写风险高
  - 假设 "加 --legacy-peer-deps 绕过 engines 校验"：handoff §1.6 明确禁止；且 engines 校验是 npm 信息级，不是 peer dep 级，--legacy-peer-deps 不会影响 EBADENGINE 产出
  - 假设 "仅改 engines 不升 runtime，依赖 `engine-strict=false` 默认忽略"：R2 Reviewer 要求"clean env 零警告"，默认 warn 模式仍产生警告，不满足 oracle

---

### 自查（三要素格式）

- **新增文件的边界 case（`frontend-nuxt/.nvmrc`）**:
  构造输入: `.nvmrc` 内容 `22.12.0\n`（单行 + 尾换行，无 v 前缀，无注释）
  运行命令: `cat frontend-nuxt/.nvmrc && wc -c frontend-nuxt/.nvmrc`
  实际输出:
  ```
  22.12.0
  8 frontend-nuxt/.nvmrc
  ```
  结论: 文件 8 字节（7 字符 + LF），符合 nvm-windows / nvm-sh 约定的裸版本号格式；工具读取时不会因 BOM / 多行 / 前缀失败

- **状态变量 / PATH 前置异常路径（`~/.bashrc` export）**:
  构造输入: 在已有 PATH 头前置 portable node 目录，确保 `which node` 解析到新路径
  运行命令: `which node && node --version && echo "$PATH" | tr ':' '\n' | head -3`
  实际输出:
  ```
  /c/Users/Administrator/bin/node-v22.22.2-win-x64/node
  v22.22.2
  /c/Users/Administrator/bin/node-v22.22.2-win-x64
  /c/Users/Administrator/bin
  /mingw64/bin
  ```
  结论: PATH 正确前置；若 ~/.bashrc 被清理或回退（`sed -i` 撤回 portable 行），系统会回退到 `C:/Program Files/nodejs/node.exe` = v20.18.0，此时 `npm ci` 将重新产生 EBADENGINE —— 这是反证 ORC-NODE-01 可重复的依据

- **字符串匹配假阴性（`grep -c hot-reload` 语义）**:
  构造输入: 在 handoff 文件里保留 `"非 WSL 中转"` 词条（不含 hot-reload），但删除 "WSL 后端 hot-reload 失效" + "而非 WSL reload" 两段
  运行命令: `grep -cE "hot-?reload|HotReload" docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md && grep -n "WSL" docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md`
  实际输出:
  ```
  0
  172:**取证**：GPT Reviewer `netstat` + `Get-CimInstance Win32_Process` 独立查证确认 9000 监听进程是 `"python.exe" -m uvicorn ...`（Windows 本机原生进程，非 WSL 中转）。
  ```
  结论: `hot-reload`（含 hyphen 变体与 CamelCase）grep count = 0；仅保留的 `WSL` 唯一位置是澄清句"非 WSL 中转"，属正面表述（说明不是 WSL 问题）而非旧根因错误措辞，符合 handoff §1.5「grep 不到 hot-reload」要求

---

### 行为变更审批记录

| Finding ID | 行为变更摘要 | 用户决定 | 理由 |
|-----------|-------------|---------|------|
| B2-F001 方案 A | 升级 Node floor 到 >=22.12.0（package.json engines 声明 + frontend-nuxt/.nvmrc 锁定版本） | **approved** @ 2026-04-14 Planner 会话 | 用户批准 "推荐 A + X"（即方案 A 主干 + X 顺手 B2-F003）。方案 A 与 lockfile 锁定 dep 的 runtime 要求自然匹配（nitropack/unplugin ≥22.12、nitropack/rollup-plugin-visualizer ≥22），自动消除 EBADENGINE；回避方案 B 降级 dep 带来的依赖图退化与传染风险。红旗模式认定：改基线环境要求 = behavior_change，故须单独批准，不批量。L017 执行记录见 CLAUDE.md 已完成设计段条目 + R3 交接卡 §1.11 |

---

### 补充：环境切换路径说明（透明记录）

handoff §1.4 建议的主路径是 winget install / nvm install。实际执行中：
1. 先尝试 `winget install OpenJS.NodeJS.22 --silent --accept-source-agreements --accept-package-agreements`
2. 下载 msi hash 通过，MSI 静默安装返回 **1603**
3. 读 MSI log: `InstallValidate. Return value 3`（failed），根因是 `MsiSystemRebootPending = 1` + 17+ node.exe 进程占用 `C:/Program Files/nodejs/node.exe`（Claude Code 自身是 Node 进程）
4. 改走 portable zip 方案（handoff §1.4 允许「手动切换 Node 环境」，portable 属等价路径）：
   - 下载 `https://nodejs.org/dist/v22.22.2/node-v22.22.2-win-x64.zip` (30.2 MB)
   - SHA256 官方校验：`7c93e9d92bf68c07182b471aa187e35ee6cd08ef0f24ab060dfff605fcc1c57c` ✅ 匹配
   - `powershell Expand-Archive` 解压至 `~/bin/node-v22.22.2-win-x64/`
   - `~/.bashrc` PATH 前置
5. 选择理由（与 L016 同源思路—避免破坏性覆盖）：不杀 node.exe 进程（会杀掉 Claude Code 自身）；不强制系统重启（中断会话）；portable 零影响系统 Node 20.18，回退即删目录 + 撤 .bashrc 一行

---

### R3 审查范围（给 Reviewer 的预告，按 review-templates.md FAIL 升级规则）

- R3 只审 code-bug + test-gap 范畴：
  - B2-F001 修复（核心）：engines 声明 + .nvmrc + runtime 实证
  - B2-F003 顺手复核：handoff `grep -c hot-reload` = 0 验证
- B2-F002 R2 verified 不重审
- PASS 条件：
  - ORC-NODE-01 在 clean env 下复现（Node ≥22.12 时 EBADENGINE = 0）
  - Vitest 24/24 PASS 不退化 ✅
  - 未引入新 HIGH/MED code-bug 或 test-gap

使用 codex-review skill 进行 GPT 代码审查（Reviewer 路径）。
