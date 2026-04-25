---
type: handoff
created: 2026-04-11 07:54:04
project_dir: C:\Users\Administrator\edu-cloud
design: (无 — 探索/需求收集阶段，尚未形成 design)
plan: (无 — 尚未进入 plan 阶段)
---

# edu-cloud 探索与后续问题梳理 — 交接卡

## 背景

上一个会话完成了 **paper-seg 整合到 edu-cloud（scan-integration, T3）** 任务，GPT R3 PASS 并合入 master。相关 commits：
- 范围: `a9bc0e4..9c18a16`
- 关键提交: `9c18a16 feat: add scan-dir endpoint + directory discovery UI`
- 报告: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-integration-review-report-batch1.md`
- Design: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-integration-design.md`（已标记 `[实现完成]`）

测试阶段用 Playwright MCP 在浏览器里验证扫描 tab 完整流程，所有 API 请求 200、零 JS 错误。

**当前阶段**：用户用 **教务主任账号** 登录平台，逐模块梳理业务逻辑，为后续补齐功能做需求收集。**没有进入 plan 阶段**，新窗口主要是陪用户探索 + 记录发现的问题。

## 当前运行中的服务

| 服务 | 端口 | 启动方式 | 状态（07:54 确认） |
|------|------|---------|-------------------|
| 后端 uvicorn | 9000 | `python ~/.claude/scripts/serve.py python -m uvicorn edu_cloud.api.app:create_app --factory --host 0.0.0.0 --port 9000 --reload`（WSL 或 Git Bash） | ✅ health 200 |
| 前端 vite | 5273 | `python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev`（`frontend/` 目录下） | ✅ 5273 200 |

**重启规则**：改后端代码后必须用上述 serve.py 重启（port_guard.py 会自动清理旧进程）。直接 `uvicorn --reload` 有时会漏识别新 router（实测 scan-dir 端点 reload 没生效，只有完整重启才识别）。

## 登录账号（种子数据）

| 用户名 | 密码 | 角色 | 用途 |
|--------|------|------|------|
| `admin` | `123456` | platform_admin | 平台超管（所在学校无数据） |
| `admin_academic_director_2` | `123456` | academic_director（教务主任 · 李明华） | **当前主账号** — 育才实验中学教务视角 |
| `admin_academic_director_3` | `123456` | academic_director（教务主任 · 赵德文） | 备用 |
| `t_dl_001` 等 | - | - | ❌ **不存在** — seed_school.py 预期创建但种子数据没覆盖该学校的教师 |

**重要**：`t_*` 格式的科任教师账号在当前数据库里不存在。测试科任视角必须从 `admin_academic_director_2` 切角色或直接用教务账号测。

## 约束与偏好

**Tier 声明**：**当前尚未定级** — 探索阶段。任何新开工任务按照 rules 重新判定 Tier。

**已识别待处理问题**（用户已口头确认，但未写入 design/plan）：

### 问题 1：人工阅卷选题页不按教师权限过滤（UX + 数据层双重 bug）
- **症状**：`t_*` 教师登录后 `/marking` 页面能看到所有科目所有题目，点进去批改时 `GET /api/v1/marking/next?question_id=...` 返回 403（后端权限正确）
- **根因**：`GET /api/v1/marking/subjects?exam_id=...` 后端没按 `get_visible_subject_codes(current_role)` 过滤。前端 `MarkingSelectPage.vue` 直接渲染后端返回的所有科目
- **影响**：教师看到"假的"可操作选项，点进去才 403，体验恶劣。类比智学网，应该只显示有权限的科目+题目
- **定位**：
  - 后端: `C:\Users\Administrator\edu-cloud\src\edu_cloud\modules\marking\router.py` §`list_subjects_with_progress`（应补过滤）
  - 前端: `C:\Users\Administrator\edu-cloud\frontend\src\pages\MarkingSelectPage.vue`

