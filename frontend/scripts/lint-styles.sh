#!/bin/bash
# 扫描 Vue SFC <style> 中的违规模式
# 只扫描 .vue 文件（组件级），不扫描 .css（token 定义文件）
# 排除 card-editor/（独立原生 JS 模块）和 backup/frozen 目录
EXIT=0

echo "=== Vue 组件硬编码颜色 ==="
COUNT=$(grep -Erohn '#[0-9a-fA-F]{6}' src/ --include="*.vue" \
  | grep -v node_modules | grep -v _backup | grep -v _frozen \
  | grep -v 'card-editor/' | wc -l)
echo "  共 $COUNT 处"
if [ "$COUNT" -gt 0 ]; then
  grep -Eron '#[0-9a-fA-F]{6}' src/ --include="*.vue" \
    | grep -v node_modules | grep -v _backup | grep -v _frozen \
    | grep -v 'card-editor/' | head -20
  [ "$COUNT" -gt 20 ] && echo "  ... 还有 $((COUNT - 20)) 处"
fi

echo ""
echo "=== font-size: 17px ==="
grep -rn 'font-size.*17px' src/ --include="*.vue" | grep -v node_modules || echo "  无"

echo ""
echo "=== font-weight: 700/800 ==="
HEAVY=$(grep -Ern 'font-weight.*(700|800)' src/ --include="*.vue" \
  | grep -v node_modules | grep -v _backup | wc -l)
echo "  共 $HEAVY 处"
grep -Ern 'font-weight.*(700|800)' src/ --include="*.vue" \
  | grep -v node_modules | grep -v _backup | head -10
[ "$HEAVY" -gt 10 ] && echo "  ... 还有 $((HEAVY - 10)) 处"

echo ""
echo "=== border-radius: 50px ==="
grep -rn 'border-radius.*50px' src/ --include="*.vue" \
  | grep -v node_modules | grep -v _backup || echo "  无"

echo ""
echo "=== 汇总 ==="
echo "  硬编码颜色: $COUNT"
echo "  font-weight 700/800: $HEAVY"
echo "  目标: 硬编码颜色 <100"

[ "$COUNT" -lt 100 ] && echo "PASS: 达到目标" || echo "WARN: 未达目标（当前 $COUNT / 目标 <100）"
exit 0
