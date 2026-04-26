<!-- legacy-format -->
# HANDOVER — edu B 端主链路 Session 2 交接（2026-04-16）

> **读者**：接替本会话的新 Claude。Session 1 完成 Phase 0-A/B/C，Session 2 完成 Phase 0-D → 1-A/B/C → 2-A/B/C → 3 自动化。用户当前卡在"真实浏览器访问前端"，用户上一条要求写这份交接文档供新会话接手。
>
> **优先阅读**：`/home/ops/projects/edu-cloud/docs/plans/2026-04-16-b-main-flow-handoff.md`（上一份自含完整铁律+背景），本文件是**差量**不重复铁律。

---

## 1. 当前待办（用户正在做的事）

用户在手机（湖南株洲移动）浏览器访问 edu-cloud 前端做真实点击测试。当前卡点：阿里云安全组只开了 5273/8080（TCP 直连被移动运营商或某层拦截，返回 `ERR_EMPTY_RESPONSE`）。

**最后一步提示已发给用户**：

> 阿里云安全组加一条 80 端口入方向规则（TCP / 端口 80 / 源 0.0.0.0/0）→ 浏览器打开 `http://47.121.197.52/` → 登录 `admin` / `123456`。

### 已完成的服务编排（用户下一次登录就能生效）

| 服务 | 状态 | 端口/路径 |
|---|---|---|
| edu-cloud 后端 | systemd 运行中 | `127.0.0.1:9000`（`edu-cloud.service`）|
| Vite dev server | 后台进程 ID `bbjcw6zm2` | `0.0.0.0:8080`（Vite 配置见 §3）|
| Nginx | systemd 运行中 | `0.0.0.0:80` → 反代 `127.0.0.1:8080`（见 §3）|
| paper-seg | 未启动 | port 8001（需要时 `cd /home/ops/projects/paper-seg && .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001`）|

### 安全组当前状态（阿里云控制台）

安全组 `sg-f8zfp00hjsvth69fwp5i` 当前入方向规则：
- 22 / SSH（默认）
- 3389 / RDP（默认）
- ICMP（默认）
- **5273 / TCP / 0.0.0.0/0**（用户加的，已废弃可删）
- **8080 / TCP / 0.0.0.0/0**（用户可能加了，已废弃可删）
- **80 / TCP / 0.0.0.0/0** ← **用户待加**

---

## 2. Session 2 交付清单（可 grep 验证）

### 2.1 Phase 0-D — paper-seg 本地模板 CRUD 清理 ✅
- 新增 `/home/ops/projects/paper-seg/app/tpl_cache.py`（只读 `TEMPLATES_DIR` + `_tpl_path`）
- 删除 `paper-seg/app/routers/templates.py`、`tests/test_tpl_import.py`
- 修改 `main.py`（去掉 templates 路由注册）、`pipeline.py:79`、`segment.py:12` import 指向新位置
- 更新 `static/index.html` 删除"导入外部模板"按钮；`static/app.js` 删 `autoMatchTemplates`、`btn-import-tpl` handler
- CLAUDE.md 同步新架构（paper-seg 只读拉取，不再持有 CRUD）
- 测试：baseline 保持 `91 passed + 7 pre-existing failed`（numpy/event-loop，环境原因）

### 2.2 Phase 1-A — 题型词汇表统一 ✅
- **设计偏离 handoff**：保留 `region.type` 作为渲染提示（choice_group/number_fill/absent_mark/barcode/subjective），**新增** `region.question_type` 作为语义字段，避免破坏 number_fill（学生考号网格）和 absent_mark 的 fillmark 处理。理由写在迁移 docstring。
- `Question.question_type` 枚举从 `objective|subjective` → `choice|multi_choice|fill_blank|essay`
- 常量写在 `src/edu_cloud/modules/exam/models.py::QUESTION_TYPE_*` 和 `QUESTION_TYPES_OBJECTIVE/SUBJECTIVE/ALL`
- Alembic 迁移 `d4f1c8a92e75_unify_question_type_vocabulary.py` 双向测过
- 读写点更新：`workers/grading.py`、`modules/scan/pipeline_router.py`、`modules/grading/router.py`、`modules/exam/router.py`（Pydantic Literal）、`modules/card/router.py::_map_standardized_type`、`modules/card/publish_service.py`、`modules/card/export.py`、`modules/scan/tpl_parser.py`、`data/seed_demo.py`、`data/import_real_exam.py`、`modules/marking/importer.py`、`modules/card/template_library.py`（兼容历史 seed JSON 里的 `"objective"` 值）
- 39 个测试文件 120 处字面量批量替换（tests/test_api_exam + test_services_exam + test_workers + test_modules）
- answer-card-editor `backend/app/core/matcher.py` 加了容错 `_CHOICE_TYPES` / `_ESSAY_TYPES`

