"""RAG 增强模块测试：智能切块 + 混合检索。"""

import pytest


class TestSmartChunker:
    @pytest.fixture
    def chunker(self):
        from rag.smart_chunker import SmartChunker
        return SmartChunker(mode="section_aware", target_chunk_size=300, min_chunk_size=50)

    def test_chunk_text_basic(self, chunker):
        text = "这是一段测试文本。\n\n" * 20  # 足够长的文本
        chunks = chunker.chunk_text(text)
        assert len(chunks) > 0
        assert all(len(c.content) > 0 for c in chunks)
        chunker.stats.total_chunks == len(chunks)

    def test_chunk_text_with_domain_terms(self, chunker):
        """测试专业术语保护。"""
        text = "VO2max 是衡量有氧运动能力的核心指标。\n\n" * 10
        chunks = chunker.chunk_text(text)
        # VO2max 应该完整保留在某个 chunk 中
        all_content = " ".join(c.content for c in chunks)
        assert "VO2max" in all_content

    def test_chunk_text_semantic_mode(self):
        from rag.smart_chunker import SmartChunker
        # 用较小的 max_chunk_size 确保产生多分块
        chunker = SmartChunker(mode="semantic", target_chunk_size=100, max_chunk_size=300)
        # 足够长的文本，确保产生多个 chunk
        text = ("段落一内容比较长，包含了很多详细的信息和知识，"
                "涵盖了运动生理学的多个方面。\n\n"
                "段落二内容也非常丰富，讨论了不同的训练主题和观点，"
                "包括力量训练和有氧运动的区别。\n\n"
                "段落三内容提供了更多的细节和例子来支持前面的论点，"
                "并给出了具体的训练建议。\n\n") * 10
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 2

    def test_chunk_text_fixed_mode(self):
        from rag.smart_chunker import SmartChunker
        chunker = SmartChunker(mode="fixed", target_chunk_size=100, chunk_overlap=20)
        text = "A" * 1000
        chunks = chunker.chunk_text(text)
        assert len(chunks) > 0
        # 固定模式下 chunk 大小接近 target
        for c in chunks:
            assert 80 <= len(c.content) <= 120 or c == chunks[-1]

    def test_chunk_stats(self, chunker):
        text = "测试内容。\n\n" * 30
        chunks = chunker.chunk_text(text)
        stats = chunker.stats
        assert stats.total_chunks == len(chunks)
        assert stats.avg_chunk_size > 0
        assert stats.min_chunk_size <= stats.avg_chunk_size
        assert stats.max_chunk_size >= stats.avg_chunk_size

    def test_chunk_has_metadata(self, chunker):
        text = "带元数据的测试。\n\n" * 10
        chunks = chunker.chunk_text(text, source="test.md")
        for c in chunks:
            assert "source" in c.metadata
            assert "chunk_index" in c.metadata
            assert c.metadata["source"] == "test.md"

    def test_semantic_density(self, chunker):
        """测试语义密度计算。"""
        text = "VO2max 乳酸阈值 心率变异性 是运动生理学的核心指标。\n\n" * 5
        chunks = chunker.chunk_text(text)
        # 包含多个专业术语的 chunk 应有较高密度
        high_density = [c for c in chunks if c.metadata.get("semantic_density", 0) > 0]
        assert len(high_density) > 0

    def test_merge_small_chunks(self):
        from rag.smart_chunker import SmartChunker
        chunker = SmartChunker(target_chunk_size=500, min_chunk_size=100)
        chunks = chunker._merge_small_chunks(["短", "短", "长" * 200])
        # 前两个短的应该被合并
        assert len(chunks) <= 2

    def test_auto_mode_selection(self):
        from rag.smart_chunker import SmartChunker
        chunker = SmartChunker(mode="auto")
        # Markdown → section_aware
        assert chunker._auto_select_mode(".md") == "section_aware"
        # PDF → semantic
        assert chunker._auto_select_mode(".pdf") == "semantic"
        # TXT → semantic
        assert chunker._auto_select_mode(".txt") == "semantic"

    def test_query_expansion_synonyms(self):
        """测试查询扩展同义词。"""
        from rag.hybrid_retriever import HybridRetriever
        from unittest.mock import MagicMock

        mock_store = MagicMock()
        mock_embedder = MagicMock()
        retriever = HybridRetriever(mock_store, mock_embedder)

        # VO2max 应扩展出同义词
        expanded = retriever._expand_query("怎么提高VO2max")
        assert len(expanded) >= 2  # 原始 + 扩展
        # 同义词应该包含最大摄氧量
        all_expanded = " ".join(expanded)
        assert "最大摄氧量" in all_expanded or "VO2" in all_expanded

    def test_metadata_rerank(self):
        """测试元数据规则重排。"""
        from rag.hybrid_retriever import HybridRetriever
        from unittest.mock import MagicMock

        mock_store = MagicMock()
        mock_embedder = MagicMock()
        retriever = HybridRetriever(mock_store, mock_embedder)

        results = [
            {"content": "VO2max 训练方法", "rrf_score": 0.8, "semantic_density": 0.1},
            {"content": "一般训练知识", "rrf_score": 0.9, "semantic_density": 0.01},
        ]
        reranked = retriever._metadata_rerank(results, "VO2max 训练")
        # 第一个因为命中 VO2max 应该被加权
        assert reranked[0]["content"] == "VO2max 训练方法"
        assert reranked[0]["final_score"] > reranked[1]["final_score"]

    def test_rrf_fusion(self):
        """测试 RRF 融合排序。"""
        from rag.hybrid_retriever import HybridRetriever
        from unittest.mock import MagicMock

        mock_store = MagicMock()
        mock_embedder = MagicMock()
        retriever = HybridRetriever(mock_store, mock_embedder)

        vector_results = [
            {"content": "A", "source": "doc1", "distance": 0.1},
            {"content": "B", "source": "doc2", "distance": 0.2},
        ]
        keyword_results = [
            {"content": "B", "source": "doc2", "bm25_score": 5.0},  # B 在两边都出现
            {"content": "C", "source": "doc3", "bm25_score": 4.0},
        ]

        fused = retriever._fusion_rank(vector_results, keyword_results, top_k=3)
        # B 因为在两个列表中都出现，应该排名最高
        assert fused[0]["content"] == "B"
        assert "rrf_score" in fused[0]

    def test_mmr_diversity(self):
        """测试 MMR 多样性。"""
        from rag.hybrid_retriever import HybridRetriever
        from unittest.mock import MagicMock

        mock_store = MagicMock()
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 384

        retriever = HybridRetriever(mock_store, mock_embedder)

        results = [
            {"content": "VO2max 训练方法 详情", "distance": 0.1},
            {"content": "VO2max 训练方法 进阶", "distance": 0.15},
            {"content": "跑步装备选择指南", "distance": 0.2},
            {"content": "VO2max 训练计划", "distance": 0.25},
            {"content": "营养学基础", "distance": 0.3},
        ]

        mmr = retriever._mmr_rerank(results, "VO2max", top_k=3, lambda_param=0.5)
        assert len(mmr) == 3
        # MMR 应该倾向于选择不同的内容
        selected_contents = [r["content"] for r in mmr]
        # 不应全是 VO2max 相关
        vo2_count = sum(1 for c in selected_contents if "VO2max" in c)
        assert vo2_count <= 2  # 至少保留 1 个多样性结果

    def test_keyword_search_empty(self):
        """空关键词检索。"""
        from rag.hybrid_retriever import HybridRetriever
        from unittest.mock import MagicMock

        mock_store = MagicMock()
        mock_store.get_collection.return_value.get.return_value = {}
        mock_embedder = MagicMock()

        retriever = HybridRetriever(mock_store, mock_embedder)
        results = retriever._keyword_search("测试", None, 5)
        assert results == []

    def test_categories_detection(self):
        """测试分类检测。"""
        from rag.retriever import _detect_query_categories
        cats = _detect_query_categories("怎么提高VO2max和耐力")
        assert "physiology" in cats
        assert "endurance" in cats

        cats2 = _detect_query_categories("力量训练增肌计划")
        assert "strength" in cats2

        cats3 = _detect_query_categories("减脂饮食怎么安排")
        assert "nutrition" in cats3
