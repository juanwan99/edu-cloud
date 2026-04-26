---
baseline_command: ".venv/bin/python -m pytest --tb=no -q"
baseline_verified_at: "2026-04-26T10:17:07+08:00"
baseline_count: "2219 passed / 23 skipped / 2 failed"
---

# edu 项目群技术债系统性修复 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复审计发现的 21 条 Critical+High 技术债（6C + 15H），按风险层分 3 Phase 推进。

**Architecture:** 纯增量修改，不引入新框架/平行系统。Phase 0 消除安全风险，Phase 1 消除稳定性风险，Phase 2 降低架构债。每 Phase 独立会话执行，codex-review 门控。

**Tech Stack:** FastAPI / SQLAlchemy 2.0 / Vue 3 + Vite / pytest / vitest / DOMPurify

**Design:** `docs/plans/2026-04-26-tech-debt-fix-design.md`

---

## Phase 0 — 安全修复（8 条）

### Task 1: 硬编码密码统一迁移到配置项 [C-01 + GPT-01]

**Files:**
- Modify: `src/edu_cloud/config.py:17` — 添加 SEED_DEFAULT_PASSWORD
- Modify: `src/edu_cloud/api/app.py:110,119` — 引用 settings
- Modify: `src/edu_cloud/data/seed_school.py:202,212,225,232,258` — 引用 settings
- Modify: `src/edu_cloud/data/seed_highschool_supplement.py:361` — 引用 settings
- Modify: `src/edu_cloud/data/import_exam_xlsx.py:274` — 引用 settings
- Modify: `src/edu_cloud/modules/student/teacher_router.py:42,562` — 引用 settings
- Modify: `.env` — 添加 SEED_DEFAULT_PASSWORD=123456

- [ ] **Step 1: 在 config.py 添加配置项**

在 `src/edu_cloud/config.py` 的 Settings 类中，`SECRET_KEY` 下方添加：

```python
SEED_DEFAULT_PASSWORD: str = "change-me-seed-password"
```

- [ ] **Step 2: 在 .env 中设置开发值**

在 `.env` 末尾添加：

```
SEED_DEFAULT_PASSWORD=123456
```

- [ ] **Step 3: 修改 app.py 种子密码**

`src/edu_cloud/api/app.py:110` 替换：

```python
# 旧
admin.set_password("123456")
# 新
from edu_cloud.config import settings
admin.set_password(settings.SEED_DEFAULT_PASSWORD)
```

`app.py:119` 替换日志行：

```python
# 旧
logger.info("seed: platform admin created (admin/123456)")
# 新
logger.info("seed: platform admin created (admin/***)")
```

- [ ] **Step 4: 修改 seed_school.py 全部 5 处**

`src/edu_cloud/data/seed_school.py` 顶部添加导入：

```python
from edu_cloud.config import settings
```

替换第 202, 212, 225, 232, 258 行的 `user.set_password("123456")` 为：

```python
user.set_password(settings.SEED_DEFAULT_PASSWORD)
```

- [ ] **Step 5: 修改 seed_highschool_supplement.py**

`src/edu_cloud/data/seed_highschool_supplement.py:361` 同样替换，顶部加 import。

- [ ] **Step 6: 修改 import_exam_xlsx.py**

`src/edu_cloud/data/import_exam_xlsx.py:274` 同样替换，顶部加 import。

- [ ] **Step 7: 修改 teacher_router.py 默认值和导入逻辑**

`src/edu_cloud/modules/student/teacher_router.py:42` 替换：

```python
# 旧
password: str = "123456"
# 新
password: str | None = None
```

`teacher_router.py` 在创建教师处（约行 189）添加 fallback：

```python
user.set_password(req.password or settings.SEED_DEFAULT_PASSWORD)
```

`teacher_router.py:562` 导入流程替换：

```python
# 旧
user.set_password("123456")
# 新
user.set_password(settings.SEED_DEFAULT_PASSWORD)
```

- [ ] **Step 8: 验证零残留**

Run: `grep -rn '"123456"' src/edu_cloud/ --include='*.py' | grep -v test | grep -v fillmark | grep -v "0123456789"`
Expected: 零匹配

