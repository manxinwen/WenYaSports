"""文档加载与切分：遍历目录读取 .md / .txt / .pdf，切分为语义片段。

- 使用 ``langchain_text_splitters.RecursiveCharacterTextSplitter`` 按
  ``CHUNK_SIZE`` / ``CHUNK_OVERLAP`` 递归切分；
- 每个片段携带 ``metadata``：``source``（文件路径）、``chunk_index``。
"""

import logging
from pathlib import Path
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import CHUNK_OVERLAP, CHUNK_SIZE

logger = logging.getLogger(__name__)

_SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf"}


class Document:
    """一个文档片段：正文 + 元数据。"""

    __slots__ = ("page_content", "metadata")

    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata

    def to_dict(self) -> dict:
        return {"content": self.page_content, **self.metadata}


def _read_text(path: Path) -> str:
    """读取文本文件（自动尝试 UTF-8 / GBK）。"""
    for encoding in ("utf-8", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError(f"无法解码文件 {path}")


def _read_pdf(path: Path) -> str:
    """使用 pypdf 提取 PDF 文本。"""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _split_chunks(text: str) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", " ", ""],
    )
    return splitter.split_text(text)


def load_documents_from_directory(directory_path: str) -> List[Document]:
    """加载目录下所有支持的文档并切分为片段。

    :param directory_path: 文档目录（含 .md / .txt / .pdf）。
    :return: Document 片段列表，metadata 含 source 与 chunk_index。
    """
    root = Path(directory_path)
    if not root.is_dir():
        raise FileNotFoundError(f"文档目录不存在: {root}")

    documents: List[Document] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        try:
            if path.suffix.lower() == ".pdf":
                text = _read_pdf(path)
            else:
                text = _read_text(path)
        except Exception as exc:  # noqa: BLE001 - 单个文件失败不阻断整体
            logger.warning("读取文档失败，已跳过 %s: %s", path, exc)
            continue

        chunks = _split_chunks(text.strip())
        for index, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            documents.append(
                Document(
                    page_content=chunk.strip(),
                    metadata={"source": str(path), "chunk_index": index},
                )
            )
        logger.info("加载 %s: %d 个片段", path.name, len(chunks))
    return documents
