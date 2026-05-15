# edu-cloud 隐性劣化系统调查罗盘

> 调查日期：2026-05-15
> 调查范围：2026-05-01 ~ 2026-05-15 全部变更（~70 commits）
> 调查触发：两次大变更（安全加固 + 技术债清理）引入"改了 A 没改 A 的消费者"式静默劣化
> 约束：只读调查，不修改任何代码

---

## 一、变更时间线总览

### 安全加固批次（2026-05-11 16:56 ~ 18:36，9 commits）
```
d648801 feat: add tenant isolation audit infrastructure (audit mode)
12edc94 fix: close 4 tenant isolation gaps — add school_id to cross-school queries
af6e00c fix: reject invalid active_role_id + upgrade knowledge log level
e1f8e61 fix: batch minor issues (C-7, H-10, H-11, H-12)
99763fd feat: add state machine registry + fix pipeline exception swallowing (C-3, C-8)
c53572a / a3e88d1 / 95efd34  docs: update tracking
7a0572c fix: console.error capture + scan pipeline cross-school isolation (H-13, M-2)
ac710f4 refactor: move auth deps to core/auth.py, eliminating 38 reverse imports (H-4)
```

### 技术债清理批次（2026-05-12 ~ 05-13）
```
84c70fe feat: rebuild AI Agent on Pydantic AI — full 8-step engine replacement (05-12 19:21)
   ↓ 11 小时并存期（新旧引擎共存，完整验证）
d2b547e feat: Steps 8b+9+10 — daily limit, old engine cleanup (05-13 08:42)
   删除 105 文件，-15,246 行
```

### Scan 连锁修复（2026-05-14 夜间高密度）
```
3fb326a fix(scan): 路径隔离改为按 exam 归属验证 (22:38)
1cdccfb fix(scan): 扫描路径补全 school_id 层级 + 调色板 PNG 兼容 (23:03, +24m)
f954ac3 fix(scan): LLM proxy URL 补全 /v1 前缀 + 租户校验 fail-closed (23:06, +3m)
f404860 fix(scan): 补全 pdf-import/import-tpl 租户校验 + dispatch scan_root 兼容双布局 (次日)
c14fdf7 feat(scan): 重新切割支持 + dispatch stage 修复 (次日)
```

### Card-Editor 事故链（2026-05-09，8 小时）
```
d27b56b revert(card-editor): 恢复 cc5b26b 误删的排版算法和 TQL 预览 (23:28)
8918fbe Revert "revert..." — 撤销上面的 revert (23:47, +19m)
33b8bc0 fix(card-editor): CSS引用修正 + choiceRowGap恢复 (次日 06:10)
c06c51e rewrite(card-editor): 完整恢复 render.js 到 cc5b26b 前的渲染引擎 (07:31)
```

### Auth 重写（2026-05-14）
```
06eb2d0 rewrite(auth): 模拟登录从只读白名单改为继承完整角色权限
   有意设计变更，非劣化。安全模型从"白名单限制"改为"入口限制+审计"。
```

---

## 二、确认的发现（Claude 验证 + 双线索核实）

### F-001 [HIGH] 状态机绕过 — exam completed→reviewing 非法转换

| 维度 | 内容 |
|------|------|
| **文件** | `src/edu_cloud/modules/exam/service.py:96` |
| **现有代码** | 行 96: `exam.status = "reviewing"` 直接赋值，未调用 `validate_transition()` |
| **状态机定义** | `core/state_machine.py:16`: `completed → {published, archived}`，**不包含 reviewing** |
| **正常路径** | 行 74: `validate_transition("exam", exam.status, status)` 正确调用 |
| **引入 commit** | 99763fd (2026-05-11) 引入状态机但未修复此处异常处理路径 |
| **历史变更** | 行 88-101 的 pipeline 回退逻辑早于 C-3 状态机引入，从未被适配 |
| **影响** | pipeline 失败时执行非法状态转换 completed→reviewing，绕过状态机 |
| **风险** | 若后续代码信赖状态机不变量，此处将成为数据一致性破口 |
| **GPT 验证** | 待合并 |

### F-002 [MEDIUM] 状态机绕过 — GradingTask 取消未经验证

