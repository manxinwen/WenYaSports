"""RAG Query Optimizer Tests."""

import pytest

from app.orchestrator.rag_optimizer import (
    QueryRewriter,
    MultiQueryGenerator,
    ResultFuser,
    ReRanker,
    QualityEvaluator,
    RAGOptimizer,
    OptimizedQuery,
    QualityMetrics,
)


# ---------------------------------------------------------------------------
# QueryRewriter Tests
# ---------------------------------------------------------------------------

class TestQueryRewriter:
    """查询改写器测试。"""

    def test_rewrite_with_domain_terms(self):
        rewriter = QueryRewriter(
            domain_terms={"配速": ["pace", "速度", "节奏"]}
        )
        result = rewriter.rewrite("跑步配速如何安排")
        assert "pace" in result
        assert "速度" in result
        assert "节奏" in result

    def test_rewrite_with_synonyms(self):
        rewriter = QueryRewriter(
            synonyms={"训练": ["锻炼", "运动"]}
        )
        result = rewriter.rewrite("如何安排训练")
        assert "锻炼" in result or "运动" in result

    def test_rewrite_no_expansion_needed(self):
        rewriter = QueryRewriter(
            domain_terms={"配速": ["pace"]},
            synonyms={"训练": ["锻炼"]},
        )
        result = rewriter.rewrite("完全不相关的查询")
        assert result == "完全不相关的查询"

    def test_add_domain_term(self):
        rewriter = QueryRewriter()
        rewriter.add_domain_term("间歇", ["interval", "高强度"])
        result = rewriter.rewrite("间歇训练")
        assert "interval" in result

    def test_add_synonym(self):
        rewriter = QueryRewriter()
        rewriter.add_synonym("恢复", ["recovery", "休息"])
        result = rewriter.rewrite("恢复日安排")
        assert "recovery" in result or "休息" in result


# ---------------------------------------------------------------------------
# MultiQueryGenerator Tests
# ---------------------------------------------------------------------------

class TestMultiQueryGenerator:
    """多查询生成器测试。"""

    def test_generate_variants(self):
        generator = MultiQueryGenerator()
        variants = generator.generate("跑步配速", num_variants=3)
        assert len(variants) >= 1
        assert variants[0] == "跑步配速"

    def test_generate_with_domain_hints(self):
        generator = MultiQueryGenerator()
        variants = generator.generate(
            "跑步",
            num_variants=3,
            domain_hints=["训练", "配速"],
        )
        assert len(variants) >= 2
        assert any("训练" in v for v in variants)

    def test_generate_with_rewriter(self):
        rewriter = QueryRewriter(domain_terms={"配速": ["pace"]})
        generator = MultiQueryGenerator(rewriter=rewriter)
        variants = generator.generate("跑步配速", num_variants=3)
        assert any("pace" in v for v in variants)

    def test_generate_respects_max_variants(self):
        generator = MultiQueryGenerator()
        variants = generator.generate("简单查询", num_variants=2)
        assert len(variants) <= 2


# ---------------------------------------------------------------------------
# ResultFuser Tests
# ---------------------------------------------------------------------------

