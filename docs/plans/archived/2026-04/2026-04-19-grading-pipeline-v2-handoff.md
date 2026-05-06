# 交接：edu-cloud 阅卷全链路实测 v2（Opus 4.6 → 新会话）

> **日期**：2026-04-19  
> **用户指令**：打通阅卷全链路，用真实扫描数据  
> **当前位置**：全链路已基本打通，选择题自动判分+主观题切割+阅卷分配完成，待教师阅卷+成绩发布

---

## 〇、接手顺序

1. `~/.claude/CLAUDE.md`（本机纪律）
2. `~/.claude/projects/C--Users-Administrator/memory/MEMORY.md`（自动记忆）
3. 本文件

---

## 一、系统现状（2026-04-19 13:20）

### 1.1 运行时

| 组件 | 端口 | 状态 |
|---|---|---|
| edu-cloud API | 9000 | active（无 --reload，改 .py 要 `sudo -n systemctl restart edu-cloud.service`） |
| llm-proxy | 8100 | active |
| nginx | 443 | active，域名 `https://mcu.asia` |
| 调试 Chrome | 9223 | 存活，当前登录 admin_academic_director_2 |

### 1.2 本轮实测考试

- **考试**：`2026第一次月考` `80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c`
- **学校**：育才实验中学 `31c17116-8182-429b-b38d-47c89eec39ef`
- **扫描件**：`/home/ops/projects/edu-cloud/uploads/scan-input/A3722/` 9科 4364 张 PNG

### 1.3 九科 subject_id

| 科目 | code | subject_id | A面图数 |
|---|---|---|---|
| 语文 | YW | f927e80e-6d8c-4f71-9345-fe1373dab801 | 363 |
| 数学 | SX | 1974216e-8aef-4a0b-b9c2-0432488d6b80 | 367 |
| 英语 | YY | 93badb44-db6c-4571-ad0e-6231c15398c1 | 365 |
| 物理 | WL | 8684dca9-9511-4562-9a84-3ea288d4b5e5 | 255 |
| 化学 | HX | b81e7a0d-18d2-4d98-92ae-21a56b250794 | 232 |
| 生物 | SW | e1cc167b-d148-4cd4-8f3b-56db078a876f | 201 |
| 政治 | ZZ | 5f424bf4-2886-4091-9783-1046a484161c | 164 |
| 历史 | LS | 824cac45-e611-488b-ad19-57c081b9c107 | 108 |
| 地理 | DL | d27b05c7-037d-4351-a3c4-a7e83f66fa9d | 127 |

### 1.4 登录账号（密码统一 `123456`）

| 账号 | 角色 | 用途 |
|---|---|---|
| admin_academic_director_2 | 教务主任 | 管理端（调试 Chrome 已登录） |
| t_yw_001 | 语文教师 | 阅卷 |
| t_sx_027 | 数学教师 | 阅卷 |
| t_yy_052 | 英语教师 | 阅卷 |
| t_wl_077 | 物理教师 | 阅卷 |
| t_hx_089 | 化学教师 | 阅卷 |
| t_sw_097 | 生物教师 | 阅卷 |
| t_zz_105 | 政治教师 | 阅卷 |
| t_ls_114 | 历史教师 | 阅卷 |
| t_dl_122 | 地理教师 | 阅卷 |

---

## 二、已完成工作（本会话）

### 2.1 OpenCV+LLM 混合答题卡检测 ✓

**核心文件**：
- ECS: `/home/ops/projects/edu-cloud/src/edu_cloud/modules/scan/auto_detect_cv.py`
- 本地源: `C:\Users\Administrator\AppData\Local\Temp\auto_detect_cv.py`
- endpoint: `POST /api/v1/scan/pipeline/auto-detect-cv`

**设计**：
- OpenCV 负责精确坐标（轮廓检测找矩形边框），LLM 只做分类+语义标签（不出坐标）
- 双通检测：Pass1 无膨胀+contourArea（粗边框），Pass2 膨胀+bboxArea（细边框），合并去重
- pyzbar 独立检测条形码区域（不依赖轮廓，虚线边框也能检出）
- 多题共框自动切分：LLM 输出 splits 比例 → OpenCV 横线检测验证 → 等分兜底
- 相邻同题号区域自动合并（作文场景：语文B 三个Q23框 → 合并为一个大区域）
- 输出 `type="subjective"`（非 "essay"）以兼容 pipeline_service 切割过滤

