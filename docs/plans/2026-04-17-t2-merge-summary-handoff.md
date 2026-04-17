<!-- legacy-format -->
# T2 · 汇总窗口（4 并行窗口完成后启动） · 交接卡

> 类型：T2 汇总收口窗口（4 并行窗口完成后唯一接管者）
> 前置条件：W1/W2/W3/W4 全部完成 + 各自 checkpoint 输出已收齐
> 起点 git HEAD：master = `6f3dc81`（commit 拆分后），4 个 feat/ 分支待 merge
> 工作分支：**`master`**（汇总到主分支）

## 1. 触发条件
- W1 输出"【W1 card 子目录化 · 待汇总】"
- W2 输出"【W2 kg Batch 3b · 待汇总】"
- W3 输出"【W3 haofenshu Batch 3 · 待汇总】"
- W4 输出"【W4 conduct Batch 1 · 待汇总】"
- 用户确认全部 checkpoint OK

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

### 2.3 Merge 顺序（依赖隔离，可任意顺序但建议）
1. **W4 conduct**（最小 footprint，先合最稳）
   ```bash
   git checkout master
   git merge --no-ff feat/conduct-roadmap-batch1 -m "merge: W4 conduct-roadmap Batch 1"
   ```
2. **W3 haofenshu**（独立目录 frontend-nuxt/，零冲突）
   ```bash
   git merge --no-ff feat/haofenshu-batch3 -m "merge: W3 haofenshu Phase 1 Batch 3"
   ```
3. **W2 kg**（前端 knowledge-tree，与 W4 frontend/conduct 不冲突但相邻目录，verify 后合）
   ```bash
   git merge --no-ff feat/kg-batch3b -m "merge: W2 kg Phase 1 Batch 3b"
   ```
4. **W1 card**（最大改动 135 import，最后合最容易定位回归）
   ```bash
   git merge --no-ff feat/card-subdir -m "merge: W1 Phase 4 card 子目录化"
   ```

每步 merge 后立即跑相关子集测试 verify。

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
