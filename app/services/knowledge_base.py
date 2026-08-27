"""知识库管理服务：文件存储、分类、向量化、索引构建。

核心流程:
  1. 接收上传文件 → 存入原始文件目录 (rag/data/raw/{category}/)
  2. AutoClassifyAgent 自动分类 → 置信度评估
  3. 文档加载器切分 → Embedder 向量化 → ChromaDB 入库
  4. 记录元数据到 SQLite knowledge_files 表
"""

import logging
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from app.agents.auto_classify_agent import AutoClassifyAgent
from app.db import database
from rag.config import CHROMA_PERSIST_DIR, DATA_DIR

logger = logging.getLogger(__name__)

# 原始知识文件存放目录
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")

# 支持的文件扩展名
_SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf", ".doc", ".docx"}

# 分类 → 子目录映射
CATEGORY_DIR_MAP = {
    "strength": "strength",
    "endurance": "endurance",
    "nutrition": "nutrition",
    "physiology": "physiology",
    "technique": "technique",
    "sports_science": "sports_science",
    "general": "general",
}


class KnowledgeBaseService:
    """知识库管理服务。"""

    def __init__(self):
        self.classifier = AutoClassifyAgent()
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保所有分类目录存在。"""
        os.makedirs(RAW_DATA_DIR, exist_ok=True)
        for dir_name in CATEGORY_DIR_MAP.values():
            os.makedirs(
                os.path.join(RAW_DATA_DIR, dir_name), exist_ok=True
            )

    # ------------------------------------------------------------------
    # 文件上传 + 自动分类 + 向量化
    # ------------------------------------------------------------------

    def upload_and_index(
        self,
        file_content: bytes,
        original_filename: str,
        admin_id: str,
        force_category: Optional[str] = None,
        skip_index: bool = False,
    ) -> Dict:
        """上传知识文件并完成分类+向量化。

        Args:
            file_content: 文件二进制内容
            original_filename: 原始文件名
            admin_id: 上传管理员 ID
            force_category: 强制覆盖分类（管理员手动指定时）
            skip_index: 是否跳过向量化（仅存储）

        Returns:
            {file_id, category, confidence, chunk_count, status, ...}
        """
        file_id = uuid.uuid4().hex
        ext = Path(original_filename).suffix.lower()
        safe_name = f"{file_id}{ext}"

        # Step 1: 提取文本内容用于分类
        text_preview = self._extract_text_preview(file_content, ext)

        # Step 2: 自动分类
        if force_category and force_category in CATEGORY_DIR_MAP:
            classification = {
                "primary_category": force_category,
                "confidence": 1.0,
                "candidates": [],
                "needs_review": False,
                "reasoning": f"管理员指定分类: {force_category}",
            }
        else:
            classification = self.classifier.classify(
                text_preview, original_filename
            )

        category = classification["primary_category"]
        cat_dir = CATEGORY_DIR_MAP.get(category, "general")

        # Step 3: 存储原始文件到分类目录
        stored_dir = os.path.join(RAW_DATA_DIR, cat_dir)
        os.makedirs(stored_dir, exist_ok=True)
        stored_path = os.path.join(stored_dir, safe_name)
        with open(stored_path, "wb") as f:
            f.write(file_content)

        # Step 4: 记录到数据库
        database.insert_knowledge_file(
            file_id=file_id,
            filename=safe_name,
            original_filename=original_filename,
            stored_path=stored_path,
            category=category,
            classification_confidence=classification["confidence"],
            uploader=admin_id,
            status="pending",
        )

        result = {
            "file_id": file_id,
            "original_filename": original_filename,
            "category": category,
            "category_name": classification.get("primary_category_name", category),
            "confidence": classification["confidence"],
            "needs_review": classification["needs_review"],
            "reasoning": classification["reasoning"],
            "candidates": classification["candidates"],
            "stored_path": stored_path,
            "status": "pending",
            "chunk_count": 0,
        }

        # Step 5: 向量化索引
        if not skip_index and ext in {".md", ".txt", ".pdf"}:
            try:
                chunk_count = self._index_file(file_id, stored_path, category)
                result["status"] = "indexed"
                result["chunk_count"] = chunk_count
                result["indexed"] = True
            except Exception as exc:
                logger.exception("向量化失败: %s", file_id)
                database.update_knowledge_file(
                    file_id, status="failed", error_message=str(exc)
                )
                result["status"] = "failed"
                result["error"] = str(exc)
                result["indexed"] = False
        else:
            result["indexed"] = False
            result["index_skipped"] = True

        return result

    def _extract_text_preview(
        self, content: bytes, ext: str
    ) -> str:
        """提取文件前 N 字符作为分类特征。"""
        max_chars = 3000  # 前 3000 字符足够分类

        if ext in {".md", ".txt"}:
            for enc in ("utf-8", "gbk"):
                try:
                    text = content.decode(enc)
                    return text[:max_chars]
                except UnicodeDecodeError:
                    continue
            return ""
        elif ext == ".pdf":
            try:
                from pypdf import PdfReader
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                reader = PdfReader(tmp_path)
                text = ""
                for page in reader.pages[:3]:  # 只读前 3 页
                    text += (page.extract_text() or "") + "\n"
                os.unlink(tmp_path)
                return text[:max_chars]
            except Exception:
                return ""
        else:
            return ""

    def _index_file(
        self, file_id: str, file_path: str, category: str
    ) -> int:
        """将单个文件向量化并写入 ChromaDB。

        使用 SmartChunker 进行智能切块（章节感知/语义段落/动态颗粒度）。

        Returns:
            切分的 chunk 数量
        """
        from rag.embedder import FakeEmbedder, MiniLMEmbedder
        from rag.smart_chunker import SmartChunker
        from rag.vector_store import VectorStoreManager

        # 使用 SmartChunker 智能切块
        chunker = SmartChunker(mode="auto")
        chunks = chunker.chunk_file(file_path)
        if not chunks:
            raise ValueError("文件内容为空，无法切分")

        # 构建 Document 列表
        from rag.document_loader import Document
        documents = []
        for chunk in chunks:
            documents.append(Document(
                page_content=chunk.content,
                metadata={
                    "source": file_path,
                    "chunk_index": chunk.chunk_index,
                    "file_id": file_id,
                    "category": category,
                    "category_name": category,
                    "semantic_density": chunk.metadata.get("semantic_density", 0),
                    "mode": chunk.metadata.get("mode", "unknown"),
                    "token_count": chunk.metadata.get("token_count", 0),
                    "char_count": chunk.metadata.get("char_count", len(chunk.content)),
                },
            ))

        # 向量化并写入
        embedder_kind = os.environ.get("RAG_EMBEDDER", "fake")
        embedder = (
            MiniLMEmbedder() if embedder_kind == "minilm" else FakeEmbedder()
        )
        store = VectorStoreManager()
        store.add_documents(documents, embedder)

        # 更新数据库
        database.update_knowledge_file(
            file_id, chunk_count=len(chunks), status="indexed"
        )

        logger.info(
            "向量化完成: file=%s, chunks=%d, category=%s, chunker_mode=%s, "
            "avg_size=%.0f, density>0=%d",
            file_id, len(chunks), category,
            chunker.mode,
            chunker.stats.avg_chunk_size,
            chunker.stats.domain_terms_preserved,
        )
        return len(chunks)

    # ------------------------------------------------------------------
    # 管理操作
    # ------------------------------------------------------------------

    def list_files(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """列出知识库文件。"""
        files = database.list_knowledge_files(category=category, status=status)
        # 补充分类名称
        for f in files:
            cat = f.get("category", "general")
            f["category_name"] = self.classifier.get_supported_categories()
            f["category_display"] = cat
            # 获取完整分类名
            for c in self.classifier.get_supported_categories():
                if c["id"] == cat:
                    f["category_display"] = c["name"]
                    break
        return files

    def delete_file(self, file_id: str) -> Dict:
        """删除知识文件（同时删除原始文件和向量）。"""
        file_info = database.get_knowledge_file(file_id)
        if not file_info:
            return {"success": False, "error": "文件不存在"}

        # 删除原始文件
        stored_path = file_info.get("stored_path", "")
        if stored_path and os.path.exists(stored_path):
            os.remove(stored_path)

        # 删除向量
        try:
            self._remove_vectors_for_file(file_id)
        except Exception as e:
            logger.warning("删除向量时出错: %s", e)

        # 删除数据库记录
        database.delete_knowledge_file(file_id)

        return {"success": True, "file_id": file_id}

    def _remove_vectors_for_file(self, file_id: str):
        """从 ChromaDB 中删除指定文件的所有向量。"""
        from rag.vector_store import VectorStoreManager
        store = VectorStoreManager()
        collection = store.get_collection()
        # 查找所有包含 file_id 的文档
        all_data = collection.get(include=[])
        ids_to_delete = []
        if all_data and all_data.get("ids"):
            for idx, meta in enumerate(
                collection.get(include=["metadatas"])["metadatas"]
            ):
                if meta and meta.get("file_id") == file_id:
                    ids_to_delete.append(all_data["ids"][idx])
        if ids_to_delete:
            collection.delete(ids=ids_to_delete)
            logger.info("删除 %d 条向量 (file=%s)", len(ids_to_delete), file_id)

    def update_file_category(
        self, file_id: str, new_category: str
    ) -> Dict:
        """修改文件分类（管理员手动覆盖）。"""
        file_info = database.get_knowledge_file(file_id)
        if not file_info:
            return {"success": False, "error": "文件不存在"}

        old_category = file_info["category"]
        old_path = file_info["stored_path"]
        ext = Path(old_path).suffix

        # 移动文件到新分类目录
        new_cat_dir = CATEGORY_DIR_MAP.get(new_category, "general")
        new_dir = os.path.join(RAW_DATA_DIR, new_cat_dir)
        os.makedirs(new_dir, exist_ok=True)
        new_path = os.path.join(new_dir, os.path.basename(old_path))

        if os.path.exists(old_path) and old_path != new_path:
            shutil.move(old_path, new_path)

        # 更新数据库
        database.update_knowledge_file(
            file_id,
            category=new_category,
            classification_confidence=1.0,
        )

        # 如果已索引，需要更新向量中的 category metadata
        if file_info["status"] == "indexed":
            self._update_vectors_metadata(file_id, new_category, new_path)

        return {
            "success": True,
            "file_id": file_id,
            "old_category": old_category,
            "new_category": new_category,
            "new_path": new_path,
        }

    def _update_vectors_metadata(
        self, file_id: str, new_category: str, new_path: str
    ):
        """更新 ChromaDB 中指定文件的 metadata。

        使用 delete + add 方式避免 ChromaDB update 触发重新嵌入。
        """
        from rag.vector_store import VectorStoreManager
        store = VectorStoreManager()
        collection = store.get_collection()

        all_data = collection.get(include=["metadatas", "documents", "embeddings"])
        if not all_data or not all_data.get("ids"):
            return

        ids_to_delete = []
        new_metadatas = []
        new_documents = []
        new_ids = []

        for idx, meta in enumerate(all_data.get("metadatas", [])):
            if meta and meta.get("file_id") == file_id:
                ids_to_delete.append(all_data["ids"][idx])
                new_meta = dict(meta)
                new_meta["category"] = new_category
                new_meta["category_name"] = new_category
                new_meta["source"] = new_path
                new_metadatas.append(new_meta)
                new_documents.append(all_data["documents"][idx])
                new_ids.append(all_data["ids"][idx])

        if not ids_to_delete:
            return

        # 删除旧向量
        collection.delete(ids=ids_to_delete)

        # 重新写入（复用原始 embedding，避免重新计算）
        has_embeddings = all_data.get("embeddings") is not None
        embeddings_to_use = []
        if has_embeddings:
            for idx, eid in enumerate(all_data["ids"]):
                if eid in ids_to_delete:
                    embeddings_to_use.append(all_data["embeddings"][idx])

        if embeddings_to_use:
            collection.add(
                ids=new_ids,
                embeddings=embeddings_to_use,
                documents=new_documents,
                metadatas=new_metadatas,
            )

        logger.info(
            "更新 %d 条向量 metadata (file=%s)", len(ids_to_delete), file_id
        )

    def rebuild_index(self) -> Dict:
        """重建整个知识库索引（删除所有向量，重新索引所有文件）。"""
        # 1. 清空 ChromaDB
        from rag.vector_store import VectorStoreManager
        store = VectorStoreManager()
        store.reset()

        # 2. 重新索引所有文件
        all_files = database.list_knowledge_files()
        total_chunks = 0
        indexed = 0
        failed = 0

        for f in all_files:
            if f["status"] == "failed":
                continue
            try:
                chunks = self._index_file(
                    f["file_id"], f["stored_path"], f["category"]
                )
                total_chunks += chunks
                indexed += 1
            except Exception as e:
                database.update_knowledge_file(
                    f["file_id"], status="failed", error_message=str(e)
                )
                failed += 1

        return {
            "total_files": len(all_files),
            "indexed": indexed,
            "failed": failed,
            "total_chunks": total_chunks,
        }

    def get_stats(self) -> Dict:
        """获取知识库统计。"""
        db_stats = database.get_knowledge_stats()
        cat_list = self.classifier.get_supported_categories()
        # 补充每个分类的中文名
        categories_with_name = {}
        for cat_id, count in db_stats["categories"].items():
            name = cat_id
            for c in cat_list:
                if c["id"] == cat_id:
                    name = c["name"]
                    break
            categories_with_name[cat_id] = {
                "name": name,
                "count": count,
            }
        return {
            **db_stats,
            "categories_detail": categories_with_name,
            "supported_categories": cat_list,
        }

    def reclassify_file(self, file_id: str) -> Dict:
        """重新对文件进行自动分类（当分类策略更新时使用）。"""
        file_info = database.get_knowledge_file(file_id)
        if not file_info:
            return {"success": False, "error": "文件不存在"}

        text = self._extract_text_preview(
            open(file_info["stored_path"], "rb").read(),
            Path(file_info["stored_path"]).suffix,
        )
        result = self.classifier.classify(
            text, file_info["original_filename"]
        )

        database.update_knowledge_file(
            file_id,
            category=result["primary_category"],
            classification_confidence=result["confidence"],
        )

        return {
            "success": True,
            "file_id": file_id,
            "new_category": result["primary_category"],
            "confidence": result["confidence"],
            "reasoning": result["reasoning"],
        }
