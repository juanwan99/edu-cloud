<!-- legacy-format -->
# T2 · 汇总窗口（4 并行窗口完成后启动） · 交接卡

> 类型：T2 汇总收口窗口（4 并行窗口完成后唯一接管者）
> 前置条件：W1/W2/W3/W4 全部完成 + 各自 checkpoint 输出已收齐
> 起点 git HEAD：master = `6f3dc81`（commit 拆分后），4 个 feat/ 分支待 merge
> 工作分支：**`master`**（汇总到主分支）

## 1. 触发条件

### 1.1 完整 T2 模式（4 W 全完成）
- W1 / W2 / W3 / W4 全部输出"待汇总"
- 用户确认全部 checkpoint OK

### 1.2 Partial T2 模式（W1+W3 完成，W2/W4 未完）⭐ 当前 2026-04-18 模式
**实查事实**：
- W1 ✅ 完成 @ `6c1ee0e`，pytest 300 PASS
- W3 ✅ 完成 @ `1439904`，vitest 29 PASS
- W2 ⏳ Code Review R1 FAIL @ `931e1c7`，等 W2-R2 修复（详 `2026-04-18-w2-r2-repair-handoff.md`）
- W4 ⏳ Plan Review R7 PASS @ `637ce2f`，T1-T5 待新 session 实施（详 `2026-04-18-w4-exec-T1-T5-handoff.md`）

**Partial T2 范围**：仅 merge `feat/card-subdir`（W1）+ `feat/haofenshu-batch3`（W3）
**T2-补遗-1**：W2 R2 PASS 后单独 merge `feat/kg-batch3b`
**T2-补遗-2**：W4 实施完 + code_review_batch1 PASS 后单独 merge `feat/conduct-roadmap-batch1`
**工作 worktree**：`/home/ops/projects/edu-cloud-t2`（已检出 master @ 29dfb8a）

**前置 verify**（必须先跑）：
```bash
cd /home/ops/projects/edu-cloud-t2
git status                          # 必空
git rev-parse --abbrev-ref HEAD     # 必 master
# 确认零冲突（已实查 2026-04-18：W1+W3 文件物理隔离 100%）
git diff master..feat/card-subdir --name-only > /tmp/w1_files.txt
git diff master..feat/haofenshu-batch3 --name-only > /tmp/w3_files.txt
sort /tmp/w1_files.txt /tmp/w3_files.txt | uniq -d  # 应空（无重叠）
```

## 2. 工作内容

### 2.1 状态收集
```bash
cd /home/ops/projects/edu-cloud
git fetch --all 2>&1
git branch -a | grep feat/
# 应见：feat/card-subdir / feat/kg-batch3b / feat/haofenshu-batch3 / feat/conduct-roadmap-batch1
git log feat/card-subdir --oneline | head -5
git log feat/kg-batch3b --oneline | head -5
git log feat/haofenshu-batch3 --oneline | head -5
git log feat/conduct-roadmap-batch1 --oneline | head -5
```

### 2.2 冲突预测（理论上零冲突，但 verify）
```bash
# 检测 4 分支间是否有任何文件交叉
for b in feat/card-subdir feat/kg-batch3b feat/haofenshu-batch3 feat/conduct-roadmap-batch1; do
  echo "=== $b ===";
  git diff master..$b --name-only
done > /tmp/branch_files.txt

# 找重叠
sort /tmp/branch_files.txt | uniq -c | sort -rn | head
# 期望：无文件出现 >1 次（除空行）
```

如有冲突 → STOP 报告，不擅自合并。

### 2.3 Merge 顺序

#### 2.3.A 完整 T2 模式（4 W 版）
1. **W4 conduct**（最小 footprint，先合最稳）
   ```bash
   git checkout master
   git merge --no-ff feat/conduct-roadmap-batch1 -m "merge: W4 conduct-roadmap Batch 1"
   ```
2. **W3 haofenshu**（独立目录 frontend-nuxt/，零冲突）
   ```bash
   git merge --no-ff feat/haofenshu-batch3 -m "merge: W3 haofenshu Phase 1 Batch 3"
   ```
3. **W2 kg**（前端 knowledge-tree，verify 后合）
   ```bash
   git merge --no-ff feat/kg-batch3b -m "merge: W2 kg Phase 1 Batch 3b"
   ```
4. **W1 card**（最大改动 135 import，最后合）
   ```bash
   git merge --no-ff feat/card-subdir -m "merge: W1 Phase 4 card 子目录化"
   ```

每步 merge 后立即跑相关子集测试 verify。

#### 2.3.B Partial T2 模式（2 W 版 · 当前 2026-04-18）⭐
**前提**：在 `/home/ops/projects/edu-cloud-t2` worktree（master @ 29dfb8a），已通过 §1.2 前置 verify。

按风险递增顺序：

