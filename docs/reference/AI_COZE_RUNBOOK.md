# AI Coze-first Runbook

Purpose: switch edu-cloud AI chat from the current Pydantic fallback to a real
Coze-first runtime without changing the public `/api/v1/ai/chat` SSE contract.

This runbook is intentionally outside `docs/context/` and governance docs. It is
an operator checklist for the AI provider migration only.

## Current Architecture

- Public chat API remains `/api/v1/ai/chat`.
- `AgentProvider` selects `coze` when Coze is configured; otherwise it falls
  back to `current_pydantic`.
- Coze handles chat orchestration and tool choice.
- edu-cloud keeps the security boundary:
  - DataScope
  - role/school/class/student scope
  - module and capability checks
  - tool execution
  - write confirmation
  - trace/artifact/chat-message persistence

## Coze Prerequisites

Official Coze Studio quickstart requires Docker and Docker Compose, with a
minimum host size of 2 CPU cores and 4 GB memory:

- https://github.com/coze-dev/coze-studio
- https://github.com/coze-dev/coze-studio/wiki

Official API docs require publishing the target agent as an API service and
using a Personal Access Token in the `Authorization: Bearer ...` header:

- https://github.com/coze-dev/coze-studio/wiki/6.-API-Reference

edu-cloud's Coze provider uses:

- `POST /v3/chat`
- `POST /v3/chat/submit_tool_outputs`

## Required edu-cloud Settings

Set these in `.env` or the deployment environment:

```env
AI_AGENT_PROVIDER=coze
AI_AGENT_FALLBACK_PROVIDER=current_pydantic
AI_COZE_ENABLED=true
AI_COZE_API_BASE=http://127.0.0.1:8888
AI_COZE_BOT_ID=<published-agent-bot-id>
AI_COZE_API_TOKEN=<personal-access-token>
AI_COZE_TIMEOUT=120
```

Never commit real values for `AI_COZE_API_TOKEN`, `AI_TOOL_GATEWAY_TOKEN`, Coze
account passwords, or provider model keys. Runtime credentials belong in `.env`,
the deployment secret store, or the local Coze operator credential file. The
committed `.env.example` must keep those values blank.

For Coze HTTP-tool callback mode, also set:

```env
AI_TOOL_GATEWAY_PUBLIC_BASE=https://<public-edu-cloud-origin>
AI_TOOL_GATEWAY_TOKEN=<long-random-service-token>
AI_TOOL_GATEWAY_HTTP_ENABLED=true
```

If using Coze `requires_action` mode only, the public gateway settings are not
required for chat readiness. The edu backend executes tools and submits tool
outputs back to Coze. Keep `AI_TOOL_GATEWAY_HTTP_ENABLED=false` until the
Coze-container-to-edu-cloud ingress has been deployed and verified.

## Current ECS Runtime

The verified ECS runtime uses:

- Coze Studio web/API on `127.0.0.1:8888`.
- edu-cloud API on `127.0.0.1:9000`.
- `AI_AGENT_PROVIDER=coze`.
- `AI_AGENT_FALLBACK_PROVIDER=current_pydantic`.
- `AI_COZE_ENABLED=true`.
- `AI_TOOL_GATEWAY_PUBLIC_BASE=http://127.0.0.1:9000`.
- `AI_TOOL_GATEWAY_HTTP_ENABLED=false` for native HTTP-plugin callbacks.

Coze Bot ID, PAT, and the local Coze account details are stored outside git.
Do not paste those secrets into docs, tests, commit messages, or review notes.

## Preflight

Check host capacity and port conflicts:

```bash
free -h
df -h /
docker --version
docker compose version
ss -ltnp | grep ':8888' || true
ss -ltnp | grep ':9000' || true
```

Check provider readiness without exposing secrets:

```bash
.venv/bin/python -m edu_cloud.cli.agent --provider-status
```

Expected after Coze is configured:

```json
{
  "active": "coze",
  "readiness": {
    "coze": {
      "chat_ready": true,
      "missing": [],
      "tool_gateway_http_ready": false,
      "tool_modes": {
        "coze_required_action": true,
        "http_tool_gateway": false
      }
    }
  }
}
```

`http_tool_gateway=false` is expected on the current ECS runtime. It means the
native Coze HTTP-plugin callback ingress is not enabled yet; it does not block
the Coze `requires_action` chat path.

## Live Smoke

Run a direct provider smoke:

```bash
.venv/bin/python -m edu_cloud.cli.agent --coze-live-smoke
```

Expected:

- command exits `0`
- output includes at least one `answer`
- final event is `done`
- no `error` event

The pytest variant is also available and skipped unless explicitly enabled:

```bash
AI_COZE_LIVE_SMOKE=1 \
  .venv/bin/python -m pytest tests/test_ai/test_engine/test_coze_live_smoke.py -q
```

## API Smoke

After provider smoke passes, call `/api/v1/ai/chat` with a normal teacher token.
The public SSE shape must remain unchanged:

- `thinking`
- optional `tool_call`
- optional `tool_result`
- optional `confirmation_required`
- `answer`
- `done`

The `done` event should include `"provider": "coze"` when Coze is active.

