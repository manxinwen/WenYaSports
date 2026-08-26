"""检索逻辑：query → 向量 → 相似度检索 → 片段列表。"""

import logging
from typing import List

from rag.config import TOP_K
from rag.embedder import Embedder
from rag.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)


def retrieve_context(
    query: str,
    embedder: Embedder,
    vector_store_manager: VectorStoreManager,
    top_k: int = TOP_K,
) -> List[dict]:
    """检索与 query 语义相关的知识片段。

    :return: ``[{"content", "source", "chunk_index", "distance"}]``，无匹配返回 []。
    """
    query_embedding = embedder.embed_query(query)
    return vector_store_manager.retrieve(query_embedding, top_k=top_k)
