import { describe, it, expect } from 'vitest'
import { computeLayout } from '../../components/knowledge-tree/layoutEngine'

const nodeA = { id: 'A', big_concept_id: 'BC1', module: 'M1' }
const nodeB = { id: 'B', big_concept_id: 'BC1', module: 'M1' }
const nodeC = { id: 'C', big_concept_id: 'BC2', module: 'M1' }
const hard = (src, tgt) => ({ source: src, target: tgt, type: 'prerequisite_hard' })

describe('layoutEngine', () => {
  describe('toposort rank', () => {
    it('empty nodes returns empty positions', () => {
      const result = computeLayout({ nodes: [], edges: [], bigConceptOrder: [] })
      expect(result.positions).toEqual({})
      expect(result.bands).toEqual({})
    })

    it('single node is centered', () => {
      const result = computeLayout({
        nodes: [nodeA], edges: [],
        bigConceptOrder: [{ id: 'BC1', name: 'BC 1' }],
      })
      expect(result.positions.A).toBeDefined()
      expect(result.positions.A.x).toBeGreaterThan(0)
      expect(result.positions.A.y).toBeGreaterThan(0)
    })

    it('linear chain A→B→C: ranks are 0,1,2', () => {
      const result = computeLayout({
        nodes: [nodeA, nodeB, nodeC],
        edges: [hard('A', 'B'), hard('B', 'C')],
        bigConceptOrder: [
          { id: 'BC1', name: 'BC 1' }, { id: 'BC2', name: 'BC 2' },
        ],
      })
      // B 必须在 A 右边
      expect(result.positions.B.x).toBeGreaterThan(result.positions.A.x)
      expect(result.positions.C.x).toBeGreaterThan(result.positions.B.x)
    })

    it('diverging: A→B, A→C', () => {
      const result = computeLayout({
        nodes: [nodeA, nodeB, nodeC],
        edges: [hard('A', 'B'), hard('A', 'C')],
        bigConceptOrder: [
          { id: 'BC1', name: 'BC 1' }, { id: 'BC2', name: 'BC 2' },
        ],
      })
      expect(result.positions.B.x).toBeGreaterThan(result.positions.A.x)
      expect(result.positions.C.x).toBeGreaterThan(result.positions.A.x)
    })
  })

  describe('determinism', () => {
    // INV-001: computeLayout 是纯函数，同输入多次调用返回完全相同的 {positions, bands, warnings}
    // F001 修复：使用非平凡输入（多 BigConcept + 链式 + 分叉 + 多节点同 rank），
    // 深度比较 positions / bands / warnings 三字段全量。
    // 反证：如果实现引入 Math.random 或依赖 Set 迭代顺序，r1 !== r2；
    //       如果 determinism oracle 不检 warnings，删除 warnings.push('cycle_detected')
    //       这一行也不会让该测试失败，但 INV-001 是三字段稳定 → 必须检 warnings
    it('non-trivial layout is deterministic across positions, bands, and warnings', () => {
      const nodes = [
        { id: 'A1', big_concept_id: 'BC1', module: 'M1' },
        { id: 'A2', big_concept_id: 'BC1', module: 'M1' },
        { id: 'A3', big_concept_id: 'BC1', module: 'M1' },
        { id: 'B1', big_concept_id: 'BC2', module: 'M1' },
        { id: 'B2', big_concept_id: 'BC2', module: 'M1' },
        { id: 'C1', big_concept_id: 'BC3', module: 'M1' },
      ]
      const edges = [
        hard('A1', 'A2'),
        hard('A1', 'A3'), // 分叉
        hard('A2', 'B1'), // 跨 BigConcept hard 边
        hard('B1', 'B2'), // 链式
        hard('A3', 'C1'), // 另一条跨 BigConcept 边
      ]
      const bigConceptOrder = [
        { id: 'BC1', name: 'BC 1' },
        { id: 'BC2', name: 'BC 2' },
        { id: 'BC3', name: 'BC 3' },
      ]
      const input = { nodes, edges, bigConceptOrder }
      const r1 = computeLayout(input)
      const r2 = computeLayout(input)

      // 非平凡性断言：结果必须含有所有 6 个节点 + 3 条 band + 无 warnings（非退化）
      expect(Object.keys(r1.positions).length).toBe(6)
      expect(Object.keys(r1.bands)).toEqual(['BC1', 'BC2', 'BC3'])
      expect(r1.warnings).toEqual([])

      // 深度相等三字段（INV-001 完整映射）
      expect(r1.positions).toEqual(r2.positions)
      expect(r1.bands).toEqual(r2.bands)
      expect(r1.warnings).toEqual(r2.warnings)
    })

    it('cyclic input determinism includes warnings field', () => {
      // F001 修复第二环：cycle 输入时 warnings 必须参与确定性比较。
      // 反证：如果实现对 warnings 使用 Set 或随机 push，两次调用 warnings 数组可能不同
      const input = {
        nodes: [
          { id: 'X', big_concept_id: 'BC1', module: 'M1' },
          { id: 'Y', big_concept_id: 'BC1', module: 'M1' },
          { id: 'Z', big_concept_id: 'BC2', module: 'M1' },
        ],
        edges: [hard('X', 'Y'), hard('Y', 'X'), hard('X', 'Z')],
        bigConceptOrder: [
          { id: 'BC1', name: 'BC 1' }, { id: 'BC2', name: 'BC 2' },
        ],
      }
      const r1 = computeLayout(input)
      const r2 = computeLayout(input)
      // 非平凡性：环被检测到
      expect(r1.warnings).toContain('cycle_detected')
      // 三字段全量稳定
      expect(r1.positions).toEqual(r2.positions)
      expect(r1.bands).toEqual(r2.bands)
      expect(r1.warnings).toEqual(r2.warnings)
    })
  })

  describe('band layout', () => {
    it('nodes of same BigConcept fall within their band Y range', () => {
      const result = computeLayout({
        nodes: [nodeA, nodeB, nodeC],
        edges: [hard('A', 'B')],
        bigConceptOrder: [
          { id: 'BC1', name: 'BC 1' }, { id: 'BC2', name: 'BC 2' },
        ],
      })
      const bc1Band = result.bands.BC1
      const bc2Band = result.bands.BC2
      expect(result.positions.A.y).toBeGreaterThanOrEqual(bc1Band.yMin)
      expect(result.positions.A.y).toBeLessThanOrEqual(bc1Band.yMax)
      expect(result.positions.B.y).toBeGreaterThanOrEqual(bc1Band.yMin)
      expect(result.positions.B.y).toBeLessThanOrEqual(bc1Band.yMax)
      expect(result.positions.C.y).toBeGreaterThanOrEqual(bc2Band.yMin)
      expect(result.positions.C.y).toBeLessThanOrEqual(bc2Band.yMax)
    })

    it('bands are ordered by bigConceptOrder', () => {
      const result = computeLayout({
        nodes: [nodeA, nodeC],
        edges: [],
        bigConceptOrder: [
          { id: 'BC1', name: 'BC 1' }, { id: 'BC2', name: 'BC 2' },
        ],
      })
      // BC1 在 BC2 上方
      expect(result.bands.BC1.yMax).toBeLessThanOrEqual(result.bands.BC2.yMin)
    })
  })

  describe('cycle handling', () => {
    it('cycle does not crash, records warning', () => {
      const result = computeLayout({
        nodes: [nodeA, nodeB],
        edges: [hard('A', 'B'), hard('B', 'A')],
        bigConceptOrder: [{ id: 'BC1', name: 'BC 1' }],
      })
      expect(result.positions.A).toBeDefined()
      expect(result.positions.B).toBeDefined()
      expect(result.warnings).toContain('cycle_detected')
    })
  })

  describe('unknown big_concept_id fallback', () => {
    // F003 修复：plan:398 声明 big_concept_id 不在 bigConceptOrder 中 → 归入 __unknown__ band。
    // 反证：如果实现删除 __unknown__ fallback 分支，节点会丢失（positions 缺 key）或落错 band。
    it('nodes with big_concept_id not in bigConceptOrder fall into __unknown__ band', () => {
      const known = { id: 'K', big_concept_id: 'BC1', module: 'M1' }
      const orphan = { id: 'O', big_concept_id: 'BC_MISSING', module: 'M1' }
      const result = computeLayout({
        nodes: [known, orphan],
        edges: [],
        bigConceptOrder: [{ id: 'BC1', name: 'BC 1' }],
      })
      // 断言 1: __unknown__ band 存在
      expect(result.bands.__unknown__).toBeDefined()
      expect(result.bands.__unknown__.label).toBe('未分类')
      // 断言 2: orphan 节点有位置（未丢失）
      expect(result.positions.O).toBeDefined()
      // 断言 3: orphan 节点 Y 落在 __unknown__ band 内
      const unknownBand = result.bands.__unknown__
      expect(result.positions.O.y).toBeGreaterThanOrEqual(unknownBand.yMin)
      expect(result.positions.O.y).toBeLessThanOrEqual(unknownBand.yMax)
      // 断言 4: known 节点在 BC1 band（未被错误分带）
      const bc1Band = result.bands.BC1
      expect(result.positions.K.y).toBeGreaterThanOrEqual(bc1Band.yMin)
      expect(result.positions.K.y).toBeLessThanOrEqual(bc1Band.yMax)
      // 断言 5: __unknown__ band 排在 BC1 之后（按 bigConceptOrder 收集顺序 + __unknown__ 追加到末尾）
      expect(bc1Band.yMax).toBeLessThanOrEqual(unknownBand.yMin)
    })

    it('all nodes in bigConceptOrder → no __unknown__ band', () => {
      // 对照组：纯 happy path 时不应创建空的 __unknown__ band
      const result = computeLayout({
        nodes: [nodeA, nodeB],
        edges: [],
        bigConceptOrder: [{ id: 'BC1', name: 'BC 1' }],
      })
      expect(result.bands.__unknown__).toBeUndefined()
    })
  })
})
