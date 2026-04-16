"""端到端联考验证脚本。模拟 2 所学校完整联考流程。

Usage: python scripts/e2e_joint_exam.py
Requires: edu-cloud running on port 9000
"""
import asyncio
import httpx

CLOUD_URL = "http://localhost:9000"


async def main():
    async with httpx.AsyncClient(base_url=CLOUD_URL) as c:
        # Step 1: Login as admin
        r = await c.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
        assert r.status_code == 200, f"Login failed: {r.text}"
        token = r.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        print("✓ Step 1: Admin login")

        # Step 2: Create 2 schools
        r1 = await c.post("/api/v1/schools", json={"name": "出题校", "code": "E2E_S1", "district": "测试区"}, headers=auth)
        assert r1.status_code == 201
        r2 = await c.post("/api/v1/schools", json={"name": "参与校", "code": "E2E_S2", "district": "测试区"}, headers=auth)
        assert r2.status_code == 201
        s1_id, s1_key = r1.json()["id"], r1.json()["api_key"]
        s2_id, s2_key = r2.json()["id"], r2.json()["api_key"]
        print("✓ Step 2: 2 schools created")

        # Step 3: Create joint exam (creator = s1)
        er = await c.post("/api/v1/joint-exams", json={
            "name": "E2E 联考", "creator_school_id": s1_id,
            "subjects": [{"code": "YW", "name": "语文", "max_score": 150},
                         {"code": "SX", "name": "数学", "max_score": 150}],
        }, headers=auth)
        assert er.status_code == 201
        exam_id = er.json()["id"]
        print(f"✓ Step 3: Exam created ({exam_id[:8]}...)")

        # Step 4: Add participant school
        await c.post(f"/api/v1/joint-exams/{exam_id}/participants",
            json={"school_id": s2_id}, headers=auth)
        print("✓ Step 4: Participant added")

        # Step 5: Upload templates (as creator school via sync)
        for subj in ["YW", "SX"]:
            r = await c.post("/api/v1/sync/templates", files={
                "skeleton": ("skeleton.json", b'{"regions": []}', "application/json"),
                "pdf": ("template.pdf", b"%PDF-fake-content", "application/pdf"),
            }, data={"joint_exam_id": exam_id, "subject_code": subj,
                     "answer_schema": f'[{{"id": "q1", "max_score": 75}}, {{"id": "q2", "max_score": 75}}]'},
               headers={"X-API-Key": s1_key})
            assert r.status_code == 200, f"Template upload {subj} failed: {r.text}"
        print("✓ Step 5: Templates uploaded (auto → templates_ready)")

        # Step 6: Distribute
        r = await c.post(f"/api/v1/joint-exams/{exam_id}/distribute", headers=auth)
        assert r.status_code == 200
        print("✓ Step 6: Distributed")

        # Step 7: Pull exams (as participant school)
        r = await c.get("/api/v1/sync/joint-exams", headers={"X-API-Key": s2_key})
        assert r.status_code == 200
        exams = r.json()["joint_exams"]
        assert len(exams) >= 1
        assert "template_url" in exams[0]["subjects"][0]
        print("✓ Step 7: Participant pulled exams (with template URLs)")

        # Step 8: Submit scores from both schools
        for key, sid, prefix in [(s1_key, s1_id, "S1"), (s2_key, s2_id, "S2")]:
            for subj in ["YW", "SX"]:
                students = [
                    {"student_name": f"{prefix}_学生{i}", "student_number": f"{prefix}_{i:03d}",
                     "total_score": 60 + i * 10,
                     "detail_scores": [{"question_id": "q1", "score": 30+i*5, "max_score": 75},
                                       {"question_id": "q2", "score": 30+i*5, "max_score": 75}]}
                    for i in range(1, 6)
                ]
                r = await c.post("/api/v1/sync/scores", json={
                    "joint_exam_id": exam_id, "subject_code": subj,
                    "student_results": students,
                }, headers={"X-API-Key": key})
                assert r.status_code == 200, f"Score upload failed: {r.text}"
        print("✓ Step 8: Scores submitted (both schools, both subjects)")

        # Step 9: Check exam status → completed
        r = await c.get(f"/api/v1/joint-exams/{exam_id}", headers=auth)
        assert r.json()["status"] == "completed"
        print("✓ Step 9: Exam status → completed")

        # Step 10: View rankings
        r = await c.get(f"/api/v1/joint-exams/{exam_id}/results?subject_code=YW", headers=auth)
        assert r.status_code == 200
        rankings = r.json()
        assert len(rankings) == 10  # 5 students × 2 schools
        print(f"✓ Step 10: Rankings (top: {rankings[0]['student_name']} = {rankings[0]['total_score']})")

        # Step 11: View school comparison
        r = await c.get(f"/api/v1/joint-exams/{exam_id}/results/by-school", headers=auth)
        assert r.status_code == 200
        comparison = r.json()
        assert len(comparison) >= 2
        print(f"✓ Step 11: School comparison ({len(comparison)} entries)")

        print("\n=== E2E 联考验证完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
