# edu-cloud 深度调查报告

> **调查时间**：2026-06-04  
> **接手会话**：sid:70dd75c7（T3，2026-06-02，lifecycle-binding + 安全审计）  
> **报告性质**：接手深度梳理——验证前任会话产出真实性，评估项目当前健康度，定位系统性断口  
> **调查方法**：handoff 交叉验证 + git history 实证 + 全量测试 + 治理文件一致性扫描

---

## 一、项目规模快照

| 维度 | 数值 |
|------|------|
| 后端 Python 文件 | 385 |
| 前端 Vue/JS/TS 文件 | 312 |
| 业务模块数（文件系统） | 22 |
| 治理登记模块数 | 21 |
| API 入口文件行数（app.py） | 374 |
| 测试用例数 | 2405（收集） / 2376 passed |
| 五月以来 commit 数 | 499 |
| 活跃开发天数（近月） | 10 天 |

---

## 二、前任会话（70dd75c7）产出验证

### 2.1 声称 vs 实证

| 声称 | 验证结论 |
|------|----------|
| 安全 Phase 1 共 17 commits on master | **真实** — `git log --since=2026-06-02` 确认 17 commits，全部在 master 且 pushed |
| Codex 5 轮 + GPT 3 轮审查通过 | **真实** — commit message 显式标注 R1-R5 + GPT R1-R3 |
| `codex/role-permission-phase2` 分支工作已合入 | **真实** — master (62789be) 包含该分支全部 commits，远程分支 ref 过期 (e7e5ddf) |
| Phase 0 部分完成（Fix-B/C/E） | **真实** — commit d15cace 含 .env.example + DEPRECATED 标记 + pytest-cov |
| exam_import MODULE.md 缺失 | **真实** — `ls` 确认不存在 |
| full-repair-plan.md 为权威文档 | **真实** — 内容完整（17 条，4 Phase），依赖调查结论有据可查 |

### 2.2 修正/偏差项

| # | 项 | 偏差 |
|---|-----|------|
| 1 | handoff 说"Fix-B/C/E 已完成" | Fix-C（死模型删除）实际只做了标 DEPRECATED，**未真删文件** |
| 2 | known-pytest-failures.txt | 最后更新 2026-05-06，未刷新为当前 4 个失败 |
| 3 | modules.yaml 登记 21 个 | 文件系统 22 个模块，**exam_import 漏网** |
| 4 | debt-report.md 说"无债务" | **失真** — aggregate 脚本未重跑，exam_import 未被检测到 |

**判定**：前任会话安全修复工作扎实可信。遗留问题集中在 Phase 0 收尾和治理一致性，不影响已交付的安全功能。

---

## 三、测试基线评估

```
2376 passed, 4 failed, 23 skipped, 2 xfailed — 22 min 17s
```

### 4 个失败归类

| # | 测试 | 根因 | 归属 |
|---|------|------|------|
| 1 | `test_large_modification_without_module_md_asks` | hook 逻辑盲区：已存在模块缺 MODULE.md 时不触发 | governance plan P1-T1 |
| 2 | `test_hook_entry_asks_on_large_legacy_touch` | 同上 | governance plan P1-T1 |
| 3 | `test_no_new_raw_school_id_in_routers` | exam_import/router.py 使用裸 `role.school_id` | governance plan P0-T3 |
| 4 | `test_extract_skeleton_preserves_data_side` | Playwright 未安装（环境依赖缺失） | 环境问题，非代码 bug |

**判定**：前 3 个失败全在 module governance repair plan 范围内。第 4 个是 E2E 环境问题（Playwright chromium 未下载），不影响后端逻辑正确性。

---

## 四、系统性断口地图

### 断口 A：治理检测→执行链断裂

```
检测能力（module_governance_guard 存在）
    ↓
  [盲区] 模块目录已在 HEAD 但缺 MODULE.md → hook 静默放行
    ↓
结果：exam_import 1428 行代码绕过全部治理流程安全着陆
```