### 2.3 Phase 1-B — 题型感知切割 ✅
- `paper-seg/app/vision/segment.py::crop_region(img, rect, question_type='essay')`
- margin 表：`choice=0 / multi_choice=0 / fill_blank=4 / essay=16`
- `segment_one_image` 和 `pipeline.py` 调用时传入 `region.question_type`
- `tests/test_segment.py` 加 5 个参数化测试

### 2.4 Phase 1-C — 上传链路携带题型 ✅
- paper-seg `ExamAIClient.upload_image` 加 `question_type` 参数
- edu-cloud `StudentAnswer.question_type: str|None` 列（迁移 `e6a921f4b8c0`）
- `/api/scan/upload`（`api/compat_router.py`）接受 `question_type` Form 字段
- `modules/grading/prompts.py`：`_SYSTEM_PROMPT_FILL_BLANK`（短答）和 `_SYSTEM_PROMPT_ESSAY`（长答），`build_grading_prompt(rubric, question, question_type)` 按类型分派
- `modules/grading/llm_client.py::grade(..., question_type=None)` 透传
- `workers/grading.py::_grade_single` 读 `answer.question_type`（缺省回落 `Question.question_type`）→ 传给 llm.grade
- `tests/test_services_exam/test_grading_prompts.py` 新建 4 tests；`test_grading_worker.py` 加 `test_process_grading_task_routes_question_type_to_llm`

### 2.5 Phase 2-A — 年级学科报告导出 ✅
- `modules/analytics/exporters.py` 新建（reportlab + openpyxl，避开 playwright）
- `build_grade_subject_report(db, ...)` 聚合 summary+distribution+aggregates+questions（top/bottom 各 5）
- `render_grade_subject_report_pdf` / `render_grade_subject_report_xlsx`
- `GET /api/v1/analytics/report/grade/{exam_id}/{subject_id}/export?format=pdf|xlsx`（`router.py:399`）
- CJK 字体检测 `_ensure_cjk_font()` 从 `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc` 注册
- `tests/test_api_exam/test_analytics_export.py` 7 tests

### 2.6 Phase 2-B — 个人学科报告导出 ✅
- `build_student_subject_report` / `render_student_subject_report_pdf` / `render_student_subject_report_xlsx`
- 数据：Student+Class → 总分 + 各题得失分（JOIN GradingResult.final_score，fallback StudentAnswer.score）+ 班级均分 + 薄弱题 top3 (<60%)
- `GET /api/v1/analytics/report/student/{student_id}/{exam_id}/{subject_id}/export?format=pdf|xlsx`
- 权限：`visible_class_ids` + `visible_subject_codes` 双层过滤
- 4 new tests（student PDF / xlsx sheets / 404 / 403）

### 2.7 Phase 2-C — 前端真实下载 ✅
- `frontend/src/api/analytics.js` 新增 `exportGradeReport` / `exportStudentReport`（`responseType: 'blob'`）+ `downloadBlob` helper（解析 `filename*=UTF-8''` 格式）
- `AnalyticsReportPage.vue`：删除旧的 `exportReport`（Studio 假实现），加 `exportSubjectId` + `canExport` computed + `handleDownload(format)` + 两个按钮（PDF / Excel）
- `AnalyticsPage.vue`：题目分析区加 PDF/Excel 两个导出按钮
- `frontend/src/pages/__tests__/AnalyticsReportPage.test.js` 整体重写，5/5 通过
- `npm run build` 通过，`npx vitest run` 234/234