- [ ] **Step 9: 跑测试**

Run: `.venv/bin/python -m pytest --tb=short -q`
Expected: ≥ 2219 passed

- [ ] **Step 10: Commit**

```bash
git add src/edu_cloud/config.py src/edu_cloud/api/app.py src/edu_cloud/data/ src/edu_cloud/modules/student/teacher_router.py .env
git commit -m "$(cat <<'EOF'
security: migrate hardcoded seed password to settings.SEED_DEFAULT_PASSWORD

C-01 + GPT-01: all 9 occurrences of "123456" in seed/import/teacher-create
now reference settings.SEED_DEFAULT_PASSWORD. TeacherCreate.password
default changed from "123456" to None with settings fallback.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: .env 从 git 追踪移除 [C-03]

**Files:**
- Modify: git index — untrack .env

- [ ] **Step 1: 确认 .gitignore 已有规则**

Run: `grep -n '\.env' .gitignore`
Expected: 应看到 `.env` 规则

- [ ] **Step 2: 从 git 追踪移除**

```bash
git rm --cached .env
git commit -m "$(cat <<'EOF'
security: remove .env from git tracking

C-03: .env was committed early and tracked despite .gitignore rule.
Contains dev SECRET_KEY. git rm --cached only, file stays on disk.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: ExamAIClient 默认端口修正 [C-05]

**Files:**
- Modify: `/home/ops/projects/paper-seg/app/client/api.py:11`

- [ ] **Step 1: 修改默认值**

`paper-seg/app/client/api.py:11` 替换：

```python
# 旧
def __init__(self, base_url: str = "http://localhost:8000"):
# 新
def __init__(self, base_url: str = "http://localhost:9000"):
```

- [ ] **Step 2: 跑 paper-seg 测试**

Run: `cd /home/ops/projects/paper-seg && python -m pytest --tb=short -q`

- [ ] **Step 3: Commit**

```bash
cd /home/ops/projects/paper-seg
git add app/client/api.py
git commit -m "$(cat <<'EOF'
fix: change ExamAIClient default port from 8000 to 9000

C-05: edu-cloud runs on port 9000, not 8000 (exam-ai legacy).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: module_middleware JWT 异常绕过修复 [GPT-02]

**Files:**
- Modify: `src/edu_cloud/api/module_middleware.py:82-88`
- Test: `tests/test_api/test_module_middleware.py` (create)

- [ ] **Step 1: 写失败测试**

创建 `tests/test_api/test_module_middleware.py`：

```python
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_middleware_blocks_on_jwt_decode_failure(client: AsyncClient):
    """GPT-02: JWT decode failure must NOT bypass module checks."""
    with patch("edu_cloud.api.module_middleware.jwt.decode", side_effect=Exception("bad token")):
        resp = await client.get(
            "/api/v1/exams",
            headers={"Authorization": "Bearer invalid-token"},
        )
    assert resp.status_code in (401, 403), f"Expected 401/403 but got {resp.status_code}"
```

- [ ] **Step 2: 跑测试确认红**

Run: `.venv/bin/python -m pytest tests/test_api/test_module_middleware.py -v`
Expected: FAIL（当前 JWT 异常后 call_next 放行）

- [ ] **Step 3: 修复 middleware**

`src/edu_cloud/api/module_middleware.py` 修改异常处理块（约行 82-88）：

```python
# 旧：JWT 解码失败后继续放行
except Exception as e:
    logger.debug("module_middleware: JWT decode failed for %s: %s", path, e)
# （然后 fall through 到 call_next）

# 新：JWT 解码失败后跳过模块检查，让后续认证中间件处理
except Exception as e:
    logger.debug("module_middleware: JWT decode failed for %s: %s", path, e)
    return await call_next(request)
