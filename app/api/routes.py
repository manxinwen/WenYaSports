"""RESTful API routes for the FIT multi-agent analysis service."""

import json
import logging
import os
import tempfile
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.agents.coordinator_agent import CoordinatorAgent, CoordinatorError
from app.db import database
from app.services.fit_parser import parse_fit_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

UPLOAD_DIR_DEFAULT = os.path.join(tempfile.gettempdir(), "fit_uploads")


def create_coordinator() -> CoordinatorAgent:
    """Build the full multi-agent pipeline."""
    from app.agents.feature_extractor_agent import FeatureExtractorAgent
    from app.agents.memory_agent import MemoryAgent
    from app.agents.parser_agent import ParserAgent
    from app.agents.recommendation_agent import RecommendationAgent

    return CoordinatorAgent(
        parser_agent=ParserAgent(),
        feature_agent=FeatureExtractorAgent(),
        memory_agent=MemoryAgent(),
        recommendation_agent=RecommendationAgent(),
    )


_coordinator: Optional[CoordinatorAgent] = None


def get_coordinator() -> CoordinatorAgent:
    """FastAPI dependency returning the shared coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = create_coordinator()
    return _coordinator


def _save_upload(file: UploadFile) -> str:
    """Persist the uploaded file and return its path."""
    upload_dir = os.environ.get("FIT_UPLOAD_DIR") or UPLOAD_DIR_DEFAULT
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = os.path.basename(file.filename or "upload.fit")
    file_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}_{safe_name}")
    content = file.file.read()
    with open(file_path, "wb") as fh:
        fh.write(content)
    return file_path


@router.post("/upload")
async def upload_fit(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: str = Form(...),
    coordinator: CoordinatorAgent = Depends(get_coordinator),
):
    """Upload a FIT file, run the multi-agent pipeline and return results."""
    if not file.filename or not file.filename.lower().endswith(".fit"):
        raise HTTPException(status_code=400, detail="请上传 .fit 格式的运动文件")

    file_path = _save_upload(file)
    try:
        result = coordinator.run(file_path, user_id, session_id)
    except CoordinatorError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    except Exception as exc:
        logger.exception("处理上传文件失败")
        raise HTTPException(status_code=500, detail=f"处理活动数据失败: {exc}") from exc

    rows = database.get_recent_activities(user_id, limit=1)
    activity_id = rows[0]["activity_id"] if rows else None

    return {
        "activity_id": activity_id,
        "metadata": result["activity_metadata"],
        "features": result["activity_features"],
        "recommendation": result["recommendation"],
        "user_profile_summary": result["user_profile_summary"],
    }


@router.get("/activities")
def list_activities(
    user_id: str = Query(...),
    limit: int = Query(10, ge=1, le=100),
):
    """Return the most recent activities (brief summary) for a user."""
    rows = database.get_recent_activities(user_id, limit=limit)
    activities = []
    for row in rows:
        features = json.loads(row["features_json"] or "{}")
        metadata = json.loads(row["metadata_json"] or "{}")
        activities.append(
            {
                "activity_id": row["activity_id"],
                "user_id": row["user_id"],
                "date": row["date"],
                "sport": metadata.get("sport"),
                "total_distance_m": features.get("total_distance_m"),
                "total_duration_seconds": features.get("total_duration_seconds"),
                "training_load": features.get("training_load"),
                "intensity_distribution": features.get("intensity_distribution"),
            }
        )
    return {"activities": activities, "total": len(activities)}


@router.get("/activities/{activity_id}")
def get_activity_detail(activity_id: int):
    """Return full activity data, including track points re-parsed from file."""
    row = database.get_activity(activity_id)
    if row is None:
        raise HTTPException(status_code=404, detail="活动不存在")

    metadata = json.loads(row["metadata_json"] or "{}")
    features = json.loads(row["features_json"] or "{}")
    recommendation = json.loads(row["recommendation_json"] or "{}")

    records: list = []
    file_path = row.get("file_path")
    if file_path and os.path.exists(file_path):
        try:
            parsed = parse_fit_file(file_path)
            records = parsed["records"]
            if not metadata:
                metadata = parsed["metadata"]
        except Exception:
            logger.warning("重新解析FIT文件失败: %s", file_path)
            records = []

    return {
        "activity_id": activity_id,
        "date": row["date"],
        "metadata": metadata,
        "features": features,
        "recommendation": recommendation,
        "records": records,
    }


@router.get("/user/profile")
def get_user_profile(user_id: str = Query(...)):
    """Return the stored user profile."""
    profile = database.get_user_profile(user_id)
    return {"user_id": user_id, "profile": profile}


# ----------------------------------------------------------------------
# RAG 个人 AI 私教：知识问答
# ----------------------------------------------------------------------
_rag_knowledge_agent = None


def _get_rag_agent():
    """懒加载 KnowledgeAgent（避免无知识库时拖慢启动）。"""
    global _rag_knowledge_agent
    if _rag_knowledge_agent is None:
        from rag.embedder import FakeEmbedder, MiniLMEmbedder
        from rag.knowledge_agent import KnowledgeAgent
        from rag.llm_client import OpenAILLMClient
        from rag.vector_store import VectorStoreManager

        embedder_kind = os.environ.get("RAG_EMBEDDER", "fake")
        embedder = (
            MiniLMEmbedder() if embedder_kind == "minilm" else FakeEmbedder()
        )
        store = VectorStoreManager()
        llm = OpenAILLMClient()
        _rag_knowledge_agent = KnowledgeAgent(
            embedder=embedder,
            vector_store_manager=store,
            llm_client=llm,
            memory_agent=get_coordinator().memory_agent,
        )
    return _rag_knowledge_agent


@router.post("/chat")
async def rag_chat(body: dict):
    """RAG 知识问答：输入 {user_id, question}，返回 {answer, sources}。"""
    user_id = (body.get("user_id") or "").strip()
    question = (body.get("question") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")

    try:
        result = _get_rag_agent().run(user_id, question)
    except Exception as exc:
        logger.exception("RAG 问答失败")
        raise HTTPException(status_code=500, detail=f"RAG 问答失败: {exc}") from exc
    return {"user_id": user_id, "question": question, **result}
