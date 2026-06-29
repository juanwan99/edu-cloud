# 结构性安全修复方案（根因治理，非打补丁）

> **性质**：T3 级结构性修复  
> **原则**：把已经存在的正确模式提升为共享基础设施，让所有消费方统一调用，而不是逐个端点加 if  
> **前提**：本方案基于 2026-06-04 深度调查实证，每个结论附代码证据  
> **约束**：不破坏现有正常功能，每步可独立 revert，全量测试验证

---

## 根因诊断

### 这不是"某个端点漏了一个 if"的问题

调查发现项目内**已经存在正确的安全模式**，但它们是模块局部的：

| 正确模式 | 在哪里 | 问题 |
|----------|--------|------|
| 完整归属链校验（exam→subject→question） | `compat_router.py:287-294` | 只在 compat 路由用了，V1 路由没用 |
| 路径 containment (`resolve` + `is_relative_to`) | `pipeline_router.py:34-42` | 只在 scan pipeline 用了，marking/grading 没用 |
| 结构化安全路径构建 | `shared/storage.py:14-24` | 只给新 pipeline 用，旧 marking importer 没用 |
| module_code→工具过滤 | `tools/__init__.py:63` | 过滤生效但没有对注册值做合法性校验 |

**根因是三个**：

```
RC-1: 归属链校验是 per-endpoint 散装实现，没有共享函数
     → 正确实现只覆盖了 1/5 的写入路径

RC-2: 路径安全是 per-module 私有函数，没有提升为共享层
     → 新模块天然不受保护，旧模块从未补上

RC-3: 工具注册没有对 module_code 做合法性断言
     → 5 个工具静默不可用，且没人知道
```

---

## 修复策略：提升模式，不是加补丁

```
现状：正确模式散落在各模块 → 部分端点覆盖，部分裸奔

目标：正确模式提升到 shared/core 层 → 所有端点统一调用

方法：
  1. 把 compat_router 的链式校验提取为 core 函数
  2. 把 pipeline_router 的路径 containment 提取为 shared 函数
  3. 把 module_code 合法性变为启动断言
  4. 所有消费方改为调用共享函数（不重写业务逻辑）
```

---

## 现有写入路径清单（调查实证）

| # | 路径 | 文件 | 当前校验 | 缺口 |
|---|------|------|----------|------|
| W1 | `/api/v1/scan/upload` | scan/router.py:44-100 | school_id 隔离 | exam↔subject↔question 无交叉验证 |
| W2 | `/api/v1/scan/upload-objective` | scan/router.py:309-427 | subject↔exam ✓ | question↔subject ✗ |
| W3 | `/api/scan/upload` (compat) | compat_router.py:255-320 | **完整链** | 无（参考实现） |
| W4 | `/api/scan/upload-objective` (compat) | compat_router.py:338-422 | subject↔exam ✓ | question↔subject ✗ |
| W5 | Pipeline save_answer | pipeline_router.py:201-236 | 信任上游 | 中风险（内部调用） |
| W6 | Pipeline save_objective | pipeline_router.py:263-310 | 信任上游 | 中风险（内部调用） |
| W7 | Marking importer | marking/importer.py:80-135 | exam→school ✓ | 路径无 containment |
| W8 | Exam import upsert | exam_import/service.py:482 | 信任上游 | 低风险（commit_import 校验） |

---

## 现有文件读取路径清单

| # | 路径 | 文件 | 当前 containment |
|---|------|------|-----------------|
| R1 | Pipeline scan-image | pipeline_router.py:977-995 | `_validate_path_within_upload_dir` + tenant ✓ |
| R2 | Card doc-page-image | card_export_router.py:340-377 | `is_relative_to` + subject ownership ✓ |
| R3 | CV auto-detect | cv_detect_router.py:31-46 | prefix + `is_relative_to` ✓ |
| R4 | Marking answer image | marking/router.py:332-363 | **无 containment** ✗ |
| R5 | Grading answer image | grading/router.py:457 | **无 containment** ✗ |
| R6 | Grading worker | workers/grading.py:223,632 | **无 containment** ✗ |

---

## Phase 1：共享归属链校验函数（RC-1 根治）

### 设计

在 `src/edu_cloud/core/ownership.py` 新建一个函数，做且只做一件事：**验证 exam→subject→question 归属链完整性**。

