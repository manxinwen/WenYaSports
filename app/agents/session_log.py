"""事件溯源会话日志（Session Log / Trajectory Log）。

设计借鉴 DeepSeek Harness 的会话日志思想：
- 所有事件以 **append-only** 方式追加到事件流，不修改、不删除历史；
- 事件流是「唯一事实来源」：模型 / Agent 看到的一切都应能从日志重建，
  从而支持回放、审计、断点续跑与故障诊断；
- 支持内存模式与 JSONL 文件持久化，并通过 :func:`load` 从日志重建状态。

可与 MessageBus 接合（见 :func:`attach_message_bus_logging`）：
订阅总线后，Agent 间通信自动落盘，形成跨 Agent 的完整轨迹。
"""

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.protocol import BROADCAST, AgentMessage, MessageBus

logger = logging.getLogger(__name__)


class EventType:
    """事件类型常量。"""

    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MESSAGE = "message"


@dataclass
class SessionEvent:
    """一条会话事件：某个 Agent 在某个时刻的「输入 → 输出」记录。"""

    session_id: str
    sequence: int
    event_type: str
    agent: str
    payload: Dict[str, Any]
    result: Optional[Dict[str, Any]]
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SessionLog:
    """append-only 事件日志：内存 + 可选 JSONL 文件持久化。

    :param file_path: 非空时将事件以 JSON Lines 追加写入该文件。
    """

    def __init__(self, file_path: Optional[str] = None) -> None:
        self._events: List[SessionEvent] = []
        self._sequence = 0
        self._file_path = file_path
        if file_path:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            self._file = open(file_path, "a", encoding="utf-8")
        else:
            self._file = None

    @classmethod
    def load(cls, file_path: str) -> "SessionLog":
        """从既有 JSONL 文件重建 SessionLog（断点续跑/恢复）。

        重建后仍以 append 模式打开文件，继续追加新事件。
        """
        log = cls.__new__(cls)
        log._events = []
        log._sequence = 0
        log._file_path = file_path
        log._file = open(file_path, "a", encoding="utf-8")
        with open(file_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                log._events.append(SessionEvent(**data))
                log._sequence = max(log._sequence, data["sequence"])
        return log

    def record(
        self,
        session_id: str,
        event_type: str,
        agent: str,
        payload: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> SessionEvent:
        """追加一条事件（自动递增 sequence、打时间戳）。"""
        self._sequence += 1
        event = SessionEvent(
            session_id=session_id,
            sequence=self._sequence,
            event_type=event_type,
            agent=agent,
            payload=payload or {},
            result=result,
            timestamp=datetime.now().isoformat(),
        )
        self._events.append(event)
        if self._file is not None:
            self._file.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
            self._file.flush()
        return event

    def events(self, session_id: Optional[str] = None) -> List[SessionEvent]:
        """按追加顺序返回事件；给定 session_id 时仅返回该会话的事件。"""
        if session_id is None:
            return list(self._events)
        return [e for e in self._events if e.session_id == session_id]

    def replay(self, session_id: str) -> List[SessionEvent]:
        """按序回放某个会话的全部事件（用于恢复 / 审计）。"""
        return self.events(session_id)

    def export_text(self, session_id: str) -> str:
        """导出为人类可读的审计文本。"""
        lines = [f"=== Session {session_id} 回放 ==="]
        for e in self.events(session_id):
            lines.append(f"[{e.sequence}] {e.event_type} @ {e.agent} ({e.timestamp})")
            if e.payload:
                lines.append(
                    f"    in:  {json.dumps(e.payload, ensure_ascii=False)}"
                )
            if e.result is not None:
                lines.append(
                    f"    out: {json.dumps(e.result, ensure_ascii=False)}"
                )
        return "\n".join(lines)

    def close(self) -> None:
        """关闭底层文件句柄。"""
        if self._file is not None:
            self._file.close()
            self._file = None


def attach_message_bus_logging(
    bus: MessageBus,
    log: SessionLog,
    session_id: str = "default",
) -> None:
    """将 MessageBus 的消息流接入 SessionLog。

    订阅广播后，所有 Agent 间通信消息都会以 ``message.<type>`` 事件落盘，
    形成跨 Agent 的通信轨迹。
    """

    def handler(message: AgentMessage) -> None:
        log.record(
            session_id=session_id,
            event_type=f"message.{message.message_type}",
            agent=message.sender,
            payload=message.to_dict(),
        )

    bus.subscribe(BROADCAST, handler)