For a role with real school context, the current gateway allowlist should expose
the edu-side tools that passed live validation:

- `get_class_list`
- `get_exam_list`
- `get_exam_summary`
- `list_homework_tasks`
- `get_homework_stats`
- `get_class_report`
- `generate_comment`

Read validation:

- `POST /internal/ai-tools/get_class_list`
- expected: `status=ok`

Write validation:

- `POST /internal/ai-tools/generate_comment`
- expected: `status=confirmation_required`
- expected: non-empty `confirmation_id`

## Tool Modes

### Coze `requires_action`

Preferred for keeping edu-cloud as the execution boundary:

1. Coze emits `conversation.chat.requires_action`.
2. edu-cloud executes the allowed tool through `Internal Tool Gateway`.
3. edu-cloud submits results to `/v3/chat/submit_tool_outputs`.
4. Coze continues the streamed answer.

This mode is covered by provider tests and keeps the execution boundary inside
edu-cloud. It does not require Coze Studio to reach `/internal/ai-tools` over
HTTP.

### HTTP Tool Gateway

Use only when Coze is configured with HTTP tools/plugins:

1. Coze calls `/internal/ai-tools/{tool_name}`.
2. Request must include `X-AI-Tool-Token`.
3. Body includes `context_token` and `arguments`.
4. Write tools return `confirmation_required` until approved by edu-cloud.

The current ECS network does not yet expose a stable Coze-container-to-edu-cloud
HTTP callback entrypoint. Direct tests from the Coze container to the host-bound
edu service timed out. Productizing native Coze HTTP plugins should be a
separate deployment task, not a code-only Agent task.

Provider readiness intentionally reports `tool_modes.http_tool_gateway=false`
unless `AI_TOOL_GATEWAY_HTTP_ENABLED=true` and both public base/token settings
are present. Do not flip this flag until the callback URL has been verified from
inside `coze-server`.

Recommended deployment plan for native Coze HTTP plugin callbacks:

1. Add an nginx location for `/internal/ai-tools` that proxies to
   `127.0.0.1:9000`.
2. Keep TLS termination at nginx when traffic leaves localhost.
3. Require `X-AI-Tool-Token` on every request; rotate it separately from Coze
   PATs.
4. Restrict source networks if possible, such as the Docker bridge, Tailscale,
   or explicit Coze host IPs.
5. Add a firewall rule only for the chosen callback ingress; do not expose the
   full edu-cloud API surface to Coze containers.
6. Verify from inside `coze-server` with:

```bash
docker exec coze-server curl -sS -o /dev/null -w '%{http_code}\n' \
  -H "X-AI-Tool-Token: <redacted>" \
  "https://<edu-origin>/internal/ai-tools?context_token=<issued-context-token>"
```

Do not change `deploy/systemd`, governance scripts, or migrations as part of
this Agent provider commit.

## Rollback

Disable Coze without changing frontend/API contracts:

```env
AI_COZE_ENABLED=false
AI_AGENT_FALLBACK_PROVIDER=current_pydantic
```

If the preferred provider is still `coze`, the provider selector will fall back
to `current_pydantic` when Coze is unavailable. To make rollback explicit, set:

```env
AI_AGENT_PROVIDER=current_pydantic
AI_AGENT_FALLBACK_PROVIDER=current_pydantic
```

Provider status should then show:

```json
{
  "active": "current_pydantic"
}
```

## Verification Commands

```bash
.venv/bin/python -m pytest \
  tests/test_ai/test_engine \
  tests/test_ai/test_ai_api.py \
  tests/test_ai/test_data_scope.py \
  tests/test_ai/test_agent_cli.py \
  --tb=short -q

.venv/bin/python -m pytest \
  tests/test_ai/test_workflow_engine.py \
  tests/test_ai/test_w3_profile.py \
  tests/test_ai/test_w6_patrol.py \
  --tb=short -q

.venv/bin/python -m pytest tests/test_config_compat.py --tb=short -q
git diff --check
```

## Commit Readiness Checklist

- `git status --short --untracked-files=all` contains only Agent/provider/API
  reference-doc/test changes.
- No paths under `docs/context`, `scripts/meta*`, `scripts/guardian*`,
  `src/edu_cloud/ai/workflow`, `deploy/systemd`, `docs/governance`,
  `scripts/governance`, `alembic`, or `migrations`.
- `git diff --check` is clean.
- Secret scan finds no real PAT, API key, password, or token in tracked or
  untracked commit candidates.
- `--provider-status` prints readiness without secret values.
- Live smoke and pytest smoke pass on a configured Coze runtime.
- `/api/v1/ai/chat` still returns `text/event-stream`.
- Read-only tool execution returns `status=ok`.
- Write tool execution returns `confirmation_required`.

## Known Non-Agent Signals

- The Coze live SSE stream may end with an empty data line; the provider logs it
  as `Malformed Coze SSE data:` and still exits successfully when answer and
  done events are received.
- Startup logs currently include a knowledge-tree stats warning about
  `evidence_ids_json`. That is not introduced by the Agent provider work and
  should be handled in a separate knowledge-tree/database-health task.
