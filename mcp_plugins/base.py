"""插件基类：定义所有 MCP 工具插件必须实现的统一接口。

主程序（PluginManager / MCP Server）只依赖本基类，不关心具体实现，
从而保证「插件化 + 统一接口」的设计目标。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BasePlugin(ABC):
    """所有外部工具插件的抽象基类。

    每个插件：
    - 通过 :attr:`name` 作为唯一标识（同时对应 config.json 中的插件名）；
    - 通过 :meth:`get_tools` 声明其提供的 MCP 工具（JSON Schema 参数定义）；
    - 通过 :meth:`execute` 执行具体工具；
    - 通过 :meth:`health_check` 验证插件可用性（如 API Key 是否有效）。
    """

    # ------------------------------------------------------------------
    # 元信息（只读属性）
    # ------------------------------------------------------------------
    @property
    @abstractmethod
    def name(self) -> str:
        """插件唯一标识，需与 config.json 中配置的插件名一致。"""

    @property
    @abstractmethod
    def description(self) -> str:
        """插件功能描述。"""

    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本号。"""

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    @abstractmethod
    def __init__(self, config: Dict[str, Any]) -> None:
        """初始化插件。

        :param config: 来自 config.json 中该插件节点下的 ``config`` 字典，
                       例如 ``{"api_key": "xxx", "default_city": "Beijing"}``。
        """

    # ------------------------------------------------------------------
    # 工具接口
    # ------------------------------------------------------------------
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """返回本插件提供的 MCP 工具定义列表。

        每个工具是一个字典，包含：
        - ``name``: 工具名（需全局唯一）；
        - ``description``: 工具说明；
        - ``parameters``: JSON Schema 格式的参数定义。

        :return: 工具定义列表。
        """

    @abstractmethod
    def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """执行指定的工具并返回结果字典。

        约定：实现方必须在内部捕获所有异常并以
        ``{"success": False, "error": "..."}`` 形式返回，
        禁止向主系统抛出未捕获异常。

        :param tool_name: 工具名（来自 get_tools() 声明）。
        :param parameters: 工具参数。
        :return: 结果字典，通常含 ``success`` 字段。
        """

    @abstractmethod
    def health_check(self) -> bool:
        """检查插件是否可用（如 API Key 是否有效）。

        :return: ``True`` 表示可用，``False`` 表示不可用。
        """
