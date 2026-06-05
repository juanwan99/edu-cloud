# edu-cloud 结构性安全修复方案 v2

> 日期：2026-06-04  
> 方案性质：T3 级结构性修复方案  
> 适用项目：`/home/ops/projects/edu-cloud`  
> 目标：从根因修复 `StudentAnswer` 归属链、服务器文件路径边界、AI 工具模块治理问题，同时避免破坏现有正常功能  
> 重要前提：本方案先做只读体检，再改代码；所有行为变更均有回归测试兜底

---

## 0. 方案结论

本次修复不能按“单接口补 if”处理，也不能直接套一层通用 path resolver。正确做法是建立两类共享边界能力：

1. **领域归属链边界**：所有写入 `StudentAnswer` 的入口必须统一验证 `school -> exam -> subject -> question`。
2. **文件路径访问边界**：所有用户输入路径、数据库存储路径、worker 读取路径必须通过共享安全函数解析，并且保留现有 `./storage/...` 历史路径兼容。

这版方案相比原方案的关键修正：

- 补上遗漏的 `/api/v1/scan/upload/batch`。
- 补上 pipeline template 中 `question_id/question_ids` 的一次性预校验。
- 路径函数拆分为“用户输入路径”和“数据库存储路径”，避免把 `./storage/...` 错解析到 `uploads/./storage/...`。
- 路径安全不仅检查 `UPLOAD_DIR/STORAGE_ROOT`，还要支持 school tenant containment。
- 历史数据体检前置为 Phase 0。
- 权限影响按真实角色表评估，而不是按简化角色假设。

---

## 1. 修复目标与非目标

### 1.1 修复目标

| 编号 | 目标 | 成功标准 |
|------|------|----------|
| G1 | 根治 `StudentAnswer` 跨科目/跨考试错写 | 任意公开/兼容/pipeline 写入口都无法写入 `subject_id` 与 `question_id` 不一致的数据 |
| G2 | 根治服务器任意目录导入/读取 | 用户输入路径不能越过允许根目录和学校边界；数据库旧路径读取不被误伤 |
| G3 | 收紧旧 marking import 权限 | 非授权角色无法触发服务器目录扫描和答卷落库 |
| G4 | 修复 AI 工具 module_code 漂移 | 所有工具 module_code 都存在于 `MODULE_CODES`，非法注册在测试/启动时失败 |
| G5 | 不破坏现有功能 | 现有 `./storage/...` 答卷图片、AI 阅卷 worker、正常扫描上传和 pipeline 均保持可用 |

### 1.2 非目标

| 非目标 | 原因 |
|--------|------|
| 重写扫描/阅卷架构 | 当前问题可通过边界层和集中校验修复 |
| 立即迁移 SQLite 到 Postgres | 属于部署架构专项，不和本修复混在一起 |
| 全量收敛 ruff 未使用导入 | 不影响本次安全边界修复，单独分阶段处理 |
| 批量修复历史 orphan question_id | 先体检和分布分析，再决定是否写数据修复脚本 |

---

## 2. 根因模型

### RC-1：核心领域不变量没有集中表达

`StudentAnswer` 的真实业务不变量是：

```text
StudentAnswer.school_id == Exam.school_id == Subject.school_id == Question.school_id
StudentAnswer.exam_id == Subject.exam_id
StudentAnswer.subject_id == Question.subject_id
StudentAnswer.question_id == Question.id
```

当前代码把这个不变量分散在不同路由中，有些只校验 school，有些校验 exam/subject，有些完全信任上游模板。这就是跨科目写入的根因。

### RC-2：文件路径安全按模块私有实现，缺少统一语义

当前项目内已有正确片段：

- scan pipeline 有 `resolve + is_relative_to`。
- scan pipeline 还有 `_check_scan_path_tenant`。
- storage 写入时按 `storage/{school}/{exam}/{subject}/{question}/{student}.png` 组织。

问题是这些规则没有成为共享能力，旧 marking importer 和 grading/worker 读取路径没有复用。

### RC-3：用户输入路径和数据库存储路径混为一谈

这是原方案可能破坏功能的关键点。两类路径语义不同：

| 路径来源 | 例子 | 解析基准 |
|----------|------|----------|
| 用户输入上传目录 | `scan-input/exam1`、`/home/.../uploads/...` | 默认相对 `UPLOAD_DIR` |
| 数据库存储图片路径 | `./storage/{school}/{exam}/...` | 默认相对项目 cwd，再检查是否落在 `STORAGE_ROOT`/`UPLOAD_DIR` |

