"""知识库索引构建脚本。

用法::

    python -m rag.build_index --data rag/data --chroma ./chroma_db

将 ``--data`` 目录下的 md/txt/pdf 文档切分、向量化并写入向量库。
支持 ``--embedder fake``（默认，无模型依赖）或 ``--embedder minilm``。
"""

import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def build_index(data_dir: str, chroma_dir: str, embedder_kind: str = "fake") -> None:
    from rag.embedder import FakeEmbedder, MiniLMEmbedder
    from rag.smart_chunker import SmartChunker
    from rag.vector_store import VectorStoreManager
    from pathlib import Path

    data_path = Path(data_dir)
    if not data_path.is_dir():
        logging.warning("目录不存在: %s", data_dir)
        return

    # 使用 SmartChunker 智能切块
    chunker = SmartChunker(mode="auto")
    chunks = chunker.chunk_directory(str(data_path))
    if not chunks:
        logging.warning("未在 %s 找到任何可切分的文档", data_dir)
        return

    # 构建 Document 列表
    from rag.document_loader import Document
    documents = []
    for chunk in chunks:
        documents.append(Document(
            page_content=chunk.content,
            metadata={
                "source": chunk.metadata.get("source", "unknown"),
                "chunk_index": chunk.chunk_index,
                "category": chunk.metadata.get("category", "general"),
                "category_name": chunk.metadata.get("category", "general"),
                "semantic_density": chunk.metadata.get("semantic_density", 0),
                "mode": chunk.metadata.get("mode", "unknown"),
                "token_count": chunk.metadata.get("token_count", 0),
                "char_count": chunk.metadata.get("char_count", len(chunk.content)),
            },
        ))

    embedder = (
        MiniLMEmbedder() if embedder_kind == "minilm" else FakeEmbedder()
    )
    store = VectorStoreManager(persist_dir=chroma_dir, embedder=embedder)
    store.add_documents(documents, embedder)

    stats = chunker.stats
    logging.info(
        "索引完成，共写入 %d 个片段到 %s | "
        "chunker_mode=%s, avg_size=%.0f, std_dev=%.0f, outlier=%d/%d, "
        "domain_terms_preserved=%d",
        len(documents), chroma_dir,
        chunker.mode, stats.avg_chunk_size, stats.std_dev,
        stats.outlier_chunks, stats.total_chunks,
        stats.domain_terms_preserved,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 RAG 知识库索引")
    parser.add_argument("--data", default="rag/data", help="文档目录")
    parser.add_argument("--chroma", default="./chroma_db", help="向量库持久化路径")
    parser.add_argument(
        "--embedder",
        choices=["fake", "minilm"],
        default="fake",
        help="向量化实现（minilm 需联网下载模型）",
    )
    args = parser.parse_args()
    build_index(args.data, args.chroma, args.embedder)


if __name__ == "__main__":
    main()
