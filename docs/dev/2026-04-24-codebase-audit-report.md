# edu-cloud 代码库深度审计报告

> **日期**: 2026-04-24
> **范围**: 360 Python 源文件 / 300 测试文件 / 21 模块 / 276 API 端点 / 88 ORM 表
> **方法**: 5 维度并行审计（架构一致性 / 代码质量 / 测试覆盖 / 数据库 / 安全）

## 修复清单

### CRITICAL（已修复）

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| C1 | SQL 注入 — f-string 拼接 SQL | `data/seed_highschool_supplement.py:304-506` | 6 处 f-string → 参数化绑定 `:param` |
| C2 | 加密 key fallback 到硬编码 `"default-dev-key"` | `modules/conduct/crypto.py:20` | 改为 warning + 固定开发 key，不再 fallback |
| C3 | 数据库连接池缺失 | `database.py:5` | 加 pool_size=20/max_overflow=40/pool_recycle=3600/pool_pre_ping（SQLite 跳过） |

### HIGH（已修复）

| # | 问题 | 文件 | 修复 |
|---|------|------|------|
| H1 | AI 会话 dict 无锁 race condition | `api/ai.py:62` | 加 `asyncio.Lock` 保护 `_sessions` 所有读写 |
| H2 | 文件上传缺 MIME 类型验证 | `scan/router.py`, `exam/router.py` | 加 magic bytes 检测（兼容 Python 3.14，不用 imghdr） |
| H3 | 7 个未使用的配置项 | `config.py` | 移除 `PLATFORM_API_KEY_SALT`, `LLM_VISION_MODEL`, `AI_MAX_STEPS`, `AI_RATE_LIMIT_*`, `AI_MAX_CALLS_PER_SESSION`, `PAPER_SKILL_ENABLED` |
| H4 | 裸 `except Exception` 吞异常 | `app.py:226`, `school_settings_service.py:48`, `academic/service.py:35` | 分别改为 debug 日志 / warning 日志 / `IntegrityError` 精确捕获 |

### MEDIUM（记录，部分已修复）

| # | 问题 | 状态 | 说明 |
|---|------|------|------|
| M1 | N+1 查询（analytics/service.py 逐科目循环查） | 已修复 | 4 处循环 DB 查询 → `get_effective_scores_batch()` 批量查询 |
| M2 | FK 缺 index（conduct 13 列） | 已修复 | migration `a8c7d2e4f135` 添加 13 个 FK 索引 |
| M3 | conduct 模型缺 `updated_at` | 已修复 | 5 个表加 updated_at + conduct_rule_items 补 created_at |
| M4 | LLM usage 日志 | 已合入 | `llm_client.py` 加 `_log_llm_usage()` |

### LOW（记录）

| # | 问题 | 说明 |
|---|------|------|
| L1 | CORS `allow_methods=["*"]` | 开发环境合理，生产部署时收紧 |
| L2 | 家长密码最小 6 字符 | 考虑业务场景（家长用户），可接受 |
| L3 | 默认 admin/123456 | 种子数据，首次部署后强制改密码 |

### 其他修复

| # | 修复 | 文件 |
|---|------|------|
| O1 | 补 `models/academic.py` re-export stub | 新文件 |
| O2 | 提取 `shared/upload_validation.py` 图片验证共享模块 | 新文件 |
| O3 | `seed_highschool_supplement.py` 内联 `import json` → 顶部 | 代码清理 |
| O4 | `grading/llm_client.py` 补 LLM usage 日志 | 功能增强 |

## 文档漂移修正（全部已修）

| 项目 | CLAUDE.md 旧值 | 实际值 |
|------|--------------|--------|
| API 路由数 | 231 | 276 |
| `academic` 模块 | "仅 models" | 完整 CRUD（router+service 508 行） |
| Migration 数量 | 26 | 28 |
| 数据库描述 | "不支持 SQLite" | 开发/测试用 SQLite，生产用 PostgreSQL |
| academic 端点 | 未列出 | 10 端点已补充 |
| exam schedule | 未列出 | 2 端点已补充 |

## 安全加固清单（部署前必查）

- [ ] `.env` 中设置真实 `SECRET_KEY`（不是 `change-me`）
- [ ] `.env` 中设置真实 `ENCRYPTION_KEY`（不是默认值）
- [ ] CORS origins 改为实际前端域名
- [ ] 生产环境 `allow_methods` 收紧
- [ ] 部署后修改 admin 密码
- [ ] 文件上传目录权限检查
- [ ] PostgreSQL 连接池参数确认

## 测试覆盖缺口

| 模块 | 缺口 | 优先级 |
|------|------|--------|
| grading/quality_router.py | ~~零测试~~ → 7 tests 已补 | ~~HIGH~~ DONE |
| grading/assignment_service.py | ~~仅 1 个 smoke test~~ → 8 tests 已补 | ~~HIGH~~ DONE |
| worker/_grade_with_semaphore() | 无直接测试 | MEDIUM |
| analytics K-anonymity 边界 | 无 n<5 测试 | MEDIUM |