### 问题 2：选择题自动打分在扫描流水线中缺失
- **症状**：scan-integration 只实现了**主观题切图存储**，选择题填涂识别（`recognize_page` / `fillmark.py`）虽然已迁入 `src/edu_cloud/modules/scan/vision/` 但 pipeline 没调用
- **paper-seg 原流程**：切割同时识别选择题填涂 → 上传到 `/api/scan/upload-objective` → 后端按标准答案自动判分
- **edu-cloud 现状**：
  - vision 模块已迁入（anchors/transform/segment/barcode/fillmark/lines 全在）
  - pipeline_service.py 只调用 `crop_region`，没调用 `recognize_page`
  - compat_router 有 `POST /api/scan/upload-objective` 旧接口但没被新 pipeline 使用
- **F003 历史背景**：GPT R1 审查时提过 anchor/affine 路径未集成，当时标为 `accepted-risk`（理由：MVP scope）。现在用户要求补齐 → 这个 accepted-risk 需要复议

### 问题 3（F003，accepted-risk 复议）：anchor/affine 校正未集成到主流水线
- `process_one_image` 只做线性缩放裁切，不使用 `detect_anchors` + `compute_affine`
- 真实扫描件倾斜时会裁错区域
- 当时被 accepted 的理由是 "plan MVP scope"，用户明确要补齐后即作废

**用户工作偏好（从会话中观察）**：
- 需求不清楚时用"我记得之前已经开发好了"作为锚定，需要先查现有代码再解释
- 发现功能缺失时会问"为什么 xxx 都不行了"，实际是早期未实现而非新 bug
- 偏好真实数据跑端到端验证（`D:\试卷数据\试卷图像\191871\A3722` 有 9 科完整切分数据）
- 纠正时语气会升级（"真实傻逼"是纯情绪释放不是否定方向，按指出的问题执行即可）

## 环境 quirks（踩过的坑）

- **Git Bash curl 发 JSON 中文编码会挂**：`curl -d '{"dir_path":"D:/试卷数据/..."}'` 返回 `"There was an error parsing the body"`。验证 API 时用 `python -c 'import httpx; ...'` 或 Playwright browser，不要用 curl。
- **Windows pip/python 禁用 `python3`**：用 `python` 而非 `python3`（env-guard hook 已拦截）
- **`uvicorn --reload` 不总是识别新 router**：改完代码如果端点返回 404，直接 `serve.py` 重启整个进程
- **Playwright MCP snapshot 的 depth 参数要给够**：默认深度看不到深层嵌套（已验证：depth=4 时仍漏下拉菜单选项，要用 screenshot 兜底）
- **Naive UI `n-select` 下拉渲染在 body 外层 portal**：playwright 点击下拉选项时要等 portal 渲染，不能用 nth(2) 直接取

## 测试真实数据路径

- **扫描图**: `D:\试卷数据\试卷图像\191871\A3722\` — 9 个科目（化学/历史/地理/政治/数学/物理/生物/英语/语文），每科 100~370 个学生，A+B 面全
- **tpl 模板**: `D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl` 等

## 启动 Prompt

复制以下 prompt 到新窗口：

```
[edu-cloud] Explorer | 2026-04-11 07:54:04
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-11-edu-cloud-exploration-handoff.md 了解上下文。

当前状态：
- 后端 :9000 + 前端 :5273 均在运行，无需重启
- 用户用 admin_academic_director_2 / 123456 登录平台梳理业务逻辑
- scan-integration (T3) 已完成合入 master，最后提交 9c18a16
- 3 个已识别待处理问题（见交接卡「已识别待处理问题」段）

新窗口职责：
1. 陪用户探索各模块，回答业务逻辑问题时先 Grep/Read 现有代码，不凭印象
2. 用户指出新问题时记录到 docs/plans/ 下的临时笔记或直接形成 design 草稿
3. 任何涉及代码变更的任务先按 Tier 判定流程（T1/T2 直接做，T3/T4 走 design→plan→handoff）
4. 阅卷权限过滤 + 选择题自动打分 + anchor/affine 集成属于 T3 起步，要走完整流程
5. 用户提问"在哪里"时直接从代码定位具体文件:行号 + 前端路由路径 + 需要的角色

禁止事项：
- 不要主动启动服务（已在运行）
- 不要碰 scan-integration 已完成的代码（docs/plans/2026-04-09-scan-integration-* 归档）
- 不要 claim "已修复"没做过 verification
- 用 Python httpx 验证 API，禁止 curl 发 JSON 中文
```