| 维度 | 内容 |
|------|------|
| **文件** | `src/edu_cloud/modules/grading/router.py:1033` |
| **现有代码** | `task.status = "cancelled"` 直接赋值 |
| **状态机定义** | `grading_task`: pending→{processing, cancelled}, processing→{completed, failed, cancelled} |
| **分析** | 行 1031 手动 guard 检查 terminal 后，剩余 pending/processing 均允许→cancelled，**当前不违反规则** |
| **治理问题** | 但不调用 validate_transition 意味着未来如果转换规则变化，此处不会感知 |
| **引入 commit** | 此端点早于 99763fd，未在 C-3 中被审计到 |
| **GPT 验证** | 待合并 |

### F-003 [MEDIUM] scorer.py 租户隔离防御纵深缺口

| 维度 | 内容 |
|------|------|
| **文件** | `src/edu_cloud/modules/marking/scorer.py` |
| **缺失行** | 219, 289, 380, 412 (`select(GradingResult).where(answer_id == X)` 无 school_id) |
| **缺失行** | 280-285 (`count(GradingResult)...question_id == X, status == confirmed` 无 school_id) |
| **缺失行** | 451 (`save_score` 的 upsert 查询无 school_id) |
| **上下文** | answer_id 是 UUID 全局唯一，上游查询已经 school_id 过滤，不存在直接跨租户泄露 |
| **安全审计** | 12edc94 对 cross-school queries 加了 school_id，但 scorer.py 被遗漏 |
| **风险等级** | 防御纵深缺口，非直接漏洞。如果 UUID 碰撞或通过其他路径传入非法 answer_id，缺少最后一道防线 |
| **GPT 验证** | 待合并 |

### F-004 [MEDIUM] scan upload-folder 缺少租户校验

| 维度 | 内容 |
|------|------|
| **文件** | `src/edu_cloud/modules/scan/pipeline_router.py:381-421` |
| **现有代码** | upload_scan_folder 端点，exam_id 直接从 Form 取，未验证归属 |
| **对比** | 同文件 browse-dir(349), scan-dir(444), start(505), pdf-import(768), import-tpl(903), scan-image(966) **全部调用** `_check_scan_path_tenant()` |
| **唯独遗漏** | upload-folder 是**唯一不调用**的端点 |
| **路径安全** | school_id 从 JWT 取，文件写到用户自己学校目录——不能写到他校 |
| **exam 归属** | 但 exam_id 未验证是否属于该 school，可能在自校目录下创建与他校 exam 同名的子目录 |
| **引入时间** | f404860 修了 pdf-import，但遗漏了 upload-folder |
| **GPT 验证** | 待合并 |

### F-005 [MEDIUM] scan preview 端点跨租户信息泄露

| 维度 | 内容 |
|------|------|
| **文件** | `src/edu_cloud/modules/scan/pipeline_router.py:811-860` |
| **现有代码** | image_dir/image_path 仅经过 `_validate_path_within_upload_dir()` 沙箱检查 |
| **缺失** | 未调用 `_check_scan_path_tenant()` 验证路径属于当前租户 |
| **攻击场景** | school_A 用户构造 `image_dir="{UPLOAD_DIR}/school_B/scan-input/exam_X"` 可预览他校扫描图 |
| **对比** | 同文件的 scan-image 端点(966) 正确调用了租户校验 |
| **历史追溯** | preview_scan 存在于 00cfc3d（2026-04-16 初始版本）；`_check_scan_path_tenant` 在 3fb326a（2026-05-14）引入时覆盖了 browse-dir/scan-dir/start/scan-image 4 个端点，f954ac3 补了 pdf-import/import-tpl 2 个，但 **preview 和 upload-folder 从未被添加过** |
| **GPT 验证** | ✅ confirmed（GPT 补充：image_path 参数同样有跨租户泄露） |

### ~~F-006~~ [FALSE POSITIVE] barcode.py Image.open 模式转换

| 维度 | 内容 |
|------|------|
| **文件** | `src/edu_cloud/modules/scan/vision/barcode.py:43` |
| **初始判断** | `img = Image.open(image_path)` 后直接 crop，无 `.convert()` |
| **历史追溯** | 原始代码(00cfc3d)流程 `open→crop→convert("L")→decode`；3ced8f5 重写后 convert("L") 移入 `_decode_with_retry` 内部(行 118-119)，**防御代码未丢失** |
| **PIL 验证** | `Image.crop()` 对 P/CMYK/RGB/L 任何模式均正常工作 |
| **GPT 验证** | ✅ **false positive**（GPT 独立确认 _decode_with_retry 内部 convert("L") 覆盖全路径） |
| **结论** | 与 auto_detect_cv.py 用 `.convert("RGB")` 是不同需求（OpenCV 需 RGB，pyzbar 需 L），不可类比 |

