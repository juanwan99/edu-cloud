import pytest


class TestTeamRegistration:
    def test_edu_data_registered(self):
        from edu_cloud.ai.agent_team import teams
        import edu_cloud.ai.teams  # noqa: F401 — trigger registration
        team = teams.get("edu_data")
        assert team is not None
        assert len(team.agents) >= 1

    def test_knowledge_registered(self):
        from edu_cloud.ai.agent_team import teams
        import edu_cloud.ai.teams  # noqa: F401
        team = teams.get("knowledge")
        assert team is not None
        assert len(team.agents) >= 1

    def test_homework_registered(self):
        from edu_cloud.ai.agent_team import teams
        import edu_cloud.ai.teams  # noqa: F401
        team = teams.get("homework")
        assert team is not None
        assert len(team.agents) >= 1

    def test_all_teams_have_descriptions(self):
        from edu_cloud.ai.agent_team import teams
        import edu_cloud.ai.teams  # noqa: F401
        for name in teams.list_teams():
            team = teams.get(name)
            assert team.description, f"Team '{name}' has no description"

    def test_tools_exist(self):
        """Every tool declared in a team must exist in the global ToolRegistry."""
        from edu_cloud.ai.agent_team import teams
        from edu_cloud.ai.registry import tools
        import edu_cloud.ai.teams  # noqa: F401
        import edu_cloud.ai.tools  # noqa: F401 — trigger tool registration

        all_registered = set(tools.list_tools())
        for name in teams.list_teams():
            team = teams.get(name)
            for tool_name in team.all_tools:
                assert tool_name in all_registered, (
                    f"Team '{name}' references tool '{tool_name}' which is not registered"
                )
