<!-- legacy-format -->
# exam-ai 兼容路由（compat_router）退役计划

> 生效日期：2026-04-17
> 决策来源：2026-04-17 技术债清理 · Q4 = B 设 deprecation 日期（`docs/plans/2026-04-17-tech-debt-cleanup-handoff.md` §5.2）
> 首动作执行：`Phase 5 · DeprecationWarning 注入`（执行窗口同卡 §5，依赖本文档 §4 时间表定义）
> 关联下游：`paper-seg`（唯一 compat 客户端，已 verify 内部项目）

本文档制定 `src/edu_cloud/api/compat_router.py`（343 行，8 端点）的退役路径 —— 端点映射、客户端改造步骤、Deprecation 注入方案、目标日期与风险监控。

## 1. 现状

- **文件**：`src/edu_cloud/api/compat_router.py`（343 行，2026-04-17 verify）
- **挂载点**：`src/edu_cloud/api/app.py:270-271`
  ```python
  from edu_cloud.api.compat_router import router as compat_router
  app.include_router(compat_router)
  ```
- **路由前缀**：`APIRouter(prefix="/api", tags=["compat"])`
- **用途**：`paper-seg` 扫描端零改动对接 edu-cloud —— 原 exam-ai 协议字段 / 路径 / 认证全部保留
- **下游客户端**：
  - `paper-seg`（内部项目，本仓之外，`C:/Users/Administrator/paper-seg`）—— 唯一 compat 客户端
  - 外部第三方：无（2026-04-17 已 verify，见 `CLAUDE.md` "关联项目"）

## 2. 端点清单与替代路径映射

基于 2026-04-17 直接读取 `src/edu_cloud/modules/*/router.py` + `src/edu_cloud/api/auth.py` 的 verify 结果：

| # | compat 路径 | 方法 | 替代 `/api/v1` 路径 | 路由定义位置 | verify |
|---|-------------|------|----------------------|--------------|:------:|
| 1 | `/api/auth/login` | POST | `/api/v1/auth/login` | `api/auth.py:43`（前缀 `/api/v1/auth`） | ✅ |
| 2 | `/api/exams` | GET | `/api/v1/exams` | `modules/exam/router.py:94`（前缀 `/api/v1/exams`） | ✅ |
| 3 | `/api/exams/{exam_id}/subjects` | GET | `/api/v1/exams/{exam_id}/subjects` | `modules/exam/router.py:140` | ✅ |
| 4 | `/api/templates/{subject_id}/{side}` | GET | `/api/v1/templates/{subject_id}/{side}` | `modules/card/template_router.py:82`（前缀 `/api/v1/templates`） | ✅ |
| 5 | `/api/scan/tasks` | POST | `/api/v1/scan/tasks` | `modules/scan/router.py:214`（前缀 `/api/v1/scan`） | ✅ |
| 6 | `/api/scan/tasks/{task_id}` | PATCH | `/api/v1/scan/tasks/{task_id}` | `modules/scan/router.py:240` | ✅ |
| 7 | `/api/scan/upload` | POST | `/api/v1/scan/upload` | `modules/scan/router.py:42` | ✅ |
| 8 | `/api/scan/upload-objective` | POST | `/api/v1/scan/upload-objective` | `modules/scan/router.py:301` | ✅ |

**verify 总结**：8 / 8 替代路径存在，**无需先补 `/api/v1`**，可以直接进 DeprecationWarning 注入阶段。

### 2.1 关键字段/协议差异（客户端迁移必读）

| # | 差异类型 | compat 行为 | `/api/v1` 行为 | 客户端改造要点 |
|---|---------|------------|----------------|---------------|
| 1 | 请求字段 | `CompatLoginRequest` 接受 `school_code`（忽略） | `LoginRequest` 无 `school_code` 字段 | paper-seg 去掉请求 body 的 `school_code` |
| 1 | 响应结构 | `{access_token}` 扁平 | `{access_token, roles[], active_role, user}` | paper-seg 解析仍可只取 `access_token`，其他字段忽略即可（向后兼容） |
| 4 | 响应结构 | `image_size: {width, height}`（嵌套 dict） | `image_width` + `image_height`（平铺字段） | paper-seg 需改 template 解析：`tpl.image_size.width` → `tpl.image_width` |
| 4 | 路径前缀 | `/api/templates/...` | `/api/v1/templates/...`（**不是** `/api/v1/card/templates/...`） | 规划交接卡 §4.2 原写 `/api/v1/card/templates/` 是误记，据实修正 |
| 2/3/5/6/7/8 | 路径 | `/api/...` | `/api/v1/...` | 客户端统一加 `/v1` 前缀即可 |

