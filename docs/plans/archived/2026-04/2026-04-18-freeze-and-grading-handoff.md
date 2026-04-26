<!-- legacy-format -->
# 交接文档：系统冻结 + 考试阅卷链路验证

> 创建时间：2026-04-18 16:40 (UTC+8)
> 创建会话：系统全面梳理 + 冻结实施
> 状态：**冻结已实施，链路验证未开始**
> 关联文档：`docs/FREEZE.md`（冻结详细记录）

---

## 一、背景与决策

用户决定对 edu-cloud 系统实施**"整体冻结 + 逐步开放"**策略：

1. 将所有前端功能模块锁定（路由重定向 + 侧栏隐藏 + 仪表盘精简）
2. 第一批开放：**考试管理 + 阅卷全链路**
3. 用种子数据跑通完整链路后，再逐步解冻其他模块

### 用户定义的第一批业务流程

```
教师数据导入
    ↓
备课组长/教务 设置本科目：上传标准答案 + 确定切割方案 + 分配阅卷任务
    ↓
教务统一切割（扫描件 → 矫正 + 切割 + 选择题自动判分）
    ↓
教师阅卷（手动 / AI / 批量，所有打分保留依据）
    ↓
阅卷记录查看 + 成绩汇总 → 教务发布成绩
```

---

## 二、已完成的工作

### 2.1 全链路代码排查（4 个并行 agent 探索）

对整条阅卷链路做了详尽的代码级排查，结论如下：

| 环节 | 后端 | 前端 | 判定 |
|------|------|------|------|
| 考试创建 | ✅ 完整 CRUD | ✅ ExamListPage + ExamDetailPage (992行) | 可用 |
| 班级/学生数据 | ✅ 含 Excel 导入 `POST /api/v1/students/import` | ❌ 无导入 UI 页面 | **缺前端** |
| **教师花名册导入** | **❌ 无批量导入接口** | **❌ 无导入 UI** | **完全缺失** |
| 教师排课分配 | ✅ 完整 | ✅ TeacherAssignmentsPage | 可用 |
| 上传标准答案 | ✅ docx/pdf + LLM 解析 | ⚠️ 嵌在 ExamDetailPage 答题卡 Tab | 可用 |
| 答题卡模板/切割方案 | ✅ template_library + layout engine | ✅ CardEditor | 可用 |
| 阅卷任务分配 | ✅ GradingAssignment CRUD + auto_assign | ✅ MarkingAssignPage | 可用 |
| 扫描切割流水线 | ✅ 6 端点 + vision 处理 | ✅ GradingDispatchPage | 可用 |
| 选择题自动判分 | ✅ objective_grading.py + 异常标记 | ✅ 集成在切割流程 | 可用 |
| 教师手动阅卷 | ✅ 状态机 (ai_pending→confirmed) | ✅ ReviewPage 统一界面 (533行) | 可用 |
| AI 阅卷 | ✅ LLMClient + 3 模板 + 微批次 | ✅ GradingDispatchPage 触发 | 可用（需 LLM 配置） |
| 阅卷记录查看 | ✅ GradingResult 含 ai_raw_response | ✅ GradingResultsPage | 可用 |
| 成绩发布 | ✅ publish_service 4 项前置校验 | ✅ GradingDispatchPage | 可用 |

**注意**：以上"可用"是代码层面判断，未经运行时验证。

### 2.2 前端冻结实施

**修改了 6 个文件**（均未 commit，是 working tree 变更）：

| 文件 | 变更内容 |
|------|---------|
| `frontend/src/router/index.js` | 44 条路由 → 10 条（login + Dashboard + 考试 3 + 阅卷调度 2 + 教师阅卷 4）+ catch-all 重定向 |
| `frontend/src/config/sidebarConfig.js` | 所有角色侧栏精简为：平台概览 + 考试管理 + 阅卷调度/阅卷/阅卷分配/阅卷进度 |
| `frontend/src/config/dashboardConfig.js` | 所有角色仪表盘只显示考试+阅卷相关 KPI 和卡片 |
| `frontend/src/__tests__/router.test.js` | 适配冻结：路由数量 3→10、schools 路由不存在 |
| `frontend/src/__tests__/sidebarConfig.conduct.test.js` | 适配冻结：conduct 入口数量 → 0 |
| `frontend/src/__tests__/config.test.js` | 适配冻结：dashboard 不再有 schools widget |
| `frontend/vite.config.js` | `allowedHosts` 从 IP 数组改为 `true`（解决外网访问 reset 问题） |