1. **W3 haofenshu**（独立目录 frontend-nuxt/）
   ```bash
   cd /home/ops/projects/edu-cloud-t2
   git merge --no-ff feat/haofenshu-batch3 -m "merge: W3 haofenshu Phase 1 Batch 3 (Task 10-12) [partial T2 1/2]"
   cd frontend-nuxt && npx vitest run 2>&1 | tail -5  # 应 29 PASS
   cd /home/ops/projects/edu-cloud-t2
   ```

2. **W1 card**（38 文件 + 135 import，最大改动放最后）
   ```bash
   git merge --no-ff feat/card-subdir -m "merge: W1 Phase 4 card 子目录化 [partial T2 2/2]"
   /home/ops/projects/edu-cloud/.venv/bin/python -m pytest tests/test_api_exam/ tests/test_exam_misc/ tests/test_services_exam/ tests/test_api/test_compat.py --tb=line -q 2>&1 | tail -3  # 应 300+ PASS
   ```

**禁 merge feat/kg-batch3b（W2 R1 FAIL，等 R2）**
**禁 merge feat/conduct-roadmap-batch1（W4 T1-T5 实施未完）**

**Partial T2 后 master 状态**：含 W1 (card 子目录) + W3 (nuxt Batch 3)，不含 W2/W4。后续两次 T2-补遗 单独处理。

### 2.4 全量 pytest（汇总后必跑）
```bash
.venv/bin/python -m pytest --tb=short -q 2>&1 | tail -5
# 预期：≥1935 + W4 新增 ≥10 = ~1945 passed / 0 failed / 23 skipped
# 实际数字由 W1+W4 的新增测试决定，T2 接卡时按 W 报告的"新增 N 测试"求和验证
```

### 2.5 前端全量 vitest（如有改动）
```bash
cd /home/ops/projects/edu-cloud/frontend && npx vitest run 2>&1 | tail -5
cd /home/ops/projects/edu-cloud/frontend-nuxt && npx vitest run 2>&1 | tail -5
```

### 2.6 CLAUDE.md 最终同步检查
- 模块结构是否与最新 src/ 一致（W1 card 子目录化必须在 CLAUDE.md 反映）
- API 端点是否完整（W4 conduct 如有新端点）
- conduct 测试数字是否更新（W4）
- 前端 nuxt 模块是否更新（W3）

如发现遗漏 → 单独 commit `docs: T2 汇总后 CLAUDE.md 同步`。

## 3. 验收契约
- 4 branch 全部 merge 到 master 无冲突
- 全量 pytest PASS（最终基线）
- 全量 vitest PASS
- CLAUDE.md 与代码状态一致
- master 比 6f3dc81 多 ≥4 merge commit + 各 branch 内部 commit

## 4. 输出格式（最终汇总）

```
【T2 汇总 · 完成】
- 起点：master 6f3dc81
- 4 branch merge：
  - W4 conduct: <merge sha>，新增 N 测试
  - W3 haofenshu: <merge sha>，新增 vitest N
  - W2 kg: <merge sha>，新增 vitest N
  - W1 card: <merge sha>，移动 16 文件 + 32 import 更新
- 全量 pytest：N passed / 0 failed / 23 skipped
- 全量 vitest (frontend)：N passed / 0 failed
- 全量 vitest (frontend-nuxt)：N passed / 0 failed
- CLAUDE.md 同步：是/否（同步内容）
- 最终 master HEAD：<sha>
- 等用户裁决：是否 push origin / 是否打 tag / 是否进入下一轮规划
```

## 5. 与其他窗口同步
- **本窗口是 master 唯一写入者**（4 W 不直接写 master）
- merge 完成后 4 branch 可保留（用户决定是否删）

## 6. 第一步指令

```bash
cd /home/ops/projects/edu-cloud
cat docs/plans/2026-04-17-t2-merge-summary-handoff.md  # 必读本卡
git status  # master 应清洁
git branch -a | grep feat/  # 应见 4 个分支
# 收集 4 W checkpoint 输出（用户提供或读各 W handoff 末尾的"待汇总"段）
# 报告："已收集 4 W 状态，开始 §2.2 冲突预测"
```

等用户确认进入 §2.3 merge 流程。

## 7. 兜底
- 任何分支 merge 出冲突 → STOP 报告，不擅自 resolve
- 全量 pytest 出现新 failed → 二分定位是哪个 W 引入，回退该 branch
- 全量 vitest fail → 同上
- CLAUDE.md 与代码大幅不一致 → 提议另起单独 doc-sync session 处理，不在 T2 范围内强行同步

## 8. 风险清单
- W1 card 改 32 文件 import，AST 重写若有疏漏 → pytest 子集应捕获，T2 时已知
- W4 conduct R-T1 权限回收 behavior_change → 用户应已批准，T2 不再 second-guess
- W3 haofenshu 后端零改动假设若被破坏 → STOP 找出谁改了后端
- 4 branch 落地时间不齐 → 先合先稳，后到的 W 自行 rebase

---

**T2 是规划闭环的最后一步。完成后，本轮 5-window 并行规划全部结束，等用户决策下一轮。**
