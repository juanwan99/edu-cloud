# Chinese School Role Hierarchy Research

> Research date: 2026-04-12
> Purpose: Inform role/permission design for edu-cloud education management platform
> Scope: 完全中学 (combined middle + high school) organizational structure

---

## 1. Overall Organizational Structure

Chinese secondary schools (完全中学) operate with a **dual-line management** structure:

```
                          校长 (Principal)
                       /        |         \
              分管副校长      分管副校长     分管副校长
            (教学 Teaching) (德育 Moral Ed) (后勤 Logistics)
               |               |              |
            教务处           德育处/政教处    总务处
        (Academic Affairs) (Student Affairs) (General Affairs)
               |               |
        ┌──────┴──────┐    年级组 (Grade Groups)
        |             |        |
     教研组         教科室    班主任 (Homeroom Teachers)
  (Subject TRGs) (Research)    |
        |                   科任教师 (Subject Teachers)
     备课组
  (Lesson Prep Groups)
```

### Two Management Lines

1. **Teaching Line (教学线)**: 校长 -> 分管副校长 -> 教务处主任 -> 教研组长 -> 备课组长 -> 教师
2. **Education/Moral Line (教育线)**: 校长 -> 分管副校长 -> 政教处/德育处主任 -> 年级组长 -> 班主任 -> 学生

These two lines create a **matrix management** structure where teachers report both to their subject chain (教研组) and their administrative chain (年级组).

### 完全中学 Specifics

A 完全中学 contains both 初中部 (junior high, grades 7-9) and 高中部 (senior high, grades 10-12). Common management patterns:
- Shared 校长 with separate 副校长 per division
- Single 教务处 handling both divisions (or separate 初中/高中 教务主任)
- Teaching Research Groups (教研组) may span both divisions for the same subject or be separated
- Grade Groups are always per-grade (6 total: G7-G12)

---

## 2. Role-by-Role Analysis

### 2.1 校长 (Principal) / 副校长 (Vice Principal)

**Position**: Top-level school leadership. The 校长 has ultimate decision authority; 副校长 each oversee a functional area (teaching, moral education, logistics).

**Responsibilities**:
- Final decision-making on school policies (人事权, 财经权, 决策权, 指挥权)
- Approve major curriculum changes and exam schedules
- Review school-wide performance data and set strategic goals
- Represent the school externally (education bureau, parents, community)
- Approve teacher evaluations and performance reviews
- Budget allocation and resource planning

**Data Access Needs**:
| Data Type | Access Level | Notes |
|-----------|-------------|-------|
| Student scores | All grades, all subjects | Aggregated views preferred, drill-down available |
| Class comparisons | Cross-grade, cross-class | Compare parallel classes within each grade |
| Teacher performance | All teachers | Teaching quality metrics, student outcome data |
| School-wide statistics | Full access | Enrollment, attendance, graduation rates |
| Financial/resource data | Full access | Not typically in education platform |
| Joint exam results | Cross-school comparison | Compare with peer schools |

**Actions**:
- View all dashboards and reports
- Approve exam schedules, notification broadcasts
- Configure school-level settings (score segments, module toggles)
- Cannot typically create exams directly (delegates to 教务处)

**Scope**: Entire school (all grades, all classes, all subjects)

**Platform mapping**: `principal` role -- currently well-modeled in edu-cloud.

---

### 2.2 教务处 (Academic Affairs Office)

#### 2.2.1 教务主任 (Academic Director)

**Position**: Middle management, directly under the 分管教学副校长. The most operationally critical role in the teaching line.

**Responsibilities**:
- **Curriculum Management**: Implement national curriculum standards, arrange course schedules for all grades
- **Exam Organization**: Organize midterm/final exams, coordinate joint exams, manage test paper creation, proctoring, grading, score tabulation, quality analysis
- **Teacher Scheduling**: Assign teachers to classes and subjects (排课), manage substitutions (调课/代课)
- **Teaching Quality Monitoring**: Conduct classroom observations (>= 2 classes/week), check lesson plans, review homework quality
- **Teacher Evaluation**: Build teacher professional files, conduct periodic teaching quality assessments
- **Teaching Research**: Guide 教研组 activities, approve teaching plans, monitor progress against curriculum standards
- **Student Academic Records**: Manage academic records (学籍), transfer processing, graduation requirements
- **Resource Management**: Oversee libraries, labs, computer rooms, audio-visual equipment

