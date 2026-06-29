# 角色体系参考（按需查阅）

> 本文件从 CLAUDE.md 移出，按需 Read。不再每次会话注入。

## 角色体系

### 统一角色体系（edu-cloud 管理，P0 重构后）

> 重构声明（2026-03-21）：edu-cloud 从联考后端升级为统一平台后，
> 学校内角色由 edu-cloud 直接管理，不再由 exam-ai 管理。
> exam-ai 退化为数据采集节点。详见 `docs/archive/plans/2026-03-21-super-platform-design.md` §1。

| 角色 | 作用域 | 核心职责 | 说明 |
|------|-------|---------|------|
| platform_admin | 全局 | 全部权限 | 平台超管 |
| district_admin | 辖区 | 辖区学校管理+跨校分析 | 教育局管理员 |
| school_admin | 全校 | = 校长全部权限，系统日常运维 | 校管理员（通常由信息技术教师担任） |
| principal | 全校 | 审批/学校配置/全局查看（>= 教务查看权） | 校长 |
| academic_director | 全校 | 考试/排课/阅卷/选考运营管理 | 教务主任 |
| teaching_research_leader | 全校·单学科 | 跨年级学科教研、质量分析 | 教研组长 |
| grade_leader | 单年级·全科 | 年级行政、班级对比、年级通知 | 年级组长 |
| lesson_prep_leader | 单年级·单学科·全平行班 | 集体备课、教学进度统一 | 备课组长 |
| homeroom_teacher | 本班全科+任教班本科 | 教师基线+班级通知管理 | 班主任 |
| subject_teacher | 任教班·任教科 | 教师基线（教学/阅卷/作业/论文） | 科任教师 |
| parent | 自己孩子 | 查看成绩/作业/通知 | 家长（企微登录）|

**权限拆分（2026-04-12）**：`MANAGE_SCHOOL_SETTINGS` → `MANAGE_SCHOOL_CONFIG`（校长：KV/模块/能力矩阵）+ `MANAGE_SCHEDULING`（教务：排课/选考）。新增 `MANAGE_EXAMS`（校内考试 CRUD）。详见 `core/permissions.py`。

**exam-ai 旧角色兼容别名**（permissions.py + api/permissions.py）：

| 旧角色 | 映射到 | 说明 |
|--------|--------|------|
| admin | platform_admin | exam-ai 迁入测试使用 |
| teacher | subject_teacher | exam-ai 迁入测试使用 |
| head_teacher | homeroom_teacher | exam-ai 迁入测试使用 |

**角色模拟**（`api/impersonate.py` + `core/auth.py`）：仅 platform_admin 可调用 `POST /api/v1/auth/impersonate`，模拟登录继承目标角色的完整权限（含 MANAGE_* 写权限），所有操作审计日志记录 impersonator_id。可模拟角色：school_admin / principal / academic_director / teaching_research_leader / grade_leader / lesson_prep_leader / homeroom_teacher / subject_teacher。
