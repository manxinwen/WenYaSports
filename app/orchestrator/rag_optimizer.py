"""RAG Query Optimizer: 检索增强生成查询优化器。

核心能力：
1. Query Rewriting: 用领域术语扩展用户查询
2. Multi-Query Generation: 生成多个查询变体以提升召回率
3. Result Fusion: 合并多个查询的检索结果
4. Re-ranking: 对检索结果进行评分排序
5. Quality Evaluation: 度量 precision@k、recall、nDCG

设计理念：
- 查询改写 → 多查询生成 → 并行检索 → 结果融合 → 重排序 → 质量评估
- 全部基于Python标准库实现，无外部依赖
- 支持领域特定的术语映射和同义词扩展

Architecture:
    User Query
        ↓
    ┌──────────────────┐
    │ Query Rewriter   │ → Expanded Query
    └──────────────────┘
        ↓
    ┌──────────────────┐
    │ Multi-Query Gen  │ → [Query1, Query2, Query3]
    └──────────────────┘
        ↓
    ┌──────────────────┐
    │ Result Fusion    │ → Merged Results
    └──────────────────┘
        ↓
    ┌──────────────────┐
    │ Re-ranker        │ → Ranked Results
    └──────────────────┘
        ↓
    Quality Evaluator → Metrics
"""

from __future__ import annotations

import logging
import math
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query Rewriter (查询改写)
# ---------------------------------------------------------------------------

class QueryRewriter:
    """查询改写器。

    用领域术语和同义词扩展用户查询，提升检索召回率。

    Args:
        domain_terms: 领域术语映射表 {原始词: [扩展词1, 扩展词2, ...]}
        synonyms: 同义词映射表 {词: [同义词1, 同义词2, ...]}
    """

    def __init__(self, domain_terms: Optional[Dict[str, List[str]]] = None,
                 synonyms: Optional[Dict[str, List[str]]] = None):
        self._domain_terms = domain_terms or {}
        self._synonyms = synonyms or {}

    def rewrite(self, query: str, expand_domain: bool = True,
                expand_synonyms: bool = True) -> str:
        """改写查询，加入扩展术语。

        Args:
            query: 原始查询
            expand_domain: 是否扩展领域术语
            expand_synonyms: 是否扩展同义词

        Returns:
            扩展后的查询
        """
        expanded_parts = [query]
        query_lower = query.lower()

        if expand_domain:
            for term, expansions in self._domain_terms.items():
                if term.lower() in query_lower:
                    expanded_parts.extend(expansions)

        if expand_synonyms:
            tokens = query.split()
            for token in tokens:
                token_lower = token.lower()
                if token_lower in self._synonyms:
                    expanded_parts.extend(self._synonyms[token_lower])
            for word, syns in self._synonyms.items():
                if word.lower() in query_lower:
                    expanded_parts.extend(syns)

        return " ".join(expanded_parts)

    def add_domain_term(self, term: str, expansions: List[str]) -> None:
        """添加一个领域术语映射。"""
        self._domain_terms[term] = expansions

    def add_synonym(self, word: str, syns: List[str]) -> None:
        """添加同义词映射。"""
        self._synonyms[word] = syns


# ---------------------------------------------------------------------------
# Multi-Query Generator (多查询生成器)
# ---------------------------------------------------------------------------

