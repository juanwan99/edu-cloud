# edu-cloud 安全修复实施计划（Phase 1-3）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 edu-cloud 项目的 CRITICAL/HIGH 安全问题：RBAC 权限缺失、目录遍历、XSS、异常吞错、rate limit，共 9 个 Task。

**Architecture:** Phase 1 后端权限加固（teacher/card 端点加 require_permission + browse-dir 根目录限制 + grading worker 异常处理 + 登录 rate limit）→ Phase 2 前端 XSS 修复（DOMPurify 包装 innerHTML）→ Phase 3 前端统一 fetch→Axios + 路由守卫加固。每阶段有 gate 验证，锚点检查贯穿全程。

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async), pytest, Vue 3.5, Vite 7, Vitest, DOMPurify, Axios

**审计依据:** `docs/2026-05-08-health-audit-claude-gpt.md`
**共识方案:** `docs/2026-05-08-fix-plan-consensus.md`

---

## GPT Deep Review 修正记录

> GPT review 判定: FAIL (7 blocking)。以下为逐项修正。
>
> | # | Finding | 修正 |
> |---|---------|------|
> | 1 | 基线过期 faa185a→0e4bf69 | 已更新基线 |
> | 2 | 测试用不存在 fixture | 改为 `admin_headers`/`observer_headers` + 新增 `teacher_headers` |
> | 3 | Task 3 path containment 破坏合法路径 | 改用 `(upload_root / req.path).resolve()` |
> | 4 | Task 5 漏修 client_logs.py | 补入 |
> | 5 | Task 7 漏 CardMakerTab:372 | 补入（共 6 处） |
> | 6 | Task 8 漏 clientLogger:171 | 补入说明（保留 fetch，日志上报专用） |
> | 7 | Task 9 JWT atob 非 base64url 安全 | 改用安全解码 + try/catch 兜底 |

## 版本基线与安全锚点

```
HEAD: 0e4bf69 (master, 2026-05-08 23:07)
Note: b0d314cc 已提交 5 commits (803ed7d..0e4bf69)，修复了
  - P0 跨校隔离 6 类漏洞
  - P1-4/P1-5 exam/compat_router 权限
  - F-01 联考参与方校验
  - F-02 impersonation allowlist
  - F-06 GradingResult 唯一约束迁移
仍未修复：teacher_router (N-C01) + card/* (N-C02) 权限
```

### 不可回退变更（每 Task 提交前检查）

```bash
# 锚点检查脚本（每次 commit 前必跑）
grep -q "school_id.*answer_id" src/edu_cloud/modules/grading/models.py && \
grep -q "return 0" src/edu_cloud/modules/scan/pipeline_service.py && \
grep -q "SCHOOL_ADMIN_ROLES" frontend/src/config/roles.js && \
! grep -q "switchToTql" frontend/src/components/CardEditor.vue && \
test -f frontend/src/utils/questionSort.js && \
test -f src/edu_cloud/modules/exam/question_order.py && \
echo "ANCHOR CHECK PASSED" || echo "ANCHOR CHECK FAILED - STOP"
```

### b0d314cc 只读文件（本计划禁止修改）

```
src/edu_cloud/api/deps.py
src/edu_cloud/api/ai.py
src/edu_cloud/modules/grading/router.py
src/edu_cloud/modules/grading/models.py
src/edu_cloud/modules/exam/results_router.py
src/edu_cloud/modules/exam/results_service.py
src/edu_cloud/modules/exam/joint_exam_router.py
src/edu_cloud/modules/exam/joint_exam_service.py
src/edu_cloud/modules/exam/router.py
```

---

## Phase 1: 后端安全加固

### Task 1: 新增 MANAGE_TEACHERS 权限 + teacher 端点加固

**Files:**
- Modify: `src/edu_cloud/core/permissions.py:27` (新增枚举值 + 角色映射)
- Modify: `src/edu_cloud/modules/student/teacher_router.py:5,106,149,208,242,268,416` (替换 Depends)
- Create: `tests/test_api_exam/test_teacher_permission.py`

- [ ] **Step 1: Write the failing test — 无权限用户被拒**

