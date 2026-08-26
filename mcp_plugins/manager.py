"""插件管理器：负责配置加载、插件动态加载、工具汇总与执行路由。

- 从 JSON 配置读取「启用哪些插件」及各插件参数；
- 通过 importlib 动态导入插件包，实例化 BasePlugin 子类；
- 单个插件加载失败仅记录错误日志并跳过，不影响主系统；
- 提供 :meth:`get_all_tools` 供 MCP Server 注册工具，
  提供 :meth:`execute_tool` / :meth:`handle_request` 供上层 Agent 调用。
"""

import importlib
import json
import logging
import os
from typing import Any, Dict, List, Optional

from mcp_plugins.base import BasePlugin
from mcp_plugins.pipeline import (
    ToolPipeline,
    audit_hook,
    cache_hook,
    rate_limit_hook,
)

logger = logging.getLogger(__name__)

#: 插件所在包的根路径（mcp_plugins.plugins.<name>）
PLUGIN_PACKAGE = "mcp_plugins.plugins"


class PluginManager:
    """管理插件生命周期与工具调用。

    :param config_path: 配置文件路径；为 ``None`` 时使用
                        ``mcp_plugins/config.json``。
    :param config: 直接传入配置字典（优先于 config_path，便于测试注入）。
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._config = config if config is not None else self._load_config(config_path)
        self._plugins: Dict[str, BasePlugin] = {}
        #: 工具执行管线（pre-execute → execute → post-execute）
        self.pipeline = ToolPipeline()
        self._load_plugins()

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------
    @staticmethod
    def _load_config(config_path: Optional[str]) -> Dict[str, Any]:
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
        with open(config_path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # ------------------------------------------------------------------
    # 插件动态加载
    # ------------------------------------------------------------------
    def _load_plugins(self) -> None:
        """遍历配置，加载所有 enabled 的插件；失败时记录日志并跳过。"""
        for entry in self._config.get("plugins", []):
            name = entry.get("name")
            if not name:
                logger.warning("忽略无效插件配置：%s", entry)
                continue
            if not entry.get("enabled", False):
                logger.info("跳过插件 %s：未启用", name)
                continue
            try:
                plugin_cls = self._discover_plugin_class(name)
                plugin = plugin_cls(entry.get("config") or {})
                self._plugins[name] = plugin
                logger.info("插件 %s (v%s) 加载成功", name, plugin.version)
            except Exception as exc:  # noqa: BLE001 - 必须隔离任何加载异常
                logger.error("插件 %s 加载失败，已跳过：%s", name, exc)

    @staticmethod
    def _discover_plugin_class(name: str) -> type:
        """导入插件包并定位其中的 BasePlugin 子类。

        约定：插件包 ``mcp_plugins/plugins/<name>/`` 的 ``__init__.py``
        需导入并暴露其插件类（见 weather、map_routing 示例）。
        """
        module = importlib.import_module(f"{PLUGIN_PACKAGE}.{name}")
        for attr in vars(module).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, BasePlugin)
                and attr is not BasePlugin
            ):
                return attr
        raise ImportError(f"插件包 {name} 中未找到 BasePlugin 子类")

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------
    def get_plugins(self) -> Dict[str, BasePlugin]:
        """返回已成功加载的插件（{插件名: 插件实例}）。"""
        return dict(self._plugins)

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """汇总所有已加载插件的 MCP 工具定义。

        每个工具定义额外附带 ``plugin`` 字段标注来源插件，便于路由。
        """
        tools: List[Dict[str, Any]] = []
        for plugin in self._plugins.values():
            for tool in plugin.get_tools():
                item = dict(tool)
                item["plugin"] = plugin.name
                tools.append(item)
        return tools

    def health_checks(self) -> Dict[str, bool]:
        """对所有已加载插件执行健康检查。"""
        return {name: plugin.health_check() for name, plugin in self._plugins.items()}

    # ------------------------------------------------------------------
    # 执行接口
    # ------------------------------------------------------------------
    def execute_tool(
        self,
        plugin_name: str,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """按插件名 + 工具名执行对应插件的方法。

        插件缺失、工具不存在等错误均以结果字典形式返回，不抛异常。
        """
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            return {"success": False, "error": f"插件 '{plugin_name}' 未加载或不存在"}
        try:
            return self.pipeline.execute(
                lambda _plugin, _tool, params: plugin.execute(_tool, params),
                plugin_name,
                tool_name,
                parameters or {},
            )
        except Exception as exc:  # noqa: BLE001 - 插件异常不得上抛
            logger.exception("执行插件 %s 工具 %s 时发生异常", plugin_name, tool_name)
            return {"success": False, "error": f"插件 '{plugin_name}' 执行异常：{exc}"}

    # ------------------------------------------------------------------
    # 管线钩子（企业级：缓存 / 限流 / 审计）
    # ------------------------------------------------------------------
    def add_pre_hook(self, hook) -> None:
        """注册 pre-execute 钩子（可拦截/短路工具执行）。"""
        self.pipeline.add_pre_hook(hook)

    def add_post_hook(self, hook) -> None:
        """注册 post-execute 钩子（可观察/落盘工具结果）。"""
        self.pipeline.add_post_hook(hook)

    def enable_cache(self, maxsize: int = 128, ttl: int = 300):
        """启用工具结果缓存：命中短路返回缓存值，成功结果回写。

        用于降低外部 API 调用成本与延迟（天气/路线等只读工具）。
        :return: 底层 TTL 缓存对象（便于测试与观测）。
        """
        from cachetools import TTLCache

        cache = TTLCache(maxsize=maxsize, ttl=ttl)
        pre, post = cache_hook(cache)
        self.add_pre_hook(pre)
        self.add_post_hook(post)
        return cache

    def enable_rate_limit(self, max_calls: int = 10, window_seconds: float = 60.0) -> None:
        """启用按 (插件, 工具) 维度的滑动窗口限流，超限拒绝并返回错误。"""
        pre, _ = rate_limit_hook(max_calls, window_seconds)
        self.add_pre_hook(pre)

    def enable_audit(self, log, session_id: str = "default") -> None:
        """启用审计：将每次工具调用与结果写入日志（如 SessionLog）。"""
        pre, post = audit_hook(log, session_id)
        self.add_pre_hook(pre)
        self.add_post_hook(post)

    def handle_request(
        self,
        tool_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """模拟 MCP 协议：仅凭工具名路由到对应插件执行。

        MCP Server 可基于 get_all_tools() 注册工具，
        上层 Agent 可直接调用本方法完成工具分发。
        """
        for name, plugin in self._plugins.items():
            for tool in plugin.get_tools():
                if tool["name"] == tool_name:
                    return self.execute_tool(name, tool_name, parameters)
        return {"success": False, "error": f"未找到工具 '{tool_name}'"}