## 3. paper-seg 客户端改造步骤

paper-seg 改造本身在 paper-seg 仓内执行，不在 edu-cloud 仓范围；本节给出**改造指令与 grep 命令模板**，供 paper-seg owner 对照。

### 3.1 改造准备（在 paper-seg 仓内执行）

```bash
# 步骤 1：盘点 paper-seg 内调用 compat 端点的全部位置
cd C:/Users/Administrator/paper-seg
grep -rn "\"/api/auth/login\"\|\"/api/exams\"\|\"/api/templates/\"\|\"/api/scan/" src/ 2>/dev/null
grep -rn "api\.base\|API_BASE\|EDUCLOUD_BASE" src/ 2>/dev/null  # baseURL 常量集中点
```

### 3.2 逐端点改造清单

| # | 改动类型 | 动作 |
|---|---------|------|
| 1 | 登录 | baseURL 路径 `/api → /api/v1`；请求 body 去掉 `school_code` |
| 2 | 考试列表 | 路径加 `/v1` |
| 3 | 科目列表 | 路径加 `/v1` |
| 4 | 模板拉取 | 路径 `/api/templates/` → `/api/v1/templates/`；解析 `image_size.width/height` → `image_width/image_height` |
| 5 | 创建扫描任务 | 路径加 `/v1` |
| 6 | 更新扫描进度 | 路径加 `/v1` |
| 7 | 上传切图（Multipart） | 路径加 `/v1`；Form 字段不变 |
| 8 | 上传选择题（JSON） | 路径加 `/v1`；schema 不变 |

### 3.3 改造联调验证

paper-seg 改造后需**全链路真实扫描图走查**一次（与 2026-04-16 B 端主链路交接 Phase 0-A→2-C 同级别验收），覆盖：
- 登录 → 考试列表 → 科目列表 → 模板拉取 → 创建扫描任务 → 上传切图 + 上传选择题 → 更新任务进度 → 查任务
- 至少一轮"缺考"流程（`is_absent=True` 分支）
- 至少一轮字段异常（如模板 `image_size` 解析 fallback，防止旧代码残留）

## 4. DeprecationWarning 注入方案（Phase 5 首动作执行）

### 4.1 三层信号（每次 compat 调用同时发出）

1. **Python 运行时**：每个 compat handler 入口 `warnings.warn(f"{endpoint} is deprecated; use {replacement}", DeprecationWarning, stacklevel=2)`
2. **HTTP Response header**：
   - `Deprecation: true`（RFC 8594）
   - `Sunset: <YYYY-MM-DD>`（RFC 8594，指向 §5 退役日期）
   - `Link: </api/v1/...>; rel="successor-version"`
3. **结构化日志**（与 `logging_config.py` JSONL 对齐）：
   ```json
   {"ts": "...", "level": "WARNING", "module": "compat_router",
    "msg": "deprecated_compat_call",
    "data": {"endpoint": "/api/auth/login", "replacement": "/api/v1/auth/login",
             "school_id": "...", "client_ua": "..."}}
   ```

### 4.2 生效时间表

| 里程碑 | 距退役日期 | 动作 | 阻断性 |
|--------|-----------|------|--------|
| T+0（Phase 5 首动作） | -90 天 | 8 handler 全部注入三层信号 + 3 个新测试验证 | 软提醒 |
| T+30 | -60 天 | 按 school_id 分组的调用次数周报推送给 paper-seg owner + edu-cloud owner | 软提醒 |
| T+60 | -30 天 | 开发/测试环境默认拒绝（除非请求带 `X-Allow-Deprecated: true`），生产仍放行 | 环境性硬拦截 |
| T+90 = 退役日 | 0 | 删除 `compat_router.py` + `app.py:270-271` 挂载 + 回归 pytest | 完全下线 |

