"""Tests for CLI argument parsing."""
import pytest
from edu_cloud.cli.agent import parse_args


class TestCLIArgs:
    def test_parse_valid(self):
        args = parse_args(["--school", "YCSY2026", "--role", "principal", "分析成绩"])
        assert args.school == "YCSY2026"
        assert args.role == "principal"
        assert args.message == "分析成绩"

    def test_missing_school(self):
        with pytest.raises(SystemExit):
            parse_args(["--role", "principal", "分析"])

    def test_missing_message(self):
        with pytest.raises(SystemExit):
            parse_args(["--school", "YCSY2026", "--role", "principal"])

    def test_default_role(self):
        args = parse_args(["--school", "YCSY2026", "分析成绩"])
        assert args.role == "principal"