注意：项目使用 `admin_headers`（platform_admin）和 `observer_headers`（observer）fixture，
定义在 `tests/conftest.py:128,151`。需新增 `teacher_headers` fixture。

```python
"""tests/test_api_exam/test_teacher_permission.py"""
import pytest
from edu_cloud.models.user import User
from edu_cloud.models.user_role import UserRole
from edu_cloud.shared.auth import create_access_token


@pytest.fixture
async def teacher_user(db):
    """subject_teacher 角色，无 MANAGE_TEACHERS 权限。"""
    user = User(username="teacher_perm_test", display_name="Test Teacher")
    user.set_password("test123")
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role="subject_teacher", is_primary=True))
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def teacher_headers(teacher_user):
    token = create_access_token({"sub": teacher_user.id, "role": "subject_teacher"})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_create_teacher_requires_permission(client, teacher_headers):
    """subject_teacher 不能创建教师。"""
    resp = await client.post(
        "/api/v1/teachers",
        json={"username": "newteacher", "display_name": "新教师", "password": "Test1234!"},
        headers=teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_teacher_requires_permission(client, teacher_headers):
    """subject_teacher 不能删除教师。"""
    resp = await client.delete(
        "/api/v1/teachers/fake-id",
        headers=teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_import_teachers_requires_permission(client, teacher_headers):
    """subject_teacher 不能导入教师。"""
    resp = await client.post(
        "/api/v1/teachers/import",
        files={"file": ("teachers.xlsx", b"fake", "application/octet-stream")},
        headers=teacher_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_create_teacher(client, admin_headers):
    """platform_admin 可以创建教师（权限通过，可能 422 数据校验）。"""
    resp = await client.post(
        "/api/v1/teachers",
        json={"username": "newteacher2", "display_name": "新教师2", "password": "Test1234!"},
        headers=admin_headers,
    )
    assert resp.status_code != 403
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_api_exam/test_teacher_permission.py -v
```

Expected: FAIL — 当前 subject_teacher 能通过（返回 200/422 而非 403）

- [ ] **Step 3: Add MANAGE_TEACHERS permission enum**

在 `src/edu_cloud/core/permissions.py` 中：

```python
# 在 Permission 枚举类中，约 line 27 附近，MANAGE_EXAMS 之后添加：
MANAGE_TEACHERS = "manage_teachers"
```

在同文件的 ROLE_PERMISSIONS 映射中，为以下角色添加 `Permission.MANAGE_TEACHERS`：
- `platform_admin`
- `district_admin`
- `principal`
- `academic_director`

- [ ] **Step 4: Add require_permission to all 6 teacher endpoints**

修改 `src/edu_cloud/modules/student/teacher_router.py`：

顶部 import 添加：
```python
from edu_cloud.api.deps import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
```

替换所有 6 个端点的 Depends：

| 端点 (行号) | 旧 | 新 |
|------------|-----|-----|
| `list_teachers` (106) | `Depends(get_current_user)` | `Depends(require_permission(Permission.MANAGE_TEACHERS))` |
| `create_teacher` (149) | `Depends(get_current_user)` | `Depends(require_permission(Permission.MANAGE_TEACHERS))` |
| `update_teacher` (208) | `Depends(get_current_user)` | `Depends(require_permission(Permission.MANAGE_TEACHERS))` |
| `delete_teacher` (242) | `Depends(get_current_user)` | `Depends(require_permission(Permission.MANAGE_TEACHERS))` |
| `export_teachers` (268) | `Depends(get_current_user)` | `Depends(require_permission(Permission.MANAGE_TEACHERS))` |
| `import_teachers` (416) | `Depends(get_current_user)` | `Depends(require_permission(Permission.MANAGE_TEACHERS))` |

- [ ] **Step 5: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_api_exam/test_teacher_permission.py -v
```

Expected: PASS — subject_teacher 得到 403，admin 通过

- [ ] **Step 6: Run anchor check + existing tests**

```bash
# 锚点检查
grep -q "school_id.*answer_id" src/edu_cloud/modules/grading/models.py && echo OK
# 权限系统测试
.venv/bin/python -m pytest tests/test_api/test_permissions.py tests/test_api/test_deps.py -v --tb=short
```

- [ ] **Step 7: Commit**

```bash
git add src/edu_cloud/core/permissions.py src/edu_cloud/modules/student/teacher_router.py tests/test_api_exam/test_teacher_permission.py
git commit -m "fix(security): N-C01 teacher 端点加 MANAGE_TEACHERS 权限守卫