**备份文件位置**（解冻时恢复原始版本）：

```
frontend/src/router/_frozen/index.full.js          ← 原始 44 路由
frontend/src/config/_frozen/sidebarConfig.full.js   ← 原始 10 角色完整侧栏
frontend/src/config/_frozen/dashboardConfig.full.js ← 原始 10 角色完整仪表盘
frontend/src/__tests__/_frozen/router.test.js.bak
frontend/src/__tests__/_frozen/sidebarConfig.conduct.test.js.bak
```

### 2.3 验证结果

- **Vitest**：24 文件 234 测试全绿
- **Playwright 截图验证**：
  - admin 登录后仪表盘只显示"考试阅卷中心"+ 4 个卡片（考试管理/阅卷调度/阅卷分配/阅卷进度）
  - 冻结路由 `/conduct` 自动重定向到 `/`
  - 考试管理页 `/exams` 正常显示

### 2.4 未 commit

所有变更在 working tree 中，**尚未 commit**。新会话可以先 `git diff` 查看变更，确认无误后再 commit。

---

## 三、未完成的工作（新会话接续）

### 3.1 最高优先级：用种子数据跑通阅卷全链路

系统已有种子数据（启动时自动创建）：
- **学校**：育才实验中学（YCSY2026），school_id = `31c17116-8182-429b-b38d-47c89eec39ef`
- **学生**：1500 人，分布在 36 个班（初一~高三，每年级 6 班）
- **教师**：227 个 subject_teacher + 56 个 homeroom_teacher + 6 个 grade_leader + 5 个 academic_director + 3 个 principal + 1 个 platform_admin
- **教务主任账号**：`admin_academic_director_2` / `123456`（李明华）
- **科任教师账号**：`t_yw_001` / `123456`（高睿皓，语文）
- **平台管理员**：`admin` / `123456`

**跑通步骤**：

1. 用教务主任账号登录 → 创建一个考试（如"2026 年期中考试"）
2. 添加科目（如语文）→ 上传标准答案（需准备 docx/pdf 测试文件）
3. 设计答题卡模板 / 导入 .tpl 模板
4. 分配阅卷任务（指定教师→题目）
5. 模拟扫描切割（需准备测试扫描图片，或用已有的 `test_output/` 下的文件）
6. 验证选择题自动判分
7. 教师账号登录 → 进入阅卷界面 → 手动打分
8. （可选）触发 AI 阅卷（需配置 LLM API）
9. 查看阅卷记录和进度
10. 教务发布成绩

**注意事项**：
- 后端在 `localhost:9000` 运行（进程 pid=338177），绑定 127.0.0.1
- 前端 Vite 在 `0.0.0.0:8080`（需手动启动：`cd frontend && npx vite --host 0.0.0.0 --port 8080 &disown`）
- 外网访问 `http://47.121.197.52:8080` 需阿里云安全组放行 8080 端口（**用户称已放行，但 curl 测试仍 connection reset，可能规则未生效或安全组绑定有误**）
- Playwright 用 Firefox（Chromium 在无 GPU 的 ECS 上 crash），截图验证命令见下方

### 3.2 已知缺口（跑通链路前不一定要修）

1. **教师花名册批量导入**：后端+前端都缺。当前可用种子数据的 227 个教师先跑通流程
2. **学生导入 UI**：后端 `POST /api/v1/students/import` 已有，缺前端页面。种子数据有 1500 学生，可先用
3. **备课组长角色缺失**：种子数据没有 `lesson_prep_leader` 角色的用户。如需测试备课组长视角，需手动创建或修改种子脚本
4. **仪表盘 KPI 数据**：部分 KPI 显示 `--`（API 返回空），不影响核心流程

### 3.3 解冻流程（后续开放新模块时）

详见 `docs/FREEZE.md` "解冻步骤" 章节。核心流程：
1. 从 `_frozen/` 目录把目标路由/侧栏项复制回来
2. 更新对应测试
3. `npx vitest run` 确认全绿
4. Playwright 截图验证

