"""Fault Tolerance System: 三级容错恢复机制。

让 Agent 具备「韧性」：
- L1 快速重试：单步失败时自动重试 / 切换同类工具 / 调整参数
- L2 策略切换：连续失败时，反思引擎生成全新执行策略
- L3 优雅降级：所有策略失败时，返回部分结果 + 不确定性声明

设计哲学：
- 失败不是终点，而是信息
- 每一级降级都让系统「退一步，海阔天空」
- 最终仍失败时，也要诚实告知用户不确定性
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

class RecoveryLevel(Enum):
    """恢复级别。"""
    L1_RETRY = "l1_retry"           # 快速重试
    L2_STRATEGY_SHIFT = "l2_strategy_shift"  # 策略切换
    L3_GRACEFUL_DEGRADE = "l3_graceful_degrade"  # 优雅降级


class ErrorCategory(Enum):
    """错误分类。"""
    NETWORK_TIMEOUT = "network_timeout"
    TOOL_UNAVAILABLE = "tool_unavailable"
    INVALID_INPUT = "invalid_input"
    COMPUTATION_ERROR = "computation_error"
    RATE_LIMITED = "rate_limited"
    DATA_QUALITY = "data_quality"
    UNKNOWN = "unknown"


@dataclass
class RecoveryAction:
    """恢复行动描述。"""
    level: RecoveryLevel
    action: str                    # retry / switch_tool / replan / degrade
    target: str                    # 目标工具或步骤
    parameters: Dict[str, Any] = field(default_factory=dict)
    estimated_success_rate: float = 0.5
    cost: float = 1.0
    reason: str = ""


@dataclass
class ErrorRecord:
    """错误记录。"""
    timestamp: float
    error_message: str
    category: ErrorCategory
    tool_name: str = ""
    recovery_attempts: int = 0
    resolved: bool = False
    resolution_level: Optional[RecoveryLevel] = None


@dataclass
class GracefulDegradationResult:
    """优雅降级结果。"""
    success: bool = False
    partial_result: Any = None
    uncertainty_declaration: str = ""
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Error Classifier
# ---------------------------------------------------------------------------

class ErrorClassifier:
    """错误分类器。

    根据错误信息判断错误类型，指导恢复策略选择。
    """

    # 错误关键词映射
    ERROR_PATTERNS: Dict[ErrorCategory, List[str]] = {
        ErrorCategory.NETWORK_TIMEOUT: [
            "timeout", "timed out", "connection refused", "network error",
            "连接超时", "网络错误",
        ],
        ErrorCategory.TOOL_UNAVAILABLE: [
            "not found", "no such tool", "tool not available", "import error",
            "未找到", "工具不可用",
        ],
        ErrorCategory.INVALID_INPUT: [
            "invalid", "validation", "schema", "type error", "key error",
            "无效", "格式错误", "参数错误",
        ],
        ErrorCategory.COMPUTATION_ERROR: [
            "computation", "overflow", "underflow", "division by zero",
            "计算错误", "溢出",
        ],
        ErrorCategory.RATE_LIMITED: [
            "rate limit", "too many requests", "quota", "429",
            "频率限制", "配额",
        ],
        ErrorCategory.DATA_QUALITY: [
            "corrupt", "invalid data", "missing field", "unexpected format",
            "数据损坏", "缺失字段",
        ],
    }

    def classify(self, error_message: str) -> ErrorCategory:
        """分类错误类型。

        Args:
            error_message: 错误信息

        Returns:
            错误分类
        """
        error_lower = error_message.lower()

        for category, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in error_lower:
                    return category

        return ErrorCategory.UNKNOWN

    def is_retryable(self, category: ErrorCategory) -> bool:
        """判断错误是否可重试。

        Args:
            category: 错误分类

        Returns:
            是否可重试
        """
        retryable = {
            ErrorCategory.NETWORK_TIMEOUT,
            ErrorCategory.RATE_LIMITED,
        }
        return category in retryable

    def is_auto_fixable(self, category: ErrorCategory) -> bool:
        """判断错误是否可自动修复。

        Args:
            category: 错误分类

        Returns:
            是否可自动修复
        """
        auto_fixable = {
            ErrorCategory.INVALID_INPUT,
            ErrorCategory.DATA_QUALITY,
        }
        return category in auto_fixable


# ---------------------------------------------------------------------------
# Fault Tolerance Manager
# ---------------------------------------------------------------------------

class FaultToleranceManager:
    """三级容错管理器。

    核心职责：
    1. 记录所有错误和恢复尝试
    2. 根据错误类型和历史，选择合适的恢复级别
    3. 执行恢复行动并验证结果
    4. 在必要时触发优雅降级

    Usage:
        ftm = FaultToleranceManager()

        # L1: 快速重试
        result = ftm.execute_with_recovery(
            action=lambda: call_tool(tool_name),
            tool_name="weather_api",
        )

        # 检查是否降级
        if result.degraded:
            handle_gracefully(result)
    """

    def __init__(
        self,
        max_l1_retries: int = 3,
        l1_retry_delay: float = 0.5,
        max_l2_shifts: int = 2,
        enable_l3_degradation: bool = True,
    ):
        """初始化容错管理器。

        Args:
            max_l1_retries: L1 最大重试次数
            l1_retry_delay: L1 重试间隔（秒）
            max_l2_shifts: L2 最大策略切换次数
            enable_l3_degradation: 是否启用 L3 优雅降级
        """
        self.max_l1_retries = max_l1_retries
        self.l1_retry_delay = l1_retry_delay
        self.max_l2_shifts = max_l2_shifts
        self.enable_l3_degradation = enable_l3_degradation

        self.classifier = ErrorClassifier()
        self._error_history: List[ErrorRecord] = []
        self._l2_strategy_count: int = 0

    # ------------------------------------------------------------------
    # L1: 快速重试
    # ------------------------------------------------------------------

    def l1_retry(
        self,
        action: Callable,
        tool_name: str = "",
        args: Optional[Dict[str, Any]] = None,
        alternative_tools: Optional[List[str]] = None,
    ) -> Tuple[Any, RecoveryAction]:
        """L1 级恢复：快速重试。

        策略：
        1. 直接重试（最多 max_l1_retries 次）
        2. 自动调整参数重试
        3. 切换到同类工具

        Args:
            action: 要执行的操作
            tool_name: 工具名称
            args: 操作参数
            alternative_tools: 可替代的工具列表

        Returns:
            (执行结果, 恢复行动)
        """
        last_error = None

        # 直接重试
        for attempt in range(self.max_l1_retries):
            try:
                result = action(**(args or {}))
                if result is not None:
                    self._record_success(tool_name, RecoveryLevel.L1_RETRY)
                    recovery = RecoveryAction(
                        level=RecoveryLevel.L1_RETRY,
                        action="retry",
                        target=tool_name,
                        parameters={"attempt": attempt + 1},
                        estimated_success_rate=0.7,
                        reason=f"第 {attempt + 1} 次重试成功",
                    )
                    return result, recovery
            except Exception as exc:
                last_error = exc
                error_msg = str(exc)
                category = self.classifier.classify(error_msg)

                # 如果不可重试，直接跳出
                if not self.classifier.is_retryable(category):
                    break

                # 等待后重试
                time.sleep(self.l1_retry_delay * (attempt + 1))

        # 尝试切换替代工具
        if alternative_tools and last_error:
            for alt_tool in alternative_tools:
                recovery = RecoveryAction(
                    level=RecoveryLevel.L1_RETRY,
                    action="switch_tool",
                    target=alt_tool,
                    estimated_success_rate=0.5,
                    reason=f"从 {tool_name} 切换到 {alt_tool}",
                )
                logger.info("L1 恢复: 切换工具 %s -> %s", tool_name, alt_tool)
                return None, recovery  # 由上层处理工具切换

        # L1 恢复失败
        if last_error:
            self._record_error(tool_name, str(last_error), RecoveryLevel.L1_RETRY)

        raise last_error or RuntimeError("L1 recovery failed")

    # ------------------------------------------------------------------
    # L2: 策略切换
    # ------------------------------------------------------------------

    def l2_strategy_shift(
        self,
        original_goal: str,
        failed_step: str,
        reflection_insights: Optional[Dict[str, Any]] = None,
    ) -> RecoveryAction:
        """L2 级恢复：策略切换。

        当连续 L1 恢复失败时，使用反思引擎生成全新的执行策略。

        Args:
            original_goal: 原始目标
            failed_step: 失败的步骤
            reflection_insights: 反思见解

        Returns:
            新的恢复行动描述
        """
        self._l2_strategy_count += 1

        # 基于反思生成新策略
        if reflection_insights:
            new_strategy = reflection_insights.get("improved_strategy", "重新规划执行路径")
            root_cause = reflection_insights.get("root_cause", "未知原因")
        else:
            new_strategy = "重新规划执行路径"
            root_cause = "多次 L1 恢复失败"

        recovery = RecoveryAction(
            level=RecoveryLevel.L2_STRATEGY_SHIFT,
            action="replan",
            target=failed_step,
            parameters={
                "original_goal": original_goal,
                "root_cause": root_cause,
                "new_strategy": new_strategy,
            },
            estimated_success_rate=0.4,
            cost=3.0,
            reason=f"L2 策略切换: {new_strategy} (根因: {root_cause})",
        )

        logger.warning("L2 恢复: %s", recovery.reason)
        return recovery

    # ------------------------------------------------------------------
    # L3: 优雅降级
    # ------------------------------------------------------------------

    def l3_graceful_degradation(
        self,
        completed_steps: List[Tuple[str, Any]],
        failed_steps: List[str],
        original_goal: str,
    ) -> GracefulDegradationResult:
        """L3 级恢复：优雅降级。

        当所有恢复策略都失败时，返回部分结果并声明不确定性。

        Args:
            completed_steps: 已完成的步骤及其结果
            failed_steps: 失败的步骤
            original_goal: 原始目标

        Returns:
            降级结果
        """
        logger.warning("L3 降级: 任务 '%s' 部分完成", original_goal)

        # 构建部分结果
        partial_data = {step: result for step, result in completed_steps}

        # 生成不确定性声明
        declaration_parts = [
            f"任务「{original_goal}」仅部分完成，存在不确定性。",
        ]

        if completed_steps:
            step_names = [s for s, _ in completed_steps]
            declaration_parts.append(f"已完成: {', '.join(step_names)}。")

        if failed_steps:
            declaration_parts.append(f"未完成: {', '.join(failed_steps)}。")

        declaration_parts.append(
            "建议检查数据质量或联系管理员以获取完整结果。"
        )

        recommendations = self._generate_recommendations(
            failed_steps, original_goal
        )

        return GracefulDegradationResult(
            success=False,
            partial_result=partial_data if partial_data else None,
            uncertainty_declaration=" ".join(declaration_parts),
            completed_steps=[s for s, _ in completed_steps],
            failed_steps=failed_steps,
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # 完整容错流程
    # ------------------------------------------------------------------

    def execute_with_protection(
        self,
        steps: List[Dict[str, Any]],
        original_goal: str,
        reflection_engine: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """执行带完整容错保护的步骤序列。

        流程：
        1. 对每个步骤执行 L1 快速重试
        2. 全部步骤失败后触发 L2 策略切换
        3. L2 也失败时触发 L3 优雅降级

        Args:
            steps: 步骤列表，每个包含:
                - name: 步骤名
                - execute: 执行函数
                - alternatives: 可选替代执行函数
            original_goal: 原始目标
            reflection_engine: 反思引擎

        Returns:
            执行结果字典
        """
        completed: List[Tuple[str, Any]] = []
        failed: List[str] = []
        consecutive_failures = 0

        for step_info in steps:
            step_name = step_info["name"]
            execute_fn = step_info.get("execute")
            alternatives = step_info.get("alternatives", [])

            if not execute_fn:
                failed.append(step_name)
                consecutive_failures += 1
                continue

            # 尝试执行
            try:
                result, _ = self.l1_retry(
                    action=execute_fn,
                    tool_name=step_name,
                )
                completed.append((step_name, result))
                consecutive_failures = 0
            except Exception:
                # L1 失败，尝试替代方案
                alt_success = False
                for alt_fn in alternatives:
                    try:
                        result, _ = self.l1_retry(
                            action=alt_fn,
                            tool_name=f"{step_name}_alt",
                        )
                        completed.append((step_name, result))
                        alt_success = True
                        consecutive_failures = 0
                        break
                    except Exception:
                        continue

                if not alt_success:
                    failed.append(step_name)
                    consecutive_failures += 1

                    # 检查是否需要 L2 切换
                    if (consecutive_failures >= self.max_l1_retries
                            and self._l2_strategy_count < self.max_l2_shifts):
                        # 获取反思见解
                        insights = None
                        if reflection_engine:
                            try:
                                insights = reflection_engine.reflect_on_failure(
                                    task_type=original_goal,
                                    original_goal=original_goal,
                                    execution_result={"failed_steps": failed},
                                )
                                insights = insights.to_dict() if hasattr(insights, 'to_dict') else {}
                            except Exception:
                                pass

                        recovery = self.l2_strategy_shift(
                            original_goal=original_goal,
                            failed_step=step_name,
                            reflection_insights=insights,
                        )
                        logger.warning(
                            "L2 恢复建议: %s", recovery.reason
                        )

        # 全部失败，触发 L3
        if not completed and failed and self.enable_l3_degradation:
            degradation = self.l3_graceful_degradation(
                completed_steps=completed,
                failed_steps=failed,
                original_goal=original_goal,
            )
            return {
                "success": False,
                "degraded": True,
                "degradation_result": degradation,
                "completed": completed,
                "failed": failed,
            }

        return {
            "success": len(completed) > 0,
            "degraded": len(failed) > 0 and len(completed) > 0,
            "completed": completed,
            "failed": failed,
            "total_steps": len(steps),
            "success_rate": len(completed) / max(len(steps), 1),
        }

    # ------------------------------------------------------------------
    # 统计与辅助
    # ------------------------------------------------------------------

    def _record_error(
        self,
        tool_name: str,
        error_message: str,
        level: RecoveryLevel,
    ) -> None:
        """记录错误。"""
        record = ErrorRecord(
            timestamp=time.time(),
            error_message=error_message,
            category=self.classifier.classify(error_message),
            tool_name=tool_name,
            recovery_attempts=1,
            resolved=False,
            resolution_level=level,
        )
        self._error_history.append(record)

    def _record_success(
        self,
        tool_name: str,
        level: RecoveryLevel,
    ) -> None:
        """记录成功恢复。"""
        # 找到最近的相关错误记录并标记为已解决
        for record in reversed(self._error_history):
            if record.tool_name == tool_name and not record.resolved:
                record.resolved = True
                record.resolution_level = level
                break

    def _generate_recommendations(
        self,
        failed_steps: List[str],
        original_goal: str,
    ) -> List[str]:
        """生成改进建议。"""
        recommendations = []

        if failed_steps:
            recommendations.append(
                f"检查以下步骤的执行条件: {', '.join(failed_steps)}"
            )

        recommendations.append(
            "考虑使用 Mock 数据在测试环境验证完整流程"
        )
        recommendations.append(
            "逐步恢复功能，从最简单的步骤开始"
        )

        return recommendations

    def get_stats(self) -> Dict[str, Any]:
        """获取容错统计。"""
        total = len(self._error_history)
        resolved = sum(1 for e in self._error_history if e.resolved)

        # 按类别统计
        category_counts: Dict[str, int] = {}
        for err in self._error_history:
            cat = err.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "total_errors": total,
            "resolved_errors": resolved,
            "resolution_rate": (resolved / max(total, 1) * 100),
            "l2_strategy_shifts": self._l2_strategy_count,
            "error_categories": category_counts,
            "max_l1_retries": self.max_l1_retries,
            "max_l2_shifts": self.max_l2_shifts,
        }
