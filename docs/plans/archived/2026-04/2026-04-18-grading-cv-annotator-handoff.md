<!-- Created 2026-04-18 ~22:20 UTC+8 on ECS edu-cloud -->
# 交接：edu-cloud 阅卷链路实测 + 答题卡标注器 (OpenCV 混合方案)

> **对接人**：新会话（Opus 4.6），接替当前 Opus 4.7 会话。  
> **用户原话**：2026-04-18 要求「最快方式 全面打通 实测」edu-cloud 阅卷全链路，**用真实扫描数据** `D:\D\试卷图像\191871\A3722`，不再用种子数据。  
> **当前位置**：18 张答题卡模板尚未标注（阻塞切割+阅卷全链路）。AI 预识别走纯 LLM 路线证实不可靠，用户拍板走 **OpenCV 主几何 + LLM 补语义** 混合。

---

## 〇、接手顺序（请按此读）

1. `C:\Users\Administrator\.claude\CLAUDE.md`（本机纪律：不关 Chrome、代理生命线、发布纪律）
2. `C:\Users\Administrator\.claude\projects\C--Users-Administrator\memory\MEMORY.md`（自动记忆索引；重点看 `project_ecs_edu_cloud_takeover.md` `feedback_no_kill_chrome.md` `reference_ecs_claude_proxy.md`）
3. ECS: `/home/ops/projects/edu-cloud/docs/plans/2026-04-18-freeze-and-grading-handoff.md`（系统冻结的前置交接，仍有效，别重复冻结动作）
4. 本文件

---

## 一、系统现状快照（2026-04-18 22:20）

### 1.1 运行时

| 组件 | 状态 | 位置 | 备注 |
|---|---|---|---|
| edu-cloud API | active, port 9000 | systemd `edu-cloud.service` | **无 --reload**，改 .py 要 `sudo -n systemctl restart edu-cloud.service` |
| llm-proxy | active, port 8100 | systemd `llm-proxy.service` | config: `providers.yaml` + `.env` (EnvironmentFile) |
| nginx | active | 生产域名 `https://mcu.asia`（root `frontend/dist/`） | 80 端口到 mcu.asia 是 301→https |
| Vite dev | 0.0.0.0:8080 | `npx vite` from `frontend/` | 外网 Empty reply（WAF/安全组）**不通**，只能 ECS 内部访问 |
| 调试 Chrome | port 9223 (CDP) | 本机 Windows，临时 user-data-dir `C:\Users\Administrator\AppData\Local\Temp\chrome-debug-edu` | **独立实例，不碰用户主 Chrome 登录态** |

### 1.2 数据

- **真实扫描件** 已上传 ECS：`/home/ops/projects/edu-cloud/uploads/scan-input/A3722/` 下 9 个学科子目录（语文/数学/英语/物理/化学/生物/历史/地理/政治），**4364 张 PNG**，文件名 `I0101000NNN[A|B].png` (A/B 双面)。
- 原 tar `/home/ops/projects/edu-cloud/uploads/scan-input/A3722.tar` 549MB 保留作兜底。
- **样卡**（每科 A+B 第 1 张）复制到 `/home/ops/projects/edu-cloud/frontend/dist/samples/{科目}-{A|B}.png`，共 18 张，已 chmod 644，nginx 可 serve：`https://mcu.asia/samples/地理-A.png` (中文要 urlencode 为 `%E5%9C%B0%E7%90%86-A.png`)。
- **B 面大多几乎空白**（5-7 KB PNG，纯信息条），只数学/语文/英语 B 面有大量内容。

### 1.3 DB（`edu_cloud.db` SQLite）

**school** 育才实验中学 `31c17116-8182-429b-b38d-47c89eec39ef`（另有株洲二中枫溪分校 `4685a9a2-ea15-4e36-8199-d5390e8758fb`，本轮实测**不用**）。

**登录账号**（都密码 `123456`）：
- `admin_academic_director_2`（教务主任李明华，user_id `39b64e36-a67d-453f-8c6a-99ba3cb789a9`，role_id `9948bd5d-dbb0-4ddc-9b07-ef5cdef5d9e5`）← 调试 Chrome 当前登录的就是它
- `t_yw_001` / `t_sx_001` / `t_yy_001` 等科任教师用于教师阅卷验证
- `admin` 平台超管

