from edu_cloud.api.module_middleware import ROUTE_MODULE_MAP


def test_bank_api_belongs_to_research_module():
    assert ROUTE_MODULE_MAP['/api/v1/bank'] == 'research'