### 2.8 Phase 3 — 自动化验收 ✅（真实扫描端到端未做）
- edu-cloud 全量 pytest：**34 failed / 1577+ passed**。34 个失败**全部**命中 handoff §6 pre-existing 清单（playwright 缺/ docx 缺 / auth fixture / flaky），不是 session 2 引入。
- paper-seg pytest：**7 failed / 91 passed**（numpy bool + event loop，环境问题，非本次）
- frontend vitest：**234/234 passed**
- 零新增 TODO/FIXME（grep 验证）
- 剩余未做：真实扫描图 + 真实考试答题卡走完整流（扫描→切图→上传→AI 评分→人工校对→导出报告）。需要真实 .png 扫描数据和已发布的考试，在 sandbox 内无法自动化。

---

## 3. Nginx + Vite 服务端配置详情（session 2 改过）

### 3.1 修改的 Nginx 配置
`/etc/nginx/conf.d/momowan.conf`（已备份到 `momowan.conf.bak-2026-04-16`）

原 `default_server` 返回 444（拒绝未知 Host），**改为反代到 `127.0.0.1:8080`**：
```nginx
# IP 直连 default_server — Phase 3 测试期间反代到 Vite dev (8080)
server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 50M;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
}
```

**测试完成后请恢复**：
```bash
sudo cp /etc/nginx/conf.d/momowan.conf.bak-2026-04-16 /etc/nginx/conf.d/momowan.conf
sudo nginx -s reload
```

已有的 `edu.momowan.xyz` server block（L33）是生产形态（静态 dist + /api 反代），后续接入正式域名时启用。

### 3.2 Vite 配置改动
`/home/ops/projects/edu-cloud/frontend/vite.config.js`：
- `port: 8080`（原 5273，为避开移动运营商 QoS）
- `host: '0.0.0.0'`（显式绑所有接口）
- `allowedHosts: ['47.121.197.52', 'localhost', '127.0.0.1', '172.20.109.183']`（Vite 7 默认只认 localhost，必须显式白名单否则 `Host: 公网IP` 会被静默 drop 成 `ERR_EMPTY_RESPONSE`）

**恢复原配置**：改回 `port: 5273`，删 `host` 和 `allowedHosts` 行即可（不急）。

### 3.3 Vite 后台进程
- Shell task ID：`bbjcw6zm2`（Bash run_in_background）
- 命令：`npx vite`（cwd=frontend，读 vite.config.js 的 8080 + allowedHosts）
- stdout 日志：`/tmp/user/1000/claude-1000/-home-ops/b54a2b88-25c8-4919-9b23-2612dbe0a30f/tasks/bbjcw6zm2.output`
- 停止：`TaskStop(task_id='bbjcw6zm2')`
- 重启：`cd /home/ops/projects/edu-cloud/frontend && npx vite` run_in_background=true

---

## 4. 关键架构知识（Session 2 新发现）

### 4.1 Aliyun ECS 网络拓扑
- 公网 IP：`47.121.197.52`（`curl ifconfig.me`）
- 内网 IP：`172.20.109.183`（本机 eth0）+ `172.17.0.1`（docker）+ `172.18.0.1`（docker）
- Hairpin NAT 回环到 `127.0.0.1`：从服务器自己 `curl http://47.121.197.52:XXXX/` 会解析到 `127.0.0.1`；**不要用自身公网 IP 做测试**，用内网 IP + Host header 或走真实外部访问。
- `HTTPS_PROXY=http://127.0.0.1:7890`（Clash 在跑）：外部 API 调用自动走代理；本地测试加 `--noproxy '*'` 避免干扰。

### 4.2 移动网络端口限制（用户卡点根因）
- 移动 4G/5G 对 5273、8080 等非标准端口有 QoS 丢包行为（表现为 `ERR_EMPTY_RESPONSE`）
- 80 / 443 通常放行
- 解决方案：用 nginx port 80 反代（已配），避开端口封锁