**本轮实测考试**：`2026第一次月考` `80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c`，status=`scanning`，9 科 subject 均已创建：

| 科目 | code | subject_id |
|---|---|---|
| 语文 | YW | `f927e80e-6d8c-4f71-9345-fe1373dab801` |
| 数学 | SX | `1974216e-8aef-4a0b-b9c2-0432488d6b80` |
| 英语 | YY | `93badb44-db6c-4571-ad0e-6231c15398c1` |
| 物理 | WL | `8684dca9-9511-4562-9a84-3ea288d4b5e5` |
| 化学 | HX | `b81e7a0d-18d2-4d98-92ae-21a56b250794` |
| 生物 | SW | `e1cc167b-d148-4cd4-8f3b-56db078a876f` |
| 政治 | ZZ | `5f424bf4-2886-4091-9783-1046a484161c` |
| 历史 | LS | `824cac45-e611-488b-ad19-57c081b9c107` |
| 地理 | DL | `d27b05c7-037d-4351-a3c4-a7e83f66fa9d` |

**templates 表**只有 2 条：
- 地理 A `1d244b33-...` → 1 region (Q17 essay 107,993 → 1166,1571)
- 数学 A `201f3f71-...` → 6 regions 全是 essay  
**两者都缺 choice_group**（选择题 region），且仅 A 面。18 个应有模板里目前命中 2 个不完整的。

**grading_tasks 5 条 (全 pending) / grading_assignments 0 / grading_results 0**——未分配过真正阅卷任务。切割产出的 **`student_answers` 地理 subject 只有 2 条**（2026-04-09 的 E2E 测试遗留，不是当前数据写入的）。

**questions** 各科 10-21 道，地理 `d27b05c7` 有 19 题。说明 subject 下挂着题目，但 template.regions 没 `question_id` 映射 → save_fn 无法写 student_answers（见 pipeline_router.py build_pipeline_save_answer_fn 源码）。

---

## 二、已完成的工作（本会话）

### 2.1 真实数据上传 ✓
- 本机 `tar -cf A3722.tar A3722` (549MB)
- 走 paramiko sftp 上传（脚本 `C:\Users\Administrator\AppData\Local\Temp\ecs_upload.py`，与 `ecs-auto-ssh.py` 共用 TOTP）
- **sftp put 首次会报 ENOENT 是正常现象**——paramiko sftp 的 put 在 transport 早期不稳，需要先用 `sftp.file(..., 'w').write('x').close()` 做一次 canary write 暖机，再 put。见 `ecs_upload.py` 代码注释。

### 2.2 scan-dir 识别 ✓
```
POST /api/v1/scan/pipeline/scan-dir  body: {"dir_path": "/home/ops/projects/edu-cloud/uploads/scan-input/A3722"}
```
返回 9 科目 + a_count/b_count/student_count。**无需登录**（无 get_current_user 依赖）。

### 2.3 地理 A 面切割一次 ✓（不完整，模板薄）
用 `POST /api/v1/scan/pipeline/start` body `{subject_id, side, image_dir}`，127 张 5 秒完成。切出 128 个 Q17.png 到 `/home/ops/projects/edu-cloud/storage/{school}/{exam}/{subject}/I0101000XXX/Q17.png`。图质量很好（学生字迹清晰、三点作答完整），见本地 `C:\Users\Administrator\AppData\Local\Temp\q17_sample.png`。

### 2.4 轻量标注器 annotator.html ✓
- 源文件：`C:\Users\Administrator\AppData\Local\Temp\annotator.html`
- 部署：`/home/ops/projects/edu-cloud/frontend/dist/annotator.html`（644, nginx 可 serve）
- 访问：`https://mcu.asia/annotator.html?subject_id=<sid>&side=<A|B>&img=/samples/{科目}-{A|B}.png`
- 功能：
  - Canvas 1:1 显示底图，鼠标拖拽画矩形
  - 顶栏 3 种类型（choice_group/essay/subjective）切换，不同颜色
  - 缩放：`−` `+` `适应` `1:1` 按钮 + `Ctrl/Alt+滚轮`
  - 矩形选中可 handle 缩放 / 拖移 / Del 删
  - 新建矩形弹 modal 填元数据（choice_group 要 rows/cols/qg_indexno/start_no/score/multi；essay 要 qno/score）
  - 右侧 sidebar 列表同步
  - 三按钮：**加载已存**（GET Template） / **AI 预识别**（见 2.5） / **保存**（PUT Template）/ 清空
  - regions 内部存 **natural 坐标**（不是 display），render 时 `ctx.scale(scale,scale)`
  - 保存接口：`PUT /api/v1/templates/{subject_id}/{side}` body `{image_width, image_height, anchors:[], regions:[], sample_image}`