---

## 三、排除的项目（调查后确认正常）

### 旧引擎删除残留 ✅
- 主项目代码零悬空引用（50+ grep 搜索确认）
- 仅 `frontend/src/card-editor/_backup_20260408/card_layout.py` 备份文件有旧 import（不影响功能）
- CLI `agent.py` 已正确更新到新引擎路径
- 保留的 10 个旧模块（anonymizer, data_scope, memory_*, prompts, ref_*, schemas）被新引擎依赖，非残留

### 前端消费者一致性 ✅
- 28 个 API 模块与后端 100% 对齐
- 52 条活跃路由全部指向存在的页面组件
- 4 个 Pinia store 无遗留引用
- Card-editor revert 链已收敛，render.js + CSS 完整
- Analytics 重构的页面删除已正确用路由重定向替代

### Auth 模拟登录重写 ✅
- 06eb2d0 是有意设计变更（白名单→完整权限继承）
- `_IMPERSONATION_ALLOWED_PERMISSIONS` 设为 None，deps.py re-export 无人使用
- 安全模型由入口限制（仅 platform_admin）+ 审计日志保障

### LLM Proxy URL ✅
- `edu_runtime.py:43` 单一真源 `LLM_PROXY_BASE = "http://localhost:8100/v1"`
- f954ac3 已修复 /v1 前缀

### 路径布局一致性 ✅
- 写端（upload-folder）和读端（grading_review_router）路径模式匹配
- 读端支持新旧双布局兼容（c14fdf7）

---

## 四、子模式分类

| 子模式 | 发现 | 检测机制 |
|--------|------|----------|
| **治理适配遗漏**：引入新机制（状态机/租户校验）后，未审计全部消费者 | F-001, F-002, F-003, F-004, F-005 | 引入新 guard 时自动 grep 全部 `.status =` / 全部同类端点 |
| ~~防御代码缺失~~ | ~~F-006~~ | F-006 经严格核验后判定为 false positive |

---

## 五、双模型核实状态

| 发现 | Claude 验证 | 现有代码证据 | 历史变更证据 | GPT 验证 | 最终判定 |
|------|------------|-------------|-------------|---------|---------|
| F-001 | ✅ confirmed | state_machine.py:16 无 reviewing | 99763fd 引入但未适配 | ✅ confirmed（GPT 额外确认：转换本身非法，双重问题） | **HIGH — 确认** |
| F-002 | ✅ confirmed | router.py:1033 直接赋值 | 早于 99763fd，未被审计 | ✅ confirmed（GPT 对比 workers/grading.py 同类操作有 validate_transition） | **MEDIUM — 确认** |
| F-003 | ✅ confirmed | scorer.py 6 处无 school_id | 12edc94 遗漏此文件 | ✅ confirmed（GPT 补充：question_id 路径有中等跨租户风险） | **MEDIUM — 确认** |
| F-004 | ✅ confirmed | upload-folder 唯一不调 tenant check | f404860 修了 pdf-import 漏了此 | ✅ confirmed（GPT 确认隐式路径隔离降低风险但治理不一致） | **MEDIUM — 确认** |
| F-005 | ✅ confirmed | preview 仅沙箱无租户检查 | 原始实现即缺失 | ✅ confirmed（GPT 补充：image_path 参数同样有跨租户泄露） | **MEDIUM-HIGH — 确认** |
| F-006 | ~~✅~~ 重审后推翻 | convert("L") 在 _decode_with_retry 内部 | 00cfc3d→3ced8f5 只是重构位置 | ✅ **false positive**（GPT 确认） | **FALSE POSITIVE** |

### GPT 补充发现（Claude 未覆盖）

- **F-003 扩展**：`/next` 端点的 question_id 路径中，上游未强制 `Question.school_id`，如果 question_id 泄露存在中等跨租户读写风险
- **F-005 扩展**：行 837 的 `image_path` 参数也只有 upload 根沙箱检查，与 image_dir 存在同类跨租户泄露

