"""UserContext: 请求级用户上下文对象。

贯穿整个请求生命周期，确保所有 Agent 和服务都能
获取到当前请求的用户身份信息，实现数据隔离。

Architecture:
    API Layer → UserContext → Agent Layer → Service Layer

    UserContext 包含:
    - user_id: 用户唯一标识
    - session_id: 当前会话标识
    - trace_id: 分布式追踪ID
    - metadata: 扩展元数据

Usage:
    ctx = UserContext(user_id="user_001", session_id="sess_abc")
    agent.run(ctx, input_data)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class UserContext:
    """请求级用户上下文。

    贯穿整个请求链路，确保数据隔离和可追溯性。
    """

    user_id: str
    session_id: str
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserContext":
        """从字典反序列化。"""
        return cls(
            user_id=data["user_id"],
            session_id=data["session_id"],
            trace_id=data.get("trace_id", uuid.uuid4().hex[:12]),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )

    def with_metadata(self, key: str, value: Any) -> "UserContext":
        """返回带有新元数据的副本。"""
        new_ctx = UserContext(
            user_id=self.user_id,
            session_id=self.session_id,
            trace_id=self.trace_id,
            timestamp=self.timestamp,
            metadata={**self.metadata, key: value},
        )
        return new_ctx

    @property
    def namespace(self) -> str:
        """生成用户级命名空间前缀。

        用于 Blackboard 等共享状态的强制隔离:
            - 旧方式: blackboard.write("memory", f"user_{user_id}", data)
            - 新方式: blackboard.write(ctx.namespace("memory"), "profile", data)
        """
        return f"user_{self.user_id}"

    def scoped_namespace(self, domain: str) -> str:
        """生成带域的用户级命名空间。

        Args:
            domain: 业务域 (e.g., "memory", "parser", "features")

        Returns:
            格式: "user_{user_id}.{domain}"
        """
        return f"{self.namespace}.{domain}"
