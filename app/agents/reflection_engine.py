"""ReflectionEngine: Agent 自我反思与策略改进引擎。

核心价值：
1. 失败反思：Agent 执行失败后，分析原因并生成改进策略
2. 经验积累：将反思经验存储到记忆系统，供后续类似任务参考
3. 策略进化：基于历史反思，动态调整 Agent 的执行策略
4. 反思链：形成"执行→评估→反思→改进→验证"的闭环

面试展示点：
- 体现了 Agent 的"学习"和"进化"能力
- 不仅仅是执行任务，还能从失败中学习
- 完整的自我改进闭环，展示了深度的 Agent 设计思考

Architecture:
    Execution → [Evaluator] → Failed? → [ReflectionEngine] → Strategy Update
                                    ↓                              ↓
                               Success                    Memory Store
                                                              ↓
                                                       Future Tasks Benefit
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.memory.memory_pool import get_memory_pool

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 反思记录
# ---------------------------------------------------------------------------

@dataclass
class ReflectionRecord:
    """单次反思记录。"""
    reflection_id: str
    task_type: str
    original_goal: str
    what_went_wrong: str
    root_cause: str
    improved_strategy: str
    confidence: float  # 对改进策略的信心
    created_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolution_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflection_id": self.reflection_id,
            "task_type": self.task_type,
            "original_goal": self.original_goal,
            "what_went_wrong": self.what_went_wrong,
            "root_cause": self.root_cause,
            "improved_strategy": self.improved_strategy,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "resolved": self.resolved,
            "resolution_notes": self.resolution_notes,
        }


# ---------------------------------------------------------------------------
# 反思引擎
# ---------------------------------------------------------------------------

class ReflectionEngine:
    """Agent 自我反思与策略改进引擎。

    核心流程：
    1. 接收失败的执行结果
    2. 分析失败原因（工具错误、参数错误、逻辑错误等）
    3. 生成改进策略
    4. 将反思经验存储到记忆系统
    5. 供后续类似任务检索使用

    使用场景：
    - Orchestrator 重规划时参考历史反思
    - Agent 执行前检查是否有相关反思经验
    - 定期回顾未解决的反思，形成长期改进策略
    """

    def __init__(self, user_id: str = "default"):
        """初始化反思引擎。

        Args:
            user_id: 用户标识，用于记忆隔离
        """
        self.user_id = user_id
        self._reflection_count = 0
        self._resolved_count = 0
        self._memory_pool = get_memory_pool()
        self._recent_reflections: List[ReflectionRecord] = []
        self.MAX_RECENT = 100

    # ------------------------------------------------------------------
    # 核心反思流程
    # ------------------------------------------------------------------

    def reflect_on_failure(
        self,
        task_type: str,
        original_goal: str,
        execution_result: Dict[str, Any],
        evaluation_feedback: Optional[Dict[str, Any]] = None,
    ) -> ReflectionRecord:
        """对失败执行进行反思。

        Args:
            task_type: 任务类型（如 "analysis", "chat", "tool_call"）
            original_goal: 原始目标
            execution_result: 执行结果（包含错误信息）
            evaluation_feedback: 评估反馈（可选）

        Returns:
            反思记录
        """
        self._reflection_count += 1

        # 分析失败原因
        error_info = self._extract_error_info(execution_result)
        root_cause = self._analyze_root_cause(
            error_info, task_type, execution_result
        )

        # 生成改进策略
        improved_strategy = self._generate_improved_strategy(
            root_cause, task_type, original_goal, evaluation_feedback
        )

        # 创建反思记录
        import uuid
        record = ReflectionRecord(
            reflection_id=f"ref_{uuid.uuid4().hex[:8]}",
            task_type=task_type,
            original_goal=original_goal,
            what_went_wrong=error_info.get("message", "Unknown error"),
            root_cause=root_cause,
            improved_strategy=improved_strategy,
            confidence=self._estimate_confidence(root_cause, improved_strategy),
        )

        # 存储到记忆系统
        self._store_reflection(record)

        logger.info(
            "Reflection recorded: task=%s, cause=%s, confidence=%.2f",
            task_type, root_cause, record.confidence,
        )

        return record

    # ------------------------------------------------------------------
    # 反思检索
    # ------------------------------------------------------------------

    def get_relevant_reflections(
        self,
        task_type: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """检索相关的历史反思。

        Args:
            task_type: 任务类型过滤（None 返回所有）
            limit: 返回数量

        Returns:
            反思记录列表
        """
        try:
            # 从记忆系统检索
            query = f"{task_type or 'all'} reflection improvement"
            results = self._memory_pool.retrieve(
                user_id=self.user_id,
                query=query,
                level="episodic",
                top_k=limit,
            )

            reflections = []
            for r in results:
                content = r.get("content", "")
                metadata = r.get("metadata", {})
                if metadata.get("type") == "reflection":
                    reflections.append({
                        "content": content,
                        "metadata": metadata,
                        "score": r.get("score", 0),
                    })

            return reflections

        except Exception as exc:
            logger.warning("Failed to retrieve reflections: %s", exc)
            return []

    def get_unresolved_reflections(self) -> List[Dict[str, Any]]:
        """获取所有未解决的反思。"""
        reflections = self.get_relevant_reflections(limit=20)
        return [
            r for r in reflections
            if not r.get("metadata", {}).get("resolved", False)
        ]

    def mark_as_resolved(
        self, reflection_id: str, resolution_notes: str = ""
    ) -> bool:
        """标记反思为已解决。

        Args:
            reflection_id: 反思 ID
            resolution_notes: 解决说明

        Returns:
            是否成功
        """
        try:
            # 在记忆中更新
            self._memory_pool.store(
                user_id=self.user_id,
                content=f"[RESOLVED] Reflection {reflection_id}: {resolution_notes}",
                level="episodic",
                metadata={
                    "type": "reflection_resolution",
                    "reflection_id": reflection_id,
                    "resolved": True,
                    "resolution_notes": resolution_notes,
                },
                topic="reflection_resolved",
                agents=["reflection_engine"],
                outcome="reflection_resolved",
            )
            self._resolved_count += 1
            logger.info("Reflection %s marked as resolved", reflection_id)
            return True
        except Exception as exc:
            logger.warning("Failed to resolve reflection: %s", exc)
            return False

    # ------------------------------------------------------------------
    # 内部分析方法
    # ------------------------------------------------------------------

    def _extract_error_info(
        self, execution_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """从执行结果中提取错误信息。"""
        error_type = "unknown"
        error_message = ""

        if "error" in execution_result:
            error_msg = str(execution_result["error"]).lower()
            error_message = execution_result["error"]

            # 分类错误类型
            if any(kw in error_msg for kw in ["timeout", "connection", "network"]):
                error_type = "network"
            elif any(kw in error_msg for kw in ["param", "invalid", "required", "missing"]):
                error_type = "parameter"
            elif any(kw in error_msg for kw in ["not found", "not exist", "404"]):
                error_type = "not_found"
            elif any(kw in error_msg for kw in ["permission", "denied", "unauthorized"]):
                error_type = "permission"
            elif any(kw in error_msg for kw in ["tool", "function"]):
                error_type = "tool_execution"

        return {
            "type": error_type,
            "message": error_message,
            "has_error": bool(error_message),
        }

    def _analyze_root_cause(
        self,
        error_info: Dict[str, Any],
        task_type: str,
        execution_result: Dict[str, Any],
    ) -> str:
        """分析失败的根本原因。

        基于错误类型和执行上下文，判断最可能的根本原因。
        """
        error_type = error_info.get("type", "unknown")

        cause_map = {
            "network": "外部服务暂时不可用，建议使用本地缓存或降级策略",
            "parameter": "输入参数不符合预期格式，建议增加参数校验层",
            "not_found": "请求的资源不存在，建议增加资源预检",
            "permission": "权限不足，建议检查认证配置",
            "tool_execution": "工具执行失败，建议检查工具配置和依赖",
            "unknown": "未知错误，需要进一步排查",
        }

        base_cause = cause_map.get(error_type, "未知原因")

        # 添加上下文分析
        if task_type == "analysis" and error_type == "parameter":
            return f"{base_cause}。运动数据文件可能格式不符合预期，建议在解析前增加文件格式校验"
        elif task_type == "tool_call" and error_type == "tool_execution":
            return f"{base_cause}。工具链可能存在兼容性问题，建议增加工具健康检查"
        elif task_type == "chat" and error_type == "network":
            return f"{base_cause}。LLM API 可能暂时不可用，建议启用规则降级模式"

        return base_cause

    def _generate_improved_strategy(
        self,
        root_cause: str,
        task_type: str,
        goal: str,
        feedback: Optional[Dict[str, Any]] = None,
    ) -> str:
        """生成改进策略。"""
        strategies = {
            "network": "使用本地缓存或备用数据源；增加指数退避重试；设置合理的超时时间",
            "parameter": "增加参数 Schema 校验层；使用 Pydantic 模型验证；提供友好的参数错误提示",
            "not_found": "增加资源预检；提供默认值或替代方案；在文档中说明资源要求",
            "permission": "检查 API Key 和认证 Token；实现权限分级；提供降级权限方案",
            "tool_execution": "增加工具健康检查；实现工具熔断机制；准备备用工具",
            "unknown": "增加详细日志；实现错误自动上报；定期进行故障演练",
        }

        # 确定错误类型
        error_type = "unknown"
        for kw in ["network", "parameter", "not_found", "permission", "tool_execution"]:
            if kw in root_cause.lower():
                error_type = kw
                break

        base_strategy = strategies.get(error_type, strategies["unknown"])

        # 结合具体任务优化
        if task_type == "analysis":
            return f"{base_strategy}。对于运动数据分析场景，建议：1) 文件格式预校验 2) 解析失败时展示友好提示 3) 支持多格式自动转换"
        elif task_type == "chat":
            return f"{base_strategy}。对于 AI 问答场景，建议：1) LLM 不可用时使用规则引擎 2) 增加本地知识库作为兜底 3) 实现渐进式回答"
        elif task_type == "tool_call":
            return f"{base_strategy}。对于工具调用场景，建议：1) 工具调用前检查可用性 2) 实现工具降级链 3) 记录工具性能指标"

        return base_strategy

    def _estimate_confidence(
        self, root_cause: str, strategy: str
    ) -> float:
        """估算改进策略的信心度（0-1）。"""
        confidence = 0.6  # 基础信心

        # 基于根因清晰度调整
        if root_cause and len(root_cause) > 20:
            confidence += 0.1  # 清晰的根因分析

        # 基于策略具体性调整
        if strategy and len(strategy) > 50:
            confidence += 0.15  # 具体的改进策略

        # 包含具体步骤加分
        if any(kw in strategy for kw in ["建议", "实现", "增加", "使用"]):
            confidence += 0.05

        return min(0.95, confidence)

    def _store_reflection(self, record: ReflectionRecord) -> None:
        """将反思存储到记忆系统。"""
        # 缓存到最近记录
        self._recent_reflections.append(record)
        if len(self._recent_reflections) > self.MAX_RECENT:
            self._recent_reflections = self._recent_reflections[-self.MAX_RECENT:]

        try:
            self._memory_pool.store(
                user_id=self.user_id,
                content=(
                    f"[Reflection] Task: {record.task_type} | "
                    f"Error: {record.what_went_wrong} | "
                    f"Root Cause: {record.root_cause} | "
                    f"Strategy: {record.improved_strategy} | "
                    f"Confidence: {record.confidence:.2f}"
                ),
                level="episodic",
                metadata={
                    "type": "reflection",
                    "reflection_id": record.reflection_id,
                    "task_type": record.task_type,
                    "root_cause": record.root_cause,
                    "strategy": record.improved_strategy,
                    "confidence": record.confidence,
                    "resolved": False,
                },
                topic=f"reflection_{record.task_type}",
                agents=["reflection_engine"],
                outcome="failure_reflected",
            )
        except Exception as exc:
            logger.warning("Failed to store reflection: %s", exc)

    # ------------------------------------------------------------------
    # 统计与管理
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """获取反思引擎统计。"""
        return {
            "total_reflections": self._reflection_count,
            "resolved_reflections": self._resolved_count,
            "pending_reflections": self._reflection_count - self._resolved_count,
            "resolution_rate": (
                self._resolved_count / self._reflection_count * 100
                if self._reflection_count > 0
                else 0
            ),
        }

    def get_recent_reflections(
        self,
        task_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[ReflectionRecord]:
        """获取最近的反思记录。

        Args:
            task_type: 任务类型过滤
            limit: 返回数量

        Returns:
            反思记录列表
        """
        reflections = self._recent_reflections
        if task_type:
            reflections = [r for r in reflections if r.task_type == task_type]
        return reflections[-limit:]

    def clear_history(self) -> None:
        """清空反思历史。"""
        self._reflection_count = 0
        self._resolved_count = 0
        logger.info("Reflection history cleared for user: %s", self.user_id)
