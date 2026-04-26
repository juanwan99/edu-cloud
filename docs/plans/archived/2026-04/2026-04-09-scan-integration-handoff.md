---
type: handoff
created: 2026-04-09 15:58:22
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-integration-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-integration-plan.md
---

# paper-seg 整合到 edu-cloud — 交接卡

## 约束与偏好

**Tier: T3 流程**（跨模块迁移 + 新增 API + 新前端界面）

- vision 模块从 `C:\Users\Administrator\paper-seg\app\vision\` 复制，只改 import 路径，不改逻辑
- `segment.py` 内部有 `from app.vision.anchors import ...` 等绝对导入，必须改为相对导入 `from .anchors import ...`
- 流水线不走 HTTP 上传，直接调 StorageService + 写 StudentAnswer 表
- 前端在 ExamDetailPage.vue 的"扫描状态"tab（第 4 个 tab，当前是空内容），不新建页面
- 扫描图来源是本地磁盘路径（用户输入），不做浏览器上传
- 模板来源优先 Template 表（答题卡发布写入），其次 .tpl 文件导入
- 依赖：opencv-python-headless + pyzbar，pyzbar 需要 zbar 系统库（Windows 自带 DLL，Linux 需 apt-get install libzbar0）
- 真实测试数据：扫描图在 `D:\试卷数据\试卷图像\191871\A3722\地理\`，tpl 模板在 `D:\试卷数据\YueXiaoEr\Scanner\Templetes\[141984011]地理.tpl`
- 当前项目 1590+ tests，前端 73 tests

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-09 15:58:22
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-integration-handoff.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-09-scan-integration-plan.md Task 1-6 执行。使用 executing-plans skill。完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