不能用同一个“相对路径默认拼 uploads”的函数处理数据库路径，否则现有 `./storage/...` 会被误判或找不到。

### RC-4：工具注册缺少模块码合法性断言

AI 工具使用的 `module_code` 会参与 `enabled_modules` 过滤。如果工具声明了 `MODULE_CODES` 中不存在的模块码，会静默不可用。

---

## 3. Phase 0：只读体检与兼容性基线

> 必须先做。此阶段不改代码、不改数据。

### 3.1 数据体检 SQL

新增脚本建议：

```text
scripts/audit_student_answer_integrity.py
```

检查项：

```sql
-- A1: subject_id 与 question.subject_id 不一致
SELECT count(*)
FROM student_answers sa
JOIN questions q ON q.id = sa.question_id
WHERE sa.subject_id != q.subject_id;

-- A2: exam_id 与 subject.exam_id 不一致
SELECT count(*)
FROM student_answers sa
JOIN subjects s ON s.id = sa.subject_id
WHERE sa.exam_id != s.exam_id;

-- A3: question_id 指向不存在的 question
SELECT count(*)
FROM student_answers sa
LEFT JOIN questions q ON q.id = sa.question_id
WHERE sa.question_id IS NOT NULL AND q.id IS NULL;

-- A4: subject_id 指向不存在的 subject
SELECT count(*)
FROM student_answers sa
LEFT JOIN subjects s ON s.id = sa.subject_id
WHERE sa.subject_id IS NOT NULL AND s.id IS NULL;
```

### 3.2 image_path 分布体检

必须输出以下分类：

```text
total image_path
./storage/*
storage/*
/home/.../storage/*
./uploads/*
uploads/*
/home/.../uploads/*
/tmp/*
/mnt/*
其他绝对路径
其他相对路径
```

已知当前生产库观测结果：

```text
image_path 非空：26402
./storage/*：26402
```

因此后续 path safety 必须兼容 `./storage/...`。

### 3.3 marking import 调用影响体检

从日志中只看接口调用还不够，因为测试也会写 `logs/app.jsonl`。上线前需要用 `user_id` 回查角色：

```sql
SELECT ur.role, count(*)
FROM user_roles ur
WHERE ur.user_id IN (...)
GROUP BY ur.role;
```

如果发现真实业务中 `subject_teacher` 直接使用 `/marking/import`，不能悄悄上线 403；需要产品确认：

- 该能力是否应由普通科任老师使用？
- 如果要允许，是否只允许导入自己学科/自己班级？
- 如果不允许，前端入口是否需要隐藏或提示权限不足？

### 3.4 Phase 0 通过标准

- 输出一份只读体检结果。
- 明确历史 `image_path` 兼容策略。
- 明确 `/marking/import` 真实调用角色。
- 若发现 mismatch/orphan，不在本阶段修数据，只记录数量和样例。

---

## 4. Phase 1：统一归属链校验

### 4.1 新增共享函数

新增文件：

```text
src/edu_cloud/core/ownership.py
```

建议接口：

```python
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Subject, Question


async def verify_exam_subject_chain(
    db: AsyncSession,
    *,
    school_id: str,
    exam_id: str,
    subject_id: str,
) -> tuple[Exam, Subject]:
    exam = (await db.execute(
        select(Exam).where(
            Exam.id == exam_id,
            Exam.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "Exam not found")

    subject = (await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.exam_id == exam_id,
            Subject.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found")

    return exam, subject


async def verify_exam_subject_question_chain(
    db: AsyncSession,
    *,
    school_id: str,
    exam_id: str,
    subject_id: str,
    question_id: str,
) -> tuple[Exam, Subject, Question]:
    exam, subject = await verify_exam_subject_chain(
        db,
        school_id=school_id,
        exam_id=exam_id,
        subject_id=subject_id,
    )

    question = (await db.execute(
        select(Question).where(
            Question.id == question_id,
            Question.subject_id == subject_id,
            Question.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found")

    return exam, subject, question
```

### 4.2 批量校验函数

为 batch/objective/pipeline 避免 N+1，增加批量版本：