**Data Access Needs**:
| Data Type | Access Level | Notes |
|-----------|-------------|-------|
| All exam data | Full CRUD | Create, organize, analyze exams |
| All student scores | Full read/write | Score entry, modification audit, quality analysis |
| Teaching schedules | Full CRUD | 排课 is a core function |
| Teacher assignments | Full CRUD | Which teacher teaches which class |
| Curriculum progress | All subjects, all grades | Track teaching progress vs plan |
| Question bank | Full CRUD | Manage school question bank |
| Joint exam management | Full lifecycle | Create, distribute, collect, analyze |

**Actions**:
- Create and manage exams (school-level and joint exams)
- Assign teachers to classes/subjects
- Generate analysis reports across all grades
- Configure grading rules and score segments
- Manage academic calendar
- Send notifications to teachers

**Scope**: Entire school -- no grade/class/subject restriction

**Platform mapping**: `academic_director` -- already the most permission-rich school-level role in edu-cloud.

#### 2.2.2 教务副主任 (Deputy Academic Director)

**Position**: Assists the 教务主任. In a 完全中学, there may be one per division (初中教务副主任 / 高中教务副主任).

**Responsibilities**: Same as 教务主任 but for their assigned division or functional area. May handle day-to-day scheduling while 教务主任 focuses on strategic quality management.

**Platform implication**: Could use the same `academic_director` role with scope restricted to specific grade_ids (e.g., grades 7-9 or 10-12). The existing UserRole.grade_ids field already supports this.

---

### 2.3 教研组 (Teaching Research Group)

**Structure**: Organized **per subject, across all grades**. Examples:
- 语文教研组 (Chinese Language TRG) -- all Chinese teachers across G7-G12
- 数学教研组 (Math TRG) -- all Math teachers across G7-G12
- In larger schools, may split: 初中数学教研组 (G7-G9) + 高中数学教研组 (G10-G12)

Typical subjects with their own TRGs: 语文, 数学, 英语, 物理, 化学, 生物, 政治/道法, 历史, 地理, 体育, 音乐, 美术, 信息技术

#### 2.3.1 教研组长 (TRG Leader)

**Position**: Not a formal middle manager, but occupies a crucial coordinating role between school administration and frontline teachers. Described as "positioned between the principal, the director of studies, and teachers" by the Ministry of Education.

**Responsibilities**:
- **Curriculum Leadership**: Formulate instruction plans, design teaching schedules for their subject across all grades
- **Teaching Research**: Organize subject-specific research activities, public demonstration lessons, lesson study sessions
- **Teacher Development**: Mentor new teachers, organize professional development within the subject
- **Quality Control**: Monitor teaching quality across all grades for their subject, organize collective lesson review
- **Assessment**: Coordinate exam question creation for their subject, analyze subject-wide exam results
- **Administrative Liaison**: Report to 教务处 on subject matters, communicate school policies to subject teachers

**Data Access Needs**:
| Data Type | Access Level | Notes |
|-----------|-------------|-------|
| Exam scores | All grades, own subject only | Cross-grade analysis within their subject |
| Student performance | All classes, own subject only | Subject-specific trends and weaknesses |
| Teaching plans | All grades, own subject | Review and approve lesson plans |
| Question bank | Own subject | Manage subject-specific question bank |
| Teacher performance | Own subject teachers only | Evaluate subject colleagues |

**Actions**:
- View cross-grade subject analysis reports
- Coordinate exam question creation for their subject
- Review and comment on lesson plans
- Generate subject-wide analysis reports
- Cannot manage teacher assignments or school settings

**Scope**: All grades, all classes, but restricted to their subject

**Platform gap identified**: edu-cloud currently has NO dedicated `teaching_research_leader` role. The closest is `subject_teacher`, but that is scoped to specific classes. A TRG leader needs **cross-grade, single-subject** access -- the UserRole model supports this via `subject_codes` (restricted) + `grade_ids` (null = all grades) + `class_ids` (null = all classes).

