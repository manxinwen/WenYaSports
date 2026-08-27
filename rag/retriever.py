"""检索逻辑：query → 扩展 → 混合检索 → 重排序 → 片段列表。

完整的 RAG 检索管线：
1. 查询扩展（同义词 + 领域术语）
2. 元数据分类过滤
3. 向量 + 关键词混合检索（RRF 融合）
4. MMR 多样性重排
5. 元数据规则重排
6. 上下文丰富
"""

import logging
from typing import List, Optional

from rag.config import TOP_K
from rag.embedder import Embedder
from rag.hybrid_retriever import HybridRetriever
from rag.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)


def _detect_query_categories(query: str) -> List[str]:
    """从查询中检测可能的类别。"""
    _CATEGORY_HINTS = {
        "strength": ["力量", "力量训练", "strength", "power", "肌肉", "负重", "抗阻", "增肌"],
        "endurance": ["耐力", "有氧", "跑步", "长跑", "马拉松", "endurance", "aerobic", "配速", "跑步"],
        "nutrition": ["营养", "饮食", "蛋白质", "碳水", "补剂", "nutrition", "diet", "protein", "补水", "减脂"],
        "physiology": ["生理", "心率", "VO2", "血乳酸", "physiology", "heart rate", "代谢", "VO2max"],
        "technique": ["技术", "姿势", "动作", "technique", "form", "跑姿", "步态", "拉伸"],
        "sports_science": ["科学", "研究", "训练", "周期化", "sports science", "research", "恢复", "热身"],
    }
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
    use_hybrid: bool = True,
) -> List[dict]:
    """完整的混合检索管线。

    Args:
        query: 用户查询
        embedder: 嵌入模型
        vector_store_manager: 向量存储
        top_k: 返回数量
        categories: 显式分类过滤
        use_hybrid: 是否使用混合检索

    Returns:
        排序后的结果列表
    """
    # 确定分类过滤器
    filter_categories = categories
    if not filter_categories:
        filter_categories = _detect_query_categories(query)

    if use_hybrid:
        # 使用混合检索引擎
        retriever = HybridRetriever(vector_store_manager, embedder)
        return retriever.search(
            query=query,
            categories=filter_categories if filter_categories else None,
            top_k=top_k,
        )
    else:
        # 纯向量检索（降级）
        query_embedding = embedder.embed_query(query)
        return vector_store_manager.retrieve_with_filter(
            query_embedding,
            top_k=top_k,
            categories=filter_categories if filter_categories else None,
        )