```python
async def verify_questions_belong_to_subject(
    db: AsyncSession,
    *,
    school_id: str,
    subject_id: str,
    question_ids: list[str],
) -> dict[str, Question]:
    unique_ids = list(dict.fromkeys(question_ids))
    if not unique_ids:
        return {}

    questions = (await db.execute(
        select(Question).where(
            Question.id.in_(unique_ids),
            Question.subject_id == subject_id,
            Question.school_id == school_id,
        )
    )).scalars().all()

    by_id = {q.id: q for q in questions}
    missing = [qid for qid in unique_ids if qid not in by_id]
    if missing:
        raise HTTPException(404, f"Question not found: {missing[0]}")
    return by_id
```

### 4.3 必改消费方

| 路径 | 文件 | 改法 |
|------|------|------|
| `/api/v1/scan/upload` | `src/edu_cloud/modules/scan/router.py` | 使用 `verify_exam_subject_question_chain` |
| `/api/v1/scan/upload/batch` | `src/edu_cloud/modules/scan/router.py` | 先 `verify_exam_subject_chain`，再批量校验全部 qids |
| `/api/v1/scan/upload-objective` | `src/edu_cloud/modules/scan/router.py` | 先校验 exam/subject，再批量校验 request answers 的 question_ids |
| `/api/scan/upload` | `src/edu_cloud/api/compat_router.py` | 可替换为共享函数，行为不变 |
| `/api/scan/upload-objective` | `src/edu_cloud/api/compat_router.py` | 批量校验 question_ids 属于 subject |
| pipeline start | `src/edu_cloud/modules/scan/pipeline_router.py` | enqueue 前校验 template 中所有 `question_id/question_ids` 属于当前 subject |

### 4.4 Pipeline 特别处理

不要在 worker save 阶段逐条查 DB。正确位置是 `start_pipeline` enqueue 前：

```python
def collect_template_question_ids(regions: list[dict]) -> list[str]:
    ids = []
    for r in regions:
        if r.get("question_id"):
            ids.append(str(r["question_id"]))
        for qid in r.get("question_ids") or []:
            ids.append(str(qid))
    return ids
```

然后：

```python
template_qids = collect_template_question_ids(regions_for_factory)
await verify_questions_belong_to_subject(
    db,
    school_id=school_id,
    subject_id=req.subject_id,
    question_ids=template_qids,
)
```

这样既不引入 N+1，也把 template 分支纳入统一不变量。

### 4.5 Phase 1 测试

新增/修改测试：

```text
test_upload_single_rejects_subject_from_other_exam
test_upload_single_rejects_question_from_other_subject
test_upload_batch_rejects_question_from_other_subject
test_upload_batch_rejects_subject_from_other_exam
test_upload_objective_rejects_question_from_other_subject
test_compat_upload_objective_rejects_question_from_other_subject
test_pipeline_rejects_template_question_from_other_subject
test_pipeline_accepts_valid_template_questions
```

### 4.6 Phase 1 不破坏正常功能的保证

必须保留：

- 正常 single upload 成功。
- 正常 batch upload 成功。
- 正常 objective upload 成功。
- 缺考 `is_absent=True` 路径成功。
- pipeline 使用正常模板成功入队。

---

## 5. Phase 2：共享路径安全层

### 5.1 新增共享文件

新增：

```text
src/edu_cloud/shared/path_safety.py
```

### 5.2 路径函数设计

必须拆分两类入口。

#### 5.2.1 用户输入路径

用于 browse-dir、scan-dir、pipeline start、marking import 等由请求体传入的目录/文件。

```python
def resolve_user_path_under_roots(
    p: str | Path,
    *,
    default_root: Path,
    allowed_roots: list[Path],
) -> Path:
    candidate = Path(p)
    if not candidate.is_absolute():
        candidate = default_root / candidate
    resolved = candidate.resolve()
    roots = [r.resolve() for r in allowed_roots]
    if not any(resolved == r or resolved.is_relative_to(r) for r in roots):
        raise HTTPException(403, "路径不在允许的根目录范围内")
    return resolved
```

#### 5.2.2 数据库存储路径

用于 `StudentAnswer.image_path` 读取前校验，必须兼容：

- `./storage/...`
- `storage/...`
- `/home/ops/projects/edu-cloud/storage/...`
- `./uploads/...`
- `uploads/...`
- `/home/ops/projects/edu-cloud/uploads/...`

