# edu 项目群技术债全面审计报告

> **审计日期**: 2026-04-26
> **审计范围**: edu-cloud / paper-seg / answer-card-editor 三仓库
> **审计方法**: Claude 6 路并行探查（后端架构 / 前端 / 测试+依赖 / paper-seg / answer-card-editor / 跨仓安全）
> **GPT 交叉审查**: Codex CLI (gpt-5.4) 3 路并行完成。base_url 从 `aiproxy.superaichao.xin` 迁移到 `superaichao.xin/openai` 后恢复连通。

---

## 项目规模概览

| 仓库 | Python 文件 | 前端文件 | Python 行数 | 定位 |
|------|------------|---------|------------|------|
| edu-cloud | 737 | 503 | ~100K | 教育云平台（主力） |
| paper-seg | 39 | 1 | ~3.5K | 试卷扫描切割客户端 |
| answer-card-editor | 44 (实际代码) | 324 | ~4K (实际) | 答题卡几何编辑器 |

---

## 一、Critical 级发现（需立即修复）

### C-01 硬编码种子密码 "123456" [edu-cloud]
- **位置**: `src/edu_cloud/api/app.py:110`, `data/seed_school.py:202,212,225,232,258`, `data/seed_highschool_supplement.py:361`, `data/import_exam_xlsx.py:274`
- **风险**: 生产环境若未覆盖，攻击者可用默认密码登录
- **修复**: 移到环境变量 `SEED_DEFAULT_PASSWORD`，启动时校验非默认值
- **工时**: 0.5h

### C-02 Alembic-ORM 双轨漂移 [edu-cloud]
- **位置**: `src/edu_cloud/api/app.py:69-70` (`Base.metadata.create_all`) + 31 个 Alembic migration
- **风险**: 开发/测试/生产 schema 不一致，新列在 ORM 定义但 migration 缺失时静默通过
- **修复**: 移除 `create_all()`，所有环境统一走 `alembic upgrade head`
- **工时**: 3h（含验证现有 migration 链完整性）
- **已知**: memory 已记录（`project_edu_cloud_alembic_drift.md`），未排期

### C-03 .env 文件在 Git 仓库中 [edu-cloud]
- **位置**: `edu-cloud/.env`（含 `SECRET_KEY=dev-secret-key-change-in-production`）
- **风险**: 密钥泄露到版本历史
- **修复**: `git rm --cached .env`，.gitignore 已有规则但文件早期已提交
- **工时**: 0.5h（含 BFG/filter-branch 清理历史，可选）

### C-04 数据库文件在 Git 仓库中 [edu-cloud]
- **位置**: `edu_cloud.db`(~5.5MB) + 2 个 `.bak` 文件 + `logs/app.jsonl.4`(~12MB)
- **风险**: 仓库膨胀，可能含用户数据
- **修复**: `git rm --cached edu_cloud.db* logs/app.jsonl.*`
- **工时**: 0.5h

### C-05 ExamAIClient 默认端口错误 [paper-seg]
- **位置**: `app/client/api.py:11` — 默认 `http://localhost:8000`，edu-cloud 实际运行在 9000
- **风险**: 新用户首次运行连错端口，无明确错误提示
- **修复**: 默认值改为 `None`，强制显式指定；或改为 9000
- **工时**: 0.5h

### C-06 依赖声明不完整 [answer-card-editor]
- **位置**: `backend/pyproject.toml` 缺 `Pillow` 和 `numpy`
- **证据**: `bubble_detector.py:8` 有 `import numpy as np`，但 pyproject 未声明
- **风险**: `pip install -e .` 后运行 `generate_spec.py` 会 ImportError
- **修复**: 补全依赖声明
- **工时**: 0.5h

---

## 二、High 级发现（下周修复）

### H-01 God Module — 3 个超大路由文件 [edu-cloud]
| 文件 | 行数 | 包含功能 |
|------|------|---------|
| `modules/card/router.py` | 1341 | 25+ 端点（CRUD/模板/渲染/导出） |
| `modules/grading/router.py` | 887 | AI阅卷/教师审核/质量检查/进度 |
| `modules/analytics/router.py` | 795 | 24+ 分析端点 |

**修复**: 按职责拆分为子路由文件（card_crud_router / template_router / export_router 等）

