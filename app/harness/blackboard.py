"""Blackboard: Shared state and data exchange for multi-agent systems.

The Blackboard is a centralised knowledge base that all agents can read from
and write to. It serves as the "shared memory" of the multi-agent system,
allowing agents to exchange data without direct coupling.

Key Features:
- Namespace-based data isolation
- Version history for traceability
- Change notifications for reactive agents
- Thread-safe operations
"""

import time
import threading
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict
from copy import deepcopy


class Blackboard:
    """Shared blackboard for agent data exchange.

    Provides a structured key-value store with:
    - Namespace isolation (e.g., "parser.data", "memory.profile")
    - Version tracking for each entry
    - Subscriber notifications on changes
    - Atomic snapshots for consistent reads
    """

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._versions: Dict[str, List[Dict]] = defaultdict(list)
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._max_history = 10  # Keep last 10 versions

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

            # Store version history
            self._versions[f"{namespace}.{key}"].append({
                "version": version,
                "value": deepcopy(value),
                "timestamp": time.time(),
                "old_value": deepcopy(old_value) if old_value is not None else None,
            })

            # Trim history
            if len(self._versions[f"{namespace}.{key}"]) > self._max_history:
                self._versions[f"{namespace}.{key}"].pop(0)

            # Write current value
            ns[key] = deepcopy(value)

            # Notify subscribers
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

    def clear_namespace(self, namespace: str) -> None:
        """Clear all data in a namespace."""
        with self._lock:
            self._data[namespace] = {}

    def _notify(self, namespace: str, key: str, new_value: Any, old_value: Any) -> None:
        """Notify all subscribers of a change."""
        # Notify key-specific subscribers
        key_topic = f"{namespace}.{key}"
        for callback in self._subscribers.get(key_topic, []):
            try:
                callback(namespace, key, new_value, old_value)
            except Exception as e:
                pass  # Don't let subscriber errors break the write

        # Notify namespace subscribers
        for callback in self._subscribers.get(namespace, []):
            try:
                callback(namespace, key, new_value, old_value)
            except Exception as e:
                pass

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the blackboard usage."""
        with self._lock:
            total_keys = sum(len(ns) for ns in self._data.values())
            total_versions = sum(len(vs) for vs in self._versions.values())
            return {
                "namespaces": list(self._data.keys()),
                "total_keys": total_keys,
                "total_versions_tracked": total_versions,
                "subscribers_count": sum(len(s) for s in self._subscribers.values()),
            }
