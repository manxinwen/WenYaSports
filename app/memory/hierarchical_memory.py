"""Hierarchical Memory System: 三层分级记忆架构。

核心设计：
- WorkingMemory: 短期会话级记忆，保存当前上下文（最近N条消息、活跃任务状态）
- EpisodicMemory: 中期情节记忆，存储对话片段及元数据（时间戳、主题、涉及Agent、结果）
- SemanticMemory: 长期语义记忆，基于TF-IDF风格的关键词+元数据过滤检索，存储领域知识

设计理念：
- 模拟人类记忆的三级模型：工作记忆（意识）→ 情节记忆（经历）→ 语义记忆（知识）
- 自动路由：store() 根据内容类型自动选择最合适的记忆层
- 可衰减性：工作记忆自动清理旧条目
- 可导出/导入：支持持久化到JSON文件

Architecture:
    Store(content) → [Auto Router] → Working / Episodic / Semantic
    Retrieve(query) → [Cross-Layer Search] → Merged Results
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TF-IDF 风格文本检索工具
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """简单的中英文分词：按空格/标点切分，同时支持单字切分。"""
    tokens = []
    for chunk in text.lower().split():
        # 英文按单词
        tokens.append(chunk)
        # 中文按单字
        if any('\u4e00' <= c <= '\u9fff' for c in chunk):
            for ch in chunk:
                if not ch.isspace():
                    tokens.append(ch)
    return tokens


def _compute_tf(tokens: List[str]) -> Dict[str, float]:
    """计算词频（Term Frequency）。"""
    if not tokens:
        return {}
    counter = Counter(tokens)
    total = len(tokens)
    return {word: count / total for word, count in counter.items()}


def _compute_idf(documents: List[List[str]]) -> Dict[str, float]:
    """计算逆文档频率（Inverse Document Frequency）。"""
    total_docs = len(documents)
    if total_docs == 0:
        return {}
    df = Counter()
    for doc_tokens in documents:
        unique = set(doc_tokens)
        for token in unique:
            df[token] += 1
    idf = {}
    for token, count in df.items():
        idf[token] = math.log((total_docs + 1) / (count + 1)) + 1.0
    return idf


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """计算两个稀疏向量的余弦相似度。"""
    common = set(vec_a.keys()) & set(vec_b.keys())
    if not common:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Working Memory (短期工作记忆)
# ---------------------------------------------------------------------------

@dataclass
class WorkingMemoryEntry:
    """工作记忆条目。"""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    message_type: str = "message"


class WorkingMemory:
    """短期会话级记忆。

    保存当前会话的最近N条消息和活跃任务状态，
    支持基于时间的自动衰减清理。

    Args:
        max_entries: 最大保留条目数
        ttl_seconds: 条目存活时间（秒），None表示不过期
    """

    def __init__(self, max_entries: int = 50, ttl_seconds: Optional[float] = None):
        self._entries: List[WorkingMemoryEntry] = []
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds

    def store(self, content: str, metadata: Optional[Dict[str, Any]] = None,
              message_type: str = "message") -> WorkingMemoryEntry:
        """存储一条工作记忆条目。"""
        self._cleanup()
        entry = WorkingMemoryEntry(
            content=content,
            metadata=metadata or {},
            message_type=message_type,
        )
        self._entries.append(entry)
        # 超限则移除最旧条目
        while len(self._entries) > self._max_entries:
            self._entries.pop(0)
        return entry

    def retrieve(self, query: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """检索工作记忆。

        Args:
            query: 查询文本（为None时返回最近的条目）
            top_k: 返回结果数量
        """
        self._cleanup()
        if not self._entries:
            return []

        if query is None:
            results = list(reversed(self._entries[-top_k:]))
            return [self._entry_to_dict(e) for e in results]

        query_tokens = _tokenize(query)
        query_tf = _compute_tf(query_tokens)

        scored = []
        for entry in self._entries:
            entry_tokens = _tokenize(entry.content)
            if not entry_tokens:
                continue
            entry_tf = _compute_tf(entry_tokens)
            sim = _cosine_similarity(query_tf, entry_tf)
            if sim > 0:
                scored.append((sim, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._entry_to_dict(e) for _, e in scored[:top_k]]

    def get_recent(self, n: int = 5) -> List[Dict[str, Any]]:
        """获取最近N条工作记忆。"""
        self._cleanup()
        return [self._entry_to_dict(e) for e in list(reversed(self._entries[-n:]))]

    def _cleanup(self) -> None:
        """清理过期条目。"""
        if self._ttl_seconds is None:
            return
        now = time.time()
        self._entries = [
            e for e in self._entries
            if (now - e.timestamp) <= self._ttl_seconds
        ]

    def _entry_to_dict(self, entry: WorkingMemoryEntry) -> Dict[str, Any]:
        return {
            "content": entry.content,
            "metadata": entry.metadata,
            "timestamp": entry.timestamp,
            "message_type": entry.message_type,
            "level": "working",
        }

    def export(self) -> Dict[str, Any]:
        """导出工作记忆数据。"""
        return {
            "max_entries": self._max_entries,
            "ttl_seconds": self._ttl_seconds,
            "entries": [asdict(e) for e in self._entries],
        }

    def import_(self, data: Dict[str, Any]) -> None:
        """导入工作记忆数据。"""
        self._max_entries = data.get("max_entries", 50)
        self._ttl_seconds = data.get("ttl_seconds")
        self._entries = [
            WorkingMemoryEntry(**e) for e in data.get("entries", [])
        ]

    def clear(self) -> None:
        """清空所有工作记忆。"""
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Episodic Memory (情节记忆)
# ---------------------------------------------------------------------------

@dataclass
class EpisodicEntry:
    """情节记忆条目。"""
    content: str
    topic: str = ""
    agents: List[str] = field(default_factory=list)
    outcome: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EpisodicMemory:
    """中期情节记忆。

    存储对话片段及其元数据（时间戳、主题、涉及Agent、结果），
    支持按主题、Agent、结果等多维度过滤检索。

    Args:
        max_episodes: 最大保存情节数量
    """

    def __init__(self, max_episodes: int = 1000):
        self._episodes: List[EpisodicEntry] = []
        self._max_episodes = max_episodes

    def store(self, content: str, topic: str = "",
              agents: Optional[List[str]] = None, outcome: str = "",
              metadata: Optional[Dict[str, Any]] = None) -> EpisodicEntry:
        """存储一个情节条目。"""
        entry = EpisodicEntry(
            content=content,
            topic=topic,
            agents=agents or [],
            outcome=outcome,
            metadata=metadata or {},
        )
        self._episodes.append(entry)
        while len(self._episodes) > self._max_episodes:
            self._episodes.pop(0)
        return entry

    def retrieve(self, query: Optional[str] = None,
                 topic: Optional[str] = None,
                 agent: Optional[str] = None,
                 outcome: Optional[str] = None,
                 metadata_filter: Optional[Dict[str, Any]] = None,
                 top_k: int = 5) -> List[Dict[str, Any]]:
        """检索情节记忆。

        Args:
            query: 文本查询（基于内容的TF-IDF检索）
            topic: 按主题过滤
            agent: 按涉及的Agent过滤
            outcome: 按结果过滤
            metadata_filter: 按元数据键值对过滤
            top_k: 返回结果数量
        """
        candidates = list(self._episodes)

        # 元数据过滤
        if metadata_filter:
            candidates = [
                e for e in candidates
                if all(e.metadata.get(k) == v for k, v in metadata_filter.items())
            ]

        # 关键词过滤（内容+主题+结果）
        if topic:
            topic_lower = topic.lower()
            candidates = [e for e in candidates if topic_lower in e.topic.lower()]

        if agent:
            agent_lower = agent.lower()
            candidates = [
                e for e in candidates
                if any(agent_lower in a.lower() for a in e.agents)
            ]

        if outcome:
            outcome_lower = outcome.lower()
            candidates = [e for e in candidates if outcome_lower in e.outcome.lower()]

        if not candidates:
            return []

        if query is None:
            results = list(reversed(candidates[-top_k:]))
            return [self._entry_to_dict(e) for e in results]

        # TF-IDF 文本相关性排序
        query_tokens = _tokenize(query)
        query_tf = _compute_tf(query_tokens)

        scored = []
        for entry in candidates:
            combined_text = f"{entry.topic} {entry.content} {entry.outcome}"
            entry_tokens = _tokenize(combined_text)
            if not entry_tokens:
                continue
            entry_tf = _compute_tf(entry_tokens)
            sim = _cosine_similarity(query_tf, entry_tf)
            if sim > 0:
                scored.append((sim, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            results = list(reversed(candidates[-top_k:]))
            return [self._entry_to_dict(e) for e in results]

        return [self._entry_to_dict(e) for _, e in scored[:top_k]]

    def _entry_to_dict(self, entry: EpisodicEntry) -> Dict[str, Any]:
        return {
            "content": entry.content,
            "topic": entry.topic,
            "agents": entry.agents,
            "outcome": entry.outcome,
            "timestamp": entry.timestamp,
            "metadata": entry.metadata,
            "level": "episodic",
        }

    def export(self) -> Dict[str, Any]:
        """导出情节记忆数据。"""
        return {
            "max_episodes": self._max_episodes,
            "episodes": [asdict(e) for e in self._episodes],
        }

    def import_(self, data: Dict[str, Any]) -> None:
        """导入情节记忆数据。"""
        self._max_episodes = data.get("max_episodes", 1000)
        self._episodes = [
            EpisodicEntry(**e) for e in data.get("episodes", [])
        ]

    def clear(self) -> None:
        """清空所有情节记忆。"""
        self._episodes.clear()

    def __len__(self) -> int:
        return len(self._episodes)


# ---------------------------------------------------------------------------
# Semantic Memory (语义记忆)
# ---------------------------------------------------------------------------

@dataclass
class SemanticEntry:
    """语义记忆条目。"""
    content: str
    source: str = ""
    domain: str = ""
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SemanticMemory:
    """长期语义记忆。

    基于TF-IDF风格的关键词+元数据过滤检索，存储领域知识和事实。
    支持混合检索：先按元数据过滤候选集，再用TF-IDF文本排序。

    Args:
        max_entries: 最大保存条目数量
    """

    def __init__(self, max_entries: int = 5000):
        self._entries: List[SemanticEntry] = []
        self._max_entries = max_entries
        self._idf_cache: Optional[Dict[str, float]] = None

    def store(self, content: str, source: str = "",
              domain: str = "", tags: Optional[List[str]] = None,
              metadata: Optional[Dict[str, Any]] = None) -> SemanticEntry:
        """存储一个语义知识条目。"""
        entry = SemanticEntry(
            content=content,
            source=source,
            domain=domain,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._entries.append(entry)
        self._idf_cache = None
        while len(self._entries) > self._max_entries:
            self._entries.pop(0)
        return entry

    def retrieve(self, query: str,
                 domain: Optional[str] = None,
                 tags: Optional[List[str]] = None,
                 source: Optional[str] = None,
                 metadata_filter: Optional[Dict[str, Any]] = None,
                 top_k: int = 5) -> List[Dict[str, Any]]:
        """检索语义记忆。

        Args:
            query: 查询文本
            domain: 按领域过滤
            tags: 按标签过滤（任一匹配即可）
            source: 按来源过滤
            metadata_filter: 按元数据键值对过滤
            top_k: 返回结果数量
        """
        candidates = list(self._entries)

        # 元数据过滤
        if metadata_filter:
            candidates = [
                e for e in candidates
                if all(e.metadata.get(k) == v for k, v in metadata_filter.items())
            ]

        # 领域过滤
        if domain:
            domain_lower = domain.lower()
            candidates = [e for e in candidates if domain_lower in e.domain.lower()]

        # 标签过滤
        if tags:
            tags_lower = [t.lower() for t in tags]
            candidates = [
                e for e in candidates
                if any(t in [tag.lower() for tag in e.tags] for t in tags_lower)
            ]

        # 来源过滤
        if source:
            source_lower = source.lower()
            candidates = [e for e in candidates if source_lower in e.source.lower()]

        if not candidates or not query:
            results = list(reversed(candidates[-top_k:]))
            return [self._entry_to_dict(e) for e in results]

        # TF-IDF 评分
        query_tokens = _tokenize(query)
        query_tf = _compute_tf(query_tokens)

        # 使用候选集计算IDF
        candidate_token_lists = [
            _tokenize(f"{e.domain} {' '.join(e.tags)} {e.content}")
            for e in candidates
        ]
        idf = _compute_idf(candidate_token_lists)

        # 计算查询的TF-IDF向量
        query_tfidf = {
            token: tf * idf.get(token, 1.0)
            for token, tf in query_tf.items()
        }

        scored = []
        for entry, doc_tokens in zip(candidates, candidate_token_lists):
            if not doc_tokens:
                continue
            doc_tf = _compute_tf(doc_tokens)
            doc_tfidf = {
                token: tf * idf.get(token, 1.0)
                for token, tf in doc_tf.items()
            }
            sim = _cosine_similarity(query_tfidf, doc_tfidf)
            if sim > 0:
                scored.append((sim, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            results = list(reversed(candidates[-top_k:]))
            return [self._entry_to_dict(e) for e in results]

        return [self._entry_to_dict(e) for _, e in scored[:top_k]]

    def _entry_to_dict(self, entry: SemanticEntry) -> Dict[str, Any]:
        return {
            "content": entry.content,
            "source": entry.source,
            "domain": entry.domain,
            "tags": entry.tags,
            "timestamp": entry.timestamp,
            "metadata": entry.metadata,
            "level": "semantic",
        }

    def export(self) -> Dict[str, Any]:
        """导出语义记忆数据。"""
        return {
            "max_entries": self._max_entries,
            "entries": [asdict(e) for e in self._entries],
        }

    def import_(self, data: Dict[str, Any]) -> None:
        """导入语义记忆数据。"""
        self._max_entries = data.get("max_entries", 5000)
        self._entries = [
            SemanticEntry(**e) for e in data.get("entries", [])
        ]
        self._idf_cache = None

    def clear(self) -> None:
        """清空所有语义记忆。"""
        self._entries.clear()
        self._idf_cache = None

    def __len__(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Hierarchical Memory Orchestrator (三层分级记忆协调器)
# ---------------------------------------------------------------------------

class HierarchicalMemory:
    """三层分级记忆协调器。

    统一协调工作记忆、情节记忆和语义记忆三层，
    提供跨层检索和自动路由存储能力。

    Usage:
        memory = HierarchicalMemory()
        memory.store("用户问了跑步配速", level="auto", metadata={"topic": "running"})
        results = memory.retrieve("配速", level="semantic", top_k=5)
        memory.export_to_file("memory_backup.json")
    """

    def __init__(self, working_max: int = 50, episodic_max: int = 1000,
                 semantic_max: int = 5000,
                 working_ttl: Optional[float] = None):
        self.working = WorkingMemory(max_entries=working_max, ttl_seconds=working_ttl)
        self.episodic = EpisodicMemory(max_episodes=episodic_max)
        self.semantic = SemanticMemory(max_entries=semantic_max)

    # ------------------------------------------------------------------
    # 存储
    # ------------------------------------------------------------------
    def store(self, content: str, level: str = "auto",
              metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """存储内容到指定记忆层。

        Args:
            content: 记忆内容
            level: 目标层 - "working" | "episodic" | "semantic" | "auto"
            metadata: 元数据
            **kwargs: 传递给底层存储的额外参数
                - episodic: topic, agents, outcome
                - semantic: source, domain, tags

        Returns:
            存储结果字典，包含 level 和 entry 信息
        """
        metadata = metadata or {}

        if level == "auto":
            level = self._auto_route(content, metadata, **kwargs)

        if level == "working":
            entry = self.working.store(content=content, metadata=metadata)
            return {"level": "working", "entry": self.working._entry_to_dict(entry)}

        elif level == "episodic":
            entry = self.episodic.store(
                content=content,
                topic=kwargs.get("topic", metadata.get("topic", "")),
                agents=kwargs.get("agents", metadata.get("agents", [])),
                outcome=kwargs.get("outcome", metadata.get("outcome", "")),
                metadata=metadata,
            )
            return {"level": "episodic", "entry": self.episodic._entry_to_dict(entry)}

        elif level == "semantic":
            entry = self.semantic.store(
                content=content,
                source=kwargs.get("source", metadata.get("source", "")),
                domain=kwargs.get("domain", metadata.get("domain", "")),
                tags=kwargs.get("tags", metadata.get("tags", [])),
                metadata=metadata,
            )
            return {"level": "semantic", "entry": self.semantic._entry_to_dict(entry)}

        else:
            raise ValueError(f"Unknown level: {level}. Use 'auto', 'working', 'episodic', or 'semantic'.")

    def _auto_route(self, content: str, metadata: Dict[str, Any],
                    **kwargs) -> str:
        """根据内容特征自动路由到最合适的记忆层。

        路由逻辑：
        - 有 domain/source/tags 等知识属性 → semantic
        - 有 topic/agents/outcome 等情节属性 → episodic
        - 其他（对话片段、当前上下文）→ working
        """
        semantic_keys = {"source", "domain", "tags"}
        episodic_keys = {"topic", "agents", "outcome"}

        md_keys = set(metadata.keys())
        kw_keys = set(kwargs.keys())
        all_keys = md_keys | kw_keys

        if all_keys & semantic_keys or kwargs.get("domain") or kwargs.get("tags"):
            return "semantic"

        if all_keys & episodic_keys or kwargs.get("topic") or kwargs.get("agents"):
            return "episodic"

        return "working"

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------
    def retrieve(self, query: str, level: Optional[str] = None,
                 top_k: int = 5, **kwargs) -> List[Dict[str, Any]]:
        """从指定层或所有层检索记忆。

        Args:
            query: 查询文本
            level: 检索层 - None=全层搜索, "working", "episodic", "semantic"
            top_k: 每层返回结果数量上限
            **kwargs: 传递给底层检索的过滤参数

        Returns:
            检索结果列表
        """
        if level is None:
            return self._cross_layer_search(query, top_k, **kwargs)

        elif level == "working":
            return self.working.retrieve(query=query, top_k=top_k)

        elif level == "episodic":
            return self.episodic.retrieve(query=query, top_k=top_k, **kwargs)

        elif level == "semantic":
            return self.semantic.retrieve(query=query, top_k=top_k, **kwargs)

        else:
            raise ValueError(f"Unknown level: {level}")

    def _cross_layer_search(self, query: str, top_k: int,
                            **kwargs) -> List[Dict[str, Any]]:
        """跨层检索，合并结果并标注来源层。"""
        all_results = []

        working_results = self.working.retrieve(query=query, top_k=top_k)
        for r in working_results:
            r["score"] = r.get("score", 0.0) + 0.3
        all_results.extend(working_results)

        episodic_results = self.episodic.retrieve(query=query, top_k=top_k, **kwargs)
        for r in episodic_results:
            r["score"] = r.get("score", 0.0) + 0.2
        all_results.extend(episodic_results)

        semantic_results = self.semantic.retrieve(query=query, top_k=top_k, **kwargs)
        for r in semantic_results:
            r["score"] = r.get("score", 0.0) + 0.1
        all_results.extend(semantic_results)

        all_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return all_results[:top_k]

    # ------------------------------------------------------------------
    # 导入/导出
    # ------------------------------------------------------------------
    def export(self) -> Dict[str, Any]:
        """导出整个分级记忆系统的所有数据。"""
        return {
            "version": "1.0",
            "working": self.working.export(),
            "episodic": self.episodic.export(),
            "semantic": self.semantic.export(),
        }

    def export_to_file(self, filepath: str) -> None:
        """将记忆系统导出到JSON文件。"""
        data = self.export()
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def import_(self, data: Dict[str, Any]) -> None:
        """导入记忆系统数据。"""
        self.working.import_(data.get("working", {}))
        self.episodic.import_(data.get("episodic", {}))
        self.semantic.import_(data.get("semantic", {}))

    def import_from_file(self, filepath: str) -> None:
        """从JSON文件导入记忆系统数据。"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.import_(data)

    # ------------------------------------------------------------------
    # 实用方法
    # ------------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        """获取记忆系统统计信息。"""
        return {
            "working_count": len(self.working),
            "episodic_count": len(self.episodic),
            "semantic_count": len(self.semantic),
            "working_max": self.working._max_entries,
            "episodic_max": self.episodic._max_episodes,
            "semantic_max": self.semantic._max_entries,
        }

    def clear(self, level: Optional[str] = None) -> None:
        """清空指定层或所有层。"""
        if level is None:
            self.working.clear()
            self.episodic.clear()
            self.semantic.clear()
        elif level == "working":
            self.working.clear()
        elif level == "episodic":
            self.episodic.clear()
        elif level == "semantic":
            self.semantic.clear()
        else:
            raise ValueError(f"Unknown level: {level}")