class TestResultFuser:
    """结果融合器测试。"""

    def test_rrf_fusion(self):
        fuser = ResultFuser(strategy="rrf", k=60)
        results_by_query = {
            "q1": [
                {"content": "文档A", "score": 0.9},
                {"content": "文档B", "score": 0.8},
                {"content": "文档C", "score": 0.7},
            ],
            "q2": [
                {"content": "文档A", "score": 0.95},
                {"content": "文档D", "score": 0.85},
            ],
        }

        fused = fuser.fuse("query", results_by_query)
        assert len(fused) > 0
        contents = [r.content for r in fused]
        assert "文档A" in contents

    def test_combsum_fusion(self):
        fuser = ResultFuser(strategy="combsum")
        results_by_query = {
            "q1": [
                {"content": "文档A", "score": 0.9},
                {"content": "文档B", "score": 0.8},
            ],
            "q2": [
                {"content": "文档A", "score": 0.95},
                {"content": "文档C", "score": 0.7},
            ],
        }

        fused = fuser.fuse("query", results_by_query)
        doc_a = next((r for r in fused if r.content == "文档A"), None)
        assert doc_a is not None
        assert doc_a.score > 0.9

    def test_combmnz_fusion(self):
        fuser = ResultFuser(strategy="combmnz")
        results_by_query = {
            "q1": [
                {"content": "文档A", "score": 0.5},
                {"content": "文档B", "score": 0.3},
            ],
            "q2": [
                {"content": "文档A", "score": 0.5},
                {"content": "文档C", "score": 0.4},
            ],
        }

        fused = fuser.fuse("query", results_by_query)
        doc_a = next((r for r in fused if r.content == "文档A"), None)
        assert doc_a is not None
        assert doc_a.score > 0.5

    def test_empty_results(self):
        fuser = ResultFuser()
        results_by_query = {"q1": [], "q2": []}
        fused = fuser.fuse("query", results_by_query)
        assert len(fused) == 0

    def test_rrf_prevents_single_query_domination(self):
        fuser = ResultFuser(strategy="rrf", k=60)
        results_by_query = {
            "q1": [
                {"content": "文档A", "score": 0.99},
            ],
            "q2": [
                {"content": "文档B", "score": 0.5},
            ],
        }
        fused = fuser.fuse("query", results_by_query)
        # RRF gives both a chance based on rank, not raw score
        assert len(fused) == 2


# ---------------------------------------------------------------------------
# ReRanker Tests
# ---------------------------------------------------------------------------

class TestReRanker:
    """重排序器测试。"""

    def test_rerank_basic(self):
        reranker = ReRanker()
        results = [
            {"content": "跑步配速训练方法", "score": 0.5},
            {"content": "饮食营养建议", "score": 0.3},
            {"content": "跑步配速控制技巧", "score": 0.6},
        ]

        reranked = reranker.rerank("跑步配速", results)
        assert len(reranked) == 3
        assert reranked[0]["content"] in ["跑步配速训练方法", "跑步配速控制技巧"]

    def test_rerank_with_metadata_boost(self):
        reranker = ReRanker()
        results = [
            {"content": "通用内容", "metadata": {"source": "blog"}},
            {"content": "跑步配速专家建议", "metadata": {"source": "expert"}},
        ]

        reranked = reranker.rerank(
            "跑步配速",
            results,
            metadata_boost={"source": 0.3},
        )
        assert len(reranked) == 2

    def test_rerank_keeps_all_results(self):
        reranker = ReRanker()
        results = [
            {"content": f"文档{i}", "score": 0.1 * i} for i in range(5)
        ]
        reranked = reranker.rerank("查询", results)
        assert len(reranked) == 5


# ---------------------------------------------------------------------------
# QualityEvaluator Tests
# ---------------------------------------------------------------------------

