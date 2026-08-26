"""RAG 个人 AI 私教模块测试。

关键设计：测试一律使用 FakeEmbedder（确定性哈希向量）与临时 Chroma 目录，
**不下载 MiniLM 模型、不依赖外部网络**，保证 CI 可跑。
"""

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from rag.document_loader import Document, load_documents_from_directory
from rag.embedder import FakeEmbedder
from rag.knowledge_agent import KnowledgeAgent
from rag.prompts import KNOWLEDGE_QA_PROMPT, format_knowledge
from rag.vector_store import VectorStoreManager


# ----------------------------------------------------------------------
# 1. 文档加载与切分
# ----------------------------------------------------------------------
def _write_doc(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_load_documents_from_directory(tmp_path):
    _write_doc(tmp_path, "running.md", "跑步训练应遵循循序渐进原则。\n" * 30)
    _write_doc(tmp_path, "recovery.txt", "恢复是训练的一部分。\n" * 20)
    docs = load_documents_from_directory(str(tmp_path))
    # 两个文件都加载，且长文本被切成多个片段
    assert len(docs) > 0
    sources = {d.metadata["source"] for d in docs}
    assert len(sources) == 2
    # 每个片段带 source 和 chunk_index
    assert all("source" in d.metadata and "chunk_index" in d.metadata for d in docs)
    # 片段不超过 CHUNK_SIZE + overlap
    assert all(len(d.page_content) <= 550 for d in docs)


def test_load_documents_skips_unsupported_files(tmp_path):
    _write_doc(tmp_path, "a.md", "x" * 10)
    (tmp_path / "b.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    docs = load_documents_from_directory(str(tmp_path))
    assert len(docs) == 1


def test_load_documents_missing_directory():
    with pytest.raises(FileNotFoundError):
        load_documents_from_directory("/no/such/dir")


# ----------------------------------------------------------------------
# 2. Embedding
# ----------------------------------------------------------------------
def test_fake_embedder_dimension():
    embedder = FakeEmbedder()
    vec = embedder.embed_query("如何安排恢复日")
    assert len(vec) == 384
    # 归一化：模长为 1
    magnitude = sum(v * v for v in vec) ** 0.5
    assert abs(magnitude - 1.0) < 1e-6


def test_fake_embedder_similarity_is_consistent():
    embedder = FakeEmbedder()
    v1 = embedder.embed_query("跑步训练应该注意什么")
    v2 = embedder.embed_query("跑步训练应该注意什么")
    assert v1 == v2


# ----------------------------------------------------------------------
# 3. 向量存储与检索
# ----------------------------------------------------------------------
def test_vector_store_add_and_retrieve(tmp_path):
    store = VectorStoreManager(persist_dir=str(tmp_path / "chroma"))
    embedder = FakeEmbedder()
    docs = [
        Document("间歇跑能有效提升最大摄氧量", {"source": "running.md", "chunk_index": 0}),
        Document("恢复日应保持低强度活动", {"source": "recovery.md", "chunk_index": 0}),
    ]
    store.add_documents(docs, embedder)
    assert store.count() == 2

    query_vec = embedder.embed_query("间歇训练提升体能")
    passages = store.retrieve(query_vec, top_k=2)
    assert len(passages) == 2
    # 语义上最相关的片段排在首位
    assert "间歇跑" in passages[0]["content"]
    assert passages[0]["source"] == "running.md"


def test_vector_store_retrieve_empty(tmp_path):
    store = VectorStoreManager(persist_dir=str(tmp_path / "chroma"))
    assert store.retrieve(FakeEmbedder().embed_query("任何内容")) == []


def test_vector_store_reset(tmp_path):
    store = VectorStoreManager(persist_dir=str(tmp_path / "chroma"))
    store.add_documents(
        [Document("内容", {"source": "a.md", "chunk_index": 0})], FakeEmbedder()
    )
    store.reset()
    assert store.count() == 0


# ----------------------------------------------------------------------
# 4. KnowledgeAgent
# ----------------------------------------------------------------------
class _FakeMemory:
    def __init__(self, context):
        self.context = context

    def get_context(self, user_id, session_id):
        return self.context


class _FakeLLM:
    def __init__(self, answer="好的，以下是建议。"):
        self.answer = answer
        self.last_messages = None

    def chat(self, messages, **kwargs):
        self.last_messages = messages
        return self.answer


def _make_agent(tmp_path, memory_context=None, llm=None):
    store = VectorStoreManager(persist_dir=str(tmp_path / "chroma"))
    embedder = FakeEmbedder()
    store.add_documents(
        [
            Document("过度训练会导致疲劳累积和恢复变慢", {"source": "overtraining.md", "chunk_index": 0}),
            Document("新手每周跑量增幅不应超过10%", {"source": "running.md", "chunk_index": 0}),
        ],
        embedder,
    )
    return KnowledgeAgent(
        embedder=embedder,
        vector_store_manager=store,
        llm_client=llm or _FakeLLM(),
        memory_agent=_FakeMemory(memory_context or {}),
    )


def test_knowledge_agent_run_returns_answer(tmp_path):
    agent = _make_agent(
        tmp_path,
        memory_context={
            "user_profile": {"level": "初级", "goal": "完成半马"},
            "recent_load_7d": 120.0,
        },
    )
    result = agent.run("user1", "我最近训练负荷偏高怎么办")
    assert "answer" in result and result["answer"]
    assert isinstance(result["sources"], list)


def test_knowledge_agent_prompt_contains_context(tmp_path):
    llm = _FakeLLM()
    agent = _make_agent(
        tmp_path,
        memory_context={
            "user_profile": {"level": "初级", "goal": "完成半马"},
            "recent_load_7d": 120.0,
        },
        llm=llm,
    )
    agent.run("user1", "如何避免过度训练")
    prompt = llm.last_messages[-1]["content"]
    assert "初级" in prompt and "完成半马" in prompt
    assert "120.0" in prompt
    assert "overtraining.md" in prompt  # 检索到的知识片段带来源


def test_knowledge_agent_falls_back_when_llm_fails(tmp_path):
    class _BrokenLLM:
        def chat(self, messages, **kwargs):
            raise RuntimeError("LLM down")

    agent = _make_agent(tmp_path, llm=_BrokenLLM())
    result = agent.run("user1", "如何避免过度训练")
    assert "LLM 服务暂不可用" in result["answer"]


def test_knowledge_agent_empty_store_answers_without_hallucination(tmp_path):
    store = VectorStoreManager(persist_dir=str(tmp_path / "chroma"))
    agent = KnowledgeAgent(
        embedder=FakeEmbedder(),
        vector_store_manager=store,
        llm_client=_FakeLLM(),
        memory_agent=_FakeMemory({}),
    )
    result = agent.run("user1", "如何安排营养")
    # 无知识命中时给出通用兜底，而非编造
    assert result["answer"]
    assert result["sources"] == []


def test_format_knowledge_lists_sources():
    text, sources = format_knowledge(
        [
            {"content": "内容A", "source": "a.md"},
            {"content": "内容B", "source": "b.md"},
        ]
    )
    assert "a.md" in text and "b.md" in text
    assert "a.md" in sources and "b.md" in sources


def test_knowledge_qa_prompt_has_all_placeholders():
    assert "{user_profile}" in KNOWLEDGE_QA_PROMPT
    assert "{training_status}" in KNOWLEDGE_QA_PROMPT
    assert "{knowledge}" in KNOWLEDGE_QA_PROMPT
    assert "{question}" in KNOWLEDGE_QA_PROMPT
    assert "{source_note}" in KNOWLEDGE_QA_PROMPT


# ----------------------------------------------------------------------
# 5. API 集成
# ----------------------------------------------------------------------
def test_chat_endpoint_returns_answer(tmp_path, monkeypatch):
    from app.api import routes

    agent = _make_agent(tmp_path, memory_context={"user_profile": {"level": "初级"}})
    monkeypatch.setattr(routes, "_get_rag_agent", lambda: agent)

    client = TestClient(TestApp())
    resp = client.post("/api/chat", json={"user_id": "u1", "question": "如何避免过度训练"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"]
    assert isinstance(body["sources"], list)


def test_chat_endpoint_validates_input(tmp_path, monkeypatch):
    from app.api import routes

    agent = _make_agent(tmp_path)
    monkeypatch.setattr(routes, "_get_rag_agent", lambda: agent)

    client = TestClient(TestApp())
    assert client.post("/api/chat", json={"user_id": "", "question": "x"}).status_code == 400
    assert client.post("/api/chat", json={"user_id": "u1", "question": ""}).status_code == 400


# 复用主应用 app，避免重复初始化
def TestApp():
    from app.main import app

    return app
