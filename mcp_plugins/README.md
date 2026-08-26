# 插件化 MCP 工具层

为多智能体运动分析系统提供一套**插件化的 MCP (Model Context Protocol) 工具层**。
外部工具（天气查询、地图路线等）被封装为独立插件，由 `PluginManager` 动态加载，
主程序统一通过 `BasePlugin` 接口调用，**无需修改核心代码即可扩展新工具**。

## 一、设计思路

```
                上层 Agent (RecommendationAgent / AdvisorAgent)
                                   │
                                   ▼
                  PluginManager (插件管理器：配置加载 / 动态加载 / 路由)
                                   │
               ┌───────────────────┼────────────────────┐
               ▼                   ▼                    ▼
        BasePlugin 接口 ── BasePlugin 接口 ── BasePlugin 接口
               │                   │                    │
         weather 插件        map_routing 插件      (可扩展其他插件)
```

- **插件化**：每个外部服务对应 `mcp_plugins/plugins/<name>/` 下的一个插件包，
  互不依赖、可独立增删。
- **统一接口**：所有插件继承抽象基类 `BasePlugin`（见 [base.py](base.py)），
  对外暴露一致的 `get_tools()` / `execute()` / `health_check()`。
- **配置驱动**：通过 [config.json](config.json) 声明启用哪些插件及各自参数
  （如 API Key），无需改代码。
- **安全与隔离**：插件在加载、执行、健康检查全链路均有异常兜底，
  单个插件失败只记日志并跳过，不会拖垮主系统。
- **MCP 集成**：`get_all_tools()` 汇总的 JSON Schema 工具定义可直接注册到
  MCP Server；`handle_request(tool_name, parameters)` 模拟 MCP 协议分发，
  供上层 Agent 直接调用。

## 二、目录结构

```
mcp_plugins/
├── __init__.py               # 包入口，导出 BasePlugin / PluginManager
├── base.py                   # 插件抽象基类
├── manager.py                # 插件管理器
├── config.json               # 插件配置示例
├── plugins/
│   ├── __init__.py
│   ├── weather/
│   │   ├── __init__.py       # 暴露 WeatherPlugin
│   │   └── weather_plugin.py # 天气查询插件（OpenWeatherMap）
│   └── map_routing/
│       ├── __init__.py       # 暴露 MapRoutingPlugin
│       └── map_plugin.py     # 地图路线插件（OpenRouteService）
└── README.md
```

## 三、如何添加一个新插件（例如营养数据库）

1. **创建插件包目录**

   ```bash
   mkdir -p mcp_plugins/plugins/nutrition
   ```

2. **实现插件类** `mcp_plugins/plugins/nutrition/nutrition_plugin.py`

   ```python
   from mcp_plugins.base import BasePlugin

   class NutritionPlugin(BasePlugin):
       @property
       def name(self): return "nutrition"

       @property
       def description(self): return "查询食物营养数据"

       @property
       def version(self): return "1.0.0"

       def __init__(self, config):
           self.api_key = config.get("api_key")

       def get_tools(self):
           return [{
               "name": "search_nutrition",
               "description": "按名称查询食物营养信息",
               "parameters": {
                   "type": "object",
                   "properties": {
                       "query": {"type": "string", "description": "食物名称"},
                   },
                   "required": ["query"],
               },
           }]

       def execute(self, tool_name, parameters):
           # 调用外部 API；异常请以 {"success": False, "error": "..."} 返回
           ...

       def health_check(self):
           # 校验 API Key 可用性，返回 bool
           ...
   ```

3. **在插件包的 `__init__.py` 暴露插件类**

   ```python
   from mcp_plugins.plugins.nutrition.nutrition_plugin import NutritionPlugin
   __all__ = ["NutritionPlugin"]
   ```

4. **在 `config.json` 中启用并配置**

   ```json
   { "name": "nutrition", "enabled": true, "config": { "api_key": "..." } }
   ```

完成以上 4 步即可，无需改动基类、管理器或上层代码。

## 四、配置文件格式

[config.json](config.json) 顶层为 `plugins` 列表，每项包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `name` | string | 插件唯一标识，需与插件包名一致 |
| `enabled` | bool | 是否启用该插件 |
| `config` | object | 传给插件 `__init__` 的配置字典（如 API Key） |

示例：

```json
{
    "plugins": [
        { "name": "weather", "enabled": true, "config": { "api_key": "YOUR_API_KEY", "default_city": "Beijing" } },
        { "name": "map_routing", "enabled": false, "config": { "api_key": "YOUR_MAPBOX_TOKEN" } }
    ]
}
```

## 五、与多智能体系统的集成

在任一 Agent（如 `RecommendationAgent`）中实例化 `PluginManager`，
将 `get_all_tools()` 交给 LLM 工具调用，用 `execute_tool` / `handle_request` 分发：

```python
from mcp_plugins import PluginManager

manager = PluginManager()          # 默认读取 mcp_plugins/config.json

# 1) 供 MCP Server / LLM 注册工具
tools = manager.get_all_tools()

# 2) 供 Agent 调用工具
result = manager.execute_tool("weather", "get_current_weather", {"city": "Beijing"})

# 或按工具名直接路由（模拟 MCP 协议）
result = manager.handle_request("get_current_weather", {"city": "Beijing"})
```

## 六、运行测试

```bash
pip install -r requirements.txt
python -m pytest tests/test_mcp_plugins.py -v
```
