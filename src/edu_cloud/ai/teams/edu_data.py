"""Education data analysis team: exam scores, class comparisons, reports."""
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.agent_team import AgentTeam, teams

_team = AgentTeam(
    name="edu_data",
    description="教育数据分析：考试成绩查询、学情分析、班级对比、年级统计、学生排名",
    agents=[
        AgentSpec(
            name="data_query",
            description="查询考试数据、成绩、班级信息",
            tools=[
                "get_exam_list", "get_exam_detail", "get_subject_questions",
                "get_class_list", "get_class_roster", "search_students", "get_student_learning_profile",
            ],
            task_complexity="data_query",
            max_turns=8,
        ),
        AgentSpec(
            name="analytics",
            description="统计分析：成绩分布、题目得分率、班级对比、排名",
            tools=[
                "get_exam_summary", "get_score_distribution", "get_question_analysis",
                "get_student_scores", "get_class_scores",
                "compare_classes", "rank_students", "get_grade_aggregates",
                "get_exam_scores", "get_class_stats",
            ],
            task_complexity="data_query",
            max_turns=10,
        ),
        AgentSpec(
            name="reporter",
            description="生成分析报告和教师评语",
            tools=["generate_report", "generate_comment"],
            task_complexity="generation",
            model_tier=1,
            max_turns=5,
        ),
    ],
    execution="sequential",
)

teams.register(_team)
