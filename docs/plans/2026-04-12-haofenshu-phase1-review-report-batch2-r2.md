# Code Review R2 报告 — haofenshu Phase 1 Batch 2

[edu-cloud] GPT Reviewer | 2026-04-14 07:35:32
Commits: 8daa076 + 5bf5c27
结论: FAIL

## 第一段：测试充分性 (Test Adequacy)

独立验证结果如下：

- `cd frontend-nuxt && npm ci --ignore-scripts`：`exit 0`，但并非 handoff 声称的“零警告”。在当前评审环境 `node v20.18.0 / npm 10.2.3` 下，实际出现多条 `npm WARN EBADENGINE Unsupported engine`，涉及 `@rollup/plugin-alias@6.0.0`、`ast-kit@2.2.0`、`magic-string-ast@1.0.3`、`nitropack@2.13.3`、`unplugin@3.0.0`、`unplugin-utils@0.3.1`、`yargs@18.0.0`、`yargs-parser@22.0.0` 等；因此 Focus 1 的“零警告（或仅可接受废弃警告）”验收未通过。
- `npm ls @nuxt/kit @nuxt/schema commander crossws --depth=2`：零 `invalid:` / 零 `extraneous`，说明 lockfile 与依赖树的结构性错配已被修到位一半。
- `./node_modules/.bin/vitest run`：实际 landed suite 为 `4 files / 24 tests passed`，不是 handoff 早先口径里的 `16/16`。当前通过的是 `useApi.test.ts 4` + `auth.test.ts 8` + `useMenus.test.ts 8` + `default.test.ts 4`。
- 反证 1 复现：临时删除 `frontend-nuxt/composables/useMenus.ts` 中 `if (err instanceof AuthError) { ... throw err }` 后，`vitest run tests/composables/useMenus.test.ts -t "AuthError 向上抛"` 变为 `2 failed, 6 skipped`，两个 Slice 2 用例都从 reject 退化成 resolve。
- 反证 2 复现：临时把 `frontend-nuxt/layouts/default.vue` 的 `if (err instanceof AuthError)` 改成 `if (true)` 后，`vitest run tests/layouts/default.test.ts -t "500"` 变为 `1 failed, 3 skipped`，命中“500 不触发 logout”断言。
- 反证 3 复现：临时把 `frontend-nuxt/composables/useApi.ts` 的 401/403 处理改成 `throw err` 后，`vitest run tests/composables/useMenus.test.ts -t "401/403"` 变为 `2 failed, 2 passed, 4 skipped`，401/403 两个 AuthError slice 均失效。
- `cd C:/Users/Administrator/edu-cloud && python -m pytest tests/test_ai/test_tool_access_fail_closed.py --tb=line`：稳定复现 `2 failed, 5 passed`，失败项仍是 `test_no_capability_record_rejects` 与 `test_partial_capability_match_rejects`，与 R1 继承口径一致。

结论：B2-F002 的新增测试具备 anti-tautology；Pre-existing 失败口径也被独立复现。但 B2-F001 的 clean install 仍未达到用户要求的“零警告”标准。

## 第二段：行为正确性 (Behavioral Correctness)

Phase 0 Contract Pack 先验收边界：

- `git diff 8daa076~1..5bf5c27 -- frontend/` 为空，INV-01 成立。
- 本次 phase1 相关 diff 仅覆盖 `frontend-nuxt/` 与 `docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md`；未见后端代码改动，INV-02/05/06 在本轮范围内未被直接触碰。
- `risk_modules` 仍未追认 `frontend-nuxt/package.json` 与 `frontend-nuxt/package-lock.json`，这一点在 R1 已暴露，本轮计划文档仍未补记，属合同包记录缺口，但不单独构成阻塞。

Focus 1 结论：B2-F001 仅部分修复，不能判定 `resolved-correct`。

- 正向证据：
  - `frontend-nuxt/package.json:15-18` 已将 `@element-plus/nuxt` 收紧为 `~1.1.4`、`nuxt` 收紧为 `~3.17.7`。
  - `npm ls` 零 `invalid`，且全文 grep 未见 `--legacy-peer-deps` 残留。
- 反证据：
  - `frontend-nuxt/package.json` 没有 `engines` 字段，仓库也没有 `.nvmrc`；但 rebuilt lockfile 已锁入一批要求更高 Node floor 的包。
  - `frontend-nuxt/package-lock.json` 明确记录了若干核心包的 engine 要求高于当前环境，例如 `@rollup/plugin-alias` (`>=20.19.0`，约在 `package-lock.json:2297-2302`)、`ast-kit` (`>=20.19.0`，约在 `3576-3585`)、`magic-string-ast` (`>=20.19.0`，约在 `5972-5980`)、`nitropack` (`^20.19.0 || >=22.12.0`，约在 `6194-6275`)、`unplugin` (`^20.19.0 || >=22.12.0`，约在 `9105-9115`)、`unplugin-utils` (`>=20.19.0`，约在 `9118-9127`)。
  - 因而 `npm ci --ignore-scripts` 虽然 exit 0，但会稳定产出非废弃类 `EBADENGINE` 警告，这与 R2 handoff 的“零警告”口径不一致，也未满足本轮 Focus 1 的验收门槛。

Focus 2 结论：B2-F002 的核心修复链路成立，R1 的 fail-closed 缺陷已被修复。