---

## 六、共同根因分析

5 个确认发现（F-006 经严格核验后排除为 false positive）共享一个模式：**引入新机制时只修了发现的点，没有 grep 全部同类**。

- 99763fd 引入状态机 → 修了 exam service 正常路径，没扫异常路径（F-001）和其他模块（F-002）
- 12edc94 加 school_id → 修了 pipeline/service 层，没扫 marking/scorer（F-003）
- 3fb326a/f954ac3 加租户校验 → 修了 6 个端点，遗漏 upload-folder（F-004）和 preview（F-005）

**防线缺口**：现有 hook 系统检测"你跑没跑测试"（VER-001）和"你删没删符号"（constraint guard），但不检测"你引入的新 guard 是否覆盖了全部同类调用点"。

**核验纪律说明**：F-006 最初被 Claude 判为 LOW confirmed，经 git 历史追溯（00cfc3d→3ced8f5）发现 convert("L") 只是重构到内部函数未丢失，GPT 独立确认为 false positive。此过程验证了双线索+双模型核验的必要性——单模型判断确实会出错。

---

## 七、后续调查补充（session 8a4e0bab 接手后发现）

### F-003-ext [HIGH] scorer.py ungraded 模式 3 处租户隔离遗漏

原 session 修了 scorer.py 的 6 处 GradingResult 查询，但遗漏了 ungraded 模式分支（行 264-287）中的 3 处：

| 行号 | 查询 | 缺失 | GPT 判定 |
|------|------|------|---------|
| 264-267 | `confirmed_ids_q` 子查询 | `GradingResult.school_id == school_id` | confirmed (MEDIUM) |
| 269-275 | StudentAnswer 主查询 | `StudentAnswer.school_id == school_id` | confirmed (HIGH) |
| 280-284 | StudentAnswer 总数统计 | `StudentAnswer.school_id == school_id` | confirmed (MEDIUM) |

对比：同文件 ai_review 模式分支（行 161-244）已正确加了 school_id。

### N-002 [HIGH] auto_detect_cv_api 路径租户校验缺失

| 维度 | 内容 |
|------|------|
| **文件** | `src/edu_cloud/modules/scan/cv_detect_router.py:23-28` |
| **问题** | `_resolve_image()` 接受 `/uploads/` 路径和任意绝对路径，无租户校验 |
| **GPT 补充** | `skip_llm=False` 时图片会发给 LLM（auto_detect_cv.py:383-402），不只返回框坐标 |
| **GPT 判定** | confirmed (HIGH) |
| **修复** | 白名单限定 `/uploads/` 和 `/samples/` 前缀 + 路径结构校验 school_id 一致性 |

### 治理一致性问题（已记录，未修复）

| 编号 | 位置 | 问题 | GPT 判定 |
|------|------|------|---------|
| N-001 | `w6_patrol.py:92-96` | GradingTask 超时直接赋值 status | confirmed (LOW) |
| N-003 | `publish_service.py:44,87` + `card/publish_service.py:256` | exam 状态赋值未调 validate_transition | confirmed (LOW) |

---

## 八、修复状态

| 发现 | 修复文件 | 修复方式 | 状态 |
|------|---------|---------|------|
| F-001 | state_machine.py + service.py | completed→reviewing 合法化 + validate_transition 调用 | ✅ |
| F-002 | grading/router.py | cancel 前加 validate_transition | ✅ |
| F-003 | scorer.py (6 处 GradingResult) | 加 school_id 过滤 | ✅ |
| F-003-ext | scorer.py (3 处 ungraded 模式) | 加 school_id 过滤 | ✅ |
| F-004 | pipeline_router.py upload-folder | 加 db + _check_scan_path_tenant | ✅ |
| F-005 | pipeline_router.py preview | 加 _check_scan_path_tenant (image_dir + image_path) | ✅ |
| N-002 | cv_detect_router.py auto-detect-cv | 路径白名单 + school_id 路径校验 | ✅ |
| N-001 | w6_patrol.py | 治理一致性，转换合法 | 🔜 后续 |
| N-003 | publish_service.py × 2 + card/publish_service.py | 治理一致性，转换合法 | 🔜 后续 |