```

注意：需要检查实际的控制流。如果 JWT 解码在 try 块内且 fall-through 到模块禁用检查，需要确保异常后直接 return call_next 而不经过模块检查逻辑。关键是 **JWT 解码失败时不应执行模块禁用判断**（因为没有有效的 school_id），直接放行到下一个中间件（认证中间件会拒绝无效 token）。

- [ ] **Step 4: 跑测试确认绿**

Run: `.venv/bin/python -m pytest tests/test_api/test_module_middleware.py -v`
Expected: PASS

- [ ] **Step 5: 全量回归**

Run: `.venv/bin/python -m pytest --tb=short -q`
Expected: ≥ 2219 passed

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/api/module_middleware.py tests/test_api/test_module_middleware.py
git commit -m "$(cat <<'EOF'
security: fix module_middleware JWT decode bypass

GPT-02: when JWT decode fails, skip module-disable check entirely
and let downstream auth middleware reject the invalid token.
Previously the exception fell through to module check logic without
a valid school_id.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: ChatPanel v-html 防护 [H-04]

**Files:**
- Modify: `frontend/package.json` — 添加 dompurify 依赖
- Modify: `frontend/src/components/workspace/ChatPanel.vue:12,33-35`

- [ ] **Step 1: 安装 DOMPurify**

Run: `cd frontend && npm install dompurify`

- [ ] **Step 2: 修改 ChatPanel.vue**

`frontend/src/components/workspace/ChatPanel.vue` 在 script setup 中添加导入：

```javascript
import DOMPurify from 'dompurify'
```

修改 `renderMarkdown` 函数（约行 33-35）：

```javascript
// 旧
function renderMarkdown(text) {
    const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
}

// 新
function renderMarkdown(text) {
    const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    const html = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')
    return DOMPurify.sanitize(html)
}
```

- [ ] **Step 3: 跑前端测试**

Run: `cd frontend && npx vitest run`
Expected: ≥ 348 passed

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/workspace/ChatPanel.vue
git commit -m "$(cat <<'EOF'
security: add DOMPurify sanitization to ChatPanel v-html

H-04: AI-generated content rendered via v-html now passes through
DOMPurify.sanitize() to prevent XSS injection.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: card-editor innerHTML 防护 [H-05]

**Files:**
- Modify: `frontend/src/card-editor/panel.js:112`
- Modify: `frontend/src/card-editor/render.js:639,699`

- [ ] **Step 1: panel.js 添加 sanitize**

`frontend/src/card-editor/panel.js` 顶部添加：

```javascript
import DOMPurify from 'dompurify'
```

行 112 替换：

```javascript
// 旧
listDiv.innerHTML = html;
// 新
listDiv.innerHTML = DOMPurify.sanitize(html);
```

行 382 替换（container.innerHTML 赋值处）：

```javascript
// 对模板字符串结果 sanitize
container.innerHTML = DOMPurify.sanitize(`...原有模板字符串...`);
```

注意：行 71 的 `listDiv.innerHTML = '<div class="hint">未加载布局</div>'` 是硬编码 HTML 常量，无注入风险，可不改。

- [ ] **Step 2: render.js 添加 sanitize**

`frontend/src/card-editor/render.js` 顶部添加：

```javascript
import DOMPurify from 'dompurify'
```

行 639 和 699 的 `previewWrap.innerHTML = ...` 替换为：

```javascript
previewWrap.innerHTML = DOMPurify.sanitize(`...原有模板字符串...`);
```

- [ ] **Step 3: 跑前端测试**

Run: `cd frontend && npx vitest run`
Expected: ≥ 348 passed

- [ ] **Step 4: Commit**

```bash
git add frontend/src/card-editor/panel.js frontend/src/card-editor/render.js
git commit -m "$(cat <<'EOF'
security: add DOMPurify to card-editor innerHTML assignments

H-05: panel.js and render.js innerHTML assignments now sanitized.
Data sources are internal but defense-in-depth applied.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: JWT localStorage 最小加固 [H-03 降级]

**Files:**
- Modify: `frontend/src/stores/auth.js:118-119` — 登出时清理全部 auth 数据

- [ ] **Step 1: 审查当前登出逻辑**

Read `frontend/src/stores/auth.js:110-120`，确认 logout 已清理 token 和 auth_state。

- [ ] **Step 2: 添加 token 过期检查**

在 `auth.js` 的 `loadAuthState()` 函数（约行 21-28）中添加 token 过期检查：

