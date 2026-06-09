"""Tests for CLI argument parsing."""
import json
import pytest
from edu_cloud.cli import agent
from edu_cloud.cli.agent import main, parse_args


class TestCLIArgs:
    def test_parse_valid(self):
        args = parse_args(["--school", "YCSY2026", "--role", "principal", "分析成绩"])
        assert args.school == "YCSY2026"
        assert args.role == "principal"
        assert args.message == "分析成绩"

    def test_missing_school(self):
        with pytest.raises(SystemExit):
            parse_args(["--role", "principal", "分析"])

    def test_missing_school_mentions_coze_live_smoke_escape(self, capsys):
        with pytest.raises(SystemExit):
            parse_args(["hello"])

        err = capsys.readouterr().err
        assert "--provider-status or --coze-live-smoke" in err

    def test_missing_message(self):
        with pytest.raises(SystemExit):
            parse_args(["--school", "YCSY2026", "--role", "principal"])

    def test_default_role(self):
        args = parse_args(["--school", "YCSY2026", "分析成绩"])
        assert args.role == "principal"

    def test_provider_status_does_not_require_school_or_message(self):
        args = parse_args(["--provider-status"])
        assert args.provider_status is True
        assert args.school is None
        assert args.message is None

    def test_coze_live_smoke_does_not_require_school_or_message(self):
        args = parse_args(["--coze-live-smoke"])
        assert args.coze_live_smoke is True
        assert args.school is None
        assert args.message is None

    def test_provider_status_prints_readiness_without_secrets(self, capsys, monkeypatch):
        from edu_cloud.config import settings

        monkeypatch.setattr(settings, "AI_COZE_ENABLED", True)
        monkeypatch.setattr(settings, "AI_COZE_BOT_ID", "bot-1")
        monkeypatch.setattr(settings, "AI_COZE_API_TOKEN", "pat-secret")

        main(["--provider-status"])

        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["preferred"] == "coze"
        assert data["readiness"]["coze"]["chat_ready"] is True
        assert "pat-secret" not in output

    def test_coze_live_smoke_exits_nonzero_when_unconfigured(self, capsys, monkeypatch):
        from edu_cloud.config import settings

        monkeypatch.setattr(settings, "AI_COZE_ENABLED", False)
        monkeypatch.setattr(settings, "AI_COZE_BOT_ID", "")
        monkeypatch.setattr(settings, "AI_COZE_API_TOKEN", "pat-secret")

        with pytest.raises(SystemExit) as exc_info:
            main(["--coze-live-smoke"])

        assert exc_info.value.code == 2
        output = capsys.readouterr().out
        data = json.loads(output)
        assert data["type"] == "error"
        assert data["data"]["message"] == "Coze provider is not configured"
        assert "pat-secret" not in output

    def test_coze_live_smoke_runs_when_configured(self, capsys, monkeypatch):
        async def fake_live_smoke(message=None):
            print(json.dumps({"type": "done", "data": {"message": message}}, ensure_ascii=False))
            return 0

        monkeypatch.setattr(agent, "_coze_live_smoke", fake_live_smoke)

        main(["--coze-live-smoke", "ping"])

        data = json.loads(capsys.readouterr().out)
        assert data["type"] == "done"
        assert data["data"]["message"] == "ping"