---

### 2.4 备课组 (Lesson Preparation Group)

**Structure**: Organized **per subject, per grade**. Examples:
- 初一数学备课组 (Grade 7 Math Prep Group)
- 高二英语备课组 (Grade 11 English Prep Group)

This is the most granular academic unit. In a typical school:
- Total prep groups = number of subjects x number of grades (e.g., 9 subjects x 6 grades = 54 groups)

#### 2.4.1 备课组长 (Lesson Prep Group Leader)

**Position**: Under the 教研组长. Directly coordinates the daily teaching work of teachers teaching the same subject in the same grade.

**Responsibilities**:
- **Collective Lesson Preparation (集体备课)**: The core function. Organize weekly prep meetings where teachers discuss upcoming lessons, share materials, align teaching approaches
- **"Five Unifications" (五统一)**: Ensure teachers align on:
  1. Teaching objectives and requirements
  2. Teaching progress/pace
  3. Example problems and exercises
  4. Test/quiz papers
  5. Homework assignments
- **Material Sharing**: Coordinate shared teaching materials, supplementary exercises, test papers
- **Progress Monitoring**: Track whether all teachers in the group are keeping pace with the curriculum calendar
- **Internal Assessment**: Organize unit quizzes and analyze results within the grade

**Data Access Needs**:
| Data Type | Access Level | Notes |
|-----------|-------------|-------|
| Exam scores | Own grade, own subject | Grade-level subject analysis |
| Student performance | All classes in own grade, own subject | Compare parallel classes |
| Teaching progress | Own grade, own subject | Track curriculum coverage |
| Homework data | Own grade, own subject | Monitor assignment consistency |

**Actions**:
- View grade-level subject analysis (compare parallel classes)
- Create/share lesson materials and exercises
- Generate grade-subject analysis reports
- Manage homework templates for the grade

**Scope**: Single grade + single subject (but ALL classes in that grade for that subject)

**Platform gap identified**: No dedicated `lesson_prep_leader` role. Could be modeled as a `subject_teacher` with `grade_ids` restricted to one grade and `subject_codes` restricted to one subject, but with elevated permissions (e.g., view all parallel classes, not just their own assigned classes). This is a meaningful distinction from a regular subject teacher.

---

### 2.5 年级组 (Grade Group) / 年级组长 (Grade Director)

**Position**: Administrative middle management. Under both 教务处 and 德育处 in the matrix structure. The 年级组长 is "the specific organizer and manager of the school's decentralized management system."

**Structure**: One per grade (G7, G8, G9, G10, G11, G12). Contains all teachers and homeroom teachers of that grade.

**Responsibilities**:
- **Grade Administration**: Implement school-wide policies at the grade level, coordinate daily operations
- **Teaching Quality**: Organize grade-level teaching quality analysis meetings, monitor exam results
- **Student Management**: Oversee student behavior, coordinate with homeroom teachers on discipline issues
- **Teacher Coordination**: Manage grade-level teacher schedules, resolve conflicts, arrange substitutions
- **Parent Communication**: Organize grade-wide parent meetings
- **Dual-Line Coordination**: Bridge between 教务处 (teaching) and 德育处 (student affairs) at the grade level
- **Data Analysis**: Review grade-level academic data, identify at-risk students, set grade targets

**Data Access Needs**:
| Data Type | Access Level | Notes |
|-----------|-------------|-------|
| Student scores | Own grade, ALL subjects | Cross-subject analysis within their grade |
| Class comparisons | All classes in own grade | Compare parallel classes |
| Student info | All students in own grade | Attendance, behavior, family situation |
| Teacher schedules | Own grade teachers | Manage substitutions |
| Homework/assignment data | Own grade, all subjects | Monitor workload balance |

**Actions**:
- View grade-wide analysis reports (all subjects)
- Compare parallel classes within the grade
- Generate notifications for grade parents
- Review student behavior records
- Cannot modify school-wide settings or other grades' data

**Scope**: Single grade, ALL subjects, ALL classes in that grade

**Platform mapping**: `grade_leader` -- already exists in edu-cloud with `grade_ids` scope. Well-modeled.