### H-02 前端巨型组件 — 25 个超 300 行 [edu-cloud]
| 组件 | 行数 |
|------|------|
| ExamDetailPage.vue | 1368 |
| AiGradingPage.vue | 838 |
| GradingDispatchPage.vue | 826 |
| DashboardPage.vue | 596 |
| DocCropPanel.vue | 561 |
| ConceptMapPanel.vue | 553 |

**修复**: 拆分为子组件，每个 ≤ 300 行

### H-03 JWT 明文存 localStorage [edu-cloud 前端]
- **位置**: `stores/auth.js:12,20,32`, `api/client.js:7`, `api/conduct.js:4`
- **风险**: XSS 攻击可盗取 token
- **修复**: 迁移到 httpOnly cookie（需后端配合）
- **工时**: 2d

### H-04 v-html 渲染 AI 内容未充分防护 [edu-cloud 前端]
- **位置**: `components/workspace/ChatPanel.vue:33-35`
- **风险**: AI 生成内容可能包含恶意 HTML
- **修复**: 引入 DOMPurify 清理 HTML
- **工时**: 0.5h

### H-05 card-editor innerHTML 多处使用 [edu-cloud 前端]
- **位置**: `card-editor/panel.js`, `card-editor/render.js` — 多处 `innerHTML = html`
- **风险**: 虽然数据受控，但缺乏输入验证
- **修复**: 逐步迁移到 Vue DOM API

### H-06 npm 高危安全漏洞 [edu-cloud + answer-card-editor]
- **edu-cloud**: 6 HIGH（happy-dom, lodash, picomatch, vite）+ 5 MODERATE
- **answer-card-editor**: 2 HIGH（picomatch, vite）+ 1 MODERATE
- **修复**: `npm audit fix --audit-level=high`
- **工时**: 0.5h

### H-07 N+1 查询 [edu-cloud]
- **位置**: `modules/analytics/service.py:220-265`（grade_aggregates 先查学生再循环查班级）
- **修复**: 使用 `joinedload()` 或 `selectinload()` 预加载关系
- **工时**: 1h

### H-08 workers/grading.py 裸 except [edu-cloud]
- **位置**: `workers/grading.py` — `except Exception:` 未记录堆栈
- **风险**: 阅卷任务失败时无诊断信息，任务可能卡死
- **修复**: `logger.error("...", exc_info=True)` + 向上抛出或转换异常
- **工时**: 1h

### H-09 Bundle 未优化 [edu-cloud 前端]
- echarts / marked / katex 全量导入，无 tree-shake
- 仅 ExamDetailPage 单独 chunk，其余合并到主 bundle（1.5M vendor + 466K app）
- **修复**: `vite.config.js` 配置 `manualChunks`

### H-10 SQLite 并发安全 [answer-card-editor]
- **位置**: `backend/app/db.py:13` — `check_same_thread=False`
- **风险**: 多并发请求共用一个连接，无锁保护写入
- **修复**: 改用 connection pool 或 SQLAlchemy

### H-11 三仓均无 CI 配置
- 无 GitHub Actions / GitLab CI / Drone
- 测试完全依赖手工执行
- **修复**: 创建 `.github/workflows/test.yml`

### H-12 .venv pip 破损 [edu-cloud + paper-seg]
- `No module named pip` — 无法 `pip install` 新依赖
- **修复**: 重建虚拟环境

---

## 三、Medium 级发现（本月修复）

### M-01 Router 直接访问 Model [edu-cloud]
- `modules/exam/router.py:16` 直接 `from ...models import Question, Subject`
- 应通过 Service 层封装

### M-02 缺少 AnalyticsService 类 [edu-cloud]
- `modules/analytics/` 逻辑分散在 router + service 两处，无统一 Service 类

### M-03 app.py lifespan 混杂 9 项启动逻辑 [edu-cloud]
- `api/app.py:74-145` 内联种子、工作流初始化、知识库加载
- 应分离到 `bootstrap.py`

### M-04 18 份冗余 Prompt 代码 [edu-cloud]
- `modules/grading/prompts/` — 9 科 × 2 学段 = 18 份，高度重复
- 应用 Template Method / Strategy Pattern 统一

### M-05 CSS 架构碎片化 [edu-cloud 前端]
- 639 处内联 `style="..."`，35 处 `!important`
- 应提取为 scoped CSS class + 全局主题变量

### M-06 API 错误处理无标准化 [edu-cloud 前端]
- `api/client.js` 仅处理 401，其他错误直接 reject
- 应建立统一错误映射和 toast 提示

### M-07 缺少 rate limiting [edu-cloud]
- 登录端点无尝试次数限制
- 应添加全局 rate limiting middleware

