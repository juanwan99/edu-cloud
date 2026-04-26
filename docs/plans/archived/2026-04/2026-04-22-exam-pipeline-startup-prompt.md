# exam-pipeline 考试业务链路打通 接手指南

## 一、本会话完成的工作（未提交，11 文件 +409/-76）

### 1. 一键全科检测并发化
- **文件**: `GradingDispatchPage.vue`
- 串行 → 3 路并发池 + 逐科实时状态更新（`detectStatus` reactive）
- 每科完成后立即更新 `allSubjects` 本地状态，按钮实时切换
- 单科检测 → 转圈 → 完成后弹编辑器；批量检测不弹编辑器

### 2. Stage 推导重构（后端 + 前端）
- **文件**: `grading/router.py` + `GradingDispatchPage.vue`
- 新增两个 stage: `pending_detect`（有上传无模板）/ `pending_cut`（有模板未切割）
- 后端 dispatch/status 加入扫描目录检测 + Template 查询
- 目录扫描 + Template 查询提到循环外（批量），响应从 26s 降到 832ms
- 返回新字段: `has_scan_dir`, `has_template`, `answer_count`

### 3. 模板预览功能
- **文件**: `pipeline_router.py`（新增 `GET /cv-template`）+ `scan.js` + `GradingDispatchPage.vue`
- 从 DB 加载已有 Template regions + 扫描图 → 打开 TemplatePreviewEditor

### 4. 切割按钮修复
- `getScanDirFallback`：用后端 `has_scan_dir` + 固定路径构造，不依赖前端内存

### 5. 英语 B 面检测修复
- **文件**: `auto_detect_cv.py`
- B 面 fallback: 有 prior_regions 时检查页面内容密度（dark_ratio > 2%）→ 有内容则全页交给 LLM

### 6. Question 自动创建
- **文件**: `pipeline_router.py` (`save_cv_template`)
- 保存模板时，region 有 qno 但 Question 不存在 → 自动 INSERT

### 7. 学生考号关联
- **文件**: `pipeline_router.py` + `pipeline_service.py`
- pipeline_router: 从 Template regions 提取 barcode rect（之前硬编码 None）
- pipeline_service: 启动时预加载 `student_number → student.id` 映射，切割后用条码值查 UUID

### 8. 科任教师 AI 阅卷按钮
- **文件**: `MarkingSelectPage.vue`
- 每个科目卡片 "AI 批量阅卷" 按钮，调 `POST /grading/tasks` → 轮询状态

### 9. UI 修复
- 编辑器拖拽手柄放大；分数按钮选中绿色；角色切换下拉可滚动

### 10. 数据修复
- superadmin 在二中枫溪加 subject_teacher + homeroom_teacher + subject_codes 全 9 科 + 地理阅卷分配

## 二、已知问题

### 需要立即处理
1. **未提交 git** — 11 个文件改动未 commit
2. **已切割数据 student_id 是旧格式** — 需重新切割
3. **其他 8 科缺 Question** — 需教务预览保存触发自动创建
4. **AI 阅卷缺 Rubric** — 无评分标准，需建数据或 UI

### 待优化
5. **AI 阅卷逐题模式未实现** — 当前 Subject 级，用户要求 Question 级逐题+可停止
6. **AI 阅卷并发控制** — 用户要求最大并发 20、间隔 0.02s、可调节
7. **侧边栏路由** — subject_teacher "阅卷"应指向 MarkingSelectPage
8. **GradingDispatchPage 权限** — 应限管理角色

## 三、运行时

| 组件 | 端口 | 说明 |
|------|------|------|
| edu-cloud API | 9000 | 无 --reload，改代码需 kill+重启 |
| nginx (mcu.asia) | 443 | 前端 dist/ 已 build |
| llm-proxy | 8100 | 模板检测 + AI 阅卷需要 |

重启后端：`kill $(ps aux | grep 'uvicorn edu_cloud' | grep -v grep | awk '{print $2}'); cd /home/ops/projects/edu-cloud && .venv/bin/python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 > /tmp/uvicorn.log 2>&1 &`

## 四、关键文件

| 文件 | 改动 |
|------|------|
| `src/edu_cloud/modules/grading/router.py` | dispatch/status 新 stage + 批量查询优化 |
| `src/edu_cloud/modules/scan/pipeline_router.py` | GET /cv-template + barcode 提取 + Question 自动创建 |
| `src/edu_cloud/modules/scan/pipeline_service.py` | 学生表预加载 + 条码→UUID 映射 |
| `src/edu_cloud/modules/scan/auto_detect_cv.py` | B 面 fallback + 内容密度检查 |
| `frontend/src/pages/GradingDispatchPage.vue` | 并发检测 + 新 stage UI + getScanDirFallback |
| `frontend/src/pages/MarkingSelectPage.vue` | AI 批量阅卷按钮 |

## 五、下一步（优先级排序）

1. **commit 当前改动**
2. **配置侧边栏路由** — subject_teacher "阅卷"→MarkingSelectPage
3. **Rubric 录入** — AI 阅卷前置依赖
4. **重新切割地理** — 验证 student_id 关联 UUID
5. **全科模板确认** — 其他 8 科预览保存→触发 Question 创建
6. **AI 阅卷 question 级拆分** — 逐题+可停止+并发参数化

## 六、数据状态

- **考试**: 2026届高三3月一模 `1cf6a4b8-aa77-4127-84d4-5831d64ce892`，9 科
- **模板**: 9 科全部有 Template（A 面），6 科有 B 面
- **Question**: 地理 3 道（17/18/19 essay），其他科 0 道
- **学生表**: 二中枫溪 368 人，student_number 10 位（如 3722230914）
- **superadmin**: 二中枫溪 academic_director + subject_teacher（全科） + homeroom_teacher