---

### 2.6 班主任 (Homeroom Teacher) vs 科任教师 (Subject Teacher)

#### 2.6.1 班主任 (Homeroom Teacher)

**Position**: The frontline manager of a single class (班级). Every class has exactly one homeroom teacher. The 班主任 is typically also a subject teacher for that class.

**Dual Role**: A 班主任 is always also a 科任教师 (they teach a subject), but has additional administrative responsibilities for their homeroom class.

**Responsibilities** (beyond subject teaching):
- **Class Management**: Daily class operations, seating arrangements, class culture, hygiene
- **Student Wellbeing**: Monitor students' academic, emotional, and behavioral status; home visits; parent communication
- **Score Overview**: View ALL subjects' scores for their class (not just their own subject), identify struggling students
- **Parent Communication**: Primary contact for parents; organize parent-teacher meetings; issue report cards
- **Student Evaluation**: Write semester evaluations (评语) for each student; recommend awards (三好学生, etc.)
- **Coordination**: Communicate with all subject teachers about class dynamics, student issues
- **Document Management**: Maintain student files, handle transfers, manage class records

**Data Access Needs**:
| Data Type | Access Level | Notes |
|-----------|-------------|-------|
| Student scores | Own homeroom class, ALL subjects | Must see full picture of each student |
| Student personal info | Own homeroom class | Family situation, health, behavior records |
| Class statistics | Own class vs grade averages | Need comparison context |
| Homework status | Own homeroom class, all subjects | Monitor student workload |
| Attendance/behavior | Own homeroom class | Daily tracking |
| Additionally: own subject | All assigned classes for their subject | As a subject teacher |

**Actions**:
- View comprehensive class reports (all subjects)
- Generate student evaluations and report cards
- Send notifications to class parents
- Manage homework (as subject teacher)
- Request parent meetings
- View (but not modify) other teachers' scores for their class

**Scope**: Own homeroom class (all subjects) + own assigned classes (own subject)

**Platform mapping**: `homeroom_teacher` -- the current implementation correctly unions homeroom class_ids with teaching assignment class_ids in DataScopeBuilder. However, the key distinction is that for their homeroom class they see ALL subjects, while for their teaching assignments they only see their own subject.

**Important nuance for the platform**: The DataScope currently tracks `visible_class_ids` and `visible_subject_codes` as flat lists. For a homeroom teacher who teaches Math in classes 7-1, 7-2, 7-3 but is homeroom teacher of 7-1:
- For class 7-1: should see ALL subjects (as homeroom teacher)
- For classes 7-2, 7-3: should only see Math scores (as subject teacher)

This cross-product scoping (class x subject) is not yet captured in the flat DataScope model. Consider a structured approach like:
```python
# Proposed enhancement
homeroom_access: list[str]  # class_ids where all subjects visible
teaching_access: list[tuple[str, str]]  # (class_id, subject_code) pairs
```

#### 2.6.2 科任教师 (Subject Teacher)

**Position**: A teacher who teaches a specific subject to one or more classes. The most numerous role in the school.

**Responsibilities**:
- Teach their subject to assigned classes
- Create homework, quizzes, and exercise materials
- Grade student work for their subject
- Analyze student performance in their subject
- Provide feedback to homeroom teachers about student issues
- Participate in 教研组 and 备课组 activities
- Contribute to question bank

**Data Access Needs**:
| Data Type | Access Level | Notes |
|-----------|-------------|-------|
| Student scores | Own assigned classes, own subject only | Cannot see other subjects' scores |
| Student basic info | Own assigned classes | Names, student numbers, class membership |
| Homework data | Own assigned classes, own subject | Create, grade, analyze |
| Question bank | Own subject | Contribute and use |

**Actions**:
- Grade exams (own subject, assigned classes)
- Create and manage homework (own subject, assigned classes)
- Generate subject-specific analysis reports
- Edit knowledge tree (own subject)
- Use AI assistant for teaching support

**Scope**: Own assigned classes + own subject only

**Platform mapping**: `subject_teacher` -- well-modeled in edu-cloud. TeacherAssignment correctly limits access.

---

### 2.7 德育处 (Student Affairs / Moral Education Department)

