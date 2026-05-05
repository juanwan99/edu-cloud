# edu-cloud 日志排查手册

> 按需阅读：排查问题时参考本文档，CLAUDE.md 日志体系段有速查路由规则。

## 工具

```bash
scripts/edu-log <command> [options]
scripts/edu-log <command> --help    # 单命令详细用法
```

## 场景索引

### 阅卷任务不动/失败

```bash
# 1. 找到任务 ID（从前端 URL 或数据库）
scripts/edu-log task <task_id> --since 1d

# 2. 如果只看到 task_create 没有 Worker 日志 → Worker 没接到任务
# 检查 Worker 进程是否存活：
ps aux | grep arq

# 3. 如果看到 LLM 重试/失败
scripts/edu-log llm --since 1h --level error

# 4. 拉完整链路（从用户点击到 LLM 返回）
scripts/edu-log trace <trace_id> --since 1d
```

### 前端页面报错

```bash
# 1. 查所有前端错误
scripts/edu-log frontend --since 24h --level error

# 2. 按页面过滤（输出含 page_route 字段，用 grep 二次过滤）
scripts/edu-log frontend --since 24h | grep "/grading"

# 3. 关联后端请求（前端日志含 trace_id）
scripts/edu-log trace <trace_id>
```

### 接口慢/超时

```bash
# 1. 找慢请求（>3 秒）
scripts/edu-log slow --over 3000 --since 24h

# 2. 定位具体请求
scripts/edu-log req <req_id>

# 3. 看该请求触发的 LLM 调用
scripts/edu-log trace <trace_id> --since 1d
```

### 分数争议（谁改了分数）

```bash
# 1. 查业务事件：分数修改
scripts/edu-log business --since 30d --action score_override
scripts/edu-log business --since 30d --action annotation_save

# 2. 按考试过滤
scripts/edu-log exam <exam_id> --since 30d

# 3. 按用户过滤（看某教师的操作）
scripts/edu-log user <user_id> --since 30d
```

### 登录/权限问题

```bash
# 1. 查登录失败
scripts/edu-log business --since 7d --action login_failed

# 2. 查权限拒绝
scripts/edu-log business --since 7d --action permission_denied

# 3. 按用户查所有操作
scripts/edu-log user <user_id> --since 7d
```

### LLM API 异常（429 限流/超时/5xx）

```bash
# 1. 查所有 LLM 错误
scripts/edu-log llm --since 24h --level error

# 2. 查 LLM 重试（warning 级别）
scripts/edu-log llm --since 24h --level warning

# 3. 实时监控 LLM 调用
scripts/edu-log tail --layer llm
```

### 学生/教师导入失败

```bash
# 1. 查业务事件
scripts/edu-log business --since 7d --action bulk_import

# 2. 查该请求的错误详情
scripts/edu-log trace <trace_id>
```

### 德育加减分记录

```bash
scripts/edu-log business --since 30d --action points_add
```

### 实时监控（开发调试）

```bash
# 全部日志
scripts/edu-log tail

# 只看错误
scripts/edu-log tail --level error

# 只看某一层
scripts/edu-log tail --layer llm
scripts/edu-log tail --layer client
scripts/edu-log tail --layer business
```

### 系统健康概览

```bash
# 日志文件统计
scripts/edu-log stats

# 最近错误
scripts/edu-log errors --since 24h

# 最近告警
scripts/edu-log alerts --since 7d
```

## 日志文件位置

```
logs/
  api/edu-api-YYYY-MM-DD.NNN.jsonl       # API 进程（14 天热存，120 天 gzip）
  worker/edu-worker-YYYY-MM-DD.NNN.jsonl  # Worker 进程（同上）
  business/edu-biz-YYYY-MM-DD.jsonl       # 业务事件归档（365 天）
```

## 紧急降级（edu-log 不可用时）

```bash
# 直接 jq 查询
cat logs/api/edu-api-$(date +%Y-%m-%d).*.jsonl | jq 'select(.trace_id=="tr_xxx")'

# 压缩文件
zcat logs/api/edu-api-2026-05-01.*.jsonl.gz | jq 'select(.level=="error")'
```
