const WORKBENCH_PROFILE_LIST = [
  {
    key: 'school_admin',
    label: '校管理员',
    icon: 'school',
    title: '从学校基础数据进入运行治理',
    summary: '校管理员的核心不是个人教学闭环，而是学校配置、人员关系、权限秩序和全校考试流程是否正常运行。',
    owns: '学校基础配置、学期校历、教师和班级关系、全校考试流程、模块和权限秩序',
    hides: '个人阅卷明细、单学科备课、班主任日常跟进、平台级跨校运维',
    primaryAction: { label: '检查学校配置', route: '/school-settings' },
    secondaryAction: { label: '查看考试流程', route: '/exams' },
    kpis: [
      { label: '配置待补', value: '6', meta: '学期、校历或学校资料', tone: 'yellow' },
      { label: '教师关系', value: '12', meta: '任课和班级需核对', tone: 'purple' },
      { label: '考试流程', value: '3', meta: '待确认或发布', tone: 'orange' },
      { label: '数据异常', value: '2', meta: '导入、权限或发布风险', tone: 'ink' },
    ],
    priorities: [
      { title: '补齐学校基础配置', desc: '先确认学校资料、学期、校历和模块开关，避免后续流程缺少基础条件。', meta: '6 项', route: '/school-settings', tone: 'yellow' },
      { title: '检查教师任课和班级关系', desc: '教师、班级、学科关系是考试、成绩和作业能否正确流转的前提。', meta: '12 条', route: '/assignments', tone: 'purple' },
      { title: '监控考试和阅卷流程', desc: '校管理员看流程是否卡住，不进入个人阅卷细节。', meta: '3 场', route: '/exams', tone: 'orange' },
    ],
    flowHint: '配置、组织、考试、数据权限是一条学校运行主线',
    flow: [
      { title: '校验基础配置', desc: '学校资料、学期、校历和模块开关先完整。', route: '/school-settings' },
      { title: '维护人员关系', desc: '教师、班级、学科、选科关系保持一致。', route: '/assignments' },
      { title: '监控考试流程', desc: '考试创建、导入、阅卷、发布是否卡住。', route: '/exams' },
      { title: '核查数据权限', desc: '教师职务、可见范围和数据归属是否正确。', route: '/teachers' },
    ],
    modules: [
      {
        title: '学校基础配置',
        items: [
          { title: '学校设置', desc: '维护学校基础资料和模块配置', route: '/school-settings' },
          { title: '学期管理', desc: '配置学期和教学周期', route: '/academic/semesters' },
          { title: '校历管理', desc: '维护教学日历和关键事件', route: '/calendar' },
        ],
      },
      {
        title: '人员和组织关系',
        items: [
          { title: '教师管理', desc: '维护教师账号、身份和职务', route: '/teachers' },
          { title: '教师分配', desc: '维护教师、班级、学科关系', route: '/assignments' },
          { title: '学生档案', desc: '维护学生基础信息和归属', route: '/students' },
        ],
      },
      {
        title: '考试和数据流程',
        items: [
          { title: '考试管理', desc: '全校考试组织和状态检查', route: '/exams' },
          { title: '成绩导入', desc: '外部成绩和数据接入', route: '/exam-import' },
          { title: '阅卷调度', desc: '监控阅卷流程和风险', route: '/grading/tasks' },
          { title: '成绩分析', desc: '确认报告发布和数据可用性', route: '/analytics/report' },
        ],
      },
    ],
    overlap: {
      current: '校管理员页只处理学校运行和基础数据治理；如果本人兼任教师或班主任，教学任务应切换身份后再处理。',
      other: [
        { role: '教务主任', title: '教学运行异常 4 项', desc: '切到教务视角处理课表和教学计划。' },
        { role: '科任教师', title: '个人阅卷待处理 6 题', desc: '不在校管理员页展开个人阅卷。' },
      ],
    },
  },
  {
    key: 'subject_teacher',
    label: '科任教师',
    icon: 'person',
    title: '从考试结果进入教学改进',
    summary: '科任教师不需要看到全校调度入口，首页应围绕相关考试、我的阅卷、班级分析、讲评巩固四步展开。',
    owns: '自己任教学科、被分配阅卷、任教班级成绩与作业巩固',
    hides: '全校考试配置、阅卷分派、德育规则、教务排课',
    primaryAction: { label: '进入我的阅卷', route: '/marking' },
    secondaryAction: { label: '查看成绩分析', route: '/analytics/report' },
    kpis: [
      { label: '待阅任务', value: '18', meta: '只含本人分配题目', tone: 'yellow' },
      { label: '相关考试', value: '3', meta: '本周可查看', tone: 'purple' },
      { label: '薄弱知识点', value: '7', meta: '来自最近考试', tone: 'orange' },
      { label: '待布置巩固', value: '2', meta: '从报告转入', tone: 'ink' },
    ],
    priorities: [
      { title: '完成被分配的阅卷题目', desc: '只进入本人负责题目，不暴露调度和分派动作。', meta: '18 题', route: '/marking', tone: 'yellow' },
      { title: '查看本班本学科薄弱点', desc: '先看结论，再下钻题目和学生名单。', meta: '7 项', route: '/analytics/report', tone: 'purple' },
      { title: '把错因生成巩固作业', desc: '报告后的动作入口，不让老师重新找作业模块。', meta: '2 份', route: '/homework', tone: 'orange' },
    ],
    flowHint: '看考试、阅卷、讲评、巩固是一条闭环',
    flow: [
      { title: '看相关考试', desc: '只列出与任教学科和班级相关的考试。', route: '/exams' },
      { title: '处理我的阅卷', desc: '按分配题目进入，不出现阅卷组织权限。', route: '/marking' },
      { title: '阅读教学报告', desc: '优先展示知识点、题目、学生分层。', route: '/analytics/report' },
      { title: '生成巩固动作', desc: '作业、错题、题库沉淀承接分析结论。', route: '/homework' },
    ],
    modules: [
      {
        title: '我的教学任务',
        items: [
          { title: '相关考试', desc: '查看与我相关的考试和科目', route: '/exams' },
          { title: '我的阅卷', desc: '处理已分配的人工阅卷', route: '/marking' },
          { title: '成绩分析', desc: '查看任教班级和学生表现', route: '/analytics/report' },
        ],
      },
      {
        title: '讲评和沉淀',
        items: [
          { title: '作业巩固', desc: '把薄弱点转成练习', route: '/homework' },
          { title: '题库管理', desc: '沉淀讲评题目', route: '/question-bank' },
          { title: '知识图谱', desc: '定位知识点覆盖', route: '/knowledge-tree' },
        ],
      },
    ],
    overlap: {
      current: '当前只显示科任任务；班主任或备课组长事项用摘要提醒，不直接展开管理入口。',
      other: [
        { role: '班主任', title: '班级德育待确认 4 条', desc: '点击身份切换后再处理规则和记录。' },
        { role: '备课组长', title: '阅卷进度异常 1 项', desc: '不在科任页直接显示分派按钮。' },
      ],
    },
  },
  {
    key: 'homeroom_teacher',
    label: '班主任',
    icon: 'class',
    title: '从班级状态进入学生跟进',
    summary: '班主任的核心不是题库和教务配置，而是班级考试状态、学生风险、德育记录、家校通知。',
    owns: '本班学生、班级成绩、德育积分、家校通知和班级阅卷协同',
    hides: '全校教务配置、跨年级资源建设、非本班调度详情',
    primaryAction: { label: '查看班级学生', route: '/students' },
    secondaryAction: { label: '进入德育工作台', route: '/conduct' },
    kpis: [
      { label: '重点学生', value: '12', meta: '成绩或德育需跟进', tone: 'yellow' },
      { label: '班级考试', value: '4', meta: '近两周', tone: 'purple' },
      { label: '待处理记录', value: '9', meta: '德育与通知', tone: 'orange' },
      { label: '家校触达', value: '86%', meta: '本周确认率', tone: 'ink' },
    ],
    priorities: [
      { title: '查看班级风险学生', desc: '把成绩波动、缺交、德育异常合在学生维度。', meta: '12 人', route: '/students', tone: 'yellow' },
      { title: '确认德育待办记录', desc: '班主任默认看到班级记录，不进入全校规则配置。', meta: '9 条', route: '/conduct', tone: 'orange' },
      { title: '发送考试跟进通知', desc: '从报告结论直接生成家校沟通内容。', meta: '2 班', route: '/analytics/report', tone: 'purple' },
    ],
    flowHint: '班级概况、学生名单、跟进动作放在同一条线上',
    flow: [
      { title: '看班级概况', desc: '班级均分、分层、缺交、德育状态同屏汇总。', route: '/analytics/report' },
      { title: '定位重点学生', desc: '按风险等级进入学生档案。', route: '/students' },
      { title: '处理德育和通知', desc: '记录、通知、家长确认形成闭环。', route: '/conduct' },
      { title: '回看跟进效果', desc: '下次考试或作业后自动对比变化。', route: '/analytics/report' },
    ],
    modules: [
      {
        title: '班级管理',
        items: [
          { title: '学生档案', desc: '以学生为中心查看成绩和记录', route: '/students' },
          { title: '班级成绩', desc: '班级维度的考试和趋势', route: '/analytics/report' },
          { title: '德育工作台', desc: '班级积分和记录处理', route: '/conduct' },
        ],
      },
      {
        title: '协同动作',
        items: [
          { title: '相关考试', desc: '查看本班考试安排', route: '/exams' },
          { title: '我的阅卷', desc: '处理班主任也参与的阅卷', route: '/marking' },
          { title: '作业跟进', desc: '查看班级作业完成情况', route: '/homework' },
        ],
      },
    ],
    overlap: {
      current: '班主任页优先班级和学生，不展开科任教学资源建设；需要处理学科任务时切到科任视角。',
      other: [
        { role: '科任教师', title: '语文阅卷剩余 18 题', desc: '保留入口提示，不在班主任页展示题目列表。' },
        { role: '年级组长', title: '年级共性风险 3 项', desc: '切换后查看跨班级对比。' },
      ],
    },
  },
  {
    key: 'lesson_prep_leader',
    label: '备课组长',
    icon: 'book',
    title: '围绕本学科组织考试、阅卷和讲评',
    summary: '备课组长需要看到同学科的组织视角，但不应承担年级全局、德育、教务排课等噪音。',
    owns: '本学科考试准备、阅卷分工、学科质量分析、备课资料沉淀',
    hides: '班级德育、全校人员配置、跨学科行政事项',
    primaryAction: { label: '管理学科考试', route: '/exams' },
    secondaryAction: { label: '查看阅卷进度', route: '/grading/tasks' },
    kpis: [
      { label: '待发布考试', value: '2', meta: '本学科', tone: 'yellow' },
      { label: '阅卷异常', value: '1', meta: '进度低于预期', tone: 'orange' },
      { label: '讲评资料', value: '6', meta: '待沉淀', tone: 'purple' },
      { label: '共性薄弱点', value: '9', meta: '跨班级', tone: 'ink' },
    ],
    priorities: [
      { title: '确认本学科考试资料', desc: '试卷、题目标签、参考答案在发布前收敛。', meta: '2 场', route: '/exams', tone: 'yellow' },
      { title: '处理阅卷进度异常', desc: '只显示本学科异常，避免进入全校调度噪音。', meta: '1 项', route: '/grading/tasks', tone: 'orange' },
      { title: '沉淀讲评题和知识点', desc: '把高频错题和讲评资料进入题库和图谱。', meta: '6 份', route: '/question-bank', tone: 'purple' },
    ],
    flowHint: '学科组织从考前准备走到考后共研',
    flow: [
      { title: '准备考试资源', desc: '维护本学科试卷、题目和知识点标签。', route: '/exams' },
      { title: '组织阅卷分工', desc: '按题目和老师分配，监控异常进度。', route: '/grading/tasks' },
      { title: '汇总学科报告', desc: '查看跨班级共性问题和优秀样例。', route: '/analytics/report' },
      { title: '沉淀共研资源', desc: '题库、知识图谱、备课资料形成复用资产。', route: '/question-bank' },
    ],
    modules: [
      {
        title: '学科组织',
        items: [
          { title: '考试管理', desc: '本学科考试和试卷材料', route: '/exams' },
          { title: '阅卷调度', desc: '本学科分派和进度', route: '/grading/tasks' },
          { title: '成绩分析', desc: '跨班级学科质量报告', route: '/analytics/report' },
        ],
      },
      {
        title: '资源沉淀',
        items: [
          { title: '题库管理', desc: '沉淀错题和讲评题', route: '/question-bank' },
          { title: '知识图谱', desc: '维护知识点覆盖', route: '/knowledge-tree' },
          { title: '作业管理', desc: '统一巩固任务', route: '/homework' },
        ],
      },
    ],
    overlap: {
      current: '备课组长页显示本学科组织动作；个人阅卷任务和班主任任务放入摘要，不抢主线。',
      other: [
        { role: '科任教师', title: '个人待阅 18 题', desc: '进入科任视角后处理具体题目。' },
        { role: '教研组长', title: '跨年级共研待审 2 项', desc: '切换后查看学科纵向质量。' },
      ],
    },
  },
  {
    key: 'grade_leader',
    label: '年级组长',
    icon: 'users',
    title: '从年级风险进入班级协同',
    summary: '年级组长的工作台应看跨班级态势、班级差异、重点学生和年级通知，而不是陷入单题阅卷细节。',
    owns: '本年级考试态势、班级对比、年级重点学生、跨班级协同',
    hides: '单个学科题库建设、全校教务设置、平台管理工具',
    primaryAction: { label: '查看年级分析', route: '/analytics/report' },
    secondaryAction: { label: '查看学生档案', route: '/students' },
    kpis: [
      { label: '异常班级', value: '3', meta: '波动较大', tone: 'yellow' },
      { label: '重点学生', value: '27', meta: '需年级跟进', tone: 'orange' },
      { label: '联考任务', value: '1', meta: '待确认', tone: 'purple' },
      { label: '德育待办', value: '14', meta: '跨班级', tone: 'ink' },
    ],
    priorities: [
      { title: '查看年级班级差异', desc: '先看异常班级和学科短板，再安排跟进。', meta: '3 班', route: '/analytics/report', tone: 'yellow' },
      { title: '确认年级重点学生名单', desc: '把成绩、德育、出勤归并到学生风险。', meta: '27 人', route: '/students', tone: 'orange' },
      { title: '处理跨班级德育事项', desc: '只显示年级相关记录和导出动作。', meta: '14 条', route: '/conduct', tone: 'purple' },
    ],
    flowHint: '年级管理看趋势、看差异、看协同结果',
    flow: [
      { title: '看年级态势', desc: '年级均分、分层、班级差异。', route: '/analytics/report' },
      { title: '定位异常班级', desc: '从班级进入学科和学生名单。', route: '/analytics/report' },
      { title: '安排班主任跟进', desc: '通知、德育、学生档案联动。', route: '/conduct' },
      { title: '复盘联考或阶段考', desc: '跨校或跨班级报告沉淀。', route: '/joint-exams' },
    ],
    modules: [
      {
        title: '年级态势',
        items: [
          { title: '成绩分析', desc: '年级和班级对比', route: '/analytics/report' },
          { title: '学生档案', desc: '重点学生跟踪', route: '/students' },
          { title: '联考管理', desc: '年级联考和跨校结果', route: '/joint-exams' },
        ],
      },
      {
        title: '年级协同',
        items: [
          { title: '德育工作台', desc: '跨班级记录和导出', route: '/conduct' },
          { title: '相关考试', desc: '查看年级考试进度', route: '/exams' },
          { title: '作业跟进', desc: '查看年级巩固完成情况', route: '/homework' },
        ],
      },
    ],
    overlap: {
      current: '年级组长页不处理个人阅卷明细；它负责发现年级风险并分派协同动作。',
      other: [
        { role: '班主任', title: '本班德育待确认 9 条', desc: '切到班主任页后进入本班处理。' },
        { role: '科任教师', title: '数学错题讲评 2 项', desc: '不占用年级首页主任务区。' },
      ],
    },
  },
  {
    key: 'teaching_research_leader',
    label: '教研组长',
    icon: 'target',
    title: '从学科质量进入教研改进',
    summary: '教研组长更关注跨年级、跨备课组的学科质量和资源建设，应弱化日常班务和单次阅卷操作。',
    owns: '学科质量趋势、共性问题、教研资源、知识体系建设',
    hides: '班级德育、个人作业批改、排课和人员配置',
    primaryAction: { label: '查看学科质量', route: '/analytics/report' },
    secondaryAction: { label: '维护知识图谱', route: '/knowledge-tree' },
    kpis: [
      { label: '学科波动点', value: '5', meta: '跨年级', tone: 'yellow' },
      { label: '共性错因', value: '11', meta: '待共研', tone: 'orange' },
      { label: '资源缺口', value: '8', meta: '题库和图谱', tone: 'purple' },
      { label: '教研结论', value: '3', meta: '待发布', tone: 'ink' },
    ],
    priorities: [
      { title: '查看学科质量趋势', desc: '跨年级比较，不进入班级细碎事务。', meta: '5 项', route: '/analytics/report', tone: 'yellow' },
      { title: '组织共性错因复盘', desc: '把高频错因转为教研主题和讲评资料。', meta: '11 条', route: '/analytics/ai-report', tone: 'orange' },
      { title: '补齐题库和知识图谱', desc: '资源建设来自真实考试证据。', meta: '8 个', route: '/knowledge-tree', tone: 'purple' },
    ],
    flowHint: '教研工作台从数据证据进入教研主题和资源建设',
    flow: [
      { title: '看学科趋势', desc: '跨年级、跨考试观察质量变化。', route: '/analytics/report' },
      { title: '提取共性问题', desc: '按知识点、题型、错因聚合。', route: '/analytics/ai-report' },
      { title: '形成教研动作', desc: '共研主题、讲评资料、改进建议。', route: '/question-bank' },
      { title: '沉淀学科资产', desc: '题库、图谱、教学计划同步更新。', route: '/knowledge-tree' },
    ],
    modules: [
      {
        title: '质量诊断',
        items: [
          { title: '成绩分析', desc: '跨年级学科趋势', route: '/analytics/report' },
          { title: '阅卷质量报告', desc: '错因和题目质量复盘', route: '/analytics/ai-report' },
          { title: '相关考试', desc: '查看学科考试证据', route: '/exams' },
        ],
      },
      {
        title: '学科建设',
        items: [
          { title: '题库管理', desc: '沉淀共性题目', route: '/question-bank' },
          { title: '知识图谱', desc: '维护学科知识结构', route: '/knowledge-tree' },
          { title: '教学计划', desc: '把诊断反馈到计划', route: '/academic/teaching-plans' },
        ],
      },
    ],
    overlap: {
      current: '教研组长页只承载学科建设，不把备课组长的考试组织和科任教师的个人阅卷展开。',
      other: [
        { role: '备课组长', title: '本周阅卷异常 1 项', desc: '切换后处理具体分工。' },
        { role: '科任教师', title: '个人作业巩固 2 份', desc: '不打断教研质量主线。' },
      ],
    },
  },
  {
    key: 'academic_director',
    label: '教务主任',
    icon: 'academic',
    title: '从教学运行进入全校配置和质量治理',
    summary: '教务主任需要全校视角，但也应按运行、考试、质量、资源四块收敛，避免直接暴露所有后台菜单。',
    owns: '全校教学运行、考试组织、阅卷质量、教师和课程配置',
    hides: '个人阅卷明细、单个班主任日常记录、平台级运维工具',
    primaryAction: { label: '查看教学运行', route: '/academic/timetable' },
    secondaryAction: { label: '进入考试管理', route: '/exams' },
    kpis: [
      { label: '运行异常', value: '4', meta: '课程和人员', tone: 'yellow' },
      { label: '考试待确认', value: '3', meta: '全校范围', tone: 'purple' },
      { label: '阅卷风险', value: '2', meta: '质量或进度', tone: 'orange' },
      { label: '配置待办', value: '6', meta: '教师与学期', tone: 'ink' },
    ],
    priorities: [
      { title: '确认教学运行异常', desc: '课表、学期、教师分配先集中处理。', meta: '4 项', route: '/academic/timetable', tone: 'yellow' },
      { title: '处理考试和阅卷风险', desc: '全校考试组织、导入、阅卷质量统一入口。', meta: '5 项', route: '/exams', tone: 'orange' },
      { title: '检查教师和课程配置', desc: '人员、班级、选科、学期配置归并到教务运行。', meta: '6 项', route: '/assignments', tone: 'purple' },
    ],
    flowHint: '教务工作台按运行治理组织，不按后台表单罗列',
    flow: [
      { title: '看运行概览', desc: '学期、课表、教师配置的异常摘要。', route: '/academic/timetable' },
      { title: '组织考试流程', desc: '考试、导入、阅卷、发布串成一条线。', route: '/exams' },
      { title: '监控质量风险', desc: '阅卷进度、结果发布、报告异常。', route: '/grading/tasks' },
      { title: '维护基础配置', desc: '教师、学生、选科、校历按治理场景进入。', route: '/assignments' },
    ],
    modules: [
      {
        title: '教学运行',
        items: [
          { title: '课程表', desc: '查看和维护课表运行', route: '/academic/timetable' },
          { title: '学期管理', desc: '学期和教学周期配置', route: '/academic/semesters' },
          { title: '教师分配', desc: '教师、班级、学科关系', route: '/assignments' },
        ],
      },
      {
        title: '考试质量',
        items: [
          { title: '考试管理', desc: '全校考试组织', route: '/exams' },
          { title: '成绩导入', desc: '外部成绩数据接入', route: '/exam-import' },
          { title: '阅卷调度', desc: '全校阅卷风险监控', route: '/grading/tasks' },
        ],
      },
      {
        title: '学校配置',
        items: [
          { title: '学生档案', desc: '基础学生信息', route: '/students' },
          { title: '教师管理', desc: '教师和职务配置', route: '/teachers' },
          { title: '校历管理', desc: '教学日历和事件', route: '/calendar' },
        ],
      },
    ],
    overlap: {
      current: '教务主任页承载全校运行治理；个人教学或班主任身份只能以提醒出现，避免首页变成后台总菜单。',
      other: [
        { role: '科任教师', title: '本人阅卷待处理 6 题', desc: '切换到科任视角处理，不在教务页展开。' },
        { role: '班主任', title: '本班通知确认率 86%', desc: '作为摘要提醒，不影响教务主线。' },
      ],
    },
  },
]

export const WORKBENCH_PROFILE_KEYS = WORKBENCH_PROFILE_LIST.map(profile => profile.key)
export const WORKBENCH_PROFILES = Object.fromEntries(
  WORKBENCH_PROFILE_LIST.map(profile => [profile.key, profile]),
)

const WORKBENCH_PROFILE_ALIASES = {
  platform_admin: 'school_admin',
  district_admin: 'school_admin',
  principal: 'school_admin',
}

export function getWorkbenchProfile(role) {
  const profileKey = WORKBENCH_PROFILES[role] ? role : WORKBENCH_PROFILE_ALIASES[role]
  return WORKBENCH_PROFILES[profileKey] || WORKBENCH_PROFILES.subject_teacher
}