**Position**: Parallel to 教务处, under the 分管德育副校长. Handles all non-academic aspects of student life.

**Key Roles**:

#### 2.7.1 德育主任 (Student Affairs Director)

**Responsibilities**:
- **Moral Education Planning**: Develop semester/annual moral education plans, establish behavioral standards
- **Homeroom Teacher Management**: Recruit, train, and evaluate homeroom teachers; organize regular 班主任 meetings
- **Student Discipline**: Handle serious disciplinary issues, manage recognition programs (三好学生, 优秀学生干部), process disciplinary actions
- **Psychological Wellness**: Coordinate psychological counseling services, organize mental health education
- **School Events**: Organize flag ceremonies, thematic assemblies, military training, community service
- **School-Family-Community**: Organize parent committees, coordinate home visits, manage community partnerships
- **Safety**: Student safety education, emergency protocols

**Data Access Needs**:
| Data Type | Access Level | Notes |
|-----------|-------------|-------|
| Student behavior records | All grades, all classes | Discipline, attendance, awards |
| Homeroom teacher info | All homeroom teachers | Evaluation, training records |
| Student personal info | All students | Family situation, health records |
| Basic academic data | Read-only, aggregated | Need academic context for behavioral analysis |

**Actions**:
- Manage student behavior records and disciplinary actions
- Coordinate homeroom teacher assignments (with 教务处)
- Organize school-wide student activities
- Generate student evaluation reports (non-academic)
- Send notifications to all parents

**Scope**: All grades, all classes (but focused on non-academic data)

**Platform gap identified**: edu-cloud does NOT have a `student_affairs_director` role. For an education management platform focused on academic operations (exams, grading, analysis), this role has limited overlap. However, if the platform expands to include student behavior tracking, attendance, or comprehensive student profiles, this role becomes important.

#### 2.7.2 年级德育干事 / 政教处干事

Lower-level roles within 德育处 that handle grade-specific student affairs. Usually not modeled separately in academic management systems.

---

### 2.8 家长 (Parent)

**Position**: External stakeholder with the most restricted access.

**What Parents Should See in a School Management System**:

Based on established platforms (智学网, 好分数):

| Feature | Detail |
|---------|--------|
| **Score Reports** | Own child's scores per exam, per subject; rank within class (if school allows); trend over time |
| **Score Analysis** | Weak subjects identification, knowledge gap analysis, personalized learning recommendations |
| **Homework Status** | Assigned homework, submission status, grades |
| **Notifications** | School announcements, exam schedules, parent-teacher meeting invitations |
| **Report Cards** | Semester evaluations, homeroom teacher comments |
| **Attendance** | Own child's attendance record |
| **AI Chat** | Ask questions about child's academic performance (with strict scope limits) |

**What Parents Should NOT See**:
- Other students' scores or personal information
- Teacher performance data
- Class rankings (unless school explicitly enables this -- configurable setting)
- Grading rubrics or internal exam materials
- School administrative data

**Data Access Controls**:
- Strictly limited to own child(ren) via `guardian_student_links` table
- `parent_can_see_ranking` school setting controls ranking visibility
- AI agent scope enforces data boundaries (DataScope.visible_student_ids)
- No write access to academic data
- Can submit homework (as proxy for child, if enabled)

**Platform mapping**: `parent` -- well-modeled in edu-cloud with GuardianStudentLink and strict DataScope enforcement.

---

## 3. Missing Roles -- Gap Analysis vs edu-cloud