### 4.3 不做的事（首动作边界）

- ❌ 不删除任何 compat 业务代码（L015 不可自治任务 / Q4 = B 设 deprecation 日期，不是立即删）
- ❌ 不在 T+0 对生产环境加 `X-Allow-Deprecated` 硬拦截
- ❌ 不改 paper-seg 仓（跨仓改造属 paper-seg owner 职责）

## 5. 目标退役日期

- **建议日期**：**2026-07-31**（2026-Q3 末，T+0 = 2026-05-02，距规划日 ~2 周缓冲，给 paper-seg owner 3 个月迁移窗口）
- **决策依据**：
  - paper-seg 是内部项目，迁移节奏可控
  - 外部第三方 client 已 verify 为零（`CLAUDE.md` "关联项目" 仅列 exam-ai / paper-seg / paper-skill）
  - 3 个月覆盖一个典型学期的扫描繁忙期（避开 6 月期末考试 + 7 月录取场景）
- **最终确认权**：用户（同时需与 paper-seg owner 对齐迁移计划）

## 6. 风险与监控

### 6.1 风险清单

| 风险 | 场景 | 缓解 |
|------|------|------|
| R1 | paper-seg 未按期改造就到 T+90 | T+60 前启用 weekly 调用量周报；T+90 未清零则顺延退役 30 天并升级风险等级 |
| R2 | paper-seg 改造后字段解析遗漏（`image_size` → `image_width/height` 回归） | §3.3 联调验证必须含"字段异常路径"；上线后开首周每日巡检日志关键字 `"image_size"` |
| R3 | 环境性硬拦截（T+60）误伤 staging 回归测试 | staging 默认注入 `X-Allow-Deprecated: true`，CI 流水线保留开关 |
| R4 | compat_login 返回字段少，paper-seg 改到 `/api/v1/auth/login` 后解析新字段报错 | §2.1 已明示"向后兼容只取 `access_token`"；改造后加 parse fallback |
| R5 | `/api/v1/templates/` vs `/api/v1/card/templates/` 前缀认知错误 | §2.1 已明示，本文档作为单一真源；paper-seg 改造 review 须对照本表 |

### 6.2 监控指标（logger + metrics，可执行）

- **日志关键字计数**：每日 grep `logs/app.jsonl` 的 `"msg":"deprecated_compat_call"`，按 `data.endpoint` 分组 + 按 `data.school_id` 分组
- **周报字段**（T+30 起）：
  - 7 日内每端点调用次数
  - 7 日内每学校调用次数
  - 与上周环比（下降 / 持平 / 上升）
  - `X-Allow-Deprecated` 请求头出现次数（异常信号，staging 以外不应有）
- **报警阈值**（T+60 起）：
  - 生产环境单日 compat 调用 > 1000 次 → 邮件告警给 paper-seg owner + edu-cloud owner
  - 任一学校当日调用 > 500 次且环比上升 → 点名告警
- **dashboard**：运行期可加 `docs/arch/observability.md`（未来补）统一观测入口；当前仅以 JSONL 日志为数据源

## 7. 执行顺序与依赖

| 阶段 | 前置条件 | 动作 | 本文档对应节 |
|------|---------|------|-------------|
| 规划 | § 2 映射表 8/8 verify | 本文档落盘 | § 1-6 |
| 首动作（Phase 5） | 用户确认 §5 退役日期 | 8 handler 注入三层信号 + 3 新测试 | § 4.1 / 4.2 T+0 |
| T+30 | 首动作上线 ≥ 30 天 | 启动周报推送 | § 4.2 / 6.2 |
| T+60 | 周报数据稳定下降 | 环境性硬拦截开关上线 | § 4.2 / 6.1 R3 |
| T+90 | paper-seg 调用归零 ≥ 7 天 | 删除 compat_router.py + 挂载 + 回归 pytest | § 4.2 / 6.1 R1 |

---

**变更记录**：

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-04-17 | 初版（Task 4，Phase 2 技术债清理 · 执行窗口） | 技术债清理执行窗口 |