```javascript
function loadAuthState() {
    const raw = localStorage.getItem('auth_state')
    if (!raw) return
    try {
        const saved = JSON.parse(raw)
        // 检查 token 是否存在，不存在则清理状态
        if (!localStorage.getItem('token')) {
            localStorage.removeItem('auth_state')
            return
        }
        // ...existing restore logic
    } catch { /* ... */ }
}
```

- [ ] **Step 3: 跑前端测试**

Run: `cd frontend && npx vitest run`
Expected: ≥ 348 passed

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/auth.js
git commit -m "$(cat <<'EOF'
security: add token existence check on auth state restore

H-03 (minimal): clear stale auth_state if token is missing.
Full httpOnly cookie migration deferred to future sprint.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Phase 0 验证与 codex-review

- [ ] **Step 1: 全量后端测试**

Run: `.venv/bin/python -m pytest --tb=short -q`
Expected: ≥ 2219 passed

- [ ] **Step 2: 全量前端测试**

Run: `cd frontend && npx vitest run`
Expected: ≥ 348 passed

- [ ] **Step 3: 密码残留检查**

Run: `grep -rn '"123456"' src/edu_cloud/ --include='*.py' | grep -v test | grep -v fillmark | grep -v "0123456789"`
Expected: 零匹配

- [ ] **Step 4: git diff 确认无计划外变更**

Run: `git diff --stat`
Expected: 仅 Phase 0 涉及的文件

- [ ] **Step 5: codex-review code**

触发 codex-review code 审查，等待 GPT PASS。

- [ ] **Step 6: 写 Phase 0 handoff**

写 `docs/plans/2026-04-26-tech-debt-phase0-handoff.md`，含：
- 每条 fix 的 commit SHA
- pytest / vitest 通过数
- codex-review 结果

---

## Phase 1 — 稳定性修复（8 条）

### Task 9: 移除 create_all，统一 Alembic [C-02]

**Files:**
- Modify: `src/edu_cloud/api/app.py:70-71` — 移除 create_all
- Test: 验证 `alembic upgrade head` 从空库建表

- [ ] **Step 1: 注释掉 create_all**

`src/edu_cloud/api/app.py:70-71` 替换：

```python
# 旧
await conn.run_sync(Base.metadata.create_all)
logger.info("database tables created")

# 新
# create_all removed (C-02): all environments use alembic upgrade head.
# Test fixtures in conftest.py still use create_all for in-memory SQLite.
logger.info("database: skipping create_all, use 'alembic upgrade head'")
```

- [ ] **Step 2: 验证 Alembic 从空库建表**

```bash
rm -f /tmp/test_alembic_clean.db
DATABASE_URL="sqlite+aiosqlite:///tmp/test_alembic_clean.db" .venv/bin/python -m alembic upgrade head
```

Expected: 成功，无报错

- [ ] **Step 3: 全量测试（conftest.py 仍用 create_all）**

Run: `.venv/bin/python -m pytest --tb=short -q`
Expected: ≥ 2219 passed（conftest.py:58 的 create_all 不受影响）

- [ ] **Step 4: Commit**

```bash
git add src/edu_cloud/api/app.py
git commit -m "$(cat <<'EOF'
fix: remove create_all from app startup, unify on Alembic

C-02: Base.metadata.create_all removed from lifespan. All environments
now use 'alembic upgrade head'. Test fixtures retain create_all for
in-memory SQLite (conftest.py:58).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: 从 git 移除 .db 和日志文件 [C-04]

**Files:**
- Modify: git index — untrack db and log files

- [ ] **Step 1: 移除追踪**

```bash
git rm --cached edu_cloud.db 2>/dev/null; git rm --cached edu_cloud.db.bak* 2>/dev/null; git rm --cached logs/app.jsonl.* 2>/dev/null
```

- [ ] **Step 2: 确认 .gitignore 覆盖**

Run: `grep -n '*.db' .gitignore && grep -n 'logs/' .gitignore`
Expected: 已有规则

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
chore: remove tracked db and log files

C-04: edu_cloud.db (~5.5MB), .bak files, and logs/app.jsonl.*
removed from git tracking. .gitignore already covers these patterns.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: answer-card-editor 补全依赖 [C-06]

**Files:**
- Modify: `/home/ops/projects/answer-card-editor/backend/pyproject.toml:6-11`

- [ ] **Step 1: 添加缺失依赖**

在 `answer-card-editor/backend/pyproject.toml` 的 dependencies 列表中添加：

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.30",
    "pydantic>=2.0",
    "playwright>=1.40",
    "orjson>=3.9",
    "Pillow>=10.0",
    "numpy>=1.24",
]
```

