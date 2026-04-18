#!/usr/bin/env bash
# edu-cloud ECS / Linux 开发环境装配（uv venv 路线，不污染系统 python）
#
# 前置：uv 已装（官方安装：curl -LsSf https://astral.sh/uv/install.sh | sh）
# 用法：bash scripts/setup_ecs_dev.sh
#
# 实测环境（2026-04-18 ECS Ubuntu 22.04）：
#   - 系统 python3: 3.10.12（不满足 pyproject requires-python >=3.11）
#   - uv: 0.11.6
#   - 核心 deps（pyzbar/lxml/opencv-python-headless/playwright）全部 pure-wheel 可装，
#     **无需 apt install 系统库**（见 §「apt 依赖备选方案」注释）
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# ---- Step 1: 检查 uv ----
if ! command -v uv >/dev/null 2>&1; then
  echo "[setup_ecs_dev] ERROR: uv 未装，先运行：curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi
echo "[setup_ecs_dev] uv: $(uv --version)"

# ---- Step 2: 装 Python 3.11（uv 管理，不碰系统 python3）----
echo "[setup_ecs_dev] 安装 Python 3.11 via uv（若已装则 no-op）..."
uv python install 3.11

# ---- Step 3: 创建 .venv ----
if [[ -d .venv ]]; then
  echo "[setup_ecs_dev] .venv 已存在，跳过 uv venv"
else
  echo "[setup_ecs_dev] 创建 .venv..."
  uv venv --python 3.11
fi

# ---- Step 4: sync 依赖（含 dev: pytest/pytest-asyncio/playwright/ruff）----
echo "[setup_ecs_dev] uv sync --extra dev..."
uv sync --extra dev

# ---- Step 5: 验证 pytest 可用 ----
# shellcheck source=/dev/null
source .venv/bin/activate
echo "[setup_ecs_dev] python: $(python --version)"
echo "[setup_ecs_dev] pytest: $(python -m pytest --version 2>&1 | head -1)"

# ---- Step 6: 核心 import smoke test（系统库依赖自检）----
python - <<'PY'
import sys
failed = []
for mod in ("pyzbar", "lxml", "cv2", "playwright", "reportlab", "openpyxl"):
    try:
        __import__(mod)
    except Exception as exc:
        failed.append((mod, str(exc)))
if failed:
    print("[setup_ecs_dev] IMPORT FAILED:", failed)
    sys.exit(2)
print("[setup_ecs_dev] core imports OK: pyzbar/lxml/cv2/playwright/reportlab/openpyxl")
PY

# ---- Step 7: collect-only smoke test ----
echo "[setup_ecs_dev] pytest --collect-only..."
python -m pytest --collect-only -q 2>&1 | tail -3

echo ""
echo "[setup_ecs_dev] DONE. 激活命令：source .venv/bin/activate"
echo "[setup_ecs_dev] 跑测试：python -m pytest tests/test_conduct/ -q"
echo ""
echo "======================================================================"
echo "apt 依赖备选方案（仅当 Step 6 import 失败时使用，需用户审批 sudo）"
echo "======================================================================"
echo "# pyzbar 运行时依赖 libzbar0（ECS 实测：pure-wheel 已含 libzbar.so，无需装）"
echo "#   sudo apt-get install -y libzbar0"
echo "# lxml 运行时依赖 libxml2 + libxslt（实测：wheel 已静态链接）"
echo "#   sudo apt-get install -y libxml2 libxslt1.1"
echo "# opencv-python-headless 运行时依赖（headless 版已剥离 GUI，一般无需）"
echo "#   sudo apt-get install -y libgl1 libglib2.0-0"
echo "# playwright Chromium 浏览器（>500MB，仅需要真实浏览器时装）"
echo "#   python -m playwright install chromium --with-deps"
echo "======================================================================"
