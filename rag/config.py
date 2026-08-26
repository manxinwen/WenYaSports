"""RAG 模块配置：模型、向量库路径、切分参数、检索参数。"""

import os

#: Embedding 模型（sentence-transformers，本地运行，无需 API 成本）
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

#: 向量数据库持久化路径（可用环境变量 RAG_CHROMA_DIR 覆盖）
CHROMA_PERSIST_DIR = os.environ.get("RAG_CHROMA_DIR", "./chroma_db")

#: Chroma collection 名称
CHROMA_COLLECTION = "fitness_knowledge"

#: 文档切分参数
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

#: 检索返回的文档片段数
TOP_K = 4

#: 知识库文档目录（用户提供文档后放置于此，或传入自定义路径）
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

#: LLM 模型名（默认 OpenAI 兼容）
LLM_MODEL = "gpt-4o-mini"

#: MiniLM-L6-v2 输出向量维度
MINILM_DIM = 384
