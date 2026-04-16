"""Knowledge base team: curriculum search, textbook, concepts, gaokao index."""
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.agent_team import AgentTeam, teams

_team = AgentTeam(
    name="knowledge",
    description="知识库查询：课标搜索、教材内容、知识点概念、高考考点索引、知识树",
    agents=[
        AgentSpec(
            name="knowledge_search",
            description="搜索课标、教材、知识点",
            tools=[
                "search_curriculum", "search_textbook",
                "get_concept_info", "search_gaokao",
                "get_knowledge_tree", "get_question_knowledge_points",
            ],
            task_complexity="retrieval",
            max_turns=10,
        ),
    ],
    execution="sequential",
)

teams.register(_team)
