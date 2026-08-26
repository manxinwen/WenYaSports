"""LLM 调用抽象：LLMClient 接口 + OpenAI 兼容实现。

封装目的是：
- 主流程（KnowledgeAgent / ReActAgent）只依赖 LLMClient 抽象，模型中立；
- 测试可用 Mock 或轻量实现替换，无需真实 API；
- 后续可扩展 DeepSeek / GLM / 本地模型等 Provider。
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """LLM 客户端抽象接口。"""

    @abstractmethod
    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """发送对话消息，返回回复文本。"""


class OpenAILLMClient(LLMClient):
    """基于 OpenAI Chat Completions 的实现（兼容任意 OpenAI 兼容端点）。

    :param api_key: API Key；缺省读取环境变量 OPENAI_API_KEY。
    :param model: 模型名。
    :param base_url: 可选，OpenAI 兼容服务地址（如 DeepSeek / 本地 vLLM）。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url

    def chat(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        if not self.api_key:
            raise RuntimeError("未配置 OPENAI_API_KEY")
        from openai import OpenAI

        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        client = OpenAI(**client_kwargs)
        resp = client.chat.completions.create(
            model=kwargs.pop("model", self.model),
            messages=messages,
            **kwargs,
        )
        return resp.choices[0].message.content
