from scripts.yuanqi.registry_doctor import find_stale, scan


NOW = "2026-06-24T12:00:00+00:00"


def _task(**overrides):
    task = {
        "task_id": "yq-20260624-test",
        "mode": "module_writer",
        "owner": "claude",
        "allowed_paths": ["src/edu_cloud/modules/grading/**"],
        "exclusive_claims": [],
        "status": "active",
        "created_at": "2026-06-24T10:00:00+00:00",
        "expires_at": "2026-06-24T13:00:00+00:00",
    }
    task.update(overrides)
    return task


def test_active_expired_task_is_stale():
    task = _task(expires_at="2026-06-24T11:59:59+00:00")

    assert find_stale([task], NOW) == [task]


def test_active_unexpired_task_is_not_stale():
    task = _task(expires_at="2026-06-24T12:00:01+00:00")

    assert find_stale([task], NOW) == []


def test_closed_task_is_never_stale_even_when_expired():
    task = _task(status="closed", expires_at="2026-06-24T11:59:59+00:00")

    assert find_stale([task], NOW) == []


def test_scan_returns_stale_active_and_total_for_task_directory(tmp_path):
    expired = _task(task_id="expired", expires_at="2026-06-24T11:59:59+00:00")
    active = _task(task_id="active", expires_at="2026-06-24T12:00:01+00:00")
    closed = _task(
        task_id="closed",
        status="closed",
        expires_at="2026-06-24T11:59:59+00:00",
    )

    (tmp_path / "01_expired.yml").write_text(_yaml(expired), encoding="utf-8")
    (tmp_path / "02_active.yaml").write_text(_yaml(active), encoding="utf-8")
    (tmp_path / "03_closed.yml").write_text(_yaml(closed), encoding="utf-8")

    result = scan(str(tmp_path), NOW)

    assert result == {
        "stale": [expired],
        "active": [expired, active],
        "total": 3,
    }


def _yaml(task):
    lines = []
    for key, value in task.items():
        if isinstance(value, list):
            if value:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: []")
        else:
            lines.append(f'{key}: "{value}"')
    return "\n".join(lines) + "\n"