---

## 四、技术参考

### 启动命令

```bash
# 后端（应该已经在运行，检查：ss -tlnp | grep 9000）
cd /home/ops/projects/edu-cloud
.venv/bin/python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 --reload

# 前端
cd /home/ops/projects/edu-cloud/frontend
npx vite --host 0.0.0.0 --port 8080 &disown
```

### 测试命令

```bash
# 前端 Vitest（当前 24 文件 234 测试）
cd /home/ops/projects/edu-cloud/frontend && npx vitest run

# 后端 pytest（当前 1934 passed / 23 skipped / 68 conduct）
cd /home/ops/projects/edu-cloud && .venv/bin/python -m pytest --tb=short -q
```

### Playwright 截图验证（Firefox，Chromium 在此 ECS 不可用）

```python
cd /home/ops/projects/edu-cloud && .venv/bin/python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.firefox.launch(headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 720})
    page.goto('http://localhost:8080/login', timeout=15000)
    page.wait_for_load_state('networkidle', timeout=10000)
    page.fill('input[placeholder=\"请输入用户名\"]', 'admin')
    page.fill('input[placeholder=\"请输入密码\"]', '123456')
    page.click('button:has-text(\"登录\")')
    page.wait_for_load_state('networkidle', timeout=10000)
    page.wait_for_timeout(2000)
    page.screenshot(path='/tmp/screenshot.png', full_page=False)
    print('URL:', page.url)
    browser.close()
"
```

### 关键文件索引

| 用途 | 文件路径 |
|------|---------|
| 冻结详细记录 | `docs/FREEZE.md` |
| 前端路由（冻结版） | `frontend/src/router/index.js` |
| 侧栏配置（冻结版） | `frontend/src/config/sidebarConfig.js` |
| 仪表盘配置（冻结版） | `frontend/src/config/dashboardConfig.js` |
| 路由原始备份 | `frontend/src/router/_frozen/index.full.js` |
| 侧栏原始备份 | `frontend/src/config/_frozen/sidebarConfig.full.js` |
| 仪表盘原始备份 | `frontend/src/config/_frozen/dashboardConfig.full.js` |
| 考试模块后端 | `src/edu_cloud/modules/exam/` |
| 扫描切割后端 | `src/edu_cloud/modules/scan/pipeline_router.py` |
| 阅卷后端 | `src/edu_cloud/modules/grading/` + `modules/marking/` |
| AI 阅卷 Worker | `src/edu_cloud/workers/grading.py` |
| 种子数据脚本 | `src/edu_cloud/data/seed_demo.py` + `seed_school.py` |
| 角色权限定义 | `src/edu_cloud/core/permissions.py` |

### 种子用户快速参考

| 角色 | 用户名 | 密码 | 说明 |
|------|--------|------|------|
| 平台管理员 | `admin` | `123456` | 全平台权限 |
| 教务主任 | `admin_academic_director_2` | `123456` | 育才实验中学 |
| 教务主任 | `mgr_4` | `123456` | 育才实验中学 |
| 校长 | `admin_principal_1` | `123456` | 育才实验中学 |
| 语文教师 | `t_yw_001` | `123456` | 科任教师 |
| 数学教师 | `t_sx_001` | `123456` | 科任教师 |
| 英语教师 | `t_yy_001` | `123456` | 科任教师 |

---

## 五、风险与注意事项

1. **变更未 commit**：所有冻结修改在 working tree 中。新会话先 `git status` + `git diff` 确认，再决定是否 commit
2. **后端未冻结**：后端 API 全部仍然注册可用，只是前端入口封堵。如果有人直接调 API 仍可访问冻结功能
3. **外网访问未通**：`47.121.197.52:8080` 从 ECS 内部 curl 返回 connection reset。`allowedHosts: true` 已设置，问题在阿里云安全组层面。用户称已放行但未验证生效
4. **Chromium 不可用**：ECS 无 GPU，Playwright Chromium 崩溃（GPU process isn't usable）。必须用 Firefox 做截图验证
5. **lesson_prep_leader 角色**：种子数据未创建此角色用户。备课组长是阅卷链路的关键角色之一，后续需补充
