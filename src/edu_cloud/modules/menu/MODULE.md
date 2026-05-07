---
name: menu
status: active
owner: backend
layer: business

owns_tables:
  - menu_configs

owns_routes:
  - /api/v1/menus
structure_pattern: standard
max_router_loc: 50
routers: [router.py]

exposes:
  services:
    - MenuService
  events: []

depends_on:
  modules:
    - school
  services:
    - school_settings_service
  ai_tools: []

created: "2026-05-05"
last_reviewed: "2026-05-05"
design_docs:
  - docs/plans/2026-04-12-haofenshu-biz-replication-design.md
---

# menu 模块

## 职责

动态菜单系统。根据用户当前角色和学校已启用模块，返回过滤后的菜单树。菜单配置存储在 DB 中（通过 seed 初始化），支持角色+模块双维度过滤。

## 边界

- **做什么**：读取 menu_configs 表 → 按角色 roles JSON 过滤 → 按学校 enabled_modules 过滤 → 返回父子树结构
- **不做什么**：模块启用/禁用管理由 `school` 模块的 school_settings_service 负责；前端侧边栏配置（sidebarConfig.js）是静态配置，与此动态菜单独立

## 使用方式

```bash
GET /api/v1/menus   # 返回当前角色+学校模块过滤后的菜单树
```

## 数据流

```
seed_menus 初始化 → menu_configs 表（8 模块 42 子菜单）
GET /menus → MenuService.get_menus_for_user(role, enabled_modules)
  → 查询 top-level menus (parent_id=NULL) + all children
  → 按 role 过滤 + 按 requires_module 过滤
  → 返回嵌套 {code, name, icon, sort, children[]}
```