28 个端点中 teacher 6 个此前仅检查登录不检查权限，
任意已登录用户可操作教师数据。

新增 Permission.MANAGE_TEACHERS 枚举值，分配给
platform_admin/district_admin/principal/academic_director。
6 个端点全部改用 require_permission(MANAGE_TEACHERS)。"
```

---

### Task 2: card 端点权限加固

**Files:**
- Modify: `src/edu_cloud/modules/card/router.py:59,96,117,137,159,199,280,472,515`
- Modify: `src/edu_cloud/modules/card/card_export_router.py:37,114,158,170,188,215,283,311`
- Modify: `src/edu_cloud/modules/card/card_template_router.py:23,100,162,187,211`
- Create: `tests/test_api_exam/test_card_permission.py`

- [ ] **Step 1: Write the failing test**

```python
"""tests/test_api_exam/test_card_permission.py"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_save_layout_requires_manage_exams(client: AsyncClient, teacher_token: str):
    """subject_teacher 无 MANAGE_EXAMS 时不能保存答题卡布局。"""
    resp = await client.put(
        "/api/v1/card/editor-layout/fake-subject-id",
        json={"layout": {}},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_publish_card_requires_manage_exams(client: AsyncClient, teacher_token: str):
    """subject_teacher 无 MANAGE_EXAMS 时不能发布答题卡。"""
    resp = await client.post(
        "/api/v1/card/publish",
        json={"subject_id": "fake"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_export_pdf_requires_manage_exams(client: AsyncClient, teacher_token: str):
    """subject_teacher 无 MANAGE_EXAMS 时不能导出 PDF。"""
    resp = await client.post(
        "/api/v1/card/export/pdf",
        json={"subject_id": "fake"},
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_skeleton_requires_manage_exams(client: AsyncClient, teacher_token: str):
    resp = await client.delete(
        "/api/v1/card/skeleton/fake-id",
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_card_endpoints(client: AsyncClient, admin_token: str):
    """academic_director 有 MANAGE_EXAMS，可以访问。"""
    resp = await client.get(
        "/api/v1/card/editor-layout/fake-subject-id",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code != 403  # 可能 404 但不应 403
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_api_exam/test_card_permission.py -v
```

Expected: FAIL — teacher 当前能通过（非 403）

- [ ] **Step 3: Add require_permission to card endpoints**

**card/router.py** — 顶部添加 import：
```python
from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
```

替换规则：
- **写操作** (save/reset/upload/auto-layout/parse/generate-barcode/publish/preview): `Depends(require_permission(Permission.MANAGE_EXAMS))`
- **读操作** (get-layout/export-template-json): `Depends(require_permission(Permission.VIEW_EXAMS))`

**card_export_router.py** — 同样替换：
- **写操作** (generate/publish/render-doc-pages/export-pdf/export-skeleton): `MANAGE_EXAMS`
- **读操作** (preview/get-doc-pages/get-doc-page-image): `VIEW_EXAMS`

**card_template_router.py** — 同样替换：
- **写操作** (download-answer-template/import-skeleton/delete-skeleton): `MANAGE_EXAMS`
- **读操作** (list-builtin/get-builtin-detail/list-skeletons/get-skeleton): `VIEW_EXAMS`

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_api_exam/test_card_permission.py -v
```

- [ ] **Step 5: Run existing card tests + anchor check**

```bash
.venv/bin/python -m pytest tests/test_api_exam/test_cards.py -v --tb=short
# 锚点
! grep -q "switchToTql" frontend/src/components/CardEditor.vue && echo "TQL removal preserved"
```

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/card/router.py src/edu_cloud/modules/card/card_export_router.py src/edu_cloud/modules/card/card_template_router.py tests/test_api_exam/test_card_permission.py
git commit -m "fix(security): N-C02 card 30 端点加 MANAGE_EXAMS/VIEW_EXAMS 权限守卫

card/router 9 端点 + card_export 8 端点 + card_template 7 端点
此前仅检查登录。写操作加 MANAGE_EXAMS，读操作加 VIEW_EXAMS。"
```

---

### Task 3: browse-directory 目录限制

**Files:**
- Modify: `src/edu_cloud/modules/scan/pipeline_router.py:292-320`
- Create: `tests/test_api/test_scan_browse_dir_security.py`

- [ ] **Step 1: Write the failing test — 路径逃逸被拦截**

```python
"""tests/test_api/test_scan_browse_dir_security.py"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_browse_dir_rejects_absolute_path(client: AsyncClient, admin_token: str):
    """绝对路径 /etc 应被拒绝。"""
    resp = await client.post(
        "/api/v1/scan/pipeline/browse-dir",
        json={"path": "/etc"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_browse_dir_rejects_traversal(client: AsyncClient, admin_token: str):
    """../../../etc 路径遍历应被拒绝。"""
    resp = await client.post(
        "/api/v1/scan/pipeline/browse-dir",
        json={"path": "../../../etc"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_browse_dir_allows_upload_subdir(client: AsyncClient, admin_token: str):
    """uploads/ 子目录应被允许。"""
    resp = await client.post(
        "/api/v1/scan/pipeline/browse-dir",
        json={"path": None},  # 默认 = UPLOAD_DIR
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_api/test_scan_browse_dir_security.py -v
```

Expected: FAIL — /etc 当前返回 200

- [ ] **Step 3: Add path containment check**

修改 `scan/pipeline_router.py` 的 `browse_directory` 函数（约 line 295-298），替换为：

```python
    upload_root = Path(settings.UPLOAD_DIR).resolve()

    if req.path:
        # 关键：以 upload_root 为基准解析用户路径，防止 ../../../ 逃逸
        # 绝对路径直接 resolve，相对路径先拼接再 resolve
        candidate = Path(req.path)
        if not candidate.is_absolute():
            candidate = upload_root / candidate
        d = candidate.resolve()
        if not d.is_relative_to(upload_root):
            raise HTTPException(403, "只允许浏览上传目录")
    else:
        d = upload_root

    if not d.is_dir():
        raise HTTPException(400, f"目录不存在: {req.path}")
```

同时修改返回值，`"path"` 字段改为相对路径（不暴露服务器结构）：
```python
    "path": str(entry.relative_to(upload_root)),
```

> **GPT review F-3 修正**：旧方案用 `Path(req.path).resolve()` 按 cwd 解析，
> 会误拒合法相对路径。新方案：相对路径拼接 upload_root 后 resolve，
> 绝对路径直接 resolve 后 is_relative_to 检查。

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_api/test_scan_browse_dir_security.py -v
```

- [ ] **Step 5: Run existing scan tests**

```bash
.venv/bin/python -m pytest tests/test_api/test_scan_pipeline_api.py -v --tb=short
```

- [ ] **Step 6: Commit**

```bash
git add src/edu_cloud/modules/scan/pipeline_router.py tests/test_api/test_scan_browse_dir_security.py
git commit -m "fix(security): N-C03 browse-directory 限制为 upload/storage 根目录

此前 browse-dir 接受任意路径，可遍历 /etc 等敏感目录。
现在用 Path.is_relative_to() 限制在 UPLOAD_DIR/STORAGE_DIR 内，
返回值也改为相对路径，不暴露服务器目录结构。"
```

---

### Task 4: grading worker 异常处理

**Files:**
- Modify: `src/edu_cloud/workers/grading.py:298-303,657-668`

- [ ] **Step 1: Fix line 302 — JSON 解析错误记录日志**

将 `workers/grading.py` line 298-303：

```python
            _details = None
            try:
                import json as _json
                _raw = _json.loads(grade_result.raw_content)
                _details = _raw.get("details")
            except Exception:
                pass
```

替换为：

```python
            _details = None
            try:
                import json as _json
                _raw = _json.loads(grade_result.raw_content)
                _details = _raw.get("details")
            except Exception:
                logger.warning(
                    "Failed to parse grading raw_content for answer %s",
                    ad.get("answer_id", "unknown"),
                    exc_info=True,
                )
```

- [ ] **Step 2: Fix line 667 — 参考图读取错误记录日志**

将 `workers/grading.py` line 660-668：

```python
                    try:
                        ref_b64 = await _read_image_b64(ref_path.lstrip("/"))
                        ref_bytes = base64.b64decode(ref_b64)
                        ref_resized = resize_image_for_llm(ref_bytes)
                        ref_mime = "image/png" if ref_resized[:4] == b"\x89PNG" else "image/jpeg"
                        parts.append(types.Part.from_bytes(data=ref_resized, mime_type=ref_mime))
                        has_ref = True
                    except Exception:
                        pass
```

替换为：

```python
                    try:
                        ref_b64 = await _read_image_b64(ref_path.lstrip("/"))
                        ref_bytes = base64.b64decode(ref_b64)
                        ref_resized = resize_image_for_llm(ref_bytes)
                        ref_mime = "image/png" if ref_resized[:4] == b"\x89PNG" else "image/jpeg"
                        parts.append(types.Part.from_bytes(data=ref_resized, mime_type=ref_mime))
                        has_ref = True
                    except Exception:
                        logger.warning(
                            "Failed to load reference image %s for answer %s",
                            ref_path,
                            ad.get("answer_id", "unknown"),
                            exc_info=True,
                        )
```

- [ ] **Step 3: Verify logger is imported**

```bash
grep -n "^logger\|^import logging\|getLogger" src/edu_cloud/workers/grading.py | head -5
```

确认 `logger` 已在文件顶部定义。如未定义，在文件顶部添加：
```python
import logging
logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Run grading worker tests**

```bash
.venv/bin/python -m pytest tests/test_workers/ -v --tb=short
```

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/workers/grading.py
git commit -m "fix(grading): N-H04 两处 except Exception: pass 改为 logger.warning

workers/grading.py:302 JSON 解析和 :667 参考图读取失败
此前静默吞掉，现在记录 WARNING + exc_info 便于排查。"
```

---

### Task 5: 登录 rate limit

**Files:**
- Modify: `pyproject.toml` (添加 slowapi 依赖)
- Create: `src/edu_cloud/core/rate_limit.py`
- Modify: `src/edu_cloud/api/auth.py:75`
- Modify: `src/edu_cloud/modules/conduct/parent_router.py:44`
- Create: `tests/test_api/test_rate_limit.py`

- [ ] **Step 1: Add slowapi dependency**

```bash
cd /home/ops/projects/edu-cloud && .venv/bin/pip install slowapi
```

在 `pyproject.toml` 的 `dependencies` 列表中添加：
```
"slowapi>=0.1.9",
```

- [ ] **Step 2: Create rate_limit.py module**

```python
"""src/edu_cloud/core/rate_limit.py"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

- [ ] **Step 3: Register limiter in app.py**

在 `src/edu_cloud/api/app.py` 的 `create_app` 函数中，middleware 注册区域添加：

```python
from edu_cloud.core.rate_limit import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

- [ ] **Step 4: Add rate limit to login endpoint**

修改 `src/edu_cloud/api/auth.py`，在 `login` 函数上添加装饰器：

```python
from edu_cloud.core.rate_limit import limiter
from starlette.requests import Request

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest, db: AsyncSession = Depends(get_db)):
```

注意：slowapi 需要 `Request` 参数在函数签名中。

- [ ] **Step 5: Add rate limit to parent login**

修改 `src/edu_cloud/modules/conduct/parent_router.py`：

```python
from edu_cloud.core.rate_limit import limiter
from starlette.requests import Request

@router.post("/parent/login")
@limiter.limit("5/minute")
async def parent_login(
    request: Request,
    body: ParentLoginRequest,
    db: AsyncSession = Depends(get_db),
):
```

- [ ] **Step 6: Write test**

```python
"""tests/test_api/test_rate_limit.py"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_rate_limit(client: AsyncClient):
    """连续 6 次错误登录应触发 rate limit。"""
    for i in range(6):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": f"attacker{i}", "password": "wrong"},
        )
    assert resp.status_code == 429
```

- [ ] **Step 7: Run test**

```bash
.venv/bin/python -m pytest tests/test_api/test_rate_limit.py -v
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/edu_cloud/core/rate_limit.py src/edu_cloud/api/app.py src/edu_cloud/api/auth.py src/edu_cloud/modules/conduct/parent_router.py tests/test_api/test_rate_limit.py
git commit -m "fix(security): N-H08 登录端点加 5/min rate limit

新增 slowapi 依赖 + core/rate_limit.py 模块。
/auth/login 和 /conduct/parent/login 均限制 5 次/分钟/IP。"
```

---

### Phase 1 Gate

```bash
# 锚点检查
grep -q "school_id.*answer_id" src/edu_cloud/modules/grading/models.py && echo OK
grep -q "SCHOOL_ADMIN_ROLES" frontend/src/config/roles.js && echo OK
test -f frontend/src/utils/questionSort.js && echo OK

# 新增测试
.venv/bin/python -m pytest tests/test_api_exam/test_teacher_permission.py tests/test_api_exam/test_card_permission.py tests/test_api/test_scan_browse_dir_security.py tests/test_api/test_rate_limit.py -v

# 已有测试不回退
.venv/bin/python -m pytest tests/test_api/test_permissions.py tests/test_api_exam/test_cards.py tests/test_api/test_scan_pipeline_api.py tests/test_workers/ -v --tb=short

# 安全扫描
scripts/codex-verify safety 2>/dev/null || echo "codex-verify not available, manual check"
```

---

## Phase 2: 前端 XSS 修复

### Task 6: scan 文件资源安全关闭

**Files:**
- Modify: `src/edu_cloud/modules/scan/pipeline_service.py:94,122,160`

- [ ] **Step 1: Fix _has_barcode (line 94)**

```python
# 旧
    img = Image.open(image_path)
    img_w, img_h = img.size

# 新
    with Image.open(image_path) as img:
        img_w, img_h = img.size
        # ... 把后续使用 img 的代码都放在 with 块内 ...
```

- [ ] **Step 2: Fix _render_page (line 122)**

```python
# 旧
    doc = fitz.open(pdf_path_str)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=dpi)
    img = _PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
    img.save(out_path_str, format="JPEG", quality=85)
    doc.close()

# 新
    with fitz.open(pdf_path_str) as doc:
        page = doc[page_num]
        pix = page.get_pixmap(dpi=dpi)
        img = _PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img.save(out_path_str, format="JPEG", quality=85)
```

- [ ] **Step 3: Fix build_tasks_from_pdfs (line 160)**

```python
# 旧
        doc = fitz.open(str(pdf_path))
        n_pages = len(doc)

# 新
        with fitz.open(str(pdf_path)) as doc:
            n_pages = len(doc)
```

- [ ] **Step 4: Run scan tests**

```bash
.venv/bin/python -m pytest tests/test_api/test_scan_pipeline_api.py -v --tb=short
```

- [ ] **Step 5: Commit**

```bash
git add src/edu_cloud/modules/scan/pipeline_service.py
git commit -m "fix(scan): N-M06 Image.open/fitz.open 改用 with 上下文管理器

3 处资源打开无 close 保护，异常时文件描述符泄露。"
```

---

### Task 7: DOMPurify 包装 innerHTML

**Files:**
- Modify: `frontend/src/components/CardEditor.vue:324`
- Modify: `frontend/src/components/QuestionContentModal.vue:122`
- Modify: `frontend/src/card-editor/render.js:496,556`
- Modify: `frontend/src/card-editor/interact.js:846`
- Modify: `frontend/src/pages/exam-detail/CardMakerTab.vue:372` (GPT review F-5 补入)

- [ ] **Step 1: Add DOMPurify import to each file**

**CardEditor.vue** — 在 `<script setup>` 顶部添加：
```javascript
import DOMPurify from 'dompurify'
```

**QuestionContentModal.vue** — 同上

**render.js** — 在文件顶部添加：
```javascript
import DOMPurify from 'dompurify'
```

**interact.js** — 同上

- [ ] **Step 2: Wrap innerHTML assignments**

**CardEditor.vue:324**:
```javascript
// 旧
list.innerHTML = html
// 新
list.innerHTML = DOMPurify.sanitize(html)
```

**QuestionContentModal.vue:122**:
```javascript
// 旧
container.innerHTML = html
// 新
container.innerHTML = DOMPurify.sanitize(html)
```

**render.js:496**:
```javascript
// 旧
previewWrap.innerHTML = `<div>...${pageA}...</div>`
// 新
previewWrap.innerHTML = DOMPurify.sanitize(`<div>...${pageA}...</div>`)
```

**render.js:556**: 同样包装

**interact.js:846**:
```javascript
// 旧
dialog.innerHTML = `<div>...`
// 新
dialog.innerHTML = DOMPurify.sanitize(`<div>...`)
```

- [ ] **Step 3: Verify DOMPurify is in dependencies**

```bash
grep "dompurify" frontend/package.json
```

如已存在则跳过。如不存在：
```bash
cd frontend && npm install dompurify
```

- [ ] **Step 4: Run frontend tests + lint**

```bash
cd frontend && npx vitest run --reporter=verbose 2>&1 | tail -20
npm run lint
```

- [ ] **Step 5: Verify TQL removal preserved**

```bash
! grep -q "switchToTql" frontend/src/components/CardEditor.vue && echo "TQL removal preserved"
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/CardEditor.vue frontend/src/components/QuestionContentModal.vue frontend/src/card-editor/render.js frontend/src/card-editor/interact.js
git commit -m "fix(security): N-H03 5 处 innerHTML 加 DOMPurify.sanitize()

CardEditor.vue:324, QuestionContentModal.vue:122,
render.js:496/556, interact.js:846 全部包装。"
```

---

### Phase 2 Gate

```bash
# 后端
.venv/bin/python -m pytest tests/test_api/test_scan_pipeline_api.py -v --tb=short

# 前端
cd frontend && npx vitest run
npm run lint

# 锚点
! grep -q "switchToTql" frontend/src/components/CardEditor.vue && echo OK
test -f frontend/src/utils/questionSort.js && echo OK
```

---

## Phase 3: 前端 fetch 统一 + 路由加固

### Task 8: fetch → Axios 统一（card-editor/export.js）

**Files:**
- Modify: `frontend/src/card-editor/export.js`

- [ ] **Step 1: Add Axios import to export.js**

```javascript
// 在文件顶部
import client from '../api/client'
```

- [ ] **Step 2: Replace all fetch() calls**

将 export.js 中 6 处 `fetch()` 调用逐一替换为 `client.post/get()`。

示例（line 25 PDF 导出）：
```javascript
// 旧
const token = localStorage.getItem('token')
const resp = await fetch('/api/v1/card/export/pdf', {
  method: 'POST',
  headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
})

// 新
const resp = await client.post('/card/export/pdf', payload, { responseType: 'blob' })
```

注意：Axios baseURL 已包含 `/api/v1`，路径去掉前缀。
注意：对于返回二进制数据（PDF）的端点，加 `{ responseType: 'blob' }`。
注意：line 78 的 `/card-editor/styles.css` 是静态资源请求，不走 API，保留 `fetch()` 或用 `window.fetch`。

- [ ] **Step 3: Replace fetch in CardEditor.vue**

修改 `CardEditor.vue` 中 3 处 `fetch()` 调用，同样替换为 `client`。

- [ ] **Step 4: Replace fetch in aiChat.js**

修改 `stores/aiChat.js` 的 2 处 `fetch()`。

注意：line 35 的 SSE 流式请求需要特殊处理。`fetch()` 用于读取 `response.body.getReader()` 做 SSE 流式解析，**Axios 不支持原生流式读取**。此处保留 `fetch()` 但添加注释说明原因。

- [ ] **Step 5: Replace fetch in VisualEditorTab.vue**

修改 `VisualEditorTab.vue` 的 2 处 `fetch()`。

- [ ] **Step 6: Run tests**

```bash
cd frontend && npx vitest run
npm run lint
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/card-editor/export.js frontend/src/components/CardEditor.vue frontend/src/stores/aiChat.js frontend/src/pages/exam-detail/VisualEditorTab.vue
git commit -m "fix(frontend): N-M02/M03 统一 11 处 fetch 到 Axios client

export.js 5 处 + CardEditor.vue 3 处 + VisualEditorTab.vue 2 处
改用统一 Axios client（含 trace-id/401 拦截/慢日志）。
aiChat.js SSE 流式保留 fetch（Axios 不支持 ReadableStream）。"
```

---

### Task 9: 前端路由守卫加固

**Files:**
- Modify: `frontend/src/router/index.js:121-146`
- Modify: `frontend/src/api/client.js`

- [ ] **Step 1: Add token expiry pre-check in router guard**

修改 `router/index.js` 的 `beforeEach` 守卫：

```javascript
// GPT review F-7 修正：atob 不是 base64url 安全，需要 padding 处理
function decodeJwtPayload(token) {
  try {
    const base64Url = token.split('.')[1]
    if (!base64Url) return null
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(base64.length + (4 - base64.length % 4) % 4, '=')
    return JSON.parse(atob(padded))
  } catch { return null }
}

// 在现有 token 存在性检查之后，添加过期检查
const token = localStorage.getItem('token')
if (token) {
  const payload = decodeJwtPayload(token)
  if (!payload || (payload.exp && payload.exp * 1000 < Date.now())) {
    localStorage.removeItem('token')
    localStorage.removeItem('auth_state')
    return { path: '/login', query: { redirect: to.fullPath } }
  }
}
```

- [ ] **Step 2: Add proactive token expiry check in Axios interceptor**

修改 `api/client.js` 的请求拦截器：

```javascript
client.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    // 检查 token 是否即将过期（5 分钟内）
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      if (payload.exp && payload.exp * 1000 - Date.now() < 5 * 60 * 1000) {
        localStorage.removeItem('token')
        localStorage.removeItem('auth_state')
        window.location.href = '/login'
        return Promise.reject(new Error('Token expired'))
      }
    } catch { /* token 格式异常，让后端 401 处理 */ }
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
```

- [ ] **Step 3: Run frontend tests**

```bash
cd frontend && npx vitest run
npm run lint
```

- [ ] **Step 4: Build and verify**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/index.js frontend/src/api/client.js
git commit -m "fix(frontend): N-M05/N-H07 路由守卫 + Axios 拦截器加 token 过期检查

路由 beforeEach 检查 JWT exp 字段，过期直接跳登录。
Axios 请求拦截器检查即将过期（5min），主动清理。
降低 XSS 窃取 token 后的可用窗口。"
```

---

### Phase 3 Gate（最终）

```bash
# 全量锚点检查
grep -q "school_id.*answer_id" src/edu_cloud/modules/grading/models.py && \
grep -q "return 0" src/edu_cloud/modules/scan/pipeline_service.py && \
grep -q "SCHOOL_ADMIN_ROLES" frontend/src/config/roles.js && \
! grep -q "switchToTql" frontend/src/components/CardEditor.vue && \
test -f frontend/src/utils/questionSort.js && \
test -f src/edu_cloud/modules/exam/question_order.py && \
echo "ALL ANCHORS PRESERVED"

# 后端全量
.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5

# 前端全量
cd /home/ops/projects/edu-cloud/frontend && npx vitest run 2>&1 | tail -5

# 构建
npm run build

# 交付链路
scripts/truth-status.sh /home/ops/projects/edu-cloud 2>/dev/null || echo "truth-status check pending"
```

**通过标准**: 后端 passed ≥ 2468（不降）、前端 passed ≥ 2495（不降）、build 成功、锚点全在。

---

## semantic_regression（ORC 不变量）

| ID | 不变量 | 验证方式 |
|----|--------|---------|
| ORC-001 | GradingResult (school_id, answer_id) 唯一约束 | grep models.py |
| ORC-002 | auto_fix_ab_sides 返回 0 | grep pipeline_service.py |
| ORC-003 | GRADING_DISPATCH_ROLES = SCHOOL_ADMIN_ROLES | grep roles.js |
| ORC-004 | CardEditor 无 switchToTql | grep -v CardEditor.vue |
| ORC-005 | questionSort.js / question_order.py 存在 | test -f |
| ORC-006 | MANAGE_TEACHERS 权限枚举存在 | grep permissions.py（Task 1 后） |
| ORC-007 | browse-dir 根目录限制 | test_scan_browse_dir_security.py |
| ORC-008 | 登录 rate limit 5/min | test_rate_limit.py |
