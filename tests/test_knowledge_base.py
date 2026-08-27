"""认证系统测试。"""

import pytest
from app.auth.auth import (
    authenticate, create_token, verify_token,
    get_current_user, UserRole, AuthUser,
    ADMIN_USERNAME, ADMIN_PASSWORD, TOKEN_TTL,
)


class TestAuthentication:
    def test_admin_login(self):
        user = authenticate(ADMIN_USERNAME, ADMIN_PASSWORD)
        assert user is not None
        assert user.is_admin
        assert user.role == UserRole.ADMIN
        assert user.user_id == "admin_001"

    def test_user_login(self):
        user = authenticate("testuser", "pass123")
        assert user is not None
        assert not user.is_admin
        assert user.role == UserRole.USER

    def test_wrong_password(self):
        user = authenticate(ADMIN_USERNAME, "wrong")
        assert user is None

    def test_empty_credentials(self):
        user = authenticate("", "")
        assert user is None

    def test_token_roundtrip(self):
        user = AuthUser(user_id="test_1", role=UserRole.ADMIN, username="test")
        token = create_token(user)
        decoded = verify_token(token)
        assert decoded is not None
        assert decoded.user_id == "test_1"
        assert decoded.role == UserRole.ADMIN

    def test_invalid_token(self):
        decoded = verify_token("invalid_token")
        assert decoded is None

    def test_expired_token(self):
        import time
        user = AuthUser(user_id="test", role=UserRole.USER)
        # Manually create an expired token
        old_ts = int(time.time()) - TOKEN_TTL - 10
        payload = f"test:user:{old_ts}"
        import hmac, hashlib
        sig = hmac.new(b"wenyasports-secret-key-change-in-production", payload.encode(), hashlib.sha256).hexdigest()
        expired_token = f"{payload}:{sig}"
        decoded = verify_token(expired_token)
        assert decoded is None

    def test_auth_user_to_dict(self):
        user = AuthUser(user_id="u1", role=UserRole.ADMIN, username="admin")
        d = user.to_dict()
        assert d["user_id"] == "u1"
        assert d["role"] == "admin"
        assert d["is_admin"] is True


class TestAutoClassifyAgent:
    @pytest.fixture
    def agent(self):
        from app.agents.auto_classify_agent import AutoClassifyAgent
        return AutoClassifyAgent()

    def test_classify_strength_text(self, agent):
        text = "力量训练是提升肌肉力量的关键。通过负重训练、抗阻训练和爆发力训练，可以有效增强肌肉肥大和最大力量。"
        result = agent.classify(text, "strength_training.md")
        assert result["primary_category"] == "strength"
        assert result["confidence"] > 0

    def test_classify_nutrition_text(self, agent):
        text = "运动营养对于提升运动表现至关重要。运动员需要摄入足够的蛋白质、碳水化合物和健康脂肪。补水和电解质平衡也是关键。"
        result = agent.classify(text)
        assert result["primary_category"] == "nutrition"
        assert result["confidence"] > 0

    def test_classify_endurance_text(self, agent):
        text = "耐力训练包括有氧运动和无氧运动。VO2max 是衡量最大摄氧量的重要指标。长距离跑步和马拉松训练能有效提升耐力。"
        result = agent.classify(text)
        assert result["primary_category"] == "endurance"
        assert result["confidence"] > 0

    def test_classify_physiology_text(self, agent):
        text = "运动生理学研究心率、血乳酸、肌纤维类型和能量代谢。快肌纤维和慢肌纤维在运动中发挥不同作用。"
        result = agent.classify(text)
        assert result["primary_category"] == "physiology"

    def test_low_confidence_needs_review(self, agent):
        text = "这是一段没有明显特征的普通文本，谈论了一些日常的事情"
        result = agent.classify(text)
        assert result["primary_category"] == "general"

    def test_filename_weighting(self, agent):
        text = "这是一些普通内容"
        result = agent.classify(text, "nutrition_guide_for_athletes.pdf")
        # 文件名包含 nutrition，应该提高 nutrition 分类的分数
        assert result is not None

    def test_supported_categories(self, agent):
        cats = agent.get_supported_categories()
        assert len(cats) >= 7
        cat_ids = [c["id"] for c in cats]
        assert "strength" in cat_ids
        assert "endurance" in cat_ids
        assert "nutrition" in cat_ids

    def test_candidates_sorted(self, agent):
        text = "力量训练和肌肉肥大的营养补充指南"
        result = agent.classify(text)
        candidates = result["candidates"]
        assert len(candidates) >= 2
        # 应该按置信度降序
        for i in range(len(candidates) - 1):
            assert candidates[i]["confidence"] >= candidates[i + 1]["confidence"]

    def test_reasoning_present(self, agent):
        text = "运动生理学和心率训练"
        result = agent.classify(text)
        assert "reasoning" in result
        assert len(result["reasoning"]) > 0


