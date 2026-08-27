"""检索逻辑：query → 向量 → 相似度检索 → 片段列表。

支持按分类 metadata filter 进行精准检索：
  1. 从查询中提取类别关键词（如 "跑步" → endurance）
  2. 优先在匹配分类内检索，若结果不足则扩展到全库
"""

import logging
import re
from typing import List, Optional

from rag.config import TOP_K
from rag.embedder import Embedder
from rag.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)

# 类别关键词映射（与 AutoClassifyAgent 保持一致）
_CATEGORY_HINTS = {
    "strength": ["力量", "力量训练", "力量训练", "strength", "power", "肌肉", "负重", "抗阻"],
    "endurance": ["耐力", "有氧", "跑步", "长跑", "马拉松", "endurance", "aerobic", "pace", "配速"],
    "nutrition": ["营养", "饮食", "蛋白质", "碳水", "补剂", "nutrition", "diet", "protein", "补水"],
    "physiology": ["生理", "心率", "VO2", "血乳酸", "physiology", "heart rate", "代谢"],
    "technique": ["技术", "姿势", "动作", "technique", "form", "跑姿", "步态"],
    "sports_science": ["科学", "研究", "训练", "周期化", "sports science", "research"],
}


def _detect_query_categories(query: str) -> List[str]:
    """从查询中检测可能的类别，用于 metadata filter。"""
    text_lower = query.lower()
    detected = []
    for cat, keywords in _CATEGORY_HINTS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                detected.append(cat)
                break
    return detected


def retrieve_context(
    query: str,
    embedder: Embedder,
    vector_store_manager: VectorStoreManager,
    top_k: int = TOP_K,
    categories: Optional[List[str]] = None,
) -> List[dict]:
    """检索与 query 语义相关的知识片段。

    支持两类分类过滤:
    1. 显式传入 categories 参数（管理员手动指定）
    2. 自动检测查询中的类别关键词

    :param categories: 显式分类过滤器。
    :return: ``[{"content", "source", "chunk_index", "distance"}]``，无匹配返回 []。
    """
    query_embedding = embedder.embed_query(query)

    # 确定分类过滤器
    filter_categories = categories
    if not filter_categories:
        filter_categories = _detect_query_categories(query)

    # 如果检测到分类，尝试在分类内检索
    if filter_categories:
        try:
            results = vector_store_manager.retrieve_with_filter(
                query_embedding, top_k=top_k, categories=filter_categories
            )
            if results:
                logger.info(
                    "分类过滤检索: categories=%s, results=%d",
                    filter_categories, len(results),
                )
                return results
        except Exception as e:
            logger.warning("分类过滤检索失败，回退到全库: %s", e)

    # 回退：全库检索
    return vector_store_manager.retrieve(query_embedding, top_k=top_k)
