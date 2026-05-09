# edu-cloud 健康度审计 + 修复 全程交接卡（最终版）

## Goal
对 edu-cloud 项目做 Claude×GPT 双模型深度健康度审计，产出调查报告 + 共识修复方案，执行全部 8 Phase 修复。

## Must Preserve
- GradingResult UniqueConstraint `(school_id, answer_id)`
- `auto_fix_ab_sides` 返回 0（no-op）
- `GRADING_DISPATCH_ROLES` = `SCHOOL_ADMIN_ROLES`
- CardEditor 无 `switchToTql`
- 3 新模块：`questionSort.js`, `question_order.py`, `basic_report_service.py`
- `MANAGE_TEACHERS` 权限枚举
- browse-dir / scan-dir / start / pdf-import / import-tpl / scan-image / preview 路径限制
- 登录 rate limit 5/min slowapi
- 6 处 innerHTML DOMPurify
- 11 处 fetch→Axios 统一
- JWT 过期检查 router+interceptor
- grading results 分页格式 `{total, page, page_size, items}`
- dispatch/status 批量查询（N+1 修复）

## Must Not Change
- `src/edu_cloud/api/deps.py` — b0d314cc 已改
- `src/edu_cloud/modules/grading/router.py` — b0d314cc 已改
- `src/edu_cloud/modules/grading/models.py` — b0d314cc 已迁移

---

## 完成的工作

### Phase 1-3：安全修复（9 Task）
| Task | Commit | 修复 |
|------|--------|------|
| T1 | 713eedf | MANAGE_TEACHERS + teacher 6 端点 |
| T2 | 5df4321 | card 24 端点 MANAGE_EXAMS/VIEW_EXAMS |
| T3 | 6f44838 | browse-dir UPLOAD_DIR 限制 |
| T4 | 0d576a7 | grading except→logger.warning |
| T5 | 00a03e3 | 登录 rate limit 5/min |
| T6 | 20b2992 | scan 资源 with 管理器 |
| T7 | cc5b26b | 6 处 innerHTML DOMPurify |
| T8 | 8b6c449 | 11 处 fetch→Axios |
| T9 | 45864cb | 路由守卫 JWT 过期检查 |

### Urgent：安全审查新发现
| Commit | 修复 |
|--------|------|
| 30b1cf7 | scan 6 端点路径遍历修复 + _validate_path_within_upload_dir helper |
| 47fec39 | GPT review F-001~F-005: preview 路径校验 + 下游穿透 + 分页参数校验 |

### Phase 4：性能
| Commit | 修复 |
|--------|------|
| 1aa7eb4 | list_results/list_pending_reviews 分页 + dispatch N+1 → 3 次批量查询 |

### Phase 5：scan 重构
| Commit | 修复 |
|--------|------|
| 77288df | pipeline_router 1336→907 行（cv_detect_router 拆出 430 行）+ 5 处 asyncio.to_thread |

### Phase 6：前端结构
| Commit | 修复 |
|--------|------|
| dee6cc4 | 5 个死组件删除（322 行）+ naive-ui manualChunk 移除 |

### Phase 7：清理
| Commit | 修复 |
|--------|------|
| 676a52f | 移除 qrcode + python-dateutil 未用依赖 |

### 测试基线（最终）

| 维度 | 结果 |
|------|------|
| 后端 passed | **2568** (+67 vs 修复前 2501) |
| 后端 failed | 42（pre-existing） |
| 前端 passed | **2496** (+1 vs 修复前) |
| 前端 failed | 5（pre-existing） |
| vite build | ✅ |
| 锚点检查 | ✅ ALL OK |

### Deferred 项（ROI 不足）
- N-H01：ReviewPage 拆分（1511 行，provide/inject 重构风险）
- N-H02：Naive UI 完全按需导入（需 unplugin + 测试 setup 改造）
- N-M07：create_all → alembic（种子脚本，非生产代码）
- N-L01：44 个过时测试（逐模块更新，工时长收益低）

---

## 锚点检查命令

```bash
grep -q "school_id.*answer_id" src/edu_cloud/modules/grading/models.py && \
grep -q "return 0" src/edu_cloud/modules/scan/pipeline_service.py && \
grep -q "SCHOOL_ADMIN_ROLES" frontend/src/config/roles.js && \
! grep -q "switchToTql" frontend/src/components/CardEditor.vue && \
test -f frontend/src/utils/questionSort.js && \
grep -q "MANAGE_TEACHERS" src/edu_cloud/core/permissions.py && \
echo "ALL ANCHORS OK" || echo "ANCHOR FAILED"
```

## 关键文档索引

| 文档 | 路径 |
|------|------|
| 联合审计报告 | `docs/2026-05-08-health-audit-claude-gpt.md` |
| 共识修复方案 | `docs/2026-05-08-fix-plan-consensus.md` |
| Phase 1-3 计划 | `docs/superpowers/plans/2026-05-08-security-fix-phase1-3.md` |
| 安全修复交接 | `docs/2026-05-09-security-fix-handoff.md` |
| GPT review gate | `docs/plans/gates.json` |