```python
async def verify_ownership_chain(
    db: AsyncSession,
    *,
    school_id: str,
    exam_id: str,
    subject_id: str | None = None,
    question_id: str | None = None,
) -> tuple[Exam, Subject | None, Question | None]:
    """
    验证实体归属链。任何断裂抛 HTTPException(404)。
    
    校验规则（逐级追加）：
    - exam: Exam.school_id == school_id
    - subject: Subject.exam_id == exam_id AND Subject.school_id == school_id
    - question: Question.subject_id == subject_id AND Question.school_id == school_id
    
    返回查到的实体，供调用方复用（避免重复查询）。
    """
```

**设计决策**：
- 不引入新概念，只提取 `compat_router.py:287-294` 的逻辑为公共函数
- 返回实体而非 bool，避免调用方再查一次
- question_id 可选——有些路径只写到 subject 级别
- 保持 HTTPException(404) 语义——与现有行为一致，不改 API contract

### 消费方改造

| 写入路径 | 改造方式 |
|----------|----------|
| W1 `scan/upload` | 删除 3 个独立 select，换为 `verify_ownership_chain(exam+subject+question)` |
| W2 `scan/upload-objective` | 循环内 question 查询加 `Question.subject_id == req.subject_id` 条件 |
| W3 compat upload | 已经正确，不动 |
| W4 compat upload-objective | 同 W2，循环内加 subject_id 条件 |
| `_verify_ownership` | 替换为 `verify_ownership_chain` 调用，旧函数删除 |

**W2/W4 的最小改动**（不换函数，加一个 WHERE 条件）：

```python
# 当前（scan/router.py:375-377）
select(Question).where(
    Question.id == ans.question_id,
    Question.school_id == current["current_role"].school_id,
)

# 修复后
select(Question).where(
    Question.id == ans.question_id,
    Question.subject_id == req.subject_id,  # ← 加这一行
    Question.school_id == current["current_role"].school_id,
)
```

### 不动的路径

- W5/W6（Pipeline 内部 save）：后台任务闭包，从已校验的 question 字典取数据。上游已校验，内部信任合理。
- W8（exam_import upsert）：内部函数，commit_import 前有完整校验。

---

## Phase 2：共享路径 containment 函数（RC-2 根治）

### 设计

在 `src/edu_cloud/shared/path_safety.py` 新建：

```python
from pathlib import Path
from fastapi import HTTPException
from edu_cloud.config import settings

_ALLOWED_ROOTS: list[Path] = [
    Path(settings.UPLOAD_DIR).resolve(),
    Path(settings.STORAGE_ROOT).resolve(),
]


def resolve_safe_path(p: str | Path, allowed_roots: list[Path] | None = None) -> Path:
    """将用户提供的路径解析为安全的绝对路径。违反抛 403。"""
    roots = allowed_roots or _ALLOWED_ROOTS
    candidate = Path(p)
    if not candidate.is_absolute():
        candidate = roots[0] / candidate
    resolved = candidate.resolve()
    for root in roots:
        if resolved == root or resolved.is_relative_to(root):
            return resolved
    raise HTTPException(403, "路径不在允许的根目录范围内")


def validate_stored_path(image_path: str) -> Path:
    """验证数据库中存储的 image_path 是否安全（读文件前调用）。"""
    return resolve_safe_path(image_path)
```

**设计来源**：提取自 `pipeline_router.py:34-42`，逻辑一致，扩展为多根目录支持。

### 消费方改造

| 路径 | 改造方式 |
|------|----------|
| R4 marking/router.py:349 | `open(answer.image_path)` 前加 `validate_stored_path(answer.image_path)` |
| R5 grading/router.py:457 | 同上 |
| R6 workers/grading.py | 同上 |
| Marking import | `resolve_safe_path(req.folder_path)` 验证目录在白名单内 |

### Marking Import 权限收紧

```python
@router.post("/import", response_model=ImportResponse)
async def import_folder(
    req: ImportRequest,
    current: dict = Depends(require_permission(Permission.MANAGE_GRADING)),  # ← 加
    db: AsyncSession = Depends(get_db),
):
    resolved_root = resolve_safe_path(req.folder_path)
    stats = await import_from_folder(db, req.exam_id, str(resolved_root), school_id)
```

---

## Phase 3：module_code 注册合法性断言（RC-3 根治）