| Real-World Role | edu-cloud Status | Gap Description | Priority |
|----------------|-----------------|-----------------|----------|
| 校长 (Principal) | `principal` exists | Well-modeled | -- |
| 副校长 (Vice Principal) | Not separate | Could use `principal` with scope restriction, or `academic_director` for teaching VP | Low |
| 教务主任 (Academic Director) | `academic_director` exists | Well-modeled | -- |
| 教务副主任 | Not separate | Use `academic_director` with `grade_ids` scope | Low |
| **教研组长 (TRG Leader)** | **MISSING** | **Needs cross-grade, single-subject access. Distinct from subject_teacher** | **Medium** |
| **备课组长 (Prep Group Leader)** | **MISSING** | **Needs single-grade, single-subject, all-classes-in-grade access** | **Medium** |
| 年级组长 (Grade Director) | `grade_leader` exists | Well-modeled | -- |
| 班主任 (Homeroom Teacher) | `homeroom_teacher` exists | Homeroom vs teaching class scope nuance needs attention | Low |
| 科任教师 (Subject Teacher) | `subject_teacher` exists | Well-modeled | -- |
| **德育主任 (Student Affairs Director)** | **MISSING** | **Needed if platform expands to student behavior/attendance** | **Low** |
| 家长 (Parent) | `parent` exists | Well-modeled with GuardianStudentLink | -- |
| 区管理员 (District Admin) | `district_admin` exists | Well-modeled | -- |
| 平台管理员 | `platform_admin` exists | Well-modeled | -- |

### Recommended Priority Additions

**教研组长 (teaching_research_leader)** -- Medium priority:
- Real-world prevalence: Every school has 10-15 TRG leaders
- Unique data need: Cross-grade view within a single subject
- Can be modeled with `subject_codes=[single_subject]` + `grade_ids=null` (all grades) + `class_ids=null` (all classes)
- Permissions: VIEW_SCORES + VIEW_EXAMS + VIEW_STUDENTS + GENERATE_REPORT + VIEW_QUESTION_BANK + VIEW_KNOWLEDGE_TREE + EDIT_KNOWLEDGE_TREE + USE_AI_CHAT + VIEW_GRADING + VIEW_HOMEWORK

**备课组长 (lesson_prep_leader)** -- Medium priority:
- Real-world prevalence: 40-60 per school
- Unique data need: Single grade + single subject, but all parallel classes
- Can potentially be modeled as an enhanced `subject_teacher` with additional scope flags
- Or model as a separate role with `grade_ids=[single_grade]` + `subject_codes=[single_subject]` + `class_ids=null`

---

## 4. Data Access Matrix

| Role | Own Class | Own Subject | Own Grade | All Grades | All Subjects | Cross-School |
|------|-----------|-------------|-----------|------------|-------------|-------------|
| platform_admin | -- | -- | -- | Yes | Yes | Yes |
| district_admin | -- | -- | -- | Yes | Yes | Yes (own district) |
| principal | -- | -- | -- | Yes | Yes | Joint exams |
| academic_director | -- | -- | -- | Yes | Yes | Joint exams |
| teaching_research_leader* | -- | Yes | -- | Yes | -- | No |
| grade_leader | -- | -- | Yes | -- | Yes (own grade) | No |
| lesson_prep_leader* | -- | Yes | Yes | -- | -- | No |
| homeroom_teacher | Yes (all subj) | Yes (assigned) | -- | -- | -- | No |
| subject_teacher | -- | Yes (assigned) | -- | -- | -- | No |
| parent | -- | -- | -- | -- | -- | No |

*Proposed new roles

---

## 5. Action Permission Matrix

| Action | platform_admin | district_admin | principal | academic_director | grade_leader | homeroom_teacher | subject_teacher | parent |
|--------|---------------|---------------|-----------|------------------|-------------|-----------------|----------------|--------|
| Create exam | Yes | Yes | No | Yes | No | No | No | No |
| Grade exams | Yes | Yes | No | Yes | No | Own class | Own class/subject | No |
| View all scores | Yes | Yes | Yes | Yes | Own grade | Own class (all subj) | Own class/subject | Own child |
| Generate reports | Yes | Yes | Yes | Yes | Own grade | Own class | Own class/subject | No |
| Manage teachers | Yes | Yes | Yes | Yes | No | No | No | No |
| Send notifications | Yes | Yes | Yes | Yes | Own grade | Own class parents | No | No |
| Configure school | Yes | Yes | Yes | Yes | No | No | No | No |
| Joint exam mgmt | Yes | Yes | No | Yes | No | No | No | No |
| View question bank | Yes | Yes | Yes | Yes | No | No | Yes | No |
| AI chat | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Edit knowledge tree | Yes | Yes | Yes | Yes | No | Yes | Yes | No |
| Manage homework | Yes | Yes | No | Yes | No | Yes | Yes | No |
| View rankings | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Configurable |

