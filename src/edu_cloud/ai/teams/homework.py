"""Homework team: task management, grading, remedial recommendations."""
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.agent_team import AgentTeam, teams

_team = AgentTeam(
    name="homework",
    description="作业管理：布置作业、查看提交、批改、统计、补救推荐",
    agents=[
        AgentSpec(
            name="homework_ops",
            description="作业任务和提交管理",
            tools=[
                "list_homework_tasks", "get_homework_stats",
                "get_submission_details", "assign_homework", "recommend_remedial",
            ],
            task_complexity="data_query",
            max_turns=10,
        ),
    ],
    execution="sequential",
)

teams.register(_team)