class TestKnowledgeBaseService:
    @pytest.fixture
    def kb(self):
        from app.services.knowledge_base import KnowledgeBaseService
        return KnowledgeBaseService()

    @pytest.fixture
    def sample_content(self):
        return (
            "# 运动营养基础\n\n"
            "蛋白质是肌肉修复的关键营养素。每公斤体重建议摄入1.6-2.2克蛋白质。\n\n"
            "碳水化合物是运动的主要能量来源，尤其是在耐力运动中。\n\n"
            "补水和电解质平衡对于运动表现至关重要。"
        ).encode("utf-8")

    def test_upload_and_index(self, kb, sample_content):
        result = kb.upload_and_index(
            file_content=sample_content,
            original_filename="nutrition_basics.md",
            admin_id="admin_001",
        )
        assert result["file_id"] is not None
        assert result["category"] is not None
        assert result["status"] in ("indexed", "pending")
        assert result["stored_path"] is not None

        # 清理
        kb.delete_file(result["file_id"])

    def test_upload_with_force_category(self, kb, sample_content):
        result = kb.upload_and_index(
            file_content=sample_content,
            original_filename="test.md",
            admin_id="admin_001",
            force_category="nutrition",
        )
        assert result["category"] == "nutrition"
        assert result["confidence"] == 1.0

        # 清理
        kb.delete_file(result["file_id"])

    def test_list_files(self, kb, sample_content):
        # 先上传一个文件
        upload_result = kb.upload_and_index(
            file_content=sample_content,
            original_filename="list_test.md",
            admin_id="admin_001",
        )
        files = kb.list_files()
        assert len(files) > 0
        assert any(f["file_id"] == upload_result["file_id"] for f in files)

        # 清理
        kb.delete_file(upload_result["file_id"])

    def test_delete_file(self, kb, sample_content):
        upload_result = kb.upload_and_index(
            file_content=sample_content,
            original_filename="delete_test.md",
            admin_id="admin_001",
        )
        result = kb.delete_file(upload_result["file_id"])
        assert result["success"] is True

        # 确认已删除
        from app.db import database
        file_info = database.get_knowledge_file(upload_result["file_id"])
        assert file_info is None

    def test_update_file_category(self, kb, sample_content):
        upload_result = kb.upload_and_index(
            file_content=sample_content,
            original_filename="cat_test.md",
            admin_id="admin_001",
            force_category="general",
        )
        result = kb.update_file_category(upload_result["file_id"], "nutrition")
        assert result["success"] is True
        assert result["new_category"] == "nutrition"

        kb.delete_file(upload_result["file_id"])

    def test_get_stats(self, kb, sample_content):
        upload_result = kb.upload_and_index(
            file_content=sample_content,
            original_filename="stats_test.md",
            admin_id="admin_001",
        )
        stats = kb.get_stats()
        assert "total_files" in stats
        assert "categories" in stats

        kb.delete_file(upload_result["file_id"])

    def test_reclassify_file(self, kb, sample_content):
        upload_result = kb.upload_and_index(
            file_content=sample_content,
            original_filename="reclassify_test.md",
            admin_id="admin_001",
            force_category="general",
        )
        result = kb.reclassify_file(upload_result["file_id"])
        assert result["success"] is True

        kb.delete_file(upload_result["file_id"])

    def test_rebuild_index(self, kb, sample_content):
        # 上传两个文件
        r1 = kb.upload_and_index(
            file_content=sample_content,
            original_filename="rebuild_1.md",
            admin_id="admin_001",
        )
        r2 = kb.upload_and_index(
            file_content=sample_content,
            original_filename="rebuild_2.md",
            admin_id="admin_001",
        )

        result = kb.rebuild_index()
        assert "total_files" in result
        assert "indexed" in result

        # 清理
        kb.delete_file(r1["file_id"])
        kb.delete_file(r2["file_id"])


class TestKnowledgeAPI:
    """通过 FastAPI TestClient 测试知识库 API 端点。"""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    @pytest.fixture
    def admin_token(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wenyasports2024",
        })
        return resp.json()["token"]

    def test_login_success(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wenyasports2024",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["is_admin"] is True

    def test_login_wrong_password(self, client):
        resp = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "wrong",
        })
        assert resp.status_code == 401

    def test_get_categories(self, client):
        resp = client.get("/api/auth/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data
        assert len(data["categories"]) >= 7

    def test_knowledge_list_requires_auth(self, client):
        resp = client.get("/api/knowledge/list")
        assert resp.status_code == 401

    def test_knowledge_list_as_admin(self, client, admin_token):
        resp = client.get(
            "/api/knowledge/list",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_knowledge_stats_as_admin(self, client, admin_token):
        resp = client.get(
            "/api/knowledge/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total_files" in data

    def test_knowledge_upload_as_admin(self, client, admin_token):
        import io
        content = (
                "# 力量训练指南\n\n"
                "力量训练可以增加肌肉力量和肌肉肥大。\n"
                "使用杠铃、哑铃等器械进行抗阻训练。\n"
            ).encode("utf-8")
        resp = client.post(
            "/api/knowledge/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"force_category": "strength"},
            files={"file": ("strength.md", content, "text/markdown")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_id"] is not None
        assert data["status"] == "indexed"

        # 清理
        client.post(
            f"/api/knowledge/{data['file_id']}/delete",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    def test_knowledge_upload_invalid_ext(self, client, admin_token):
        resp = client.post(
            "/api/knowledge/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("test.docx", b"content", "application/msword")},
        )
        assert resp.status_code == 400

    def test_knowledge_classify_preview(self, client, admin_token):
        content = "运动营养和蛋白质摄入对于运动员至关重要".encode("utf-8")
        resp = client.post(
            "/api/knowledge/classify",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("test.md", content, "text/markdown")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "primary_category" in data
        assert "confidence" in data

    def test_knowledge_update_category(self, client, admin_token):
        # 先上传
        content = "测试内容".encode("utf-8")
        upload_resp = client.post(
            "/api/knowledge/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"force_category": "general"},
            files={"file": ("cat_test.md", content, "text/markdown")},
        )
        file_id = upload_resp.json()["file_id"]

        # 修改分类
        resp = client.post(
            f"/api/knowledge/{file_id}/category",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"new_category": "strength"},
        )
        assert resp.status_code == 200

        # 清理
        client.post(
            f"/api/knowledge/{file_id}/delete",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    def test_user_cannot_access_admin(self, client):
        # 用普通用户登录
        login_resp = client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "pass123",
        })
        token = login_resp.json()["token"]

        resp = client.get(
            "/api/knowledge/list",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
