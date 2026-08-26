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
    from rag.document_loader import load_documents_from_directory
    from rag.embedder import FakeEmbedder, MiniLMEmbedder
    from rag.vector_store import VectorStoreManager

    documents = load_documents_from_directory(data_dir)
    if not documents:
        logging.warning("未在 %s 找到任何文档", data_dir)
        return

    embedder = (
        MiniLMEmbedder() if embedder_kind == "minilm" else FakeEmbedder()
    )
    store = VectorStoreManager(persist_dir=chroma_dir, embedder=embedder)
    store.add_documents(documents, embedder)
    logging.info("索引完成，共写入 %d 个片段到 %s", len(documents), chroma_dir)


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
