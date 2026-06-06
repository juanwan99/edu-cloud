from edu_cloud.api.module_middleware import ROUTE_MODULE_MAP


def test_bank_api_belongs_to_research_module():
    assert ROUTE_MODULE_MAP['/api/v1/bank'] == 'research'


def test_profile_api_belongs_to_study_analytics_module():
    # R4 子任务（0.6C）：学情画像后端门控实装，收口 profile-backend-fail-open drift。
    # profile router 全端点为学情语义（trend/knowledge/error-patterns/class-weakness/ai-diagnosis），归 study_analytics。
    assert ROUTE_MODULE_MAP['/api/v1/profile'] == 'study_analytics'