### M-08 分数段边界值未校验 [edu-cloud]
- `analytics/segments/config` — `[0, 60, 50, 100]` 非法值不会被拦截
- 应校验单调递增

### M-09 CORS 配置不一致 [跨仓]
- edu-cloud: 仅 `localhost:5173`（生产应为 `mcu.asia`）
- answer-card-editor: `allow_origins=["*"]`
- paper-seg: 无 CORS

### M-10 Python 版本要求不一致 [跨仓]
- edu-cloud / answer-card-editor: `>=3.11`
- paper-seg: `>=3.10`

### M-11 三仓均无 Python lock 文件
- 仅设置最低版本约束，无 pip-compile / poetry.lock / uv.lock
- 存在版本漂移风险

### M-12 paper-seg 文件句柄泄漏 [paper-seg]
- `app/routers/detect.py:19`, `segment.py:46`, `vision/segment.py:51` — `Image.open(p)` 无 with
- 批量处理数千张图可能耗尽 fd

### M-13 paper-seg 缺少返回类型标注 [paper-seg]
- 7/7 路由文件所有 handler 均无 `-> dict` 标注

### M-14 generate_spec 路径硬编码 [answer-card-editor]
- `tools/generate_spec.py:28-39` — `D:/试卷数据/YueXiaoEr/...`（Windows 路径）
- Linux 无法直接运行 `--all`

### M-15 px/mm 转换系数混用 [answer-card-editor]
- `geometry_builder.py:14` 用 `25.4 / dpi`（源 DPI），`validator.py:9` 用 `25.4 / 96`（CSS DPI）
- 混用可能导致单位错配

### M-16 TQL 解析器需契约测试 [跨仓]
- answer-card-editor 和 edu-cloud 各有 TQL 解析器（都继承自 exam-ai）
- 格式不同步会导致渲染失败

### M-17 废弃代码清理 [edu-cloud 前端]
- `card-editor/_backup_20260408/` 备份目录
- `router/_frozen/index.full.js` 冻结路由
- 应删除或归档到 git history

### M-18 缺少 SQL 索引 [edu-cloud]
| 表 | 缺失索引 |
|----|---------|
| student_answers | (subject_id, student_id) |
| grading_results | (answer_id, final_score) |
| conduct_records | (class_id, created_at) |

---

## 四、Low 级发现（可选优化）

| ID | 问题 | 仓库 | 位置 |
|----|------|------|------|
| L-01 | POST /exams/{id}/publish 应为 PATCH | edu-cloud | API 语义 |
| L-02 | /scan/pipeline/start 应返回 202 | edu-cloud | API 协议 |
| L-03 | ESLint 规则不完整 | edu-cloud | eslint.config.js |
| L-04 | v-for 缺 key 或用 :key="i" | edu-cloud | 多处组件 |
| L-05 | 前端无 CSP/X-Frame-Options | edu-cloud | nginx 配置 |
| L-06 | paper-seg 警告列表上限 100 条后静默丢弃 | paper-seg | client/state.py:54 |
| L-07 | paper-seg httpx 超时 30s 对大图不足 | paper-seg | client/api.py:14 |
| L-08 | answer-card-editor 无生产日志 | ace | 全局 |
| L-09 | answer-card-editor tools/ 脚本杂乱 | ace | tools/ |
| L-10 | requirements.txt 与 pyproject.toml 重复 | ace | 根目录 |
| L-11 | answer-card-editor 前端无错误重试 | ace | App.vue:21 |
| L-12 | schema_id 残留 "exam-ai" 前缀 | ace | geometry_spec.py:79 |

---

## 五、跨仓一致性矩阵

| 维度 | edu-cloud | paper-seg | answer-card-editor |
|------|-----------|-----------|-------------------|
| Python 要求 | >=3.11 | >=3.10 ❌ | >=3.11 |
| FastAPI | >=0.115 | >=0.115 ✓ | >=0.115 ✓ |
| Pydantic | >=2.0 | — | >=2.0 ✓ |
| 端口 | 9000 | 8001 ✓ | 8200 ✓ |
| 日志格式 | JSONL+Console UTC+8 | 无 ❌ | 无 ❌ |
| .env.example | 有 | 无 ❌ | 无 ❌ |
| CI | 无 ❌ | 无 ❌ | 无 ❌ |
| Python lock | 无 ❌ | 无 ❌ | 无 ❌ |
| 测试文件数 | 300 | 16 | 3 ❌ |
| 测试通过 | 2219/2244 | 完整 | 有限 |

