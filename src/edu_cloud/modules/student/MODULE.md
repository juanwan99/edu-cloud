---
name: student
status: active
owner: backend
layer: foundation

owns_tables:
  - students
  - classes

owns_routes:
  - /api/v1/students
  - /api/v1/classes
  - /api/v1/grades
  - /api/v1/teachers

exposes:
  services:
    - list_classes
    - list_students
    - get_student
    - create_student
    - update_student
    - delete_student
  events: []

depends_on:
  modules: []
  services:
    - school_settings_service
  ai_tools:
    - ai/tools/students.py

created: "2026-05-05"
last_reviewed: "2026-05-05"
design_docs: []
---

# student 模块

## 职责

基础数据层：学生/班级/年级管理 + 教师管理。提供学生 CRUD、班级列表、年级列表、教师 CRUD + 导入导出。这是基础模块，被 analytics/pipeline/conduct/homework/profile 等多数业务模块依赖。

## 边界

- **做什么**：Student/Class ORM + CRUD + 批量导入导出（Excel）；教师 User+UserRole 管理（15 列档案）；年级列表（从 classes 聚合）；角色 scope 过滤（visible_class_ids）；选科分配（selection_id FK）
- **不做什么**：User/UserRole 表定义在 `models/` 平台层（非本模块 owns）；学校注册由 `school` 模块负责；成绩数据由 `exam`/`profile` 模块管理

## 使用方式

```bash
GET    /api/v1/classes                    # 班级列表（grade/school 过滤）
GET    /api/v1/grades                     # 年级列表（从 classes 聚合）
GET    /api/v1/students                   # 学生列表（class/selection/subject 过滤）
POST   /api/v1/students                   # 创建学生
PATCH  /api/v1/students/{id}              # 更新
DELETE /api/v1/students/{id}              # 删除
POST   /api/v1/students/import            # Excel 导入
GET    /api/v1/students/export            # Excel 导出
GET    /api/v1/teachers                   # 教师列表
POST   /api/v1/teachers                   # 创建教师（含角色分配）
PATCH  /api/v1/teachers/{id}              # 更新教师
DELETE /api/v1/teachers/{id}              # 删除教师
POST   /api/v1/teachers/import            # Excel 导入
GET    /api/v1/teachers/export            # Excel 导出
```

## 数据流

```
管理员 CRUD → students/classes 表
Excel 导入 → 批量写入 students
其他模块（analytics/pipeline/conduct/homework/profile）→ import Student/Class
AI tools (students.py) → get_class_list / get_class_roster / search_students / get_student_profile
```