**13面测试结果**：
- 9/9 A面检出 barcode ✓
- 7/9 A面检出 choice_group（数学A、物理A 的选择题区边框不稳定，偶尔检不出）
- 全部 13 面有 region 输出，0 失败

### 2.2 标注器 annotator.html ✓

**部署**：`/home/ops/projects/edu-cloud/frontend/dist/annotator.html` (nginx serve)  
**本地源**：`C:\Users\Administrator\AppData\Local\Temp\annotator.html`  
**访问**：`https://mcu.asia/annotator.html?subject_id=<sid>&side=<A|B>&img=/samples/<科目>-<A|B>.png`

**功能**：
- CV 检测按钮（调 auto-detect-cv endpoint）
- 条形码类型（黄色框）
- 保存时自动注入 question_id/question_ids（查 `/api/v1/questions` 按 qno 映射）
- 保存时 essay/subjective 统一转 type="subjective"
- 已删除旧 AI 预识别按钮（纯 LLM 方案已废弃）

### 2.3 全科模板保存 ✓

- 脚本 `/tmp/batch_templates.py` 批量 CV 检测 + question_id 映射 + 写 DB
- 13/13 模板保存成功（9A + 4B有内容面）
- 缺题库的 4 科（语文/数学/英语/物理）已用 `/tmp/batch_create_questions.py` 自动建题

### 2.4 切割 pipeline 全科完成 ✓

- 脚本 `/tmp/batch_pipeline.py` 依次 POST /scan/pipeline/start
- 全部处理完毕，0 failures
- **52,466 条 student_answers** 写入 DB
- crop 图片存储在 `storage/{school_id}/{exam_id}/{subject_id}/{student_id}/`

### 2.5 选择题自动判分 ✓（部分）

| 科目 | answers | 已评分 | 备注 |
|---|---|---|---|
| 语文 | 4,221 | 3,216 | ✓ |
| 数学 | 6,973 | 4,037 | ✓ |
| 英语 | 20,805 | 20,075 | ✓ 最多 |
| 物理 | 3,825 | 2,550 | ✓ |
| 化学 | 2,415 | 2,033 | ✓ |
| 生物 | 4,719 | **0** | ⚠️ 选择题 correct_answer 可能为空 |
| 政治 | 3,280 | 2,624 | ✓ |
| 历史 | 2,052 | 1,728 | ✓ |
| 地理 | 636 | **0** | ⚠️ 同上 |

### 2.6 阅卷任务分配 ✓

- 脚本 `/tmp/batch_assign.py` 为 9 科各分配 1 个教师
- 写入 `grading_assignments` 表，status=pending
- 教师登录验证通过（t_dl_122 能看到分配的任务）

---

## 三、下一步任务

### 3.1 修复生物/地理选择题评分为 0

检查这两科的 questions 表 `correct_answer` 是否为空：
```bash
python /c/Users/Administrator/Documents/ecs-auto-ssh.py "cd /home/ops/projects/edu-cloud && .venv/bin/python -c \"
import sqlite3
con = sqlite3.connect('edu_cloud.db')
for sid in ['e1cc167b-d148-4cd4-8f3b-56db078a876f', 'd27b05c7-037d-4351-a3c4-a7e83f66fa9d']:
    rows = con.execute('SELECT name, question_type, correct_answer FROM questions WHERE subject_id=? AND question_type=\\\"choice\\\" LIMIT 5', (sid,)).fetchall()
    print(f'{sid[:8]}: {rows}')
\""
```

如果 correct_answer 为空，需要从试卷或教师处获取标准答案后填入，再重跑选择题评分。

### 3.2 教师手动阅卷

1. 用教师账号登录 `https://mcu.asia/`
2. 进入阅卷页面（具体路由看前端菜单）
3. 逐题打分

关键 API：
- `GET /api/v1/marking/my-assignments` — 教师查看分配给自己的任务
- `GET /api/v1/marking/next?assignment_id=<aid>` — 获取下一道待批答题
- `GET /api/v1/marking/answer/{answer_id}/image` — 获取学生答题图片
- `POST /api/v1/marking/score` — 提交评分 `{answer_id, score, comment?}`

### 3.3 AI 阅卷（可选）