- **关键实现细节**：
  - token 从 `localStorage.getItem('token')` 取 Bearer，已在 mcu.asia 登录才能用
  - regions schema 匹配后端 `Template.regions`（见 `src/edu_cloud/modules/card/template_router.py`）
  - choice_group 输出字段：`id type=choice_group question_type rect rows cols labels multi_select qg_indexno start_no score`
  - essay 输出字段：`id type=essay|subjective qno rect question_type score`

### 2.5 AI 预识别 endpoint ✓（但质量差，需升级为 OpenCV+LLM 混合）
- 后端：`/home/ops/projects/edu-cloud/src/edu_cloud/modules/scan/auto_detect.py`
- 挂接：`pipeline_router.py` 末尾 `@router.post('/auto-detect')` 已 append
- 走 llm-proxy `answer-vision` slot → gemini-3-pro-preview（chain fallback 到 flash）
- 本会话做了 4 轮迭代：
  1. v1 原始：被 Pro 429 降级到 flash，识别碎片（同题拆 3 块）
  2. v2 prompt 加强「一题一框」+ 后端按 qno 合并 bounding box ← **这个合并逻辑要保留**
  3. v3 `response_format={"type":"json_object"}` + max_tokens 8192 ← 仍需保留
  4. v4 兼容 rect 为 `[y1,x1,y2,x2]` 数组 + 0-1000 归一化还原到原图像素 ← 仍需保留
- **最终实测 (pro + 所有修复)**：地理 A 识别 7 region，3 个 choice_group 重复框同一片气泡，Q17/18/19 bbox 仍然横跨多栏（Q17 x1=151, x2=2151 —— 把左栏卡头+选择题都吞了）。**LLM 纯方案做像素级几何定位不可靠。**

### 2.6 LLM key 更新 ✓
用户给了新 key 替换 vectorengine.ai 通道（`/home/ops/projects/llm-proxy/.env`）：
- `VECTO_KEY=sk-fOIzJEyD0PvKDFvwv4v7kMdtAOL9zQoPwoeijQfQyQGxXLgz`（官转 主力）
- `VECTO_KEY2=sk-4xkL2UoY6W4jWDTrE5u9OP7CLAtU0f4dBqTvX9xoiF1fqJc3`（优质官转 备用）
已 `sudo -n systemctl restart llm-proxy`，pro 通道解锁（直连 `api.vectorengine.ai/v1` + `gemini-3-pro-preview` 返回 200）。

---

## 三、下一步任务（Opus 4.6 开始干这个）

### 3.1 OpenCV + LLM 混合方案（用户 22:13 已同意思路）

**文件**：新建 `src/edu_cloud/modules/scan/auto_detect_cv.py`（不改 auto_detect.py，对比好回滚）

**流程**：
1. 读图 → 灰度 → 自适应二值化
2. **几何识别**（OpenCV）：
   a. `cv2.findContours` 找所有闭合轮廓
   b. `cv2.approxPolyDP` 近似为多边形 → 过滤 4 顶点
   c. 过滤条件：面积 ≥ 图面 1%（排除小噪点）+ 长宽比合理（0.2-5，排除极细长）+ 位置不在四角 100px 内（排除定位点）
   d. 得到 N 个候选 **essay region**
   e. 同时用 `cv2.HoughCircles` 找半径 15-30 px 的圆（选择题气泡）；按 y 行聚类 → 每行数量 ≥ 4 即为气泡阵列；行间距稳定的连续阵列合并为 **choice_group region**（给出 rows, cols）
3. **语义补标**（LLM）：
   a. 对每个 region crop 缩略图 (最长边 512px)
   b. 一次性把整张原图 + 所有 region rect 列表发给 gemini-3-pro（新 prompt），让它输出 **每个 region 的 qno, score, qg_indexno, start_no** —— 不要 LLM 出坐标，只要语义标签
   c. 按 region_id 关联回 OpenCV 的 rect
4. 合并同 qno 子题（沿用 auto_detect.py 里的 merged 逻辑）
5. 返回 `{regions: [...], width, height, raw}`