class TestQualityEvaluator:
    """质量评估器测试。"""

    def test_perfect_precision(self):
        evaluator = QualityEvaluator()
        metrics = evaluator.evaluate(
            retrieved=["doc1", "doc2", "doc3"],
            relevant=["doc1", "doc2", "doc3"],
            k=3,
        )
        assert metrics.precision_at_k == 1.0
        assert metrics.recall_at_k == 1.0
        assert metrics.ndcg_at_k == 1.0

    def test_partial_match(self):
        evaluator = QualityEvaluator()
        metrics = evaluator.evaluate(
            retrieved=["doc1", "doc2", "doc3"],
            relevant=["doc1", "doc3", "doc5"],
            k=3,
        )
        assert metrics.precision_at_k == pytest.approx(2 / 3, abs=0.01)
        assert metrics.recall_at_k == pytest.approx(2 / 3, abs=0.01)

    def test_no_match(self):
        evaluator = QualityEvaluator()
        metrics = evaluator.evaluate(
            retrieved=["doc1", "doc2"],
            relevant=["doc3", "doc4"],
            k=2,
        )
        assert metrics.precision_at_k == 0.0
        assert metrics.recall_at_k == 0.0
        assert metrics.ndcg_at_k == 0.0

    def test_empty_relevant(self):
        evaluator = QualityEvaluator()
        metrics = evaluator.evaluate(
            retrieved=["doc1"],
            relevant=[],
            k=1,
        )
        assert metrics.precision_at_k == 0.0
        assert metrics.total_retrieved == 1

    def test_f1_score(self):
        evaluator = QualityEvaluator()
        metrics = evaluator.evaluate(
            retrieved=["doc1", "doc2", "doc3", "doc4"],
            relevant=["doc1", "doc2", "doc5"],
            k=4,
        )
        expected_precision = 2 / 4  # 0.5
        expected_recall = 2 / 3  # 0.667
        expected_f1 = (
            2 * expected_precision * expected_recall
            / (expected_precision + expected_recall)
        )
        assert metrics.f1_at_k == pytest.approx(expected_f1, abs=0.01)

    def test_ndcg_penalizes_wrong_order(self):
        evaluator = QualityEvaluator()
        relevant = ["doc1", "doc2", "doc3"]

        # 完美排序：所有相关文档在前
        metrics_good = evaluator.evaluate(
            retrieved=["doc1", "doc2", "doc3", "doc4", "doc5"],
            relevant=relevant,
            k=5,
        )
        # 较差排序：相关文档被无关文档分开
        metrics_bad = evaluator.evaluate(
            retrieved=["doc4", "doc1", "doc5", "doc2", "doc3"],
            relevant=relevant,
            k=5,
        )
        assert metrics_good.ndcg_at_k > metrics_bad.ndcg_at_k

    def test_batch_evaluation(self):
        evaluator = QualityEvaluator()
        metrics = evaluator.evaluate_batch(
            queries=["q1", "q2"],
            retrieved_list=[
                ["a", "b", "c"],
                ["d", "e"],
            ],
            relevant_list=[
                ["a", "b", "c"],
                ["d", "f"],
            ],
            k=3,
        )
        assert "avg_precision_at_k" in metrics
        assert "avg_recall_at_k" in metrics
        assert metrics["query_count"] == 2


# ---------------------------------------------------------------------------
# RAGOptimizer Integration Tests
# ---------------------------------------------------------------------------

class TestRAGOptimizer:
    """RAG优化器集成测试。"""

    def test_optimize_query(self):
        optimizer = RAGOptimizer()
        result = optimizer.optimize_query("跑步配速", num_variants=3)
        assert isinstance(result, OptimizedQuery)
        assert result.original == "跑步配速"
        assert len(result.variants) >= 1

    def test_optimize_with_domain_terms(self):
        rewriter = QueryRewriter(domain_terms={"配速": ["pace", "速度"]})
        optimizer = RAGOptimizer(rewriter=rewriter)
        result = optimizer.optimize_query("跑步配速")
        assert any("pace" in v for v in result.variants)

    def test_fuse_and_rerank(self):
        optimizer = RAGOptimizer()
        results_by_query = {
            "q1": [
                {"content": "文档A", "score": 0.9},
                {"content": "文档B", "score": 0.8},
            ],
            "q2": [
                {"content": "文档A", "score": 0.95},
                {"content": "文档C", "score": 0.7},
            ],
        }

        results = optimizer.fuse_and_rerank("查询", results_by_query, top_k=3)
        assert len(results) <= 3
        assert all("score" in r for r in results)

    def test_optimize_and_retrieve(self):
        def mock_retrieve(query_str, **kwargs):
            return [
                {"content": f"结果关于: {query_str}", "score": 0.8},
            ]

        optimizer = RAGOptimizer()
        results = optimizer.optimize_and_retrieve(
            "跑步配速",
            retrieve_fn=mock_retrieve,
            num_variants=2,
            top_k=3,
        )
        assert len(results) > 0

    def test_get_quality_metrics(self):
        optimizer = RAGOptimizer()
        metrics = optimizer.get_quality_metrics(
            retrieved=["doc1", "doc2", "doc3"],
            relevant=["doc1", "doc2", "doc3"],
            k=3,
        )
        assert isinstance(metrics, QualityMetrics)
        assert metrics.precision_at_k == 1.0

    def test_default_strategy_is_rrf(self):
        optimizer = RAGOptimizer()
        assert optimizer.fuser._strategy == "rrf"