---

## 六、测试覆盖评估

| 仓库 | 后端测试 | 前端测试 | 集成测试 | E2E | 评分 |
|------|---------|---------|---------|-----|------|
| edu-cloud | 2219 passed | 348 vitest | ❌ 无 | ❌ 无 | ★★★★☆ |
| paper-seg | 16 文件全覆盖 | ❌ 无 | ❌ 无 | ❌ 无 | ★★★☆☆ |
| answer-card-editor | 3 文件 | ❌ 无 | ❌ 无 | ❌ 无 | ★★☆☆☆ |

**关键缺口**: edu-cloud 关键路径缺集成测试（router→service→model 链路），answer-card-editor 核心算法（geometry_builder, patch_engine, validator）无测试。

---

## 七、安全审计总结

| 类别 | 发现数 | Critical | High | Medium |
|------|--------|----------|------|--------|
| 硬编码密钥/密码 | 3 | 2 (C-01, C-03) | 0 | 1 |
| XSS 风险 | 3 | 0 | 2 (H-04, H-05) | 1 |
| SQL 注入 | 0 | — | — | — |
| 路径遍历 | 0 | — | — | — |
| 认证/授权 | 2 | 0 | 1 (H-03) | 1 (M-07) |
| CORS 配置 | 3 | 0 | 0 | 1 (M-09) |
| 依赖漏洞 | 2 | 0 | 1 (H-06) | 0 |
| Git 卫生 | 2 | 2 (C-03, C-04) | 0 | 0 |

**正面**: 无 SQL 注入、无路径遍历、JWT+bcrypt 实现正确、paper-seg 路径防护达生产标准。

---

## 八、综合评分

| 维度 | edu-cloud | paper-seg | answer-card-editor |
|------|-----------|-----------|-------------------|
| 架构设计 | 7.5/10 B+ | 8/10 A- | 8/10 A- |
| 代码质量 | 7/10 B | 6/10 C+ | 7.5/10 B+ |
| 数据库设计 | 8/10 A- | N/A | 6/10 C+ |
| API 设计 | 7.5/10 B+ | 7/10 B | 7/10 B |
| 安全性 | 6.5/10 C+ | 7/10 B | 6/10 C+ |
| 测试覆盖 | 7.5/10 B+ | 6/10 C+ | 4/10 D |
| 依赖健康 | 6/10 C+ | 6.5/10 C+ | 5/10 D+ |
| 文档 | 8.5/10 A- | 7/10 B | 8/10 A- |
| **综合** | **7.1/10 B** | **6.8/10 B-** | **6.4/10 C+** |

---

## 九、修复优先级路线图

### Phase 0 — 立即（1-2 天）
- [ ] C-01: 硬编码密码移到环境变量
- [ ] C-03: .env 从 git 移除
- [ ] C-04: .db 和日志从 git 移除
- [ ] C-05: paper-seg 端口默认值修正
- [ ] C-06: answer-card-editor 补全依赖声明
- [ ] H-06: npm audit fix

### Phase 1 — 本周（3-5 天）
- [ ] C-02: 移除 create_all()，统一 Alembic
- [ ] H-07: N+1 查询修复
- [ ] H-08: 异常处理加固
- [ ] H-12: .venv 重建
- [ ] M-18: 补充 SQL 索引

### Phase 2 — 下周（5-7 天）
- [ ] H-01: 拆分 3 个 God Module 路由
- [ ] H-09: Bundle 优化（manualChunks）
- [ ] H-04: DOMPurify 防护
- [ ] M-04: Prompt 模板统一
- [ ] M-17: 废弃代码清理

### Phase 3 — 本月（10+ 天）
- [ ] H-02: 拆分 25 个巨型前端组件（逐步）
- [ ] H-03: JWT 迁移到 httpOnly cookie
- [ ] H-10: answer-card-editor 数据库层升级
- [ ] H-11: CI 配置
- [ ] M-11: 引入 Python lock 文件
- [ ] M-16: TQL 契约测试

### 持续优化
- [ ] M-01~M-03: 架构分层改善
- [ ] M-05~M-06: 前端 CSS/错误处理标准化
- [ ] answer-card-editor 测试补齐（核心算法）
- [ ] 类型标注覆盖率提升

---

## 十、已知债务 vs 新发现

