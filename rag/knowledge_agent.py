"""KnowledgeAgent：个人 AI 私教的知识问答 Agent。

流程：
1. 从 MemoryAgent（依赖注入）获取用户画像与近期训练状态；
2. 对问题做向量检索，取得相关知识片段；
3. 拼装 Prompt（画像 + 训练状态 + 知识 + 问题）调用 LLM；
4. 返回回答与引用的 sources。

容错：
- LLM 调用失败 → 返回基于检索知识的规则兜底回答；
- 知识库为空 / 未检索到 → 明确提示，不产生幻觉。
"""

import logging
from typing import Any, Dict, List, Optional

from rag.embedder import Embedder
from rag.prompts import (
    KNOWLEDGE_QA_PROMPT,
    format_knowledge,
    format_training_status,
    format_user_profile,
)
from rag.retriever import retrieve_context
from rag.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)


class KnowledgeAgent:
    """个人 AI 私教知识问答。

    :param embedder: 向量化实现。
    :param vector_store_manager: 知识库向量存储。
    :param llm_client: LLM 调用抽象（可 mock）。
    :param memory_agent: 提供 ``get_context(user_id, session_id) -> dict``
                         的对象（如 app.agents.memory_agent.MemoryAgent）。
    """

    def __init__(
        self,
        embedder: Embedder,
        vector_store_manager: VectorStoreManager,
        llm_client,
        memory_agent: Optional[Any] = None,
        top_k: int = 4,
    ):
        self.embedder = embedder
        self.vector_store_manager = vector_store_manager
        self.llm_client = llm_client
        self.memory_agent = memory_agent
        self.top_k = top_k

    def _get_user_context(self, user_id: str) -> Dict[str, Any]:
        """从 MemoryAgent 获取用户上下文；未注入时返回空。"""
        if self.memory_agent is None:
            return {}
        try:
            return self.memory_agent.get_context(user_id, session_id=f"rag_{user_id}")
        except Exception as exc:  # noqa: BLE001 - 记忆故障不阻断问答
            logger.warning("获取用户上下文失败: %s", exc)
            return {}

    def run(self, user_id: str, question: str) -> Dict[str, Any]:
        """回答问题，返回 ``{"answer", "sources"}``。

        :return: ``{"answer": str, "sources": [{"source", "content"}]}``。
        """
        context = self._get_user_context(user_id)
        profile = context.get("user_profile") or {}
        status = {
            "recent_load_7d": context.get("recent_load_7d"),
            **context.get("short_term_context", {}),
        }

        # 检索知识
        passages = retrieve_context(
            question, self.embedder, self.vector_store_manager, top_k=self.top_k
        )
        knowledge_text, source_note = format_knowledge(passages)

        # 拼装 Prompt
        prompt = KNOWLEDGE_QA_PROMPT.format(
            user_profile=format_user_profile(profile),
            training_status=format_training_status(status),
            knowledge=knowledge_text,
            question=question,
            source_note=source_note,
        )

        try:
            answer = self.llm_client.chat(
                [
                    {
                        "role": "system",
                        "content": "你是专业的运动科学教练，回答必须基于提供的知识，语言简洁专业。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
        except Exception as exc:  # noqa: BLE001 - LLM 故障走规则兜底
            logger.warning("LLM 回答失败，使用兜底回答: %s", exc)
            answer = self._fallback_answer(passages, question)

        sources = [
            {"source": p["source"], "content": p["content"]} for p in passages
        ]
        return {"answer": answer, "sources": sources}

    def _fallback_answer(self, passages: List[dict], question: str) -> str:
        """LLM 不可用时的规则兜底回答。"""
        if not passages:
            return "抱歉，当前知识库暂无与该问题相关的内容，请稍后重试或查看基础训练指南。"
        snippet = passages[0]["content"][:200]
        return (
            "（LLM 服务暂不可用，以下为知识库检索结果摘要，供参考）\n"
            f"与问题「{question}」最相关的内容：\n{snippet}\n"
            "建议：结合自身近期训练负荷（近 7 天累计）合理安排恢复，必要时咨询专业教练。"
        )
