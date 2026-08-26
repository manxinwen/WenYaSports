"""插件注册中心。

每个子包（如 weather、map_routing）代表一个独立插件。
PluginManager 通过导入 ``mcp_plugins.plugins.<name>`` 来发现插件类，
因此各子包的 ``__init__.py`` 必须暴露其 BasePlugin 子类。
"""