**prompt 草稿（LLM 二次打标）**：
```
下面是一张答题卡，OpenCV 已检测出 N 个区域，按顺序列出它们在原图的位置：
  R01: rect=(x,y,x,y)
  R02: rect=(x,y,x,y)
  ...
请为每个 region 返回：
- type: choice_group | essay | not_a_region (非作答区，如卡头/条形码/信息填涂)
- 若 choice_group: rows, cols, start_no, qg_indexno
- 若 essay: qno (大题号整数), score (题号旁"X分"字样，无则 0)
输出：{"regions":[{"id":"R01","type":"...","qno":...},...]}
```

**annotator 按钮**：  
改 `btnAI.onclick` 或新加 `btnCV` 按钮调用 `/api/v1/scan/pipeline/auto-detect-cv`，其他逻辑沿用 `aiDetect()`。

**调参预期**：A3 landscape 3284×2295 扫描件，阈值 adaptive blocksize=25 C=10 是起点。开始会有误检（请在各题目答题区域内作答 这种说明文字框 也是矩形），做白名单/黑名单过滤。

### 3.2 标 18 张 template（跑通全链路前提）

不动 3.1 情况下能先做：在 annotator 里**手工标**地理 A 作为 smoke-test，跑通端到端。9 科 × A/B 18 张大概手标 2-3 小时（B 面多半近空白，3 分钟）。

**保存后验证**：
```python
# 在 ECS 上
cd /home/ops/projects/edu-cloud
.venv/bin/python -c "
import sqlite3, json
con = sqlite3.connect('edu_cloud.db'); cur = con.cursor()
r = cur.execute('SELECT regions FROM templates WHERE subject_id=? AND side=?', ('d27b05c7-...','A')).fetchone()
print(json.dumps(json.loads(r[0]), ensure_ascii=False, indent=2))
"
```

### 3.3 标完后重跑切割

```bash
# 单科 A 面
python /c/Users/Administrator/AppData/Local/Temp/cdp_fetch.py --url "https://mcu.asia/api/v1/scan/pipeline/start" --method POST --body '{"subject_id":"...","side":"A","image_dir":"/home/ops/projects/edu-cloud/uploads/scan-input/A3722/地理"}' --timeout 60
```
进度：`GET /api/v1/scan/pipeline/progress`

**确保 Template.regions 里至少 1 个 region 有 `question_id` 字段** —— 否则 save_answer_fn 的 `region_map = {r["id"]: r["question_id"] for r in regions if r.get("question_id")}` 空 → 切出图片但 student_answers 表零增量。

对应做法：标注时让 region.id 与 `questions` 表的某个 id/name 挂钩。或者在 auto_detect_cv.py 或 annotator 保存前做一次映射补全（按 qno 去 questions 表查对应 Question.id 注入 region.question_id）。建议**在 annotator 的 saveToServer 前端里加**：调 `GET /api/v1/questions?subject_id=...` 取题库，按 qno 匹配，注入 question_id 字段再 PUT。

### 3.4 之后的链路（一步跟一步）

| 步 | 入口 | 输入 | 验证 |
|---|---|---|---|
| 分配阅卷 | `MarkingAssignPage` 或 `POST /api/v1/marking/assignments` | subject + 教师 + 题号 | grading_assignments 表有新条目 |
| 选择题自动判分 | 随 切割 pipeline 同步完成 | choice_group region + Question.correct_answer | objective_grading.py 产出 grading_results |
| 教师手动阅卷 | `/review` 页（ReviewPage） | 教师账号 t_yw_001 登录 | grading_results 状态 confirmed |
| AI 阅卷 | `GradingDispatchPage` AI 触发 | llm-proxy `grading-vision` slot | grading_results.ai_raw_response 非空 |
| 成绩发布 | `GradingDispatchPage` 发布按钮 | publish_service 前置校验 | exams.status=completed + exam_results 写入 |

---

## 四、工具箱（本机 Windows 已就绪）