**影响面**：未来任何渐进式构建的新模块都可复现此路径。  
**修复成本**：P1-T1，修 hook + 补回归测试，2-4 小时。

### 断口 B：治理文档→事实源漂移

```
aggregate_modules.py（手动触发）
    ↓
  [无触发器] 没有 hook/CI 强制刷新
    ↓
结果：modules.yaml 说 21 个、debt-report 说无债，实际 22 个 + 1 个缺 MODULE.md
```

**影响面**：治理文档失信，人工决策基于错误数据。  
**修复成本**：P2-T2，aggregate --check 进 CI，1 小时。

### 断口 C：安全修复 Phase 1 剩余风险窗口

| 风险 | 当前状态 | 窗口 |
|------|----------|------|
| /uploads 无鉴权 | 题目图片/文档页/扫描件通过 StaticFiles 直接暴露 | 全时段开放 |
| CSP 缺失 | 无 Content-Security-Policy header | XSS 可利用 |
| Token fail-open | Redis 故障时 JWT 撤销失效，24h 有效期内不可强制登出 | Redis 故障期间 |

**影响面**：/uploads 风险最高（静态文件暴露试卷内容），CSP 次之，Token 有条件触发。  
**修复成本**：Fix-G 约 4 小时（两步），Fix-H 约 1 小时，Fix-I 需产品决策。

### 断口 D：数据完整性定时炸弹（远期）

| 炸弹 | 触发条件 | 爆炸范围 |
|------|----------|----------|
| FK 全部 NO ACTION | 任何直接开 PRAGMA foreign_keys=ON 的操作 | 64+ 删除路径 500 |
| 租户隔离 bypass=0 | 任何切 enforce 的操作 | seed/worker/pipeline 全部断 |

**影响面**：当前不影响功能（FK 关闭 + 隔离未 enforce），但任何"修复"操作如果不走三阶段流程会引发生产事故。  
**铁律**：这两项是**陷阱型风险**——不修不炸，乱修才炸。

---

## 五、优先级评估矩阵

```
                    紧急
                     ↑
        Fix-G(/uploads)
                     |
                     |        governance P0
    Fix-H(CSP)      |       (基线修正)
                     |
        ─────────────┼──────────────────→ 重要
                     |
    Fix-I(Token)     |    governance P1-P2
                     |    (闭环强制)
                     |
   Phase 0 尾巴      |    Phase 2(FK/tenant)
   (Fix-A/D/F)      |
                     ↓
                   不紧急
```

---

## 六、推荐执行路径

### 短期（本周）

1. **governance P0**：补 exam_import MODULE.md + 刷新 modules.yaml（消除治理失真，30 min）
2. **Phase 0 收尾**：Fix-A(迁移) + Fix-D(刷新 known-failures)（扫清低风险尾巴，1h）
3. **Fix-G step 1**：为 /uploads/questions/* 建 proxy 端点（堵住最大暴露面，2h）

### 中期（1-2 周）

4. **governance P1**：修 hook 盲区 + 回归测试 + 固化依赖（关闭断口 A）
5. **Fix-G step 2**：前端切 proxy 完毕后删 StaticFiles mount
6. **Fix-H**：CSP header
7. **governance P2**：CI governance job 补全（关闭断口 B）

### 远期（需设计审查）

8. Fix-I（Token 策略，需产品决策）
9. Fix-J（FK 三阶段，T3 流程）
10. Fix-K（租户 enforce，T3 流程）

---

## 七、结论

edu-cloud 经过 70dd75c7 会话的安全加固后，**核心认证/鉴权路径已收紧**（时序攻击、scope 校验、匿名化兜底）。当前最大风险是 /uploads 静态文件暴露和治理体系一致性漂移。

项目处于"安全债大幅清偿、结构债稳定、治理债小幅新增"的状态。推荐优先关闭 /uploads 暴露窗口和治理断口，远期 FK/tenant 需独立设计审查。