### 4.3 现有 nginx 子域名布局（参考）
`/etc/nginx/conf.d/subdomains.conf` + `momowan.conf` 已配置：
- `paper.momowan.xyz` → 127.0.0.1:8200（paper-skill）
- `zhixue.momowan.xyz` → 127.0.0.1:3000
- `class-points.momowan.xyz` → 127.0.0.1:8500
- `zhcps.momowan.xyz` → ?
- `bio.momowan.xyz`、`kb.momowan.xyz`
- `edu.momowan.xyz` → 静态 dist + /api→9000（生产形态）
- `api.momowan.xyz` → ?

DNS：`momowan.xyz` 解析到 Cloudflare（104.21.85.32 / 172.67.201.191）；子域名需用户在 Cloudflare 后台加 A 记录指向 `47.121.197.52`。

### 4.4 关键路径守卫（critical path guard）
本机启用了 PreToolUse hook 防止误改关键路径。触发范围：
- 改 iptables / ufw / 安全组
- 改 nginx / systemd 配置
- 读 /etc/nginx/*、sudo 命令部分场景

触发后需要用户回复固定短语 **`批准 critical path`** 或 `approve critical path` 才能继续。不要自作主张绕开。

---

## 5. 恢复到"干净态"的指引（测试完/下次启动前）

```bash
# 1. 恢复 nginx 到测试前状态
sudo cp /etc/nginx/conf.d/momowan.conf.bak-2026-04-16 /etc/nginx/conf.d/momowan.conf
sudo nginx -s reload

# 2. 恢复 Vite 配置到原 5273
cd /home/ops/projects/edu-cloud/frontend
# 编辑 vite.config.js：port: 5273；删 host 和 allowedHosts 行

# 3. 停 Vite 后台进程
# TaskStop(task_id='bbjcw6zm2')  （通过 Claude 工具）
# 或 pkill -f "node.*vite"

# 4. 删阿里云安全组临时规则：5273、8080、80（测完后手动在控制台删）
```

---

## 6. 数据库迁移头（比上一份交接更新）

```
$ .venv/bin/alembic heads
e6a921f4b8c0 (head)
```

链条：`a7e9c4b8d123`（Phase 0-A）→ `d4f1c8a92e75`（Phase 1-A）→ `e6a921f4b8c0`（Phase 1-C）

---

## 7. 新会话启动 checklist

1. 读本文件 + `2026-04-16-b-main-flow-handoff.md`（铁律 + Phase 0-A/B/C 背景）
2. `TaskList` 看 8 个 Task 全部 completed
3. 读 `MEMORY.md` 里更新过的 `handoff_edu_bflow.md`（Session 2 尾声更新过）
4. 如果用户接着做"真实扫描端到端"：
   - 启 paper-seg（port 8001）
   - 需要 `.png` 扫描图真实样本（`/home/ops/projects/paper-seg/test_data/`）
   - edu-cloud 先造一个 draft 考试 + 答题卡（或用 seed 的"2026年春季期末考试"）
5. 如果用户要上线到公网给学校用，启动"生产加固"任务流（上一份回答里列了对照表）

---

## 8. Session 2 未解/遗留

- **真实 E2E 扫描走查未做**：需要启 paper-seg + 真实扫描图 + 真实答题卡，sandbox 不适合自动化。
- **answer-card-editor 模板 schema 未完全统一**：仅加了 matcher 容错，`QuestionItem.type` 注释 TODO 标明同时接受新旧枚举。后续若统一前端到 edu-cloud 的 canonical vocab，需要同步改。
- **前端导出按钮未加学生报告入口**：Phase 2-B 后端端点已就位，但前端没有学生选择 UI（AnalyticsPage 上只有 subject 选择）。handoff 原文也没强求；如果后续要做，在 AnalyticsPage 或 ExamDetailPage 的学生行加"查看学生报告"按钮即可。
- **用户本次测试反馈未收到**：用户开安全组 80 后是否能打开页面、登录是否顺利，未知。下一个会话开场问用户 "刚才 80 端口开了吗？测试页面进去了吗？"

祝顺利。
