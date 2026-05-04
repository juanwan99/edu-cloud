## Goal

执行 `docs/superpowers/plans/2026-04-29-guardian-p2.1-boundary-plan.md`（7 个 Task），完成守护者 P2.1 Shadow 阶段：修 5 个 bug + 建契约层 + 新增卫生 issue 类型。这是**元能力×守护者职责边界重划**的第一步——Guardian 先具备能力（Shadow），hooks 完全不动，后续 7 天双跑对账再切主。

## Must Preserve

- **hooks 零改动**（ORC-3）：本阶段只改 `~/.claude/guardian/` 和新建 `~/.claude/contracts/`，33 条 governance clause 不动
- **truth status / truth doctor** bash CLI 不受影响（ORC-1）
- **systemd timer 不中断**（ORC-5）：guardian.timer 已 active，改完 collector 后 timer 自动用新代码
- **端口分类行为不变**（ORC-4）：port_policy.py 改为读 JSON 但分类结果必须一致
- **全局架构**：元能力=动作裁判（deny 权），守护者=审计账本（只读 issue）——设计共识见 `docs/superpowers/plans/2026-04-29-guardian-meta-boundary-design.md` §3 权力模型

## Must Not Change

- `~/.claude/hooks/` 下任何文件（governance_audit_lite 等迁移在 Phase 3 Cutover，不是现在）
- `scripts/truth-status.sh` / `scripts/truth-doctor.sh`
- Guardian 的零执行权限原则（不 kill/build/restart）
- 现有 issue fingerprint 算法（`sha256(version+code+project+target)[:16]`）