class MultiQueryGenerator:
    """多查询变体生成器。

    基于原始查询生成多个变体，用于并行检索以提升召回率。

    支持的变体策略：
    - 原始查询
    - 扩展查询（加入领域术语）
    - 泛化查询（移除限定词）
    - 具体化查询（添加限定词）
    """

    def __init__(self, rewriter: Optional[QueryRewriter] = None):
        self._rewriter = rewriter or QueryRewriter()

    def generate(self, query: str, num_variants: int = 3,
                 domain_hints: Optional[List[str]] = None) -> List[str]:
        """生成查询变体。

        Args:
            query: 原始查询
            num_variants: 生成的变体数量
            domain_hints: 可选的领域提示词

        Returns:
            查询变体列表
        """
        variants = [query]

        # 变体1: 扩展查询
        expanded = self._rewriter.rewrite(query)
        if expanded != query:
            variants.append(expanded)

        # 变体2: 添加领域提示
        if domain_hints:
            for hint in domain_hints[:num_variants - len(variants)]:
                variants.append(f"{query} {hint}")

        # 变体3: 关键词提取
        keywords = self._extract_keywords(query)
        if keywords and len(variants) < num_variants:
            variants.append(" ".join(keywords))

        # 变体4: 泛化（移除限定词）
        generalized = self._generalize(query)
        if generalized and generalized != query and len(variants) < num_variants:
            variants.append(generalized)

        return variants[:num_variants]

    def _extract_keywords(self, query: str) -> List[str]:
        """提取查询中的关键词。"""
        stop_words = {"的", "了", "在", "是", "我", "有", "和", "就",
                      "不", "人", "都", "一", "一个", "上", "也", "很",
                      "the", "a", "an", "is", "are", "was", "were",
                      "how", "what", "why", "when", "where", "to", "for"}
        tokens = query.split()
        return [t for t in tokens if t.lower() not in stop_words]

    def _generalize(self, query: str) -> Optional[str]:
        """泛化查询（移除具体限定词）。"""
        specific_patterns = [
            r'\d+[分钟小时天周月年]',
            r'\d+[次组公里千米]',
            r'具体地|详细地|精确地',
        ]
        import re
        generalized = query
        for pattern in specific_patterns:
            generalized = re.sub(pattern, '', generalized)
        generalized = ' '.join(generalized.split())
        return generalized if generalized != query else None


# ---------------------------------------------------------------------------
# Result Fusion (结果融合)
# ---------------------------------------------------------------------------

@dataclass
class FusedResult:
    """融合后的检索结果。"""
    content: str
    score: float
    source_queries: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResultFuser:
    """多查询结果融合器。

        融合策略：
        - RRF (Reciprocal Rank Fusion): 基于排名倒数的融合
        - CombSUM: 分数求和融合
        - CombMNZ: 分数求和乘以出现次数

    Args:
        strategy: 融合策略 - "rrf" | "combsum" | "combmnz"
        k: RRF参数（通常为60）
    """

    def __init__(self, strategy: str = "rrf", k: int = 60):
        self._strategy = strategy
        self._k = k

    def fuse(self, query: str,
             results_by_query: Dict[str, List[Dict[str, Any]]]) -> List[FusedResult]:
        """融合多个查询的检索结果。

        Args:
            query: 原始查询
            results_by_query: {查询: [检索结果列表]}

        Returns:
            融合后的结果列表
        """
        if self._strategy == "rrf":
            return self._rrf_fusion(results_by_query)
        elif self._strategy == "combsum":
            return self._combsum_fusion(results_by_query)
        elif self._strategy == "combmnz":
            return self._combmnz_fusion(results_by_query)
        else:
            return self._rrf_fusion(results_by_query)

    def _rrf_fusion(self, results_by_query: Dict[str, List[Dict[str, Any]]]) -> List[FusedResult]:
        """RRF融合：基于排名倒数的融合算法。"""
        fused: Dict[str, Dict[str, Any]] = {}
        k = self._k

        for query_str, results in results_by_query.items():
            for rank, result in enumerate(results, start=1):
                content = result.get("content", str(result))
                if content not in fused:
                    fused[content] = {
                        "content": content,
                        "score": 0.0,
                        "source_queries": [],
                        "metadata": result.get("metadata", {}),
                    }
                fused[content]["score"] += 1.0 / (k + rank)
                if query_str not in fused[content]["source_queries"]:
                    fused[content]["source_queries"].append(query_str)

        sorted_results = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
        return [
            FusedResult(
                content=r["content"],
                score=r["score"],
                source_queries=r["source_queries"],
                metadata=r["metadata"],
            )
            for r in sorted_results
        ]

    def _combsum_fusion(self, results_by_query: Dict[str, List[Dict[str, Any]]]) -> List[FusedResult]:
        """CombSUM融合：分数求和。"""
        fused: Dict[str, Dict[str, Any]] = {}

        for query_str, results in results_by_query.items():
            for result in results:
                content = result.get("content", str(result))
                score = result.get("score", 0.0)
                if content not in fused:
                    fused[content] = {
                        "content": content,
                        "score": 0.0,
                        "source_queries": [],
                        "metadata": result.get("metadata", {}),
                    }
                fused[content]["score"] += score
                if query_str not in fused[content]["source_queries"]:
                    fused[content]["source_queries"].append(query_str)

        sorted_results = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
        return [
            FusedResult(
                content=r["content"],
                score=r["score"],
                source_queries=r["source_queries"],
                metadata=r["metadata"],
            )
            for r in sorted_results
        ]

    def _combmnz_fusion(self, results_by_query: Dict[str, List[Dict[str, Any]]]) -> List[FusedResult]:
        """CombMNZ融合：分数求和乘以出现次数。"""
        fused: Dict[str, Dict[str, Any]] = {}

        for query_str, results in results_by_query.items():
            for result in results:
                content = result.get("content", str(result))
                score = result.get("score", 0.0)
                if content not in fused:
                    fused[content] = {
                        "content": content,
                        "score": 0.0,
                        "source_queries": [],
                        "metadata": result.get("metadata", {}),
                    }
                fused[content]["score"] += score
                if query_str not in fused[content]["source_queries"]:
                    fused[content]["source_queries"].append(query_str)

        for content in fused:
            n = len(fused[content]["source_queries"])
            if n > 1:
                fused[content]["score"] *= n

        sorted_results = sorted(fused.values(), key=lambda x: x["score"], reverse=True)
        return [
            FusedResult(
                content=r["content"],
                score=r["score"],
                source_queries=r["source_queries"],
                metadata=r["metadata"],
            )
            for r in sorted_results
        ]


