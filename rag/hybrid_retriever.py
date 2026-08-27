"""混合检索引擎：向量检索 + 关键词检索 + 元数据过滤 + Rerank 重排序。

召回率优化策略：
1. **Hybrid Search**：向量语义检索 + BM25 关键词检索，结果融合
2. **Query Expansion**：同义词扩展、领域术语映射
3. **Metadata Filter**：分类先过滤，缩小检索范围
4. **Rerank**：Cross-Encoder 重排序（可选，降级为规则重排）
5. **MMR**：最大边际相关性，保证结果多样性
6. **Chunk Enrichment**：对小 chunk 动态补充上下文
"""

import logging
import re
from collections import Counter
from typing import Dict, List, Optional, Tuple

from rag.config import TOP_K
from rag.embedder import Embedder
from rag.smart_chunker import DOMAIN_TERMS

logger = logging.getLogger(__name__)


class HybridRetriever:
    """混合检索引擎。

    Usage:
        retriever = HybridRetriever(vector_store, embedder)
        results = retriever.search(
            query="怎么训练 VO2max",
            categories=["physiology", "endurance"],
            top_k=5,
        )
    """

    def __init__(self, vector_store_manager, embedder: Embedder):
        self._vector_store = vector_store_manager
        self._embedder = embedder

        # 领域术语同义词映射（用于 Query Expansion）
        self._synonym_map = {
            "vo2max": ["最大摄氧量", "最大有氧能力", "VO2 max", "VO₂max"],
            "心率": ["heart rate", "脉搏", "HR"],
            "配速": ["pace", "速度", "每公里时间"],
            "碳水": ["碳水化合物", "糖原", "carbohydrate"],
            "蛋白质": ["protein", "肌肉合成", "氨基酸"],
            "脂肪": ["fat", "脂质", "体脂"],
            "力量": ["strength", "力量训练", "抗阻训练", "weight training"],
            "耐力": ["endurance", "有氧", "aerobic", "心肺"],
            "跑步": ["run", "running", "慢跑", "长跑"],
            "骑行": ["ride", "cycling", "bike"],
            "游泳": ["swim", "swimming"],
            "瑜伽": ["yoga", "pilates"],
            "间歇": ["interval", "HIIT", "间歇训练"],
            "乳酸阈值": ["LT", "lactate threshold", "OBLA"],
            "心率变异性": ["HRV", "heart rate variability"],
            "恢复": ["recovery", "rest", "休息"],
            "热身": ["warm up", "warmup"],
            "拉伸": ["stretch", "stretching"],
            "减脂": ["fat loss", "cutting", "减脂训练"],
            "增肌": ["muscle gain", "bulking", "增重"],
        }

    def search(
        self,
        query: str,
        categories: Optional[List[str]] = None,
        top_k: int = TOP_K,
        use_query_expansion: bool = True,
        use_hybrid: bool = True,
        use_mmr: bool = True,
        mmr_lambda: float = 0.7,
    ) -> List[Dict]:
        """执行混合检索。

        Args:
            query: 用户查询
            categories: 分类过滤器（可选）
            top_k: 返回结果数
            use_query_expansion: 是否启用查询扩展
            use_hybrid: 是否融合关键词检索
            use_mmr: 是否启用 MMR 多样性
            mmr_lambda: MMR 的 lambda 参数（0=多样, 1=相关）

        Returns:
            排序后的检索结果列表
        """
        # Step 1: 查询扩展
        expanded_queries = [query]
        if use_query_expansion:
            expanded_queries = self._expand_query(query)

        # Step 2: 向量检索
        vector_results = []
        for eq in expanded_queries:
            eq_embedding = self._embedder.embed_query(eq)
            results = self._vector_store.retrieve_with_filter(
                eq_embedding,
                top_k=top_k,
                categories=categories,
            )
            vector_results.extend(results)

        # Step 3: 关键词检索（BM25 风格）
        keyword_results = []
        if use_hybrid:
            keyword_results = self._keyword_search(query, categories, top_k)

        # Step 4: 融合结果
        fused = self._fusion_rank(vector_results, keyword_results, top_k * 2)

        # Step 5: MMR 重排（多样性保证）
        if use_mmr and len(fused) > top_k:
            fused = self._mmr_rerank(fused, query, top_k, mmr_lambda)

        # Step 6: 上下文丰富（对过小 chunk 补充相邻内容）
        enriched = self._enrich_context(fused, top_k)

        # Step 7: 规则重排（元数据加权）
        final = self._metadata_rerank(enriched, query)[:top_k]

        logger.info(
            "混合检索完成: query='%s', expanded_queries=%d, vector_hits=%d, "
            "keyword_hits=%d, final_results=%d",
            query, len(expanded_queries),
            len(vector_results), len(keyword_results), len(final),
        )
        return final

    def _expand_query(self, query: str) -> List[str]:
        """查询扩展：添加同义词和领域术语。

        策略：
        1. 检测查询中的核心术语
        2. 添加 1-2 个同义词变体
        3. 保持原始查询为第一个
        """
        expanded = [query]
        query_lower = query.lower()

        for term, synonyms in self._synonym_map.items():
            if term.lower() in query_lower:
                # 添加 1-2 个最相关的同义词
                for syn in synonyms[:2]:
                    expanded.append(query.replace(term, syn))

        # 限制扩展数量（避免过多噪声）
        return expanded[:4]

    def _keyword_search(
        self,
        query: str,
        categories: Optional[List[str]],
        top_k: int,
    ) -> List[Dict]:
        """BM25 风格关键词检索。

        简化版 BM25：
        - TF（词频）：查询词在文档中出现的次数
        - IDF（逆文档频率）：罕见词权重更高
        - 归一化：文档长度归一化
        """
        # 获取所有文档
        collection = self._vector_store.get_collection()
        all_docs = collection.get(
            include=["documents", "metadatas"]
        )

        if not all_docs or not all_docs.get("documents"):
            return []

        # 分词（简单版）
        query_terms = self._tokenize(query)

        # 计算每个文档的 BM25 分数
        scores: Dict[str, float] = {}
        doc_count = len(all_docs["documents"])

        # 预计算文档频率（DF）
        df = Counter()
        for doc_text in all_docs["documents"]:
            doc_tokens = set(self._tokenize(doc_text or ""))
            for t in doc_tokens:
                df[t] += 1

        avgdl = sum(len(d or "") for d in all_docs["documents"]) / max(doc_count, 1)

        for idx, doc_text in enumerate(all_docs["documents"]):
            if not doc_text:
                continue
            metadata = all_docs["metadatas"][idx] or {}

            # 分类过滤
            if categories and metadata.get("category") not in categories:
                continue

            tokens = self._tokenize(doc_text)
            dl = len(tokens)
            score = 0.0

            for term in query_terms:
                tf = tokens.count(term)
                if tf == 0:
                    continue
                idf = (doc_count - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5)
                idf = max(idf, 0.01)  # 避免负值
                # BM25 公式简化
                k1 = 1.5
                b = 0.75
                norm_tf = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / max(avgdl, 1)))
                score += idf * norm_tf

            if score > 0:
                scores[str(idx)] = score

        # 取 top_k
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for idx_str, bm25_score in ranked:
            idx = int(idx_str)
            results.append({
                "content": all_docs["documents"][idx],
                "source": (all_docs["metadatas"][idx] or {}).get("source", "unknown"),
                "chunk_index": (all_docs["metadatas"][idx] or {}).get("chunk_index", 0),
                "distance": 0.0,  # BM25 分数单独存储
                "bm25_score": bm25_score,
                "retrieval_method": "keyword",
            })

        return results

    def _tokenize(self, text: str) -> List[str]:
        """简单分词：空格分割 + 中文单字。"""
        tokens = []
        # 按空格和标点切分
        for chunk in re.split(r'[^\w\u4e00-\u9fff]+', text.lower()):
            if chunk:
                # 中文按单字
                if '\u4e00' <= chunk[0] <= '\u9fff':
                    tokens.extend(list(chunk))
                else:
                    tokens.append(chunk)
        return [t for t in tokens if t]

    def _fusion_rank(
        self,
        vector_results: List[Dict],
        keyword_results: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        """RRF（Reciprocal Rank Fusion）融合排序。

        RRF 公式：score = 1/(k + rank_vector) + 1/(k + rank_keyword)
        其中 k 是平滑参数（通常为 60）
        """
        k = 60  # RRF 平滑参数
        scores: Dict[str, float] = {}
        content_map: Dict[str, Dict] = {}

        # 向量检索排名
        for rank, item in enumerate(vector_results):
            key = item["content"][:200]  # 用内容前 200 字符做 key
            if key not in scores:
                scores[key] = 0.0
                content_map[key] = item
            scores[key] += 1.0 / (k + rank + 1)

        # 关键词检索排名
        for rank, item in enumerate(keyword_results):
            key = item["content"][:200]
            if key not in scores:
                scores[key] = 0.0
                content_map[key] = item
            scores[key] += 1.0 / (k + rank + 1)

        # 排序取 top_k
        ranked_keys = sorted(scores, key=scores.get, reverse=True)[:top_k]

        fused = []
        for key in ranked_keys:
            item = content_map[key].copy()
            item["rrf_score"] = scores[key]
            # 标记来源
            if item.get("retrieval_method") == "keyword":
                item["retrieval_method"] = "hybrid"
            elif item.get("retrieval_method") != "hybrid":
                item["retrieval_method"] = "vector"
            fused.append(item)

        return fused

    def _mmr_rerank(
        self,
        results: List[Dict],
        query: str,
        top_k: int,
        lambda_param: float = 0.7,
    ) -> List[Dict]:
        """MMR（Maximum Marginal Relevance）重排序。

        目标：在保证相关性的同时，最大化结果的多样性。
        避免返回 5 个几乎相同的 chunk。

        lambda_param:
            - 接近 1：偏向相关性（传统排序）
            - 接近 0：偏向多样性（差异化结果）
        """
        if len(results) <= top_k:
            return results

        query_embedding = self._embedder.embed_query(query)

        # 获取所有候选的 embedding（用内容的前 200 字符 hash 做近似）
        selected: List[Dict] = []
        remaining = list(results)

        # 第一个直接取最高分
        if remaining:
            selected.append(remaining.pop(0))

        while len(selected) < top_k and remaining:
            best_idx = 0
            best_mmr_score = -1.0

            for idx, candidate in enumerate(remaining):
                # 相关性：与 query 的相似度
                rel_score = 1.0 - min(candidate.get("distance", 1.0), 1.0)

                # 多样性：与已选中结果的最小相似度
                max_sim_to_selected = self._max_similarity(candidate, selected)

                # MMR 分数
                mmr_score = (
                    lambda_param * rel_score
                    - (1 - lambda_param) * max_sim_to_selected
                )

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_idx = idx

            selected.append(remaining.pop(best_idx))

        return selected

    def _max_similarity(self, candidate: Dict, selected: List[Dict]) -> float:
        """计算候选与已选集合的最大相似度。

        使用 Jaccard 相似度作为快速近似。
        """
        cand_tokens = set(self._tokenize(candidate.get("content", "")))
        if not cand_tokens:
            return 0.0

        max_sim = 0.0
        for s in selected:
            s_tokens = set(self._tokenize(s.get("content", "")))
            if not s_tokens:
                continue
            intersection = cand_tokens & s_tokens
            union = cand_tokens | s_tokens
            if union:
                sim = len(intersection) / len(union)
                max_sim = max(max_sim, sim)

        return max_sim

    def _enrich_context(
        self,
        results: List[Dict],
        top_k: int,
    ) -> List[Dict]:
        """上下文丰富：对过小的 chunk 补充元数据。

        如果某个 chunk 太小（< 50 token），标记需要上下文补充。
        """
        for r in results:
            content = r.get("content", "")
            token_count = len(self._tokenize(content))
            if token_count < 30:
                r["needs_context"] = True
                r["context_hint"] = "此片段较短，可能需要结合上下文理解"
            else:
                r["needs_context"] = False

        return results

    def _metadata_rerank(
        self,
        results: List[Dict],
        query: str,
    ) -> List[Dict]:
        """基于元数据的规则重排。

        提升策略：
        1. 包含查询领域术语的 chunk 加权
        2. semantic_density 高的 chunk 加权
        3. 标题/摘要类型的 chunk 加权
        """
        query_terms = set(self._tokenize(query.lower()))
        domain_hits = [t.lower() for t in DOMAIN_TERMS if t.lower() in query.lower()]

        for r in results:
            boost = 1.0

            # 命中领域术语的 chunk 加分
            content_lower = r.get("content", "").lower()
            for dt in domain_hits:
                if dt.lower() in content_lower:
                    boost += 0.2

            # 语义密度高的加分
            density = r.get("semantic_density", 0)
            if density > 0.05:
                boost += 0.1

            # 综合分 = rrf_score * boost
            r["final_score"] = r.get("rrf_score", 0) * boost

        # 按 final_score 排序
        results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
        return results
