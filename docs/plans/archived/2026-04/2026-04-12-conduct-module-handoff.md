---
type: handoff
created: 2026-04-12 20:54:56
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-plan.md
---

## 约束与偏好

**T4 流程**。18 Tasks / 6 Batches，Subagent-Driven 执行。

- **家长端优先**：Batch 1-3 先完成（数据基础 + 家长后端 + 家长前端），再做管理端
- **不做视觉伴侣**：用户明确拒绝，按现有 edu-cloud 暗色主题风格实现
- **不做数据迁移**：class-points 云端数据不迁移，从零开始
- **parent_admin 角色取消**：不实现 class-points 的家长管理员角色，班主任直接管理
- **手机号作为登录名**：家长注册时 username 设为手机号，与 edu-cloud 已有 username 唯一约束共存
- **GuardianStudentLink 已存在**：edu-cloud 已有 `guardian_student_links` 表（含 relationship, is_primary, school_id 字段），直接复用，不需要迁移
- **ENCRYPTION_KEY 配置**：config.py 可能需要追加此字段，执行时检查
- **前端端口**：dev server 在 5273，后端在 9000
- **测试隔离**：SQLite in-memory，conftest 中 DI override get_db

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-12 20:55:28
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-handoff.md，
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-conduct-module-plan.md 执行。
使用 superpowers:subagent-driven-development skill。
完成后输出审查交接单。
```
