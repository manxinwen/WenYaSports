"""Tests for Fault Tolerance System."""

import pytest
import time

from app.orchestrator.fault_tolerance import (
    ErrorClassifier,
    ErrorCategory,
    RecoveryLevel,
    RecoveryAction,
    FaultToleranceManager,
    GracefulDegradationResult,
)


class TestErrorClassifier:
    """错误分类器测试。"""

    def test_classify_network_timeout(self):
        """分类网络超时。"""
        classifier = ErrorClassifier()
        cat = classifier.classify("Connection timed out")
        assert cat == ErrorCategory.NETWORK_TIMEOUT

    def test_classify_tool_unavailable(self):
        """分类工具不可用。"""
        classifier = ErrorClassifier()
        cat = classifier.classify("tool not found")
        assert cat == ErrorCategory.TOOL_UNAVAILABLE

    def test_classify_invalid_input(self):
        """分类无效输入。"""
        classifier = ErrorClassifier()
        cat = classifier.classify("invalid schema validation failed")
        assert cat == ErrorCategory.INVALID_INPUT

    def test_classify_rate_limited(self):
        """分类频率限制。"""
        classifier = ErrorClassifier()
        cat = classifier.classify("rate limit exceeded 429")
        assert cat == ErrorCategory.RATE_LIMITED

    def test_classify_unknown(self):
        """分类未知错误。"""
        classifier = ErrorClassifier()
        cat = classifier.classify("something went wrong")
        assert cat == ErrorCategory.UNKNOWN

    def test_is_retryable(self):
        """判断是否可重试。"""
        classifier = ErrorClassifier()
        assert classifier.is_retryable(ErrorCategory.NETWORK_TIMEOUT)
        assert classifier.is_retryable(ErrorCategory.RATE_LIMITED)
        assert not classifier.is_retryable(ErrorCategory.INVALID_INPUT)
        assert not classifier.is_retryable(ErrorCategory.TOOL_UNAVAILABLE)

    def test_is_auto_fixable(self):
        """判断是否可自动修复。"""
        classifier = ErrorClassifier()
        assert classifier.is_auto_fixable(ErrorCategory.INVALID_INPUT)
        assert classifier.is_auto_fixable(ErrorCategory.DATA_QUALITY)
        assert not classifier.is_auto_fixable(ErrorCategory.NETWORK_TIMEOUT)


class TestFaultToleranceManager:
    """容错管理器测试。"""

    def test_l1_retry_success_first_attempt(self):
        """L1 首次重试成功。"""
        ftm = FaultToleranceManager(max_l1_retries=3)
        call_count = [0]

        def succeed_first():
            call_count[0] += 1
            return "success"

        result, action = ftm.l1_retry(succeed_first, "test_tool")
        assert result == "success"
        assert action.level == RecoveryLevel.L1_RETRY
        assert call_count[0] == 1

    def test_l1_retry_second_attempt(self):
        """L1 第二次重试成功。"""
        ftm = FaultToleranceManager(max_l1_retries=3)
        call_count = [0]

        def fail_first():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionError("timeout")
            return "success"

        result, action = ftm.l1_retry(fail_first, "test_tool")
        assert result == "success"
        assert call_count[0] == 2

    def test_l1_retry_exhausted(self):
        """L1 重试耗尽。"""
        ftm = FaultToleranceManager(max_l1_retries=2, l1_retry_delay=0)

        def always_fail():
            raise ConnectionError("timeout")

        with pytest.raises(ConnectionError):
            ftm.l1_retry(always_fail, "test_tool")

    def test_l1_switch_tool(self):
        """L1 切换替代工具。"""
        ftm = FaultToleranceManager(
            max_l1_retries=2,
            l1_retry_delay=0,
        )

        def fail_always():
            raise ConnectionError("timeout")

        recovery = ftm.l1_retry(
            fail_always,
            "primary_tool",
            alternative_tools=["fallback_tool"],
        )
        # 应返回 None 结果和切换行动
        assert recovery[0] is None
        assert recovery[1].action == "switch_tool"
        assert recovery[1].target == "fallback_tool"

    def test_l2_strategy_shift(self):
        """L2 策略切换。"""
        ftm = FaultToleranceManager()

        recovery = ftm.l2_strategy_shift(
            original_goal="分析数据",
            failed_step="parse_file",
            reflection_insights={
                "improved_strategy": "改用 CSV 解析器",
                "root_cause": "FIT 格式不兼容",
            },
        )

        assert recovery.level == RecoveryLevel.L2_STRATEGY_SHIFT
        assert recovery.action == "replan"
        assert recovery.estimated_success_rate == 0.4

    def test_l3_graceful_degradation(self):
        """L3 优雅降级。"""
        ftm = FaultToleranceManager()

        completed = [("parse_data", {"rows": 100})]
        failed = ["analyze_features", "generate_report"]

        result = ftm.l3_graceful_degradation(
            completed_steps=completed,
            failed_steps=failed,
            original_goal="完整分析",
        )

        assert isinstance(result, GracefulDegradationResult)
        assert result.success is False
        assert result.partial_result is not None
        assert "不确定性" in result.uncertainty_declaration
        assert len(result.recommendations) > 0

    def test_execute_with_protection_all_success(self):
        """完整容错流程 - 全部成功。"""
        ftm = FaultToleranceManager()

        steps = [
            {
                "name": "step1",
                "execute": lambda: "result1",
            },
            {
                "name": "step2",
                "execute": lambda: "result2",
            },
        ]

        result = ftm.execute_with_protection(steps, "test goal")
        assert result["success"] is True
        assert len(result["completed"]) == 2
        assert result["success_rate"] == 1.0

    def test_execute_with_protection_partial(self):
        """完整容错流程 - 部分失败。"""
        ftm = FaultToleranceManager(max_l1_retries=1, l1_retry_delay=0)

        def fail_fn():
            raise ValueError("invalid input")

        steps = [
            {
                "name": "step1",
                "execute": lambda: "result1",
            },
            {
                "name": "step2",
                "execute": fail_fn,
                "alternatives": [],
            },
        ]

        result = ftm.execute_with_protection(steps, "test goal")
        assert result["success"] is True  # 部分成功也算成功
        assert result["degraded"] is True
        assert len(result["completed"]) == 1
        assert len(result["failed"]) == 1

    def test_execute_with_protection_all_fail(self):
        """完整容错流程 - 全部失败触发 L3。"""
        ftm = FaultToleranceManager(
            max_l1_retries=1,
            l1_retry_delay=0,
            enable_l3_degradation=True,
        )

        def fail_fn():
            raise RuntimeError("critical error")

        steps = [
            {"name": "step1", "execute": fail_fn},
            {"name": "step2", "execute": fail_fn},
        ]

        result = ftm.execute_with_protection(steps, "test goal")
        assert result["success"] is False
        assert result["degraded"] is True
        assert "degradation_result" in result

    def test_get_stats(self):
        """统计信息。"""
        ftm = FaultToleranceManager()

        # 执行一些操作
        try:
            ftm.l1_retry(
                lambda: (_ for _ in ()).throw(ConnectionError("timeout")),
                "fail_tool",
            )
        except ConnectionError:
            pass

        stats = ftm.get_stats()
        assert "total_errors" in stats
        assert "resolution_rate" in stats