- llm-proxy 有 `grading-vision` slot
- 在阅卷调度页面触发
- 需要 AI 阅卷的前端页面支持（检查 GradingDispatchPage）

### 3.4 成绩发布

- 所有题目评分完成后可发布
- `publish_confirm_guard` hook 会拦截
- 需要 `CONFIRM_PUBLISH=1` env 前缀

---

## 四、工具箱

| 文件 | 位置 | 用途 |
|---|---|---|
| ecs-auto-ssh.py | `Documents/` | SSH + TOTP 跑 ECS 命令 |
| cdp_nav.py | `Temp/` | CDP 导航+截图（SPA 页面容易超时） |
| cdp_fetch.py | `Temp/` | CDP 浏览器内 fetch API |
| annotator.html | `Temp/` | 标注器本地源 |
| auto_detect_cv.py | `Temp/` | CV 检测本地源 |
| batch_templates.py | ECS `/tmp/` | 批量 CV 检测+保存模板 |
| batch_create_questions.py | ECS `/tmp/` | 批量建题 |
| batch_pipeline.py | ECS `/tmp/` | 批量跑切割 pipeline |
| batch_assign.py | ECS `/tmp/` | 批量分配阅卷 |
| test_visual.py | ECS `/tmp/` | 生成标注图 → `/tmp/cv_visual/` |
| test_all_cv.py | ECS `/tmp/` | 全科 CV 检测回归测试 |

**CDP 超时坑**：cdp_nav.py 的 websocket timeout=15s。SPA 页面加载慢会超时。annotator 有 confirm 弹窗会卡死所有 CDP 连接。解决：关掉 annotator tab 再操作。

---

## 五、凭证

| 项 | 值 | 位置 |
|---|---|---|
| ECS SSH | `ops@47.121.197.52:22` Ed25519 + TOTP | ecs-auto-ssh.py |
| VECTO_KEY | [REDACTED] | llm-proxy .env |
| VECTO_KEY2 | [REDACTED] | 同上 |
| JWT secret | 在 edu-cloud .env | 不改 |
| sudo | `ops` 免密，仅 systemctl restart | — |

---

## 六、已踩的坑（新增）

1. **LLM 非确定性**：同一张图多次检测结果不同（有时检出 choice_group 有时不检出）。模板已保存到 DB，不需要重新检测，但如果重检要注意结果可能变化。
2. **Pipeline wait 竞态**：pipeline/start 返回 queued 后立即检查 progress 可能看到 idle（还没开始跑）。正确做法是 sleep 几秒再轮询。
3. **contourArea vs bboxArea**：细边框答题卡的轮廓面积极小但 bounding rect 面积正常。双通检测合并解决。
4. **多题共框切分**：LLM 提供 splits 比例 > OpenCV 横线检测 > 等分兜底。横线检测阈值：跨宽度 50%+、距边缘 10%+、间距 8%+。
5. **作文合并**：相邻（y 重叠 >50%）同题号区域自动合并为大框。
6. **语文选择题不稳定**：cg=0 或 cg=1 取决于 LLM 本次输出。模板已保存含 choice_group 的版本。
7. **batch_pipeline.py 的 wait_pipeline 有 bug**：竞态条件导致提前返回。实际 pipeline 会继续在后台跑完所有队列。用 `GET /api/v1/scan/pipeline/progress` 的 `status` 字段判断。
8. **生物/地理选择题 0 分**：可能是 questions 表 correct_answer 为空（自动建题时没填标准答案）。

---

## 七、用户风格 memo

- 短快不废话，不总结不说教
- 先打通后优化
- 要看视觉效果验证（不接受"应该没问题"）
- "等高切分不合理"——要按实际答题空间比例切
- 不关主 Chrome、不动代理、不改 hook

---

## 八、决策树

```
用户第一句 →
  "继续" / "阅卷" → 引导教师登录 mcu.asia 进入阅卷页
  "修复生物/地理评分" → 查 questions.correct_answer 是否为空，补填后重跑选择题评分
  "AI 阅卷" → 检查 GradingDispatchPage 前端 + grading-vision slot
  "发布成绩" → 确认所有题已评分 → CONFIRM_PUBLISH=1 走发布流程
  "重标模板" → 用 annotator.html + CV 检测
  其他 → 读用户话，不扩大范围
```

完。
