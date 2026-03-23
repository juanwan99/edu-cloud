"""paper-skill REST API 客户端。"""

import httpx
import logging
from edu_cloud.config import settings

logger = logging.getLogger(__name__)

class PaperService:
    """paper-skill REST API 客户端"""

    def __init__(self):
        self.base_url = settings.PAPER_SKILL_URL

    async def create_paper(
        self,
        budget_tier: str = "standard",
        title: str | None = None,
        seed_idea: str | None = None,
        journal_id: str | None = None,
    ) -> dict:
        """调用 paper-skill 创建论文任务"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/api/paper/create",
                    json={
                        "budget_tier": budget_tier,
                        "title": title,
                        "seed_idea": seed_idea,
                        "journal_id": journal_id,
                    },
                )
                data = resp.json()
                if data.get("success"):
                    return data["data"]
                return {"error": data.get("error", "创建失败")}
        except Exception as e:
            logger.error(f"paper-skill create failed: {e}")
            return {"error": f"论文服务不可用: {e}"}

    async def get_status(self, paper_id: str) -> dict:
        """查询论文进度"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.base_url}/api/paper/{paper_id}/status")
                data = resp.json()
                if data.get("success"):
                    return data["data"]
                return {"error": data.get("error", "查询失败")}
        except Exception as e:
            logger.error(f"paper-skill status failed: {e}")
            return {"error": f"论文服务不可用: {e}"}
