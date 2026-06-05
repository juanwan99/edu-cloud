# Portal Aggregation Contract

> Date: 2026-06-04
> Scope: future portal homepage, service center, todo center, message center,
> and personal workspace aggregation.

## Purpose

The future portal must aggregate school work without owning business data. It
may compose existing modules, but it must not query source tables directly from
page code or from a portal router. Portal code should depend on stable source
module services/adapters and return normalized DTOs.

This contract exists before absorbing a mature university portal, so the new
homepage can reuse portal concepts without turning edu-cloud into a tightly
coupled dashboard.

## Current Source Boundaries

- Notifications API: `src/edu_cloud/api/notifications_api.py`,
  `/api/v1/notifications`, backed by `notifications`.
- Conduct parent notifications:
  `src/edu_cloud/modules/conduct/notification_router.py`, backed by
  `conduct_notifications`.
- Calendar API: `src/edu_cloud/modules/calendar/router.py`,
  `/api/v1/calendar/events`, backed by `calendar_events` and
  `notification_rules`.
- Studio approval flow: `src/edu_cloud/modules/studio/approval_service.py`,
  backed by `approval_flows` and `approval_steps`.
- AI workflow engine: `src/edu_cloud/ai/workflow/engine.py`, backed by
  `workflow_runs` and `workflow_steps`.
- Legacy DashboardPage currently calls several business endpoints directly.
  That page is not the future portal contract; migration should happen after
  backend portal aggregation APIs exist.

## Future Portal APIs

The portal frontend should consume these future endpoints instead of calling
business modules one by one:

- `GET /api/v1/portal/summary`
- `GET /api/v1/portal/todos`
- `GET /api/v1/portal/messages`
- `GET /api/v1/portal/calendar-digest`
- `GET /api/v1/portal/services`

Each endpoint must apply current role, tenant scope, module switches, and
permissions before returning items.

## DTO Contracts

### TodoItem

Required fields:

- `id`: stable portal item id.
- `source_module`: owning module such as `exam`, `grading`, `homework`,
  `studio`, `conduct`, or `calendar`.
- `source_type`: source-specific type such as `grading_task`,
  `homework_submission`, `approval_step`, `workflow_step`, or
  `calendar_deadline`.
- `source_id`: id in the owning module.
- `title`: short user-facing title.
- `summary`: optional one-line context.
- `status`: `open`, `pending_approval`, `in_progress`, `overdue`, or `done`.
- `priority`: `low`, `normal`, `high`, or `urgent`.
- `school_id`: source tenant.
- `assignee_scope`: normalized role/class/grade/subject scope.
- `due_at`: optional ISO timestamp.
- `created_at`: ISO timestamp.
- `updated_at`: ISO timestamp.
- `action_url`: frontend route for the next action.
- `permission`: permission required to open the action.
- `module_code`: school module switch code required for visibility.

### MessageItem

Required fields:

- `id`
- `source_module`
- `source_type`
- `source_id`
- `kind`: `notification`, `approval`, `calendar`, `workflow`, or `system`.
- `title`
- `summary`
- `severity`: `info`, `success`, `warning`, or `error`.
- `read`: boolean.
- `created_at`
- `action_url`
- `permission`
- `module_code`

### CalendarDigestItem

Required fields:

- `id`
- `source_module`
- `source_id`
- `event_date`
- `title`
- `type`
- `school_id`
- `action_url`
- `module_code`

### ServiceEntry

Required fields:

- `id`
- `module_code`
- `title`
- `description`
- `route`
- `permission`
- `enabled`
- `badge_source`: optional source for counts such as todo or unread message
  totals.

## Adapter Rules

- Portal aggregation must call source module services/adapters, not import
  `Notification`, `CalendarEvent`, `ApprovalFlow`, `ApprovalStep`,
  `WorkflowRun`, or `WorkflowStep` directly.
- Source modules keep ownership of tables and status transitions.
- Portal adapters may normalize read models but must not mutate source state.
- Every item must include `source_module`, `source_id`, `action_url`,
  `permission`, and `module_code`.
- Module switch filtering must happen before permission-based item shaping.
- Permission checks must use `src/edu_cloud/core/permissions.py` contracts, not
  page-local role lists.
- New source modules must add a `MODULE.md` contract before being exposed in the
  portal.

## Migration Order

1. Keep the existing dashboard behavior until the frontend migrates.
2. Use the backend `portal` module with `MODULE.md`, no owned business tables,
   and adapters for notification/calendar/homework sources as the first
   aggregation boundary.
3. Extend adapters for approval/workflow sources before exposing them in the
   homepage.
4. Move the frontend homepage to `/api/v1/portal/*` endpoints.
5. Only then absorb richer mature-portal modules such as service center,
   business-system center, personal workspace, and unified message center.