```python
def resolve_stored_file_path(
    p: str | Path,
    *,
    allowed_roots: list[Path] | None = None,
) -> Path:
    roots = [r.resolve() for r in (allowed_roots or [
        Path(settings.UPLOAD_DIR),
        Path(settings.STORAGE_ROOT),
    ])]

    candidate = Path(p)

    # 关键：数据库历史值如 ./storage/... 必须相对当前项目 cwd 解析，
    # 不能默认拼到 UPLOAD_DIR。
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate

    resolved = candidate.resolve()
    if not any(resolved == r or resolved.is_relative_to(r) for r in roots):
        raise HTTPException(403, "文件路径不在允许范围内")
    return resolved
```

### 5.3 school tenant containment

仅 root containment 不够。新增可选函数：

```python
def assert_path_for_school(
    resolved: Path,
    *,
    school_id: str | None,
    storage_root: Path | None = None,
    upload_root: Path | None = None,
) -> None:
    if not school_id:
        return

    storage_root = (storage_root or Path(settings.STORAGE_ROOT)).resolve()
    upload_root = (upload_root or Path(settings.UPLOAD_DIR)).resolve()

    # storage 当前结构：storage/{school_id}/{exam_id}/{subject_id}/...
    if resolved.is_relative_to(storage_root):
        rel = resolved.relative_to(storage_root)
        if rel.parts and rel.parts[0] != school_id:
            raise HTTPException(403, "无权访问其他学校文件")

    # uploads 当前 scan-input 结构：uploads/{school_id}/scan-input/{exam_id}/...
    if resolved.is_relative_to(upload_root):
        rel = resolved.relative_to(upload_root)
        # doc-pages 等历史路径未必以 school_id 开头，不能一刀切。
        # 对 scan-input 强制 school_id；其他业务目录按各自业务 ownership 校验。
        if rel.parts and rel.parts[0] == "scan-input":
            raise HTTPException(403, "scan-input 必须位于学校目录下")
        if len(rel.parts) >= 2 and rel.parts[1] == "scan-input" and rel.parts[0] != school_id:
            raise HTTPException(403, "无权访问其他学校扫描目录")
```

注意：`uploads/doc-pages/...` 当前不是统一 school 前缀，不能粗暴要求 `rel.parts[0] == school_id`。doc-pages 应继续用 subject ownership 校验。

### 5.4 Marking import 改造

目标：

- 权限从登录态提升到 `MANAGE_GRADING`。
- 输入路径必须在允许根内。
- 默认只允许 `UPLOAD_DIR` 下的扫描输入目录。
- 如果确需支持 `STORAGE_ROOT` 导入，必须明确写入白名单和测试。

建议第一版更保守：

```python
resolved_root = resolve_user_path_under_roots(
    req.folder_path,
    default_root=Path(settings.UPLOAD_DIR).resolve(),
    allowed_roots=[Path(settings.UPLOAD_DIR).resolve()],
)
assert_path_for_school(resolved_root, school_id=school_id)
```

然后调用：

```python
stats = await import_from_folder(db, req.exam_id, str(resolved_root), school_id)
```

如果测试里大量使用 `tmp_path`，测试应显式 monkeypatch `settings.UPLOAD_DIR = tmp_path` 或使用项目内临时 uploads 目录，而不是放宽生产逻辑。

### 5.5 图片读取改造

改造位置：

| 位置 | 当前问题 | 改法 |
|------|----------|------|
| `marking/router.py` answer image | `open(answer.image_path)` 前无 containment | 使用 `resolve_stored_file_path` + `assert_path_for_school` |
| `grading/router.py` AI rescore | `aiofiles.open(answer.image_path)` 前无 containment | 同上 |
| `workers/grading.py::_read_image_b64` | worker 直接读路径 | 在 `_read_image_b64` 内统一校验 |

worker 内建议：

```python
async def _read_image_b64(path: str, *, school_id: str | None = None) -> str:
    safe_path = resolve_stored_file_path(path)
    assert_path_for_school(safe_path, school_id=school_id)
    async with aiofiles.open(safe_path, "rb") as f:
        data = await f.read()
    return base64.b64encode(data).decode()
```

调用方已有 `ad` 字典时，应传入 `ad.get("school_id")`。

### 5.6 Phase 2 测试

新增/修改：

