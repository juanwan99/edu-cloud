# ECS / Linux pytest 装配指南

> 适用：在 ECS（Ubuntu 22.04）上让 `python -m pytest` 能跑 edu-cloud 全量 2246 测试。
> 首次装配实证 2026-04-18（T-H 任务）。

## §1. 前置依赖

| 项 | 要求 | 本环境实测 |
|---|---|---|
| Shell | bash | ✅ |
| uv | ≥ 0.5（本脚本用 venv + sync 子命令） | `uv 0.11.6` |
| 磁盘 | ≥ 500MB（venv + wheels） | 充裕 |
| 网络 | 能访问 PyPI（走 DMIT 代理 7890 亦可） | ✅ 默认出口 |
| 系统 python | **不要求** `>=3.11`，uv 会自行装 3.11 | 系统 3.10.12 |

**不需要**：apt install 任何系统包；`sudo`；Chromium 浏览器（除非跑真正的 browser 测试）。

## §2. 一键装配

```bash
cd /home/ops/projects/edu-cloud-t2
bash scripts/setup_ecs_dev.sh
# 激活
source .venv/bin/activate
# 验证
python -m pytest --version          # 期望 pytest 9.0.3+
python -m pytest tests/test_conduct/ -q   # 期望 68 passed
```

`setup_ecs_dev.sh` 做了 6 件事：侦查 uv → 装 Py 3.11 → 建 venv → `uv sync --extra dev` → 核心 import smoke → `pytest --collect-only`。

## §3. 已知坑位

### 3.1 系统 python 版本 < 3.11
**现象**：`python3 -m pytest` 报 `No module named pytest`，或 pyproject `requires-python` 不满足。
**原因**：ECS Ubuntu 22.04 自带 3.10.12；项目要求 ≥ 3.11。
**处理**：用 uv 自管 Python（`uv python install 3.11`），不要 `sudo apt install python3.11`（污染系统环境）。

### 3.2 pyzbar / lxml / opencv-python-headless 系统库依赖
**现象**：import 时可能报 `libzbar.so.0 not found` 或 `libxml2` 缺失。
**本环境实测**：**全部 pure-wheel 自带**，无需 apt。
**降级方案**（若 `setup_ecs_dev.sh` Step 6 报错）：按脚本末尾注释段装 apt 包（**需用户审批 sudo**）。

### 3.3 playwright Chromium 浏览器 > 500MB
**现象**：`uv sync --extra dev` 会装 playwright Python 包（~30MB），**不会**自动下载浏览器。
**处理**：仅需跑 browser 测试时才 `python -m playwright install chromium --with-deps`（按需触发）。

### 3.4 SECRET_KEY 默认值 UserWarning
**现象**：每次 pytest 输出 `SECRET_KEY is using default value 'change-me'`。
**处理**：开发环境无害警告，忽略；生产环境须在 `.env` 设 SECRET_KEY。

## §4. 与 Windows 开发环境的差异

| 维度 | Windows / WSL（主力） | ECS Linux（本指南） |
|---|---|---|
| Python 来源 | Anaconda / py launcher / Windows Store | uv 托管 cpython-3.11.15 |
| 激活脚本 | `.venv\Scripts\activate.bat` / `activate.ps1` | `.venv/bin/activate` |
| 事件循环 | SelectorEventLoop（Windows 默认） | uvloop（Linux 默认，已装） |
| 路径分隔 | 混合 `C:/Users/...` 和 `/c/...` | 纯 POSIX `/home/ops/...` |
| 行结束 | 留意 `git config core.autocrlf` | LF 默认 |
| CLAUDE.md 启动命令 | `python -m uvicorn ...` 在 WSL 内 | 同命令，工作目录 `/home/ops/projects/edu-cloud-t2` |

## §5. 排查指南

| 症状 | 排查步骤 |
|---|---|
| `uv: command not found` | `curl -LsSf https://astral.sh/uv/install.sh \| sh`；重新 `source ~/.bashrc` |
| `uv sync` 网络超时 | 检查代理 `echo $HTTPS_PROXY`；edu-cloud ECS 走 DMIT sing-box 127.0.0.1:7890 |
| `pytest --collect-only` 有 ImportError | 看 Error 信息定位模块；常见是 pyzbar（参 §3.2）或路径错（确认 `pyproject.toml pythonpath = ["src"]`） |
| `pytest tests/test_conduct/` passed 数 ≠ 68 | 看 `docs/plans/archived/2026-04/2026-04-18-ecs-pytest-baseline-report.md` 对照基线；真数字变了才是新情况 |
| 模块级测试一直 collect 0 | 验证 `tests/conftest.py` 存在且 `pyproject.toml` 有 `asyncio_mode = "auto"` |
| 跑 alembic 测试报 `aiosqlite not found` | `uv.lock` 要 sync：重跑 `uv sync --extra dev` |

## §6. 参考

- 首次装配任务 & 红线：`docs/plans/archived/2026-04/2026-04-18-ecs-pytest-setup-handoff.md`
- baseline 实测报告（含 grep 函数数 vs pytest passed 数对账）：`docs/plans/archived/2026-04/2026-04-18-ecs-pytest-baseline-report.md`
- T-E 接管审计（说明为何 reviewer 过去没在 ECS 实跑）：`docs/plans/archived/2026-04/2026-04-18-takeover-impact-audit-report.md`
