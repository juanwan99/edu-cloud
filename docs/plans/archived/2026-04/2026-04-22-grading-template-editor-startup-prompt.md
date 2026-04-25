# grading-template-editor 接手指南

## 一、本会话完成的工作（commit 857e749，已推送）

1. **历史科目补录**：import_exam_xlsx truthiness bug 修复 + subjects 表补 LS，dispatch/status 返回 9 科
2. **TemplatePreviewEditor 组件**：`frontend/src/components/TemplatePreviewEditor.vue`，扫描图叠加区域编辑器（拖拽/缩放/分割/画框/A-B双面/8色交替）
3. **LLM 标注修复**：skip_llm 默认改回 False，模型换 gemini-3.0-flash，prompt 优化选择题识别，B面传 A面 prior_regions 上下文
4. **权限体系**：auth 响应加 subject_codes/class_ids；scan 端点加认证+VIEW_GRADING；dispatch/status 加 subject_code；路由放行 lesson_prep_leader；教务主任一键全科检测/备课组长只看本科
5. **SSH push 修复**：LD_PRELOAD=proxychains 导致 EBADF crash，.bashrc 加 unset

## 二、已知问题（教师可在编辑器手动修正）

- 数学/英语 score=0（答题卡未印分值，LLM 无法读取）
- 英语填空题分割粒度不稳定（LLM 每次略不同）
- 物理/生物/政治/历史/地理 B 面 0 区域（正确——B 面空白）

## 三、下一步（优先级排序）

### 3.1 验证切割全链路
1. mcu.asia 登录 superadmin → 切到二中枫溪角色 → 阅卷调度 → 选一模
2. 点「模板检测」→ 编辑器打开 → 确认区域 → 保存
3. 点「切割」→ pipeline 运行 → stage 变 ready
4. 确认 student_answers 写入正确

### 3.2 StudentsPage 同类排查（L019）
教师管理 9 次 fix 后，StudentsPage 可能有类似模式问题

### 3.3 conduct-roadmap-batch1 待执行
T1-T5 已通过 Gate 1 R7 PASS，实施待新会话 Executor

## 四、运行时

| 组件 | 端口 | 说明 |
|------|------|------|
| edu-cloud API | 9000 | 无 --reload，改代码需 kill+重启 |
| nginx (mcu.asia) | 443 | 前端 dist/ 已 build |
| llm-proxy | 8100 | 模板检测 LLM 标注需要 |
| Vite dev | 8080 | HMR，localhost 开发用 |

重启后端：`kill $(ps aux | grep 'uvicorn edu_cloud' | grep -v grep | awk '{print $2}'); cd /home/ops/projects/edu-cloud && .venv/bin/python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 > /tmp/uvicorn.log 2>&1 &`

## 五、关键文件

| 文件 | 说明 |
|------|------|
| `frontend/src/components/TemplatePreviewEditor.vue` | 模板区域编辑器（本会话新建） |
| `frontend/src/pages/GradingDispatchPage.vue` | 阅卷调度页（权限+一键检测+编辑器集成） |
| `src/edu_cloud/modules/scan/auto_detect_cv.py` | OpenCV+LLM 检测（gemini-3.0-flash + B面context） |
| `src/edu_cloud/modules/scan/pipeline_router.py` | scan-image 端点 + 权限检查 |
| `src/edu_cloud/api/auth.py` | 登录响应加 subject_codes |
| `frontend/src/api/scan.js` | fetchScanImageBlob + autoDetectCV 带 priorRegions |

## 六、数据状态

- **二中枫溪考试**：2026届高三3月一模 `1cf6a4b8-aa77-4127-84d4-5831d64ce892`，9 科，status=completed
- **扫描件**：`uploads/scan-input/1cf6a4b8-.../` 9 科 4364 张 PNG（A/B 双面）
- **登录**：superadmin/123456（platform_admin + 二中枫溪 academic_director），切换到教务主任角色操作
