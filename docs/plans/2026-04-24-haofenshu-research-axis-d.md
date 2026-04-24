# 附录 D：D 轴行政配置域调研报告

**Date**: 2026-04-24
**Agent**: Explore (thoroughness: thorough)
**Scope**: 好分数 baseinfo + academic → edu-cloud student / school / calendar / menu / conduct
**Parent Design**: [2026-04-24-haofenshu-vs-edu-phase2-design.md](./2026-04-24-haofenshu-vs-edu-phase2-design.md)

---

## 业务能力对照表

| 能力分类 | 好分数 | edu-cloud | 备注 |
|---------|--------|----------|------|
| **学校基础档案** | | | |
| 学校注册/编辑 | 内嵌于系统（单校 OR 多校区模式） | `POST/PATCH /api/v1/schools` + API Key 发放 | edu-cloud: 平台层显式学校注册机制 + heartbeat 监控 |
| 学校设置（名称/代码/地址） | `SchoolSetting` 实体 | `RegisteredSchool` 表 + `school_settings` KV | edu-cloud 更细粒度分离（档案 vs 配置） |
| 多校（区域教育局）管理 | 未见明确实现 | `district_admin` 角色 + 区级成绩对比 API | edu-cloud 超前：好分数无正式多校聚合 |
| **班级基础档案** | | | |
| 班级 CRUD（名称/年级/班号） | `classManage` 端点 + Vue 页面 | `Class` 模型 + `GET/POST /api/v1/classes` | 两侧均基础 CRUD |
| 班级-年级-学段映射 | `baseXueduan`（学段：小学/初中/高中） | `Class.grade` + 学段在 `school_settings` | edu-cloud 分散配置 |
| **学生基础档案** | | | |
| 学生 CRUD | students 表 + paginated list API | Student 模型 + router 30+ 方法（import/export/search） | edu-cloud: Excel 导入超完整（班级识别/选科映射/fuzzy match） |
| 学生档案字段 | name/student_no/exam_no/phone/enrollment_year/grade/status/tags/class_id | name/student_number/class_id/grade/gender/id_card/selection_id | edu-cloud 新增：gender/id_card + 选科组合关联 |
| 选科（新高考）关联 | `selected_exam`（学生表含 selected_exam_id） | `Student.selection_id` → `SubjectSelection` | 都支持 |
| **教师基础档案** | | | |
| 教师 CRUD | teachers 列表（含角色/学科聚合） | User + UserRole（RBAC 多角色）+ 教师档案扩展 15 列 | edu-cloud 教师档案远更完整 |
| 教师学科绑定 | `user_roles.subject_id` | `UserRole.subject_codes` (JSON) | edu-cloud 支持多科 |
| 教师班级绑定 | `user_roles.class_id` | `UserRole.class_ids` (JSON) + 显式 TeacherAssignment | edu-cloud JSON 支持多班 |
| **年级管理** | | | |
| 年级 CRUD（名称/序号） | `grades` 表 + `gradeGroups` 端点按 xueduan 分组 | `Grade` 隐含在 `Class.grade`（字符串属性） | **缺失**：edu-cloud 未见独立 Grade 表，缺年级级聚合逻辑 |
| 年级段（xueduan） | `base_xueduan`（学段代码） | 未见对应字段 | 🟡 优化缺口 |
| **课程表/排课** | | | |
| 教师排课 | `teacher_schedules` 表（timetable_json） | `TeacherAssignment` 表（无 timetable 细节） | 好分数含时间表 JSON；edu-cloud 仅排课记录 |
| 冲突检测 | 未见算法实现 | 未见实现 | 🔴 双方都缺 |
| **选考管理（新高考 3+3 / 3+1+2）** | | | |
| 选考组合 CRUD | `selected_exam` 表（mode: "3+1+2"/"3+3"） | `SubjectSelection` 表（mode 枚举 + subject_codes JSON） | edu-cloud 更结构化 |
| 学生选科分配 | `Student.selected_exam_id` | `Student.selection_id` | 关联逻辑同 |
| 选考验证 | 未见科目数量校验 | `service.py` 校验（3+1+2 模式科目数） | 🟢 edu-cloud 锦上添花 |
| **德育/行为管理** | | | |
| 德育积分 | 未见实现 | conduct 模块完整（8 表 + 30+ 端点 + 家长端）| 🟢 edu-cloud 大幅超前 |
| 班规管理 | 未见 | ConductRuleCategory + ConductRuleItem | 🟢 edu-cloud 超前 |
| 积分记录/排行 | 未见 | ConductRecord + rankings API | 🟢 edu-cloud 超前 |
| 家长端绑定 | 未见 | GuardianStudentLink + 家长注册/登录/积分查看 | 🟢 edu-cloud 超前 |
| **RBAC 权限体系** | | | |
| 角色枚举 | 3 个：systemAdmin/schoolAdmin/teacher | 8 个：platform_admin/district_admin/principal/... | edu-cloud 远更细粒度 |
| 权限检查 | `POST /filter/yue/v353/role/showCheck` | 34 个 Permission 枚举 + `require_permission()` 装饰器 | 🟢 edu-cloud 细度 11 倍 |
| 权限 Scope | 角色内嵌 grade/class/subject | UserRole 表 grade_ids/class_ids/subject_codes (JSON) + ScopeFilter | 同设计，edu-cloud 更显式 |
| **模块开关（功能控制）** | | | |
| 学校模块启停 | 未见 | `school_modules` 表（9 codes） | 🟢 edu-cloud 平台级功能隔离 |
| 能力矩阵 | 未见 | `capabilities` 表（role×domain×action） | 🟢 edu-cloud 锦上添花 |