- [ ] **Step 2: Commit**

```bash
cd /home/ops/projects/answer-card-editor
git add backend/pyproject.toml
git commit -m "$(cat <<'EOF'
fix: declare missing Pillow and numpy dependencies

C-06: bubble_detector.py and generate_spec.py import numpy/PIL
but pyproject.toml didn't declare them.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: npm 安全漏洞修复 [H-06]

**Files:**
- Modify: `frontend/package-lock.json`
- Modify: `/home/ops/projects/answer-card-editor/frontend/package-lock.json`

- [ ] **Step 1: edu-cloud 前端修复**

```bash
cd /home/ops/projects/edu-cloud/frontend
npm audit fix --audit-level=high
npm audit --audit-level=high
```

Expected: 0 high vulnerabilities

- [ ] **Step 2: answer-card-editor 前端修复**

```bash
cd /home/ops/projects/answer-card-editor/frontend
npm audit fix --audit-level=high
npm audit --audit-level=high
```

Expected: 0 high vulnerabilities

- [ ] **Step 3: 验证 build 不破**

```bash
cd /home/ops/projects/edu-cloud/frontend && npx vite build
cd /home/ops/projects/answer-card-editor/frontend && npx vite build
```

- [ ] **Step 4: Commit（各仓库分别）**

```bash
cd /home/ops/projects/edu-cloud
git add frontend/package-lock.json frontend/package.json
git commit -m "$(cat <<'EOF'
security: fix 6 high npm vulnerabilities

H-06: npm audit fix for happy-dom, lodash, picomatch, vite CVEs.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: N+1 查询修复 [H-07]

**Files:**
- Modify: `src/edu_cloud/modules/analytics/service.py:220-265`

- [ ] **Step 1: 审查当前查询模式**

Read `src/edu_cloud/modules/analytics/service.py:210-270`，确认 N+1 位置。

探查结果显示行 223-225 已用 `IN` 批量查询学生→班级映射，行 253-254 已批量查询班级名称。真正的 N+1 在于行 257-264 的循环内统计计算可推到查询层。

- [ ] **Step 2: 优化聚合逻辑**

如果循环内确实有额外 DB 查询，改用 `selectinload` 或合并到前面的批量查询中。如果仅是内存计算（纯 Python 循环聚合），则标注为已优化，无需改动。

- [ ] **Step 3: 跑测试**

Run: `.venv/bin/python -m pytest tests/ -k "analytics" --tb=short -q`
Expected: 全 PASS

- [ ] **Step 4: Commit（如有改动）**

---

### Task 14: grading.py 异常处理加固 [H-08]

**Files:**
- Modify: `src/edu_cloud/workers/grading.py:182-184`

- [ ] **Step 1: 修改异常处理**

`src/edu_cloud/workers/grading.py:182-184` 替换：

```python
# 旧
except Exception:
    llm_url, llm_key, llm_model = None, None, None
    logger.info("grading_task: task=%s, llm_config fallback to .env", task_id)

# 新
except Exception:
    llm_url, llm_key, llm_model = None, None, None
    logger.warning("grading_task: task=%s, llm_config DB lookup failed, fallback to .env", task_id, exc_info=True)
```

- [ ] **Step 2: 跑测试**

Run: `.venv/bin/python -m pytest tests/test_workers/ --tb=short -q`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/edu_cloud/workers/grading.py
git commit -m "$(cat <<'EOF'
fix: upgrade grading worker exception logging to WARNING with traceback

H-08: LLM config DB lookup failure now logged at WARNING with exc_info
instead of INFO without traceback.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: audit_service 异常处理加强 [GPT-03]

**Files:**
- Modify: `src/edu_cloud/services/audit_service.py:142-143`

- [ ] **Step 1: 加强日志**