```text
test_resolve_stored_file_path_accepts_dot_storage
test_resolve_stored_file_path_accepts_absolute_storage
test_resolve_stored_file_path_rejects_tmp
test_marking_import_requires_manage_grading
test_marking_import_rejects_path_outside_upload_root
test_marking_import_accepts_allowed_upload_root
test_marking_answer_image_accepts_existing_dot_storage_path
test_marking_answer_image_rejects_other_school_storage_path
test_grading_rescore_accepts_existing_dot_storage_path
test_worker_read_image_rejects_path_outside_allowed_roots
```

### 5.7 Phase 2 不破坏正常功能的保证

必须证明：

- 生产现有 `./storage/...` 路径能正常读取。
- 正常 marking answer image 返回图片。
- 正常 grading rescore 能读取图片。
- worker 批量阅卷仍能读取图片。
- `/tmp/...`、`/etc/...`、其他学校 `storage/{other_school}/...` 被拒绝。

---

## 6. Phase 3：权限收紧与前端契约

### 6.1 权限策略

`/api/v1/marking/import` 是服务器目录扫描 + 数据写入能力，应要求：

```text
Permission.MANAGE_GRADING
```

但上线前必须按真实角色表确认影响。当前权限表里有 `MANAGE_GRADING` 的角色包括：

```text
platform_admin
district_admin
school_admin
principal
academic_director
lesson_prep_leader
homeroom_teacher
admin
head_teacher
```

没有该权限的典型角色：

```text
subject_teacher
teacher
teaching_research_leader
grade_leader
parent
observer
exam_coordinator
```

### 6.2 前端处理

当前前端只发现 API wrapper：

```text
frontend/src/api/marking.js
```

没有明显页面调用点。若后续发现页面入口，需：

- 根据当前角色/权限隐藏导入入口。
- 403 时给出明确提示。
- 不要让普通用户输入服务器路径。

### 6.3 Phase 3 测试

```text
test_marking_import_forbidden_for_subject_teacher
test_marking_import_allowed_for_academic_director
test_marking_import_allowed_for_school_admin
test_marking_import_allowed_for_homeroom_teacher_if_policy_keeps_manage_grading
```

---

## 7. Phase 4：AI 工具 module_code 治理

### 7.1 修复模块码

当前问题工具：

```text
card_parse_answers            card      -> exam
card_auto_layout              card      -> exam
card_adjust_layout            card      -> exam
get_knowledge_tree            knowledge -> research
get_question_knowledge_points knowledge -> research
```

理由：

- `card` 不是学校模块枚举，答题卡能力归属考试管理。
- `knowledge` 不是学校模块枚举，知识树能力当前更接近教研题库。

### 7.2 增加注册合法性测试

建议优先用测试阻断，而不是一开始就在生产启动时 hard fail。

```text
tests/test_ai/test_tool_module_codes.py
```

测试逻辑：

```python
from edu_cloud.ai.engine.tools import collect_all_tools
from edu_cloud.models.school_settings import MODULE_CODES


def test_all_ai_tool_module_codes_are_registered():
    invalid = []
    for fn in collect_all_tools():
        meta = getattr(fn, "_edu_meta", None)
        if meta and meta.module_code not in MODULE_CODES:
            invalid.append((meta.name, meta.module_code))
    assert invalid == []
```

等测试稳定后，再考虑在 dev/staging 启动断言；production hard fail 建议下一轮再评估，避免因为非核心 AI 工具注册问题阻断主服务启动。

---

## 8. Phase 5：历史数据处理决策

Phase 0 只读体检如果发现异常，按类型处理。

### 8.1 subject/question mismatch

如果数量为 0：无需数据修复。

如果数量非 0：

1. 导出样例。
2. 判断以 `question.subject_id` 为准还是以 `student_answer.subject_id` 为准。
3. 先写 dry-run 修复脚本，输出将修改行数。
4. 备份 SQLite。
5. 人工确认后执行。

### 8.2 exam/subject mismatch

同上，但更高风险。必须确认该 `StudentAnswer` 是否应属于 subject 所在 exam。

### 8.3 orphan question_id

当前已观测到大量 `StudentAnswer.question_id` 指向不到 `questions` 的情况。不要在本修复里直接删除。

先分类：

