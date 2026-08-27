"""智能切块策略：多种切分方式 + 动态颗粒度 + 章节感知。

支持四种切块模式：
1. **按章节切分**（Markdown 标题/一级/二级标题为边界）
2. **按语义段落切分**（自然段落为边界）
3. **固定长度切分**（带 overlap，保底方案）
4. **动态颗粒度**（根据内容密度自动调整 chunk_size）

核心设计思想：
- 切块不是越小越好，也不是越大越好
- 颗粒度需要匹配查询的期望粒度
- 运动领域专业术语（如"VO2max""乳酸阈值"）不应被切断
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from langchain_text_splitters import (
    RecursiveCharacterTextSplitter,
    MarkdownTextSplitter,
)

from rag.config import CHUNK_OVERLAP, CHUNK_SIZE

logger = logging.getLogger(__name__)

# 运动领域专业术语（切块时保护不被切断）
DOMAIN_TERMS = [
    "VO2max", "VO2", "乳酸阈值", "LT", "OBLA",
    "心率变异性", "HRV", "RPE", "1RM",
    "宏量营养素", "微量营养素", "GI值",
    "周期化训练", "周期化", "Tapering",
    "DOMS", "EPOC", "脂肪燃烧区",
    "最大摄氧量", "有氧能力", "无氧能力",
    "基础代谢", "TDEE", "BMR",
]


@dataclass
class Chunk:
    """增强版文档片段，包含位置和结构信息。"""
    content: str
    metadata: Dict = field(default_factory=dict)
    chunk_index: int = 0
    section_path: str = ""  # 章节路径，如 "跑步/训练原则/间歇训练"
    token_count: int = 0
    semantic_density: float = 0.0  # 语义密度（专业术语占比）


@dataclass
class ChunkingStats:
    """切块统计信息，用于评估颗粒度合理性。"""
    total_chunks: int = 0
    avg_chunk_size: float = 0.0
    min_chunk_size: int = 0
    max_chunk_size: int = 0
    std_dev: float = 0.0
    outlier_chunks: int = 0  # 过大/过小的异常块数
    domain_terms_preserved: int = 0  # 完整保留的专业术语数


class SmartChunker:
    """智能切块器。

    Usage:
        chunker = SmartChunker(mode="section_aware")
        chunks = chunker.chunk_file("nutrition_guide.md")
        chunks = chunker.chunk_text(text, source="manual")
    """

    def __init__(
        self,
        mode: str = "auto",
        target_chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1500,
    ):
        """
        Args:
            mode: 切块模式
                - "section_aware": 按章节边界切分（推荐用于 Markdown）
                - "semantic": 按语义段落切分
                - "fixed": 固定长度切分
                - "auto": 自动选择（根据文件类型）
            target_chunk_size: 目标 chunk 大小（字符数）
            chunk_overlap: 相邻 chunk 重叠字符数
            min_chunk_size: 最小 chunk 大小（低于此值合并）
            max_chunk_size: 最大 chunk 大小（高于此值强制拆分）
        """
        self.mode = mode
        self.target_chunk_size = target_chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self._stats = ChunkingStats()

    @property
    def stats(self) -> ChunkingStats:
        return self._stats

    def chunk_file(self, file_path: str) -> List[Chunk]:
        """从文件加载并切块。"""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(file_path)

        # 读取内容
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            text = self._read_pdf(path)
        else:
            text = self._read_text(path)

        # 选择模式
        effective_mode = self.mode
        if self.mode == "auto":
            effective_mode = self._auto_select_mode(suffix)

        chunks = self.chunk_text(
            text, source=str(path), mode=effective_mode
        )
        return chunks

    def chunk_text(
        self,
        text: str,
        source: str = "unknown",
        mode: Optional[str] = None,
    ) -> List[Chunk]:
        """将文本切块。"""
        active_mode = mode or self.mode
        clean_text = text.strip()
        if not clean_text:
            return []

        # 保护专业术语不被切断
        protected_text = self._protect_domain_terms(clean_text)

        # 根据模式切分
        raw_chunks = self._split_by_mode(protected_text, active_mode)

        # 后处理：恢复术语、过滤过小/合并
        chunks = self._post_process(raw_chunks, source)

        # 更新统计
        self._update_stats(chunks)

        return chunks

    def _split_by_mode(self, text: str, mode: str) -> List[str]:
        """根据模式选择切分策略。"""
        if mode == "section_aware":
            return self._split_by_sections(text)
        elif mode == "semantic":
            return self._split_by_semantic(text)
        elif mode == "fixed":
            return self._split_fixed(text)
        else:
            return self._split_fixed(text)

    def _split_by_sections(self, text: str) -> List[str]:
        """按章节边界切分（Markdown/标题感知）。

        策略：
        1. 识别 Markdown 标题 (# / ## / ###)
        2. 按一级/二级标题为边界分割
        3. 过长的章节内部再递归切分
        """
        # 识别标题行
        heading_pattern = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)

        # 找到所有标题位置
        headings = [(m.start(), m.group(1), m.group(2)) for m in heading_pattern.finditer(text)]

        if headings:
            # 按标题切分
            chunks = []
            boundaries = [0] + [h[0] for h in headings] + [len(text)]

            for i in range(len(boundaries) - 1):
                start = boundaries[i]
                end = boundaries[i + 1]
                section = text[start:end].strip()
                if section:
                    # 如果章节过长，内部递归切分
                    if len(section) > self.max_chunk_size:
                        sub_chunks = self._split_fixed(section)
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append(section)

            return chunks
        else:
            # 无标题，回退到语义切分
            return self._split_by_semantic(text)

    def _split_by_semantic(self, text: str) -> List[str]:
        """按语义段落切分。

        策略：
        1. 先按段落（双换行）分割
        2. 合并过短段落到相邻段落
        3. 过长段落内部递归切分
        """
        paragraphs = re.split(r'\n\s*\n', text)
        chunks: List[str] = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 如果当前块加上新段落不超过 max，合并
            if current_chunk and len(current_chunk) + len(para) < self.max_chunk_size:
                current_chunk += "\n\n" + para
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = para

            # 如果当前块超过 max，强制切分
            if len(current_chunk) > self.max_chunk_size:
                sub = self._split_fixed(current_chunk)
                chunks.extend(sub[:-1])
                current_chunk = sub[-1] if sub else ""

        if current_chunk:
            chunks.append(current_chunk)

        # 合并过小的块
        chunks = self._merge_small_chunks(chunks)
        return chunks

    def _split_fixed(self, text: str) -> List[str]:
        """固定长度切分（带 overlap）。"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.target_chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""],
        )
        return splitter.split_text(text)

    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """合并过小的 chunk。"""
        if not chunks:
            return chunks

        merged: List[str] = []
        buffer = ""

        for chunk in chunks:
            if len(chunk) < self.min_chunk_size:
                buffer += "\n" + chunk
            else:
                if buffer:
                    chunk = buffer + "\n" + chunk
                    buffer = ""
                merged.append(chunk)

        if buffer:
            # 最后一块如果还小，合并到前一块
            if merged:
                merged[-1] += "\n" + buffer
            else:
                merged.append(buffer)

        return merged

    def _auto_select_mode(self, suffix: str) -> str:
        """根据文件类型自动选择切块模式。"""
        if suffix == ".md":
            return "section_aware"
        elif suffix == ".pdf":
            return "semantic"
        else:
            return "semantic"

    def _protect_domain_terms(self, text: str) -> str:
        """保护专业术语不被切断。

        用特殊标记替换专业术语，切块后恢复。
        """
        protected = text
        for term in sorted(DOMAIN_TERMS, key=len, reverse=True):
            placeholder = f"\x00{term}\x00"
            protected = protected.replace(term, placeholder)
        return protected

    def _restore_domain_terms(self, text: str) -> str:
        """恢复被保护的专业术语。"""
        return text.replace("\x00", "")

    def _post_process(self, raw_chunks: List[str], source: str) -> List[Chunk]:
        """后处理：恢复术语、计算元数据、过滤空块。"""
        chunks: List[Chunk] = []
        term_count = 0

        for idx, raw in enumerate(raw_chunks):
            content = self._restore_domain_terms(raw.strip())
            if not content:
                continue

            # 计算 token 数（粗估：中文字符=1 token，英文单词≈1.3 token）
            token_count = self._estimate_tokens(content)

            # 计算语义密度（专业术语占比）
            semantic_density = self._calc_semantic_density(content)
            if semantic_density > 0:
                term_count += 1

            chunks.append(Chunk(
                content=content,
                chunk_index=idx,
                metadata={
                    "source": source,
                    "chunk_index": idx,
                    "token_count": token_count,
                    "char_count": len(content),
                    "semantic_density": round(semantic_density, 3),
                    "mode": self.mode,
                },
            ))

        self._stats.domain_terms_preserved = term_count
        return chunks

    def _estimate_tokens(self, text: str) -> int:
        """粗估 token 数。"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_text = ''.join(c for c in text if not '\u4e00' <= c <= '\u9fff')
        words = len(other_text.split())
        return int(chinese_chars + words * 1.3)

    def _calc_semantic_density(self, text: str) -> float:
        """计算语义密度：专业术语出现数 / 总词数。"""
        term_hits = 0
        for term in DOMAIN_TERMS:
            term_hits += text.count(term)
        total_words = len(text.split()) + 1
        return term_hits / total_words

    def _update_stats(self, chunks: List[Chunk]) -> None:
        """更新切块统计。"""
        if not chunks:
            return

        sizes = [len(c.content) for c in chunks]
        self._stats.total_chunks = len(chunks)
        self._stats.avg_chunk_size = sum(sizes) / len(sizes)
        self._stats.min_chunk_size = min(sizes)
        self._stats.max_chunk_size = max(sizes)

        # 标准差
        mean = self._stats.avg_chunk_size
        variance = sum((s - mean) ** 2 for s in sizes) / len(sizes)
        self._stats.std_dev = variance ** 0.5

        # 异常块数（偏离均值 2 倍标准差）
        lower = mean - 2 * self._stats.std_dev
        upper = mean + 2 * self._stats.std_dev
        self._stats.outlier_chunks = sum(
            1 for s in sizes if s < lower or s > upper
        )

    def _read_text(self, path: Path) -> str:
        for encoding in ("utf-8", "gbk"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise UnicodeDecodeError(f"无法解码文件 {path}")

    def _read_pdf(self, path: Path) -> str:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