## Gap 清单

### 🔴 高价值缺失（edu-cloud 角度）

**注意**：D 轴对照后发现大多数"Gap"是**好分数缺**（edu-cloud 超前），而非 edu-cloud 缺。以 edu-cloud 视角真实 Gap 只有 1 项：

1. **年级聚合分析（edu-cloud 缺）**
   - 好分数：`grades` 独立表 + `gradeGroups` 按 xueduan 分组
   - edu-cloud：年级是 `Class.grade` 字符串，无独立 Grade 表，缺少年级级统计
   - **价值**：年级学情对比、年级排名、教学质量评价
   - **调研**：edu-cloud `models/` 下无 `grade.py`，年级仅在 Class 属性
   - **工作量**：S（1-2 人日）

### 🟡 有价值优化（两方都缺或 edu-cloud 可补）

1. **教师排课冲突检测**
   - 好分数：teacher_schedules 表有 timetable JSON，但无冲突算法
   - edu-cloud：TeacherAssignment 仅记录名单，也无冲突检测
   - **共性**：两者均缺，但好分数有时间粒度可以补齐
   - **工作量**：M（3-5 人日）

### 好分数缺（edu-cloud 超前，不在本 Phase 2 范围）

1. **多校（区域教育局）管理** — 好分数无 districtAdmin，edu-cloud 有
2. **Conduct 德育模块** — 好分数无，edu-cloud 2416 行完整
3. **Excel 学生导入** — 好分数无，edu-cloud import_students 400+ 行
4. **RBAC 细粒度** — 好分数 3 角色，edu-cloud 8 角色 × 34 权限
5. **教师档案 15 列扩展字段** — 好分数基础字段，edu-cloud 含 title/hire_date/education/employee_id 等

## edu-cloud 超前清单（战略性优势）

1. **Conduct 模块（德育积分）—— Phase 1 完全交付**
   - 行数：2416（admin_service 537 + models 175 + 9 routes 文件）
   - 功能完整度：班规→积分→排行→家长查看→导出
   - 价值：素质教育评价数字化
   - 好分数对标：无对应模块

2. **RBAC + Scope 治理**
   - DataScope 快照：每次请求冻结用户可见数据集（fail-closed）
   - ScopeFilter 工具：自动注入 WHERE 条件
   - 价值：多角色并发安全、权限越界不可能

3. **学生导入的健壮性**
   - 支持班级、选科、性别、身份证自动识别
   - 简称模糊匹配（"物化生"）
   - 冲突智能合并

4. **模块化开关 + 能力矩阵**
   - school_modules 表（9 codes）支持学校级功能启停
   - capabilities 表支持 role×domain×action 细粒度配置

## 边界说明

本轴不覆盖：
- 考试管理 → A 轴
- 成绩分析/学情 → B 轴
- 作业/教学资源 → C 轴

## 优先级建议（Phase 2 edu-cloud 视角）

### P1 优先（真实 Gap）

**补 D 轴 1：年级聚合分析**
- 维护 `grades` 独立表，增加年级级 API（班级列表、年级排名、年级学情聚合）
- 工作量：低（1-2 人日）
- ROI：高（教学管理核心需求）

### P2 优先（共同缺）

**补：教师排课冲突检测**
- 基于 `TeacherAssignment` + 时间粒度扩展实现冲突算法
- 工作量：中（3-5 人日）
- ROI：高（教务核心运维）

### 不在 Phase 2 范围（edu-cloud 已超前）

- 多校管理 / Conduct / Excel 导入 / RBAC / 模块化开关 — 保留现状

## 特别关注点

| 点 | 好分数 | edu-cloud | 建议 |
|---|-------|----------|-----|
| **选考模式支持** | 有（3+1+2/3+3），无校验 | 有，含校验 | edu-cloud 保持现有优势 |
| **多校权限隔离** | 弱 | 强 | edu-cloud 保持 |
| **教师档案** | 基础 | 完整 | edu-cloud 保持 |
| **RBAC 深度** | 浅 | 深 | edu-cloud 保持 |
| **德育** | 无 | 完整 | edu-cloud 保持 |
| **排课冲突** | 有表无算法 | 有表无算法 | 都需要补齐（可选 Phase 2 后） |

## 调研结论

D 轴真正的 Phase 2 deliverable 只有 **Grade 独立表**（L1 1.3），并入 S1 数据层 Sprint。其他均为 edu-cloud 超前或共同缺，不在本 design 范围。
