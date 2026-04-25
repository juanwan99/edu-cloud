#!/bin/bash
# E2E 测试 runner — 用 Claude Code + Playwright MCP 驱动
# 用法:
#   ./run.sh specs/login-flow.md              # 跑单个测试
#   ./run.sh specs/                            # 跑整个目录
#   ./run.sh specs/full-pipeline.md --resume   # 断点续跑（附加上次输出）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESULTS_DIR="$SCRIPT_DIR/results"
SCREENSHOT_DIR="$RESULTS_DIR/screenshots"
SYSTEM_PROMPT="$SCRIPT_DIR/system-prompt.md"
TIMESTAMP=$(date '+%Y%m%d-%H%M%S')

mkdir -p "$SCREENSHOT_DIR"

usage() {
    echo "用法: $0 <spec-file-or-dir> [--resume]"
    echo ""
    echo "示例:"
    echo "  $0 specs/login-flow.md          # 单个测试"
    echo "  $0 specs/                        # 目录下全部"
    echo "  $0 specs/pipeline.md --resume    # 断点续跑"
    exit 1
}

[ $# -lt 1 ] && usage

TARGET="$1"
RESUME_FLAG=""
[ "${2:-}" = "--resume" ] && RESUME_FLAG="--resume"

run_spec() {
    local spec_file="$1"
    local spec_name=$(basename "$spec_file" .md)
    local report_file="$RESULTS_DIR/${spec_name}-${TIMESTAMP}.report.md"

    echo "=== 执行测试: $spec_name ==="
    echo "  规格: $spec_file"
    echo "  报告: $report_file"
    echo ""

    local spec_content
    spec_content=$(cat "$spec_file")

    local system_content
    system_content=$(cat "$SYSTEM_PROMPT")

    local prompt="$system_content

---

# 当前测试规格

$spec_content

---

执行以上测试规格。截图保存到 $SCREENSHOT_DIR/${spec_name}/ 目录。
完成后输出结构化测试报告。"

    claude -p "$prompt" \
        --allowedTools "mcp__playwright__*,Bash(mkdir *),Bash(date *),Read,Write($report_file)" \
        --model sonnet \
        $RESUME_FLAG \
        > "$report_file" 2>&1

    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo "  [DONE] 报告已写入 $report_file"
    else
        echo "  [FAIL] 退出码 $exit_code，查看 $report_file"
    fi

    return $exit_code
}

if [ -d "$TARGET" ]; then
    total=0
    passed=0
    failed=0
    for spec in "$TARGET"/*.md; do
        [ -f "$spec" ] || continue
        total=$((total + 1))
        if run_spec "$spec"; then
            passed=$((passed + 1))
        else
            failed=$((failed + 1))
        fi
        echo ""
    done
    echo "=== 汇总: $total 个测试, $passed 通过, $failed 失败 ==="
else
    run_spec "$TARGET"
fi
