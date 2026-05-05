---
name: paper
status: active
owner: backend
layer: infrastructure

owns_tables: []

owns_routes: ""

exposes:
  services:
    - PaperService
  events: []

depends_on:
  modules: []
  services: []
  ai_tools: []

created: "2026-05-05"
last_reviewed: "2026-05-05"
design_docs: []
---

# paper 模块

## 职责

外部 paper-skill 服务（端口 9103）的 REST 客户端封装。提供论文创建和状态查询能力。

## 边界

- **做什么**：
  - 调用 paper-skill `/api/paper/create` 创建论文任务
  - 调用 paper-skill `/api/paper/{id}/status` 查询进度
  - 定义 `PaperAccessLevel` 枚举（试卷访问层级常量，S4 4.2 消费）
- **不做什么**：
  - 不持有任何数据库表（数据在外部 paper-skill 服务）
  - 不暴露 API 路由（由 `modules/studio/router.py` 挂载 Studio 论文端点）
  - 论文内容生成 → 外部 paper-skill 服务

## 架构

Template C（纯 service，无 router，无 models）。作为 thin client 封装外部 HTTP 服务调用。

## 数据流

```
Studio router POST /api/v1/studio/paper/create
       │
       ▼
services/paper_service.py (re-export)
       │
       ▼
paper.service.PaperService.create_paper
       │  httpx POST
       ▼
paper-skill (外部服务 localhost:9103)
```

## 使用方式

### 外部调用方

- `services/paper_service.py`: re-export `PaperService` 供 Studio router 使用

### 配置

- `PAPER_SKILL_URL`: 环境变量，默认 `http://localhost:9103`

## 常量

- `PaperAccessLevel`: 三级试卷访问权限枚举（teacher_private / school_shared / district_shared），供 S4 分享工作流消费。

## 变更历史

- 2026-05-05: 创建 MODULE.md
