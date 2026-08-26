"""向量化模块：Embedder 抽象 + 生产实现 + 测试桩。

- :class:`Embedder`：抽象接口，主流程只依赖此接口；
- :class:`MiniLMEmbedder`：生产实现，sentence-transformers 本地模型，
  首次运行需联网下载（约 80MB）；
- :class:`FakeEmbedder`：确定性哈希向量（384 维），用于测试与无网环境，
  保证语义上"相似文本 → 高相似度"。
"""

import hashlib
import logging
from abc import ABC, abstractmethod
from typing import List

from rag.config import MINILM_DIM

logger = logging.getLogger(__name__)


class Embedder(ABC):
    """向量化抽象接口。"""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量生成文档向量。"""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """生成查询向量。"""


class MiniLMEmbedder(Embedder):
    """基于 sentence-transformers / all-MiniLM-L6-v2 的生产实现。

    模型懒加载：首次调用时才加载（避免启动即下载模型）。
    模型下载失败时抛出异常，由调用方决定是否降级为 FakeEmbedder。
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("加载 embedding 模型: %s（首次运行需下载）", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        vectors = model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]


class FakeEmbedder(Embedder):
    """确定性哈希向量桩：适合测试与无网环境。

    基于字符 n-gram 哈希构造 384 维向量，使词面相似文本获得较高余弦相似度，
    足以支撑"相似查询命中相关文档"的端到端测试。
    """

    def __init__(self, dim: int = MINILM_DIM):
        self.dim = dim

    def _vectorize(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        norm_text = " ".join(text.lower().split())
        for n in (1, 2, 3):
            grams = [
                norm_text[i : i + n] for i in range(len(norm_text) - n + 1)
            ]
            for gram in grams:
                digest = hashlib.md5(gram.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "big") % self.dim
                weight = int.from_bytes(digest[4:6], "big") / 65535.0
                vec[idx] += weight
        magnitude = (sum(v * v for v in vec) ** 0.5) or 1.0
        return [v / magnitude for v in vec]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._vectorize(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._vectorize(text)
