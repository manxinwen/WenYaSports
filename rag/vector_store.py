"""向量数据库管理：基于 ChromaDB 的持久化存储与检索。

- :class:`VectorStoreManager` 封装 Chroma 客户端生命周期；
- 支持持久化目录（默认 ``./chroma_db``，可用 ``RAG_CHROMA_DIR`` 覆盖）；
- :meth:`retrieve` 返回含正文与 metadata 的片段列表，供上层拼装 prompt。
"""

import logging
from typing import List

from rag.config import CHROMA_COLLECTION, CHROMA_PERSIST_DIR, TOP_K
from rag.document_loader import Document
from rag.embedder import Embedder

logger = logging.getLogger(__name__)


class VectorStoreManager:
    """管理 Chroma collection 的增、查。"""

    def __init__(
        self,
        persist_dir: str = CHROMA_PERSIST_DIR,
        collection_name: str = CHROMA_COLLECTION,
        embedder: Embedder | None = None,
    ):
        import chromadb

        self.persist_dir = persist_dir
        self.collection_name = collection_name
        # 统一由外部 embedder 生成向量，Chroma 不加载自身 embedding 模型
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        # 在途的 embedder 引用（用于需要按 id 查询的场景）
        self._embedder = embedder

    def get_collection(self):
        """返回底层 Chroma collection（便于高级操作）。"""
        return self._collection

    def add_documents(self, documents: List[Document], embedder: Embedder) -> None:
        """将文档片段向量化并写入 collection。

        :param documents: 待写入片段。
        :param embedder: 用于生成向量的 Embedder 实现。
        """
        if not documents:
            return
        texts = [doc.page_content for doc in documents]
        vectors = embedder.embed_documents(texts)
        ids = [
            f"{doc.metadata['source']}#{doc.metadata.get('chunk_index', 0)}"
            for doc in documents
        ]
        metadatas = [dict(doc.metadata) for doc in documents]
        # 使用显式向量写入，避免 Chroma 内嵌模型
        self._collection.add(ids=ids, embeddings=vectors, documents=texts, metadatas=metadatas)
        logger.info("写入 %d 个片段到 collection '%s'", len(documents), self.collection_name)

    def retrieve(self, query_embedding: List[float], top_k: int = TOP_K) -> List[dict]:
        """按查询向量做余弦相似度检索，返回 ``{"content", "source", "chunk_index", "distance"}``。

        无匹配时返回空列表。
        """
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        passages: List[dict] = []
        docs = result.get("documents", [[]])[0] or []
        metas = result.get("metadatas", [[]])[0] or []
        dists = result.get("distances", [[]])[0] or []
        for content, meta, dist in zip(docs, metas, dists):
            passages.append(
                {
                    "content": content,
                    "source": (meta or {}).get("source", "未知来源"),
                    "chunk_index": (meta or {}).get("chunk_index", 0),
                    "distance": dist,
                }
            )
        return passages

    def count(self) -> int:
        """返回 collection 中的片段数量。"""
        return self._collection.count()

    def reset(self) -> None:
        """清空 collection（重建知识库用）。"""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name, metadata={"hnsw:space": "cosine"}
        )