### 修复 5 个工具的 module_code

| 工具 | 当前 module_code | 修复为 | 理由 |
|------|-----------------|--------|------|
| card_parse_answers | `card` | `exam` | 答题卡解析属于考试管理 |
| card_auto_layout | `card` | `exam` | 同上 |
| card_adjust_layout | `card` | `exam` | 同上 |
| get_knowledge_tree | `knowledge` | `research` | 知识树属于教研题库 |
| get_question_knowledge_points | `knowledge` | `research` | 同上 |

### 启动断言

在 `tools/__init__.py` 或 `create_app()` lifespan 加：

```python
def _validate_tool_registry():
    from edu_cloud.ai.engine.tool_meta import TOOL_META_REGISTRY
    from edu_cloud.models.school_settings import MODULE_CODES
    invalid = [
        (name, meta.module_code)
        for name, meta in TOOL_META_REGISTRY.items()
        if meta.module_code not in MODULE_CODES
    ]
    if invalid:
        names = ", ".join(f"{n}(code={mc})" for n, mc in invalid)
        raise RuntimeError(f"AI 工具 module_code 非法: {names}")
```

---

## Phase 4：历史数据体检

### 体检 SQL（只读，在生产库运行）

```sql
-- 1. subject_id 与 question 所属 subject 不一致
SELECT count(*) FROM student_answers sa
JOIN questions q ON q.id = sa.question_id
WHERE sa.subject_id != q.subject_id;

-- 2. exam_id 与 subject 所属 exam 不一致
SELECT count(*) FROM student_answers sa
JOIN subjects s ON s.id = sa.subject_id
WHERE sa.exam_id != s.exam_id;

-- 3. image_path 指向非法路径
SELECT count(*) FROM student_answers sa
WHERE sa.image_path IS NOT NULL
  AND sa.image_path NOT LIKE '%/uploads/%'
  AND sa.image_path NOT LIKE '%/storage/%';
```

如果结果非零 → 需要写修复脚本（具体方案取决于脏数据量和分布）。

---

## 执行顺序与依赖

```
Phase 1（归属链，2-3h）→ commit + review
    ↓
Phase 2（路径+权限，2-3h）→ commit + review
    ↓
Phase 3（module_code，30min）→ commit + review
    ↓
Phase 4（数据体检，30min）→ 根据结果决策
```

每个 Phase 独立可 revert。Phase 间无代码依赖。

---

## 风险评估

| Phase | 破坏可能性 | 原因 |
|-------|-----------|------|
| 1 | **极低** | 只加 WHERE 条件。正常数据天然满足（question 本来就属于 subject） |
| 2 | **低** | 权限收紧可能阻断无 MANAGE_GRADING 权限的用户。需先查日志确认 |
| 3 | **零** | 改字符串值 + 加启动断言 |
| 4 | **零** | 只读查询 |

### Phase 2 权限收紧的破坏性评估

marking import 当前只需登录就能调。改为 MANAGE_GRADING 后：
- school_admin ✓（有此权限）
- grade_leader ✓（有此权限）
- teacher ✗（无此权限）

**上线前必须做的事**：在服务器日志搜 marking/import 的调用者角色。如果教师在用 → 需要产品确认再收紧。

---

## 不做的事

| 项 | 理由 |
|-----|------|
| 重写 scan 上传架构 | 加一个 WHERE 就够了 |
| 给 pipeline 内部 save 加校验 | 会引入 N+1，上游已校验 |
| 统一所有路由权限模型 | "写强权限 + 读数据域"的设计是合理的 |
| 替换 pipeline_router 的 _validate_path | 功能等价，无意义 diff |
| 新增 card/knowledge 到 MODULE_CODES | 不应为工具扩模块，应让工具归入已有模块 |

---

## 语义回归不变量（ORC）

修复后以下行为必须保持不变：
1. 正常上传（question 属于正确 subject）必须 200
2. 缺席学生批量写 0 分流程不受影响
3. 正常 marking import（目录在 uploads 下 + 有 MANAGE_GRADING）必须成功
4. 正常 answer image 读取（路径在 storage/uploads 下）必须返回图片
5. AI 工具在启用了 exam/research 模块的学校必须可用
6. Pipeline 后台评分流程不受影响
7. 已有的 compat router 正确校验行为不变