---

## 6. Practical Observations for Platform Design

### 6.1 One Person, Multiple Roles Is the Norm

In Chinese schools, role stacking is extremely common:
- A Math teacher is simultaneously: 科任教师 (math, classes 7-1/7-2/7-3) + 班主任 (class 7-1) + 备课组长 (G7 math) + possibly 教研组长 (school math)
- A senior teacher might be: 科任教师 + 年级组长 + 教研组长

The UserRole table already supports multiple roles per user. The platform must handle seamless role switching (RoleSwitcher.vue exists) and correctly union data access across active roles.

### 6.2 The 教研组/备课组 Split Is a Key Chinese Differentiator

Unlike Western schools where "department" roughly maps to subject groups, Chinese schools have a clear two-tier structure:
- **教研组** (cross-grade, per-subject): Strategic, research-oriented
- **备课组** (per-grade, per-subject): Tactical, lesson-preparation-focused

This means features like "collective lesson preparation," "unified test paper creation," and "teaching progress alignment" are highly valued and should be scoped to the 备课组 level.

### 6.3 Homeroom Teacher Scope Is Asymmetric

The homeroom teacher has an asymmetric data scope that is unique:
- For their homeroom class: ALL subjects visible (they need to see the full student picture)
- For their teaching assignments: only their own subject visible

This asymmetry is not trivially captured by flat `visible_class_ids` + `visible_subject_codes` lists. The current DataScopeBuilder unions them, which may over-grant access (a homeroom teacher of 7-1 who teaches Math in 7-2 would see all subjects in both classes, when they should only see Math in 7-2).

### 6.4 Score Visibility Is Politically Sensitive

Chinese education policy increasingly restricts score ranking publication. The platform should:
- Make ranking visibility configurable at the school level (`parent_can_see_ranking` already exists)
- Support anonymized analysis (show distribution without identifying students)
- Allow different visibility levels for different roles
- Respect regional education bureau directives on score publication

### 6.5 Grade Group Power Is Growing

There is a trend in Chinese school management toward strengthening the 年级组 as a management unit (年级制管理). Some schools give grade directors (年级主任) near-vice-principal authority for their grade. The platform should anticipate this by ensuring `grade_leader` can be granted elevated permissions without code changes (the Capability system supports this).

---

## Sources

- [浅谈教研组和备课组的功能、职责与运行](https://blog.sina.com.cn/s/blog_dc9031ec0102w17i.html)
- [年级组 - 百度百科](https://baike.baidu.com/item/%E5%B9%B4%E7%BA%A7%E7%BB%84/6189034)
- [中小学校领导人员管理暂行办法 - 教育部](http://www.moe.gov.cn/jyb_xwfb/s6319/zb_2017n/2017_zb02/17zb02_wj/201701/t20170123_295587.html)
- [中学常见的中层岗位设置及主要工作内容 - 知乎](https://zhuanlan.zhihu.com/p/668681380)
- [教导处主任工作职责 - 知乎](https://zhuanlan.zhihu.com/p/516101138)
- [备课组长与教研组长有什么区别 - 百度知道](https://zhidao.baidu.com/question/475896941.html)
- [Teaching research group leaders' perceptions of curriculum leadership (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9549138/)
- [教育部关于进一步加强中小学班主任工作的意见](http://www.moe.gov.cn/srcsite/A06/s3325/200606/t20060604_81917.html)
- [德育处工作职责 - 中科大附中](https://kdfz.ustc.edu.cn/2010/1221/c5341a53614/pagem.htm)
- [年级组长的地位与职责](https://blog.sina.com.cn/s/blog_4dd469dc010009pa.html)
- [70年：中小学组织结构之变革与发展 - 中国社会科学网](https://www.cssn.cn/jyx/jyxyl/202211/t20221108_5561131.shtml)
- [集体备课 - 百度百科](https://baike.baidu.com/item/%E9%9B%86%E4%BD%93%E5%A4%87%E8%AF%BE/9761690)
- [德育处 - 百度百科](https://baike.baidu.com/item/%E5%BE%B7%E8%82%B2%E5%A4%84/1929980)
