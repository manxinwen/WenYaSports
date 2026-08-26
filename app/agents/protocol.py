"""Agent 间通信协议：AgentMessage + MessageBus。

解决当前多智能体系统「Agent 之间仅靠同步方法调用、无消息/协议抽象」的缺口。
Agent 通过消息总线发布/订阅消息，实现松耦合协作。
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)

#: 广播接收者通配符
BROADCAST = "*"

#: 常用消息类型常量
class MessageType:
    """消息类型枚举（字符串常量，便于序列化与扩展）。"""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


@dataclass
class AgentMessage:
    """一条 Agent 间消息。

    :param sender: 发送方 Agent 名称。
    :param receiver: 接收方 Agent 名称；为 ``*`` 时广播给所有订阅者。
    :param message_type: 消息类型（见 MessageType）。
    :param payload: 消息体（任意可 JSON 序列化数据）。
    :param message_id: 消息唯一 ID（自动生成）。
    :param timestamp: 消息时间戳（ISO 格式，自动生成）。
    """

    sender: str
    receiver: str
    message_type: str
    payload: Dict[str, Any]
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type,
            "payload": self.payload,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
        }


class MessageBus:
    """轻量内存消息总线：支持点对点与广播投递。

    用法：
    - Agent 用 :meth:`subscribe` 注册自己的消息处理器；
    - 用 :meth:`publish` 发送消息，总线按 ``receiver`` 精确匹配，
      同时将消息投递给 ``*`` 广播订阅者；
    - 消息投递失败不会影响总线本身（错误隔离）。
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[AgentMessage], None]]] = {}
        self._history: List[AgentMessage] = []

    def subscribe(self, agent_name: str, handler: Callable[[AgentMessage], None]) -> None:
        """注册 ``agent_name`` 的消息处理器。

        :param agent_name: Agent 名称，或 ``BROADCAST`` 表示接收所有消息。
        """
        self._subscribers.setdefault(agent_name, []).append(handler)

    def publish(self, message: AgentMessage) -> None:
        """发布一条消息：精确投递给 receiver，同时投递给广播订阅者。"""
        self._history.append(message)
        targets = []
        if message.receiver in self._subscribers:
            targets.extend(self._subscribers[message.receiver])
        if BROADCAST in self._subscribers:
            targets.extend(self._subscribers[BROADCAST])
        for handler in targets:
            try:
                handler(message)
            except Exception:  # noqa: BLE001 - 单个订阅者失败不影响总线
                logger.exception(
                    "投递消息到订阅者失败（sender=%s, type=%s）",
                    message.sender,
                    message.message_type,
                )

    def history(self) -> List[AgentMessage]:
        """返回已发布消息的历史记录（按发布顺序）。"""
        return list(self._history)

    def clear(self) -> None:
        """清空订阅者与历史（便于测试隔离）。"""
        self._subscribers.clear()
        self._history.clear()
