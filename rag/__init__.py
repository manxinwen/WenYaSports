"""RAG（检索增强生成）个人 AI 私教模块。

面向运动分析多智能体系统的知识库问答能力：
- 领域知识库（运动训练 / 恢复 / 营养 / 伤病预防）切分 → 向量化 → 持久化；
- 语义检索相关文档片段；
- KnowledgeAgent 结合用户画像 + 近期训练状态 + 检索知识，生成个性化回答。

模块与主系统解耦：通过 Embedder / VectorStore / LLMClient 抽象注入，
测试与生产可替换不同实现。
"""

__all__ = [
    "Embedder",
    "MiniLMEmbedder",
    "FakeEmbedder",
    "VectorStoreManager",
    "LLMClient",
    "OpenAILLMClient",
    "KnowledgeAgent",
]