`src/edu_cloud/services/audit_service.py:142-143` 已有 `logger.warning(..., exc_info=True)`。验证这已经足够（比 GPT 报告的"完全吞掉"要好）。

如果确认 warning + exc_info 已满足需求，标注为 verified-adequate。如需加强，可添加 metric counter：

```python
except Exception:
    logger.warning("Failed to write audit log for %s/%s", entity_type, eid, exc_info=True)
```

- [ ] **Step 2: Commit（如有改动）**

---

### Task 16: 重建 .venv [H-12]

- [ ] **Step 1: edu-cloud .venv 重建**

```bash
cd /home/ops/projects/edu-cloud
rm -rf .venv
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

- [ ] **Step 2: paper-seg .venv 重建**

```bash
cd /home/ops/projects/paper-seg
rm -rf .venv
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

- [ ] **Step 3: 验证 pip 可用**

```bash
/home/ops/projects/edu-cloud/.venv/bin/pip --version
/home/ops/projects/paper-seg/.venv/bin/pip --version
```

Expected: 两个都显示 pip 版本号

- [ ] **Step 4: 全量测试**

```bash
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q
cd /home/ops/projects/paper-seg && .venv/bin/python -m pytest --tb=short -q
```

---

### Task 17: Phase 1 验证与 codex-review

同 Task 8 结构：全量测试 + npm audit + codex-review + handoff。

---

## Phase 2a — 后端架构 + Bundle + CI + ace

### Task 18: God Module 路由文件拆分 [H-01]

**Files:**
- Split: `src/edu_cloud/modules/card/router.py` → 3 文件
- Split: `src/edu_cloud/modules/grading/router.py` → 2 文件
- Split: `src/edu_cloud/modules/analytics/router.py` → 2 文件
- Modify: `src/edu_cloud/api/app.py` — 更新 include_router

- [ ] **Step 1: card/router.py 拆分**

创建 `src/edu_cloud/modules/card/card_template_router.py`，将模板相关端点迁入。
创建 `src/edu_cloud/modules/card/card_export_router.py`，将导出/PDF 相关端点迁入。
`card/router.py` 保留核心 CRUD 端点。

每个新文件顶部创建自己的 `router = APIRouter(prefix="/api/v1/card", tags=["card"])`。

- [ ] **Step 2: grading/router.py 拆分**

创建 `src/edu_cloud/modules/grading/grading_review_router.py`，将教师审核相关端点迁入。
`grading/router.py` 保留任务创建和 rubric 端点。

- [ ] **Step 3: analytics/router.py 拆分**

创建 `src/edu_cloud/modules/analytics/analytics_report_router.py`，将趋势/报告端点迁入。
`analytics/router.py` 保留核心查询端点。

- [ ] **Step 4: 更新 app.py include_router**

在 `app.py` 的 lifespan 或 create_app 中，添加新路由的 include_router 调用。

- [ ] **Step 5: 全量测试**

Run: `.venv/bin/python -m pytest --tb=short -q`
Expected: ≥ 2219 passed（API 端点不变，仅文件拆分）

- [ ] **Step 6: Commit**

---

### Task 19: Bundle 优化 [H-09]

**Files:**
- Modify: `frontend/vite.config.js`

- [ ] **Step 1: 添加 manualChunks**

在 `frontend/vite.config.js` 的 `defineConfig` 中添加 build 配置：

```javascript
build: {
    rollupOptions: {
        output: {
            manualChunks: {
                'echarts-vendor': ['echarts', 'vue-echarts'],
                'marked-katex': ['marked', 'katex'],
                'ui-vendor': ['naive-ui'],
            }
        }
    }
}
```

- [ ] **Step 2: 构建并对比体积**

```bash
cd frontend
du -sh dist/ 2>/dev/null  # 记录旧体积
npx vite build
du -sh dist/              # 对比新体积
```

- [ ] **Step 3: Commit**

---

### Task 20: ace SQLite 并发安全 [H-10]

**Files:**
- Modify: `/home/ops/projects/answer-card-editor/backend/app/db.py`
- Modify: `/home/ops/projects/answer-card-editor/backend/app/main.py`
- Modify: `/home/ops/projects/answer-card-editor/backend/app/api/templates.py`

