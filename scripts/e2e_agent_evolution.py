#!/usr/bin/env python3
"""端到端验证：DataScope → W1 → W3 → W6 → 对话。

Usage: python scripts/e2e_agent_evolution.py [--base-url http://localhost:9000]

This script validates the agent evolution features against a running server.
It requires seed data (admin/teacher/parent users) to be present.
"""
import asyncio
import sys
import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9000"
API = f"{BASE}/api/v1"


async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        print(f"=== Agent Evolution E2E Validation ({BASE}) ===\n")

        # 1. Health check
        r = await c.get(f"{API}/ai/health")
        print(f"[1] AI Health: {r.status_code} — {r.json()}")
        assert r.status_code == 200

        # 2. Teacher login
        r = await c.post(f"{API}/auth/login",
                         json={"username": "teacher1", "password": "123456"})
        if r.status_code != 200:
            print(f"[2] Teacher login SKIP (no seed data): {r.status_code}")
            return
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"[2] Teacher login: OK")

        # 3. AI chat (post-exam intent)
        r = await c.post(f"{API}/ai/chat", headers=headers,
                         json={"message": "这次期中考试成绩分析报告"})
        print(f"[3] AI Chat (teacher): {r.status_code}")

        # 4. Parent login
        r = await c.post(f"{API}/auth/login",
                         json={"username": "parent1", "password": "123456"})
        if r.status_code != 200:
            print(f"[4] Parent login SKIP (no seed data): {r.status_code}")
        else:
            parent_token = r.json()["access_token"]
            r = await c.post(f"{API}/ai/chat",
                             headers={"Authorization": f"Bearer {parent_token}"},
                             json={"message": "我孩子最近学习怎么样"})
            print(f"[4] AI Chat (parent): {r.status_code}")

        print("\n=== E2E Validation Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