所有临时工具放在 `C:\Users\Administrator\AppData\Local\Temp\`：

| 文件 | 用途 | 用法 |
|---|---|---|
| `ecs-auto-ssh.py`（`Documents\`）| SSH + TOTP 2FA 跑 shell | `python /c/Users/Administrator/Documents/ecs-auto-ssh.py "cmd"` |
| `ecs_upload.py` | sftp 上传下载 | `from ecs_upload import connect; sftp = paramiko.SFTPClient.from_transport(connect())` |
| `cdp_nav.py` | CDP 导航 + 截图 + eval JS | `--goto URL --click-text "text" --wait N --eval "js" --text --shot` |
| `cdp_fetch.py` | 在调试 Chrome 里 fetch API（带 auth token） | `--url 完整URL --method POST --body '{...}' --timeout N` |
| `cdp_login_edu.py` | 初始化教务主任登录 | 已登录过，一般不重跑 |
| `annotator.html` | 本地源，改完 sftp 上传覆盖 `frontend/dist/annotator.html` | —— |
| `auto_detect.py` | 本地源，改完 sftp 上传覆盖 `src/edu_cloud/modules/scan/auto_detect.py` + restart edu-cloud | —— |

**CDP timeout 坑**：`cdp_nav.py` `cdp_fetch.py` 创建 websocket 时 timeout=15-30 秒。AI 识别耗时 10-60 秒，浏览器 fetch 直接跑没问题，但 CDP 脚本里 awaitPromise 会因 WS 超时失败。**别用 CDP 触发耗时 >15s 的 fetch**，直接用 `.venv/bin/python` 在 ECS 上调 auto_detect_regions 测试更快。

**中文 URL**：Windows curl 默认 GBK 编码，mcu.asia 的 samples 中文文件名要 urlencode。Chrome 里直接输中文 URL 会自动 encode，没问题。

---

## 五、凭证 & 敏感值

| 项 | 值 | 位置 |
|---|---|---|
| ECS SSH | `ops@47.121.197.52:22`，Ed25519 key `~/.ssh/aliyun_emergency` + passphrase + TOTP | `ecs-auto-ssh.py` 里写死 |
| 教务登录 | `admin_academic_director_2` / `123456` | 调试 Chrome 9223 localStorage 已有 JWT |
| VECTO_KEY | sk-fOIzJEyD0PvKDFvwv4v7kMdtAOL9zQoPwoeijQfQyQGxXLgz | `/home/ops/projects/llm-proxy/.env` |
| VECTO_KEY2 | sk-4xkL2UoY6W4jWDTrE5u9OP7CLAtU0f4dBqTvX9xoiF1fqJc3 | 同上 |
| AIPROXY_OAI_KEY | sk-1bd2780c...（未动） | 同上 |
| sudo | `ops` 免密 sudo（`-n` 可用），仅用于 `systemctl restart edu-cloud/llm-proxy`，不做其他 sudo 动作 | —— |

**sudo 白名单**：只用 `sudo -n systemctl restart`, `sudo -n journalctl`, `sudo -n cat /proc/<pid>/environ`。**不要 sudo 动 nginx 配置**（生产站点，改错会挂）。

---

## 六、坑位 / 已踩 / 别再踩

1. **不要关主 Chrome**（`feedback_no_kill_chrome.md`）。调试浏览器用独立 user-data-dir 在端口 9223，已跑。关它要先找到 `chrome-debug-edu` 目录的 chrome PID 再 Stop-Process 单个，不要 `taskkill /IM chrome.exe`。
2. **edu-cloud.service 没有 --reload**。改 .py 之后 **一定要 `sudo -n systemctl restart edu-cloud.service`**，否则热加载不生效（会让你怀疑人生）。
3. **Vite dev 8080 外网 Empty reply**：阿里云 WAF 或安全组层拦截，与前端无关。冻结期别折腾这个（handoff doc 记录过），走 mcu.asia 生产 dist 就是对的路。
4. **mcu.asia 的 dist 是 `npm run build` 后的产物，不含 Vite 热加载**。要让 annotator.html 可访问，把文件放 `frontend/dist/` 直接就行（`try_files $uri $uri/ /index.html` 会先找实际文件）。
5. **nginx 权限**：复制到 dist/ 的文件要 chmod 644/755，父目录要 o+rx，否则 nginx user 返 403。
6. **gemini 3 坐标输出不稳**：可能 `{x1,y1,x2,y2}` 也可能 `[y1,x1,y2,x2]`（Gemini 标准），也可能 0-1000 归一化。auto_detect.py 已兼容，但 OpenCV 版就不用操心这个——OpenCV 坐标本来就是像素。
7. **`response_format: json_object` 对 gemini 3 有效**（走 vecto OpenAI 兼容），但对 aiproxy-claude 走 anthropic native format 无效 —— 要换 Claude 做语义的话 prompt 里强制"纯 JSON 不要 markdown"。
8. **llm-proxy `X-LLM-Slot` header 跟 body 里 `model` 任选其一就行**。`answer-vision` slot chain = vecto gemini-3-pro → vecto2 gemini-3-pro → aiberm gemini-3-flash（最后一档弱很多）。
9. **paramiko sftp 第一次 put 报 ENOENT 是玄学**（transport 初期不稳）：做一次小文件 canary write 再 put 大文件即可。别花 30 分钟 debug。
10. **TOTP 冲突**：`ecs-auto-ssh.py` 每次新连接都重新算 OTP，一秒内连发几次会失败（同一 OTP 被 sshd 侧 AntiReplay 拒了）。遇到 auth failed 等 30 秒再试，别狂刷。

---

## 七、用户风格 memo（从会话里学到的）

- **短、快、不废话**。长文分析会被打断。
- 做事优先级：先打通，后优化；先能用，后好看。
- 已知反感：
  - 总结/升华/建议收尾（`feedback_no_preaching.md`）
  - 无故让他做手动活（文档读不进去，工具到位 3 秒就知道好不好用）
  - 给方案时的冗长 tradeoff 表（但简短对比表他接受）
- 已知偏好：
  - 技术分享式的平实语言
  - 直接给编号选项让他选 `1/A/B/C`
  - 关键结论前置，细节后置
- **禁区**（CLAUDE.md 和 memory 里）：
  - 不关主 Chrome
  - 不动代理（sing-box / DMIT）
  - 不跑 metactl / projectctl（是开发机工具，推广机没用）
  - 不改本机 hook（是开发机 scp 过来的副本）
- **发布纪律**：本会话没触发，但如果跑到"成绩发布"要知道 `publish_confirm_guard` hook 会拦截，需要 `CONFIRM_PUBLISH=1` env。详见 `~/.claude/control/profile-publish.yaml`。

---

## 八、上次会话 Task 状态快照

```
#1. [completed] 盘点可用测试素材
#2. [pending]   Playwright Firefox 登录教务主任账号创建考试
#3. [pending]   上传标准答案 + 设计答题卡模板
#4. [in_progress] B 方案：构建轻量标注器 + 打通切割全链路
#5. [pending]   教师手动阅卷验证 + (可选) AI 阅卷
#6. [pending]   发布成绩 + 链路全程截图归档
#7. [completed] 加 AI 预识别 endpoint + annotator 按钮
#8. [pending]   OpenCV 规则检测 region + LLM 补语义 ← 下一步
```

新会话可以全部重建 TaskList，不必继承 ID。

---

## 九、一键热身命令（新会话第一分钟跑）

```bash
# 1. ECS 存活
python /c/Users/Administrator/Documents/ecs-auto-ssh.py "hostname && systemctl is-active edu-cloud llm-proxy nginx && ss -tlnp | grep -E ':9000|:8100|:443'"