| 类别 | 已知（memory/CLAUDE.md 记录） | 本次新发现 |
|------|-----|------|
| Alembic-ORM 双轨 | ✓ C-02 | — |
| 硬编码密码 | — | ✓ C-01 |
| .env 在 git 中 | — | ✓ C-03 |
| .db 在 git 中 | — | ✓ C-04 |
| God Module | — | ✓ H-01 |
| JWT localStorage | — | ✓ H-03 |
| npm 漏洞 | — | ✓ H-06 |
| N+1 查询 | — | ✓ H-07 |
| paper-seg 端口错误 | — | ✓ C-05 |
| ace 依赖缺失 | — | ✓ C-06 |

**结论**: 已知债务仅 1 条（Alembic-ORM），本次审计新发现 6 条 Critical + 12 条 High + 18 条 Medium，技术债积累量显著。

---

## 十一、GPT 交叉审查补充（gpt-5.4 独立发现）

GPT Codex CLI 3 路并行审查完成，以下为 **GPT 发现但 Claude 未覆盖的增量问题**：

### GPT-01 教师创建 API 硬编码密码 [High, Claude 遗漏]
- **位置**: `modules/student/teacher_router.py:42`（创建默认 password=123456）、`:562`（导入流程硬编码 123456）
- **Claude C-01 只发现了 seed 和 app.py**，GPT 额外找到了业务 API 层的同模式
- **影响**: 正常业务流程（非种子数据）中创建的教师账户也用弱密码
- **修复**: 与 C-01 合并修复，统一环境变量 + 强制首次登录改密

### GPT-02 module_middleware JWT 异常绕过模块禁用 [High, Claude 遗漏]
- **位置**: `api/module_middleware.py:86` — `except Exception` 后直接 `call_next()`
- **风险**: JWT 解码失败时，本应拦截的被禁用模块 API 请求会放行
- **修复**: 捕获异常后返回 401/403，不放行

### GPT-03 audit_service 吞审计日志写入失败 [High, Claude 遗漏]
- **位置**: `services/audit_service.py:142` — 审计日志写入失败被 except 吞掉
- **风险**: 操作成功但无审计记录，合规/取证数据丢失且调用方无感知
- **修复**: 审计失败应至少 `logger.error()` 并考虑事务回滚

### GPT-04 CardEditor.vue window 全局变量 [Medium, Claude 部分覆盖]
- **位置**: `frontend/src/components/CardEditor.vue:321` — `window._cardLayout`、`window._choices`
- **Claude H-05 覆盖了 innerHTML 问题**，GPT 额外指出了全局变量绕过 Vue 响应式的架构债

### GPT-05 前端 build 不含 test [Medium, Claude 未提]
- **位置**: `frontend/package.json:9` — `prebuild` 只跑 `lint`，不跑 `vitest`
- **风险**: 前端 build 通过但测试可能失败
- **修复**: `prebuild` 加入 `vitest run`

### GPT-06 answer-card-editor templates.py 反模式 DI [Medium, Claude 未提]
- **位置**: `answer-card-editor/backend/app/api/templates.py:20` — 直接引用 `app.main._db_conn`
- **风险**: 隐式跨模块依赖，无法测试
- **修复**: 改用 FastAPI `Depends()` 注入

### 交叉比对总结

| 维度 | Claude 独有 | GPT 独有 | 双方一致 |
|------|------------|---------|---------|
| 硬编码密码 | seed_school.py 5处 | teacher_router.py 2处 | app.py:110 |
| 异常处理 | workers/grading.py | module_middleware / audit_service | — |
| God Module | card 1341 / grading 887 / analytics 795 | renderer.py 1235 / pipeline_router 804 | 一致 |
| 前端安全 | v-html 3处 / localStorage | window globals / prebuild 缺 test | CardEditor innerHTML |
| 数据库 | N+1 3处 / 缺索引 3处 | — | create_all 双轨 |
| 跨仓 | CORS / Python 版本 / lock 文件 / TQL 契约 | paper-seg 全局单例耦合 | ExamAIClient 端口 |
| ace | 依赖缺失 / px/mm 混用 | templates.py 反模式 DI | check_same_thread |

**交叉收益**: GPT 发现了 3 个 Claude 完全遗漏的 High 级问题（GPT-01/02/03），特别是 module_middleware 的安全绕过（GPT-02）是本次审计最重要的增量发现。

---

*双模型审计完成。Claude 6 路并行 + GPT 3 路并行，总计 42 条发现（6C + 15H + 21M），含 3 条 GPT 独有 High 级发现。*