- [ ] **Step 1: 改为 connection-per-request**

重写 `db.py`：每次请求创建新连接，用 FastAPI Depends 注入，请求结束关闭。移除 `check_same_thread=False`。

- [ ] **Step 2: 更新 templates.py 使用 Depends**

替换 `app.main._db_conn` 引用为 FastAPI Depends 注入。

- [ ] **Step 3: 跑测试**

```bash
cd /home/ops/projects/answer-card-editor && python -m pytest --tb=short -q
```

- [ ] **Step 4: Commit**

---

### Task 21: CI 配置 [H-11]

**Files:**
- Create: `.github/workflows/test.yml`（edu-cloud）
- Create: `/home/ops/projects/paper-seg/.github/workflows/test.yml`
- Create: `/home/ops/projects/answer-card-editor/.github/workflows/test.yml`

- [ ] **Step 1: edu-cloud CI**

创建 `.github/workflows/test.yml`：

```yaml
name: Tests
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -e ".[dev]"
      - run: python -m pytest --tb=short -q
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22' }
      - run: cd frontend && npm ci && npx vitest run
      - run: cd frontend && npm audit --audit-level=high
```

- [ ] **Step 2: paper-seg CI（精简版）**
- [ ] **Step 3: ace CI（精简版）**
- [ ] **Step 4: Commit（各仓库分别）**

---

### Task 22: Phase 2a 验证与 codex-review

同 Task 8 结构。

---

## Phase 2b — 前端组件拆分 Top 3

### Task 23: ExamDetailPage 拆分 [H-02 Part 1]

**Files:**
- Modify: `frontend/src/pages/ExamDetailPage.vue` — 保留 tab 壳
- Create: `frontend/src/pages/exam-detail/SubjectTab.vue`
- Create: `frontend/src/pages/exam-detail/CardTab.vue`
- Create: `frontend/src/pages/exam-detail/QuestionTab.vue`
- Create: `frontend/src/pages/exam-detail/ScanTab.vue`
- Create: `frontend/src/pages/exam-detail/GradingTab.vue`

- [ ] **Step 1-5: 按 Tab 逐个提取子组件**

每个子组件接收 `examId` 和 `subjectId` 作为 props，自管状态。ExamDetailPage 保留 tab 切换、exam 加载、全局 examId/subjectId。

- [ ] **Step 6: 跑前端测试**

Run: `cd frontend && npx vitest run`

- [ ] **Step 7: Commit**

---

### Task 24: AiGradingPage 拆分 [H-02 Part 2]

**Files:**
- Modify: `frontend/src/pages/AiGradingPage.vue`
- Create: `frontend/src/pages/ai-grading/ExamSelector.vue`
- Create: `frontend/src/pages/ai-grading/QuestionList.vue`
- Create: `frontend/src/pages/ai-grading/GradingPanel.vue`

- [ ] **Step 1-4: 提取 3 个子组件**
- [ ] **Step 5: 跑前端测试 + Commit**

---

### Task 25: GradingDispatchPage 拆分 [H-02 Part 3]

**Files:**
- Modify: `frontend/src/pages/GradingDispatchPage.vue`
- Create: `frontend/src/pages/dispatch/ScanStage.vue`
- Create: `frontend/src/pages/dispatch/ObjectiveStage.vue`
- Create: `frontend/src/pages/dispatch/GradingStage.vue`

- [ ] **Step 1-4: 按阶段提取子组件**
- [ ] **Step 5: 跑前端测试 + Commit**

---

### Task 26: Phase 2b 验证与 codex-review

同 Task 8 结构。

---

### Task 27: 审计报告更新

- [ ] **Step 1: 更新审计报告**

在 `docs/2026-04-26-tech-debt-audit.md` 末尾添加修复记录，每条 fix 附 commit SHA。

- [ ] **Step 2: 最终 Commit**

```bash
git add docs/2026-04-26-tech-debt-audit.md
git commit -m "$(cat <<'EOF'
docs: update tech debt audit with fix commit SHAs

All 21 C+H findings resolved across Phase 0-2.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```