```sql
SELECT sa.exam_id, sa.subject_id, count(*)
FROM student_answers sa
LEFT JOIN questions q ON q.id = sa.question_id
WHERE sa.question_id IS NOT NULL AND q.id IS NULL
GROUP BY sa.exam_id, sa.subject_id
ORDER BY count(*) DESC;
```

可能原因：

- 历史题目被删除但答卷未清理。
- 测试/演示数据残留。
- 迁移期间 FK 未 enforce 导致孤儿数据。

处理策略单独成案，不阻塞本次边界修复。

---

## 9. 推荐执行顺序

```text
Phase 0：只读体检
  ↓
Phase 1：归属链共享函数 + 所有 StudentAnswer 写入口接入
  ↓
Phase 1 回归测试
  ↓
Phase 2：路径安全函数 + marking/grading/worker 接入
  ↓
Phase 2 回归测试
  ↓
Phase 3：marking import 权限收紧 + 前端/测试适配
  ↓
Phase 4：AI module_code 修复 + 注册合法性测试
  ↓
Phase 5：根据体检结果决定是否做历史数据修复
```

建议 commit 拆分：

```text
commit 1: audit scripts only
commit 2: ownership chain helpers + scan/compat/pipeline tests
commit 3: path_safety helpers + marking/grading/worker tests
commit 4: marking import permission policy + tests
commit 5: AI tool module_code consistency + tests
```

---

## 10. 回滚方案

| Phase | 回滚方式 | 数据影响 |
|-------|----------|----------|
| Phase 0 | 删除/忽略审计脚本 | 无 |
| Phase 1 | revert ownership commit | 无 schema 变化；已阻断的非法写入恢复旧行为 |
| Phase 2 | revert path_safety commit | 无 schema 变化；图片读取恢复旧行为 |
| Phase 3 | revert permission commit | 无 schema 变化；import 恢复登录即可调用 |
| Phase 4 | revert module_code commit | 无 schema 变化；AI 工具恢复旧过滤行为 |
| Phase 5 | 数据修复脚本必须先备份 | 需要 SQLite 备份回滚 |

Phase 5 是唯一可能触及生产数据修复的阶段，必须单独审批。

---

## 11. 验收命令

### 11.1 定向测试

```bash
.venv/bin/python -m pytest \
  tests/test_api/test_scan_path_containment.py \
  tests/test_api/test_scan_browse_dir_security.py \
  tests/test_api/test_marking_import_isolation.py \
  tests/test_api/test_compat.py \
  tests/test_api/test_impersonate.py \
  tests/test_api_exam/test_marking.py \
  tests/test_ai/test_tool_module_codes.py
```

### 11.2 新增测试分组

如果新增专项测试文件，建议：

```bash
.venv/bin/python -m pytest \
  tests/test_api/test_student_answer_ownership_chain.py \
  tests/test_api/test_path_safety.py \
  tests/test_ai/test_tool_module_codes.py
```

### 11.3 静态检查

先只跑高信号规则：

```bash
.venv/bin/python -m ruff check src tests --select F821,F811,E9
```

不建议本次把全部 unused import 作为阻塞项。

### 11.4 前端

```bash
cd frontend
npm run lint -- --quiet
```

---

## 12. 上线前检查清单

```text
[ ] Phase 0 体检已输出并归档
[ ] 现有 ./storage/... 图片路径读取测试通过
[ ] 所有 StudentAnswer 写入口均接入归属链校验
[ ] upload/batch 已覆盖
[ ] upload-objective 主路由和 compat 路由均覆盖
[ ] pipeline template question_id/question_ids 已预校验
[ ] marking import 只能访问允许根目录
[ ] marking import 已按真实角色表评估权限影响
[ ] marking/grading/worker 读取路径均做 containment
[ ] school tenant containment 已覆盖 storage/{school_id}
[ ] AI 工具 module_code 合法性测试通过
[ ] 定向 pytest 通过
[ ] 前端 lint 通过
[ ] 未执行任何未经审批的数据修复
```

---

## 13. 最终判断

这版方案是结构性修复，而不是小补丁。它把系统目前缺失的两个核心边界补起来：

1. **领域数据边界**：`StudentAnswer` 只能写入合法的 exam/subject/question 链。
2. **文件访问边界**：任何服务器路径访问都必须经过 root containment、历史路径兼容、tenant containment。

只要按 Phase 0 先体检、Phase 1/2 分开提交、每步跑回归测试，就可以在不破坏正常功能的前提下修到根因。

