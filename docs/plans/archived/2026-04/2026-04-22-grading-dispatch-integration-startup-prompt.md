# grading-dispatch-integration 接手指南

## 一、本会话完成的工作（8 文件 +642/-300 行，未 commit）

1. **路由测试修复**：router.test.js 子路由数 14→16，schools 权限断言修正
2. **OpenCV 扫描切割集成**：auto_detect_cv.py 的纯 OpenCV 模式（skip_llm=True，0.4s vs LLM 34-76s），前端 scan.js 加 autoDetectCV/saveCVTemplate/uploadScanFolder API
3. **阅卷调度页重构**：GradingDispatchPage 从 6 列挤压表格改为卡片式布局 + 汇总条 + 可折叠扫描区 + 进度条 + 文件夹上传
4. **侧栏菜单**：「阅卷分派」→「阅卷调度」（避免与「阅卷分配」混淆）
5. **platform_admin 跨校权限修复**（关键 Bug）：dispatch/status 和 pipeline/start 等 API 用 school_id==NULL 过滤导致跨校 404，改为从 exam/subject 回填 effective_school_id
6. **文件夹上传**：前端 `<input webkitdirectory>` → 分批上传 → 后端 `POST /upload-folder` 按子文件夹存储 → 选考试自动检测已上传目录

## 二、数据状态

- **二中枫溪考试**：2026届高三3月一模 `1cf6a4b8-aa77-4127-84d4-5831d64ce892`，8 科（缺历史），status=completed
- **扫描件**：`uploads/scan-input/1cf6a4b8-.../` 9 科 4364 张 PNG（化学464/历史216/地理254/政治328/数学734/物理510/生物402/英语730/语文726）
- **登录**：superadmin/123456（platform_admin + 二中枫溪 academic_director），浏览器需切换到教务主任(二中枫溪)角色

## 三、下一步（优先级排序）

### 3.1 验证扫描切割全链路
1. mcu.asia 登录 superadmin → 切到二中枫溪角色 → 阅卷调度 → 选一模
2. 点「模板检测」→ 应 <1 秒（纯 OpenCV）
3. 点「切割」→ pipeline 运行，stage 变 ready
4. 确认 student_answers 写入正确

### 3.2 已知问题
- 历史科缺科：dispatch/status 返回 8 科，需查 subjects 表
- pipeline_router.py L349 `output_dir` 用 school_id 可能仍为 NULL（需验证 effective_school_id 是否覆盖到此处）
- 考试 status=completed 是否阻止重新切割
- 数学大题 max_score=0、语文第 23 题 180 分待确认

### 3.3 commit 改动
验证后 commit：`feat(grading): 阅卷调度页重构 + OpenCV扫描切割集成 + platform_admin跨校修复`

### 3.4 StudentsPage 同类排查（L019）
教师管理 9 次 fix 后，StudentsPage 可能有类似问题

## 四、运行时

| 组件 | 端口 | 说明 |
|------|------|------|
| edu-cloud API | 9000 | 无 --reload，改代码需 kill+重启 |
| nginx (mcu.asia) | 443 | 前端 dist/ 已 build |
| llm-proxy | 8100 | auto-detect-cv skip_llm=false 时需要 |
| Vite dev | 8080 | HMR，localhost 开发用 |

重启后端：`kill $(ps aux | grep 'uvicorn edu_cloud' | grep -v grep | awk '{print $2}'); .venv/bin/python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 > /tmp/uvicorn.log 2>&1 &`

## 五、关键文件

| 文件 | 说明 |
|------|------|
| `src/edu_cloud/modules/scan/auto_detect_cv.py` | OpenCV 检测核心，`skip_llm` + `_build_opencv_only()` |
| `src/edu_cloud/modules/scan/pipeline_router.py` | +upload-folder/save-cv-template/browse-dir + 跨校修复 |
| `frontend/src/pages/GradingDispatchPage.vue` | 布局重构 + 模板检测 + 文件夹上传 |
| `src/edu_cloud/modules/grading/router.py:404` | dispatch/status 跨校权限修复 |
| `frontend/src/api/scan.js` | 新增 3 个 API 方法 |