- `frontend-nuxt/composables/useApi.ts:8-15` 新增 `export class AuthError extends Error`，`getMenus()` 在 `46-55` 对 401/403 转抛 `AuthError`，其他错误原样上抛。
- `frontend-nuxt/composables/useMenus.ts:1-18` 正确导入 `AuthError`；`loadMenus()` 在 AuthError 分支先 `setMenus([])` 再 `throw err`，非 auth 错误则只降级为空菜单。
- `frontend-nuxt/layouts/default.vue:15-50` 正确导入 `AuthError`，且只有 `err instanceof AuthError` 才触发 `authStore.logout()`；无差别 logout 模式已消失。
- `frontend-nuxt/stores/auth.ts:119-127` 的 `logout()` 会同时清空 `user`、`menus` 与 `edu_token`，因此 `ORC-auth-state-consistency` 由 “useMenus 先清空菜单” + “logout 再清空用户/令牌” 双重守住。
- `frontend-nuxt/tests/composables/useMenus.test.ts` 与 `frontend-nuxt/tests/layouts/default.test.ts` 合计 12 个新增 case 已覆盖 4 slices，且三条反证都能打穿错误实现，不存在 tautology。

需要注明的偏差：

- 独立修复设计 §2.4 的草案文本是“`else console.warn()`”，而 landed code 选择了静默保留 session（`void err` + 注释），这与 `5bf5c27` 里补写的 logging-guard 说明一致。该偏差没有破坏 fail-closed 契约，也没有造成新的行为回退，因此本轮不把它升级为阻塞 finding，但它说明“严格逐字按设计落地”的表述并不准确。
- `ORC-no-double-logout` 当前只被单次 401/403 路径的 `toHaveBeenCalledTimes(1)` 间接守住，没有覆盖“连续/并发 401”场景，这里仍留有未测风险。

Focus 3 结论：B2-F003 未完全收窄，仍应判定 `contested`。

- R2 handoff 新增了正确的新表述：`docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md:174-176` 已写成“`9000 常驻后端进程陈旧/未重启` + fresh 9001 对照”。
- 但同一文档仍保留了旧表述：`docs/plans/2026-04-12-haofenshu-phase1-review-handoff-batch2-r2.md:171` 仍出现 `WSL 后端 hot-reload 失效`。用户对 Focus 3 的验收要求是“旧措辞必须消失”；当前属于“新旧混合并存”，因此 B2-F003 只能算低风险修正未收口，不影响主结论但不能记 `verified`。

Focus 4 结论：R2-F001 继承口径正确。Pre-existing pytest 的 `2 failed, 5 passed` 已被独立复现，无偏差。

## 第三段：未测试风险 (Non-tested Risks)

- `frontend-nuxt/stores/auth.ts:108-118` 的 `switchRole()` 也会直接调用 `loadMenus()`，但当前没有单独的 AuthError 回归测试覆盖这条“非 default.vue watch”路径；若该路径未来遇到 401/403，异常传播与 UI 收口方式仍未被明示验证。
- `frontend-nuxt/layouts/default.vue:27-53` 只验证了“单次 token 变化触发一次 logout”。若发生连续 401、并发 `loadMenus()`、或 logout 导航前又触发一次 watcher，本轮没有显式测试保证绝不双重 logout / 双重 navigate。
- `AuthError` 依赖同 bundle 的 `instanceof` 身份；当前 Vitest 单 bundle 环境通过，但未覆盖 SSR/hydration 或跨 bundle 身份场景。
- 依赖环境基线仍未写入仓库合同。当前 lockfile 在 `node v20.18.0` 上稳定产生 `EBADENGINE`；若 Gate/CI/Executor 机器的 Node 版本继续漂移，B2-F001 会重复出现“本机能过、换机有警告”的不稳定性。

## R1 finding 复核

| Finding | R1 | R2 终态 (Executor 声明) | GPT 复核 |
|---------|----|----|----|
| B2-F001 | MED code-bug | resolved-correct | contested |
| B2-F002 | MED code-bug | resolved-correct | verified |
| B2-F003 | LOW design-concern | resolved-correct | contested |

## 新发现清单（R2 新 finding，如有）

无新增阻塞 finding。本轮 FAIL 由 R1 既有 finding `B2-F001` 未通过复核触发。

## 行为变更审批记录（如有 behavior_change）

无新增 behavior_change finding。

## PASS/FAIL 判定依据

依据 `review-templates.md` 的 PASS/FAIL 规则，`code-bug` 或 `test-gap` 的 HIGH/MED 未修复即 FAIL。本轮中：

- `B2-F001` 仍未满足 Focus 1 的验收门槛。虽然 `npm ls` 已 clean，但 `npm ci --ignore-scripts` 在当前评审环境仍稳定产生非废弃类 `EBADENGINE` 警告，故 MED `code-bug` 未修复，结论必须为 FAIL。
- `B2-F002` 行为链路、4 slices 与 3 条反证均验证通过，不再阻塞。
- `B2-F003` 仅属 LOW `design-concern`，单独不阻塞，但因旧措辞仍残留，不能记为已完全解决。

## Inv-conflict 标注

possible — INV-01~06 未见直接冲突，但 plan 的 `risk_modules` 仍未追认 `frontend-nuxt/package.json` 与 `frontend-nuxt/package-lock.json`，导致依赖基线风险没有被合同包显式登记。