# 2. 调试 Chrome 存活
NO_PROXY="*" curl -sS http://127.0.0.1:9223/json/version | head -3

# 3. mcu.asia 可达
NO_PROXY="*" curl -sS -o /dev/null -w "HTTP=%{http_code}\n" https://mcu.asia/annotator.html

# 4. 预识别 endpoint 活
python -X utf8 /c/Users/Administrator/AppData/Local/Temp/cdp_fetch.py --url "https://mcu.asia/api/v1/health" --method GET --timeout 5
```

全过绿才开干。任一项挂先排查，别硬推。

---

## 十、下一步决策树（给新会话）

```
用户第一句指令 →
  若说 "继续" / "干" / "开始" → 直接进 3.1 OpenCV 混合方案实现
  若说 "先标几张手动" → 引导他用 annotator.html，按 §一.2 的 18 URL 表
  若说 "切换 XX 模型" → 只改 auto_detect.py 里 body["model"] + 确保 llm-proxy providers.yaml 里该 model 存在
  若说 "跑地理全量" → 提醒"template 只 Q17，切 1/19 题，先标模板"
  若说 "发布成绩" → 提醒 publish_confirm_guard + CONFIRM_PUBLISH=1
  其他 → 读用户话，不要自作主张扩大范围
```

完。
