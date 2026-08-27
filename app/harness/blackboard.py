"""Blackboard: Shared state and data exchange for multi-agent systems.

The Blackboard is a centralised knowledge base that all agents can read from
and write to. It serves as the "shared memory" of the multi-agent system,
allowing agents to exchange data without direct coupling.

Key Features:
- Namespace-based data isolation
- Version history for traceability
- Change notifications for reactive agents
- Thread-safe operations
- User-scoped namespaces for multi-tenant isolation
"""

import time
import threading
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from collections import defaultdict
from copy import deepcopy

if TYPE_CHECKING:
    from app.models.user_context import UserContext


class Blackboard:
    """Shared blackboard for agent data exchange.

    Provides a structured key-value store with:
    - Namespace isolation (e.g., "parser.data", "memory.profile")
    - Version tracking for each entry
    - Subscriber notifications on changes
    - Atomic snapshots for consistent reads
    - User-scoped helpers for multi-tenant safety

    Multi-Tenant Isolation:
        Use user_write/user_read methods to automatically scope data
        to a specific user, preventing cross-user data leakage.
    """

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._versions: Dict[str, List[Dict]] = defaultdict(list)
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._max_history = 10

    # ------------------------------------------------------------------
    # Core operations (backward compatible)
    # ------------------------------------------------------------------

    def write(self, namespace: str, key: str, value: Any) -> int:
        """Write a value to a namespace. Returns the new version number.

        Args:
            namespace: Logical grouping (e.g., "parser", "memory", "features")
            key: Data identifier within the namespace
            value: Any serializable data

        Returns:
            Version number (incremented on each write)
        """
        with self._lock:
            ns = self._data.setdefault(namespace, {})
            old_value = ns.get(key)
            version = len(self._versions[f"{namespace}.{key}"]) + 1

            self._versions[f"{namespace}.{key}"].append({
                "version": version,
                "value": deepcopy(value),
                "timestamp": time.time(),
                "old_value": deepcopy(old_value) if old_value is not None else None,
            })

            if len(self._versions[f"{namespace}.{key}"]) > self._max_history:
                self._versions[f"{namespace}.{key}"].pop(0)

            ns[key] = deepcopy(value)
            self._notify(namespace, key, value, old_value)
            return version

    def read(self, namespace: str, key: Optional[str] = None) -> Any:
        """Read a value or entire namespace.

        Args:
            namespace: Namespace to read from
            key: Specific key (optional, returns entire namespace if omitted)

        Returns:
            The stored value, or entire namespace dict
        """
        with self._lock:
            if key is None:
                return deepcopy(self._data.get(namespace, {}))
            return deepcopy(self._data.get(namespace, {}).get(key))

    def delete(self, namespace: str, key: str) -> bool:
        """Delete a key from a namespace.

        Returns:
            True if the key existed and was deleted
        """
        with self._lock:
            ns = self._data.get(namespace, {})
            if key in ns:
                del ns[key]
                self._notify(namespace, key, None, "deleted")
                return True
            return False

    # ------------------------------------------------------------------
    # User-scoped operations (multi-tenant safe)
    # ------------------------------------------------------------------

    @staticmethod
    def user_namespace(user_id: str, domain: str) -> str:
        """生成用户级命名空间，强制隔离。

        Args:
            user_id: 用户唯一标识
            domain: 业务域 (e.g., "memory", "parser", "features")

        Returns:
            格式: "user_{user_id}.{domain}"
        """
        return f"user_{user_id}.{domain}"

    def user_write(self, user_id: str, domain: str, key: str, value: Any) -> int:
        """用户级写入，自动添加用户命名空间前缀。

        Args:
            user_id: 用户唯一标识
            domain: 业务域 (e.g., "memory", "parser")
            key: 数据键
            value: 数据值

        Returns:
            版本号
        """
        ns = self.user_namespace(user_id, domain)
        return self.write(ns, key, value)

    def user_read(self, user_id: str, domain: str, key: Optional[str] = None) -> Any:
        """用户级读取，自动添加用户命名空间前缀。

        Args:
            user_id: 用户唯一标识
            domain: 业务域
            key: 数据键（None 返回整个域）

        Returns:
            存储的值
        """
        ns = self.user_namespace(user_id, domain)
        return self.read(ns, key)

    def user_delete(self, user_id: str, domain: str, key: str) -> bool:
        """用户级删除，自动添加用户命名空间前缀。

        Args:
            user_id: 用户唯一标识
            domain: 业务域
            key: 数据键

        Returns:
            是否成功删除
        """
        ns = self.user_namespace(user_id, domain)
        return self.delete(ns, key)

    def user_clear_domain(self, user_id: str, domain: str) -> None:
        """清除用户指定域的所有数据。

        Args:
            user_id: 用户唯一标识
            domain: 业务域
        """
        ns = self.user_namespace(user_id, domain)
        self.clear_namespace(ns)

    # ------------------------------------------------------------------
    # Advanced operations
    # ------------------------------------------------------------------

    def get_history(self, namespace: str, key: str) -> List[Dict]:
        """Get version history for a specific key.

        Returns:
            List of version entries, newest first
        """
        with self._lock:
            return list(reversed(self._versions.get(f"{namespace}.{key}", [])))

    def subscribe(self, namespace: str, key: Optional[str], callback: Callable) -> None:
        """Subscribe to changes on a namespace/key.

        Args:
            namespace: Namespace to watch
            key: Key to watch (None = watch entire namespace)
            callback: Function called with (namespace, key, new_value, old_value)
        """
        topic = f"{namespace}.{key}" if key else namespace
        self._subscribers[topic].append(callback)

    def get_snapshot(self) -> Dict[str, Any]:
        """Get a complete atomic snapshot of all data.

        Useful for consistent reads across the system.

        Returns:
            Deep copy of all blackboard data
        """
        with self._lock:
            return deepcopy(self._data)

    def get_user_snapshot(self, user_id: str) -> Dict[str, Any]:
        """获取指定用户的所有数据快照。

        Args:
            user_id: 用户唯一标识

        Returns:
            用户的所有命名空间数据
        """
        with self._lock:
            prefix = f"user_{user_id}."
            user_data = {}
            for ns, data in self._data.items():
                if ns.startswith(prefix) or ns == f"user_{user_id}":
                    user_data[ns] = deepcopy(data)
            return user_data

    def clear_namespace(self, namespace: str) -> None:
        """Clear all data in a namespace."""
        with self._lock:
            self._data[namespace] = {}

    def clear_user(self, user_id: str) -> int:
        """清除指定用户的所有数据。

        Args:
            user_id: 用户唯一标识

        Returns:
            清除的命名空间数量
        """
        with self._lock:
            prefix = f"user_{user_id}."
            cleared = 0
            namespaces_to_clear = [
                ns for ns in self._data
                if ns.startswith(prefix) or ns == f"user_{user_id}"
            ]
            for ns in namespaces_to_clear:
                self._data[ns] = {}
                cleared += 1
            return cleared

    def _notify(self, namespace: str, key: str, new_value: Any, old_value: Any) -> None:
        """Notify all subscribers of a change."""
        key_topic = f"{namespace}.{key}"
        for callback in self._subscribers.get(key_topic, []):
            try:
                callback(namespace, key, new_value, old_value)
            except Exception:
                pass

        for callback in self._subscribers.get(namespace, []):
            try:
                callback(namespace, key, new_value, old_value)
            except Exception:
                pass

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the blackboard usage."""
        with self._lock:
            total_keys = sum(len(ns) for ns in self._data.values())
            total_versions = sum(len(vs) for vs in self._versions.values())

            # 统计用户数据
            user_namespaces = [
                ns for ns in self._data
                if ns.startswith("user_")
            ]
            unique_users = set()
            for ns in user_namespaces:
                user_id = ns.split(".")[0].replace("user_", "")
                unique_users.add(user_id)

            return {
                "total_namespaces": len(self._data),
                "total_keys": total_keys,
                "total_versions_tracked": total_versions,
                "subscribers_count": sum(len(s) for s in self._subscribers.values()),
                "active_users": len(unique_users),
                "user_namespaces_count": len(user_namespaces),
            }