# ---------------------------------------------------------------------------
# Re-ranker (重排序器)
# ---------------------------------------------------------------------------

class ReRanker:
    """检索结果重排序器。

    基多种评分策略对融合后的结果进行重新排序：
    - 文本相关性评分（基于TF-IDF）
    - 元数据匹配加权
    - 去重合并
    """

    def rerank(self, query: str,
               results: List[Dict[str, Any]],
               metadata_boost: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        """重排序检索结果。

        Args:
            query: 查询文本
            results: 待排序的结果列表
            metadata_boost: 元数据字段加权 {字段名: 权重}

        Returns:
            排序后的结果列表，每条附带 score 字段
        """
        scored_results = []
        query_lower = query.lower()
        boost_fields = metadata_boost or {}

        for result in results:
            content = result.get("content", str(result))
            score = self._compute_relevance(query_lower, content)

            # 元数据匹配加权
            metadata = result.get("metadata", {})
            for field, boost in boost_fields.items():
                field_value = str(metadata.get(field, "")).lower()
                if field_value and field_value in query_lower:
                    score += boost

            scored_entry = dict(result)
            scored_entry["score"] = round(score, 6)
            scored_results.append(scored_entry)

        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results

    def _compute_relevance(self, query: str, content: str) -> float:
        """计算查询与内容的相关性分数。"""
        query_tokens = query.split()
        content_lower = content.lower()

        score = 0.0
        for token in query_tokens:
            if token in content_lower:
                score += 1.0
                # 精确短语匹配加分
                if token in content_lower:
                    score += 0.5

        # 归一化
        if query_tokens:
            score = score / len(query_tokens)

        return min(score, 1.0)


# ---------------------------------------------------------------------------
# Quality Evaluator (质量评估器)
# ---------------------------------------------------------------------------

@dataclass
class QualityMetrics:
    """检索质量指标。"""
    precision_at_k: float = 0.0
    recall_at_k: float = 0.0
    ndcg_at_k: float = 0.0
    f1_at_k: float = 0.0
    total_relevant: int = 0
    total_retrieved: int = 0


class QualityEvaluator:
    """检索质量评估器。

    度量检索系统的关键指标：
    - Precision@k: 前k个结果中相关结果的比例
    - Recall@k: 相关结果被检索到的比例
    - nDCG@k: 归一化折损累计增益
    - F1@k: 精确率和召回率的调和平均

    Usage:
        evaluator = QualityEvaluator()
        metrics = evaluator.evaluate(
            retrieved=["doc1", "doc2", "doc3"],
            relevant=["doc1", "doc3", "doc5"],
            k=3,
        )
    """

    def evaluate(self, retrieved: List[str], relevant: List[str],
                 k: int = 5) -> QualityMetrics:
        """评估检索结果质量。

        Args:
            retrieved: 检索到的文档ID列表（按排序）
            relevant: 相关文档ID列表
            k: 评估的截止位置

        Returns:
            QualityMetrics 指标对象
        """
        if not relevant:
            return QualityMetrics(total_retrieved=len(retrieved))

        retrieved_at_k = retrieved[:k]
        relevant_set = set(relevant)

        # Precision@k
        relevant_found_at_k = sum(1 for d in retrieved_at_k if d in relevant_set)
        precision_at_k = relevant_found_at_k / k if k > 0 else 0.0

        # Recall@k
        recall_at_k = relevant_found_at_k / len(relevant_set) if relevant_set else 0.0

        # F1@k
        if precision_at_k + recall_at_k > 0:
            f1_at_k = 2 * precision_at_k * recall_at_k / (precision_at_k + recall_at_k)
        else:
            f1_at_k = 0.0

        # nDCG@k
        ndcg_at_k = self._compute_ndcg(retrieved_at_k, relevant, k)

        return QualityMetrics(
            precision_at_k=round(precision_at_k, 6),
            recall_at_k=round(recall_at_k, 6),
            ndcg_at_k=round(ndcg_at_k, 6),
            f1_at_k=round(f1_at_k, 6),
            total_relevant=len(relevant),
            total_retrieved=len(retrieved),
        )

    def _compute_ndcg(self, retrieved: List[str], relevant: List[str],
                      k: int) -> float:
        """计算nDCG@k。"""
        if not retrieved or k <= 0:
            return 0.0

        relevant_set = set(relevant)
        dcg = 0.0
        for i, doc_id in enumerate(retrieved[:k]):
            rel = 1.0 if doc_id in relevant_set else 0.0
            dcg += rel / math.log2(i + 2)

        # 理想DCG
        ideal_relevant = [1.0] * min(len(relevant), k)
        idcg = 0.0
        for i, rel in enumerate(ideal_relevant):
            idcg += rel / math.log2(i + 2)

        if idcg == 0.0:
            return 0.0

        return dcg / idcg

    def evaluate_batch(self, queries: List[str],
                       retrieved_list: List[List[str]],
                       relevant_list: List[List[str]],
                       k: int = 5) -> Dict[str, float]:
        """批量评估多个查询。

        Args:
            queries: 查询列表
            retrieved_list: 每个查询对应的检索结果列表
            relevant_list: 每个查询对应的相关文档列表
            k: 评估的截止位置

        Returns:
            汇总指标字典
        """
        all_metrics = []
        for retrieved, relevant in zip(retrieved_list, relevant_list):
            metrics = self.evaluate(retrieved, relevant, k)
            all_metrics.append(metrics)

        n = len(all_metrics)
        if n == 0:
            return {}

        return {
            "avg_precision_at_k": round(sum(m.precision_at_k for m in all_metrics) / n, 6),
            "avg_recall_at_k": round(sum(m.recall_at_k for m in all_metrics) / n, 6),
            "avg_ndcg_at_k": round(sum(m.ndcg_at_k for m in all_metrics) / n, 6),
            "avg_f1_at_k": round(sum(m.f1_at_k for m in all_metrics) / n, 6),
            "query_count": n,
            "k": k,
        }


# ---------------------------------------------------------------------------
# RAG Optimizer (RAG查询优化器主类)
# ---------------------------------------------------------------------------

@dataclass
class OptimizedQuery:
    """优化后的查询集。"""
    original: str
    rewritten: str
    variants: List[str]
    domain_terms_used: List[str] = field(default_factory=list)


class RAGOptimizer:
    """RAG查询优化器。

    整合查询改写、多查询生成、结果融合和重排序为完整的优化管线。

    Usage:
        optimizer = RAGOptimizer()
        optimized = optimizer.optimize_query("跑步配速如何安排")
        # optimized.variants = ["跑步配速如何安排", "跑步 配速 pace 训练", ...]

        # 用于实际RAG流程
        results = optimizer.optimize_and_retrieve(
            query="跑步配速",
            retrieve_fn=my_retrieval_function,
        )
    """

    def __init__(self,
                 rewriter: Optional[QueryRewriter] = None,
                 generator: Optional[MultiQueryGenerator] = None,
                 fuser: Optional[ResultFuser] = None,
                 reranker: Optional[ReRanker] = None,
                 evaluator: Optional[QualityEvaluator] = None,
                 default_top_k: int = 5):
        self.rewriter = rewriter or QueryRewriter()
        self.generator = generator or MultiQueryGenerator(self.rewriter)
        self.fuser = fuser or ResultFuser(strategy="rrf")
        self.reranker = reranker or ReRanker()
        self.evaluator = evaluator or QualityEvaluator()
        self.default_top_k = default_top_k

    def optimize_query(self, query: str, num_variants: int = 3,
                       domain_hints: Optional[List[str]] = None) -> OptimizedQuery:
        """优化查询：改写 + 多变体生成。

        Args:
            query: 原始查询
            num_variants: 生成的变体数量
            domain_hints: 领域提示词

        Returns:
            OptimizedQuery 包含改写后的查询和变体列表
        """
        rewritten = self.rewriter.rewrite(query)
        variants = self.generator.generate(query, num_variants, domain_hints)

        domain_terms_used = []
        for term in self.rewriter._domain_terms:
            if term.lower() in query.lower():
                domain_terms_used.append(term)

        return OptimizedQuery(
            original=query,
            rewritten=rewritten,
            variants=variants,
            domain_terms_used=domain_terms_used,
        )

    def fuse_and_rerank(self, query: str,
                        results_by_query: Dict[str, List[Dict[str, Any]]],
                        top_k: Optional[int] = None,
                        metadata_boost: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
        """融合多查询结果并重排序。

        Args:
            query: 原始查询
            results_by_query: {查询: [检索结果列表]}
            top_k: 返回结果数量
            metadata_boost: 元数据加权

        Returns:
            融合排序后的结果列表
        """
        top_k = top_k or self.default_top_k

        fused = self.fuser.fuse(query, results_by_query)

        # 转为字典格式供reranker使用
        fused_dicts = [
            {
                "content": r.content,
                "score": r.score,
                "source_queries": r.source_queries,
                "metadata": r.metadata,
            }
            for r in fused
        ]

        reranked = self.reranker.rerank(query, fused_dicts, metadata_boost)
        return reranked[:top_k]

    def optimize_and_retrieve(self, query: str,
                               retrieve_fn: Any,
                               num_variants: int = 3,
                               top_k: Optional[int] = None,
                               **kwargs) -> List[Dict[str, Any]]:
        """完整优化管线：查询优化 → 多路检索 → 融合 → 重排序。

        Args:
            query: 原始查询
            retrieve_fn: 检索函数，签名为 (query_str, **kwargs) -> List[Dict]
            num_variants: 查询变体数量
            top_k: 最终返回数量
            **kwargs: 传递给检索函数的额外参数

        Returns:
            优化后的检索结果
        """
        top_k = top_k or self.default_top_k

        optimized = self.optimize_query(query, num_variants)

        results_by_query: Dict[str, List[Dict[str, Any]]] = {}
        for variant in optimized.variants:
            try:
                results = retrieve_fn(variant, **kwargs)
                results_by_query[variant] = results
            except Exception as exc:
                logger.warning("Retrieval failed for variant '%s': %s", variant, exc)
                results_by_query[variant] = []

        return self.fuse_and_rerank(query, results_by_query, top_k)

    def get_quality_metrics(self, retrieved: List[str],
                             relevant: List[str], k: int = 5) -> QualityMetrics:
        """获取质量评估指标。"""
        return self.evaluator.evaluate(retrieved, relevant, k)