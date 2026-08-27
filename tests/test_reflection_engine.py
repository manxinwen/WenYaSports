"""ReflectionEngine 单元测试。

验证自我反思引擎的核心能力：
1. 失败反思：分析失败原因、生成改进策略
2. 经验检索：基于任务类型检索历史反思
3. 解决追踪：标记反思为已解决
4. 统计管理：反思计数、解决率统计
"""

import pytest

from app.agents.reflection_engine import (
    ReflectionRecord,
    ReflectionEngine,
)


# ---------------------------------------------------------------------------
# ReflectionRecord 测试
# ---------------------------------------------------------------------------

class TestReflectionRecord:
    """反思记录数据结构测试。"""

    def test_record_to_dict(self):
        record = ReflectionRecord(
            reflection_id="ref_001",
            task_type="analysis",
            original_goal="分析跑步数据",
            what_went_wrong="文件格式错误",
            root_cause="FIT 文件头不符合协议",
            improved_strategy="增加文件格式预校验",
            confidence=0.85,
        )

        d = record.to_dict()

        assert d["reflection_id"] == "ref_001"
        assert d["task_type"] == "analysis"
        assert d["confidence"] == 0.85
        assert d["resolved"] is False
        assert "created_at" in d


# ---------------------------------------------------------------------------
# ReflectionEngine 测试
# ---------------------------------------------------------------------------

class TestReflectionEngine:
    """反思引擎主测试。"""

    def test_reflect_on_network_failure(self):
        """网络故障反思。"""
        engine = ReflectionEngine(user_id="test_user")

        execution_result = {"error": "Connection timeout after 30s"}

        record = engine.reflect_on_failure(
            task_type="chat",
            original_goal="获取天气数据",
            execution_result=execution_result,
        )

        assert isinstance(record, ReflectionRecord)
        assert record.task_type == "chat"
        assert record.confidence > 0.5
        assert len(record.improved_strategy) > 0
        assert len(record.root_cause) > 0

    def test_reflect_on_parameter_error(self):
        """参数错误反思。"""
        engine = ReflectionEngine(user_id="test_user")

        execution_result = {"error": "Missing required parameter: file_path"}

        record = engine.reflect_on_failure(
            task_type="analysis",
            original_goal="解析运动数据文件",
            execution_result=execution_result,
        )

        assert "parameter" in record.root_cause.lower() or "参数" in record.root_cause
        assert len(record.improved_strategy) > 0

    def test_reflect_on_tool_execution_failure(self):
        """工具执行失败反思。"""
        engine = ReflectionEngine(user_id="test_user")

        execution_result = {"error": "Tool 'parser' execution failed: Invalid format"}

        record = engine.reflect_on_failure(
            task_type="tool_call",
            original_goal="调用解析器",
            execution_result=execution_result,
        )

        assert record.confidence > 0.5

    def test_reflect_with_evaluation_feedback(self):
        """带评估反馈的反思。"""
        engine = ReflectionEngine(user_id="test_user")

        execution_result = {"error": "Tool failed"}
        evaluation_feedback = {
            "score": 4.5,
            "issues": ["缺少数据支撑", "建议不具体"],
        }

        record = engine.reflect_on_failure(
            task_type="analysis",
            original_goal="分析跑步数据",
            execution_result=execution_result,
            evaluation_feedback=evaluation_feedback,
        )

        assert record.confidence > 0.5
        assert len(record.improved_strategy) > 30  # 策略应该比较详细

    def test_get_relevant_reflections(self):
        """检索相关反思记录。"""
        engine = ReflectionEngine(user_id="test_user")

        # 创建几条反思
        engine.reflect_on_failure(
            task_type="analysis",
            original_goal="分析跑步数据",
            execution_result={"error": "timeout"},
        )
        engine.reflect_on_failure(
            task_type="chat",
            original_goal="AI 问答",
            execution_result={"error": "API unavailable"},
        )

        reflections = engine.get_relevant_reflections(task_type="analysis", limit=5)

        assert isinstance(reflections, list)

    def test_get_unresolved_reflections(self):
        """获取未解决反思。"""
        engine = ReflectionEngine(user_id="test_user")

        engine.reflect_on_failure(
            task_type="analysis",
            original_goal="测试",
            execution_result={"error": "test error"},
        )

        unresolved = engine.get_unresolved_reflections()

        assert isinstance(unresolved, list)

    def test_mark_as_resolved(self):
        """标记反思为已解决。"""
        engine = ReflectionEngine(user_id="test_user")

        record = engine.reflect_on_failure(
            task_type="analysis",
            original_goal="测试",
            execution_result={"error": "test error"},
        )

        success = engine.mark_as_resolved(
            record.reflection_id,
            resolution_notes="已修复：增加了超时重试机制",
        )

        assert success is True

    def test_get_stats(self):
        """统计信息检查。"""
        engine = ReflectionEngine(user_id="test_user")

        engine.reflect_on_failure(
            task_type="analysis",
            original_goal="测试1",
            execution_result={"error": "error1"},
        )
        engine.reflect_on_failure(
            task_type="chat",
            original_goal="测试2",
            execution_result={"error": "error2"},
        )

        stats = engine.get_stats()

        assert stats["total_reflections"] == 2
        assert stats["pending_reflections"] == 2
        assert stats["resolution_rate"] == 0

    def test_clear_history(self):
        """清空历史。"""
        engine = ReflectionEngine(user_id="test_user")

        engine.reflect_on_failure(
            task_type="test",
            original_goal="测试",
            execution_result={"error": "error"},
        )

        engine.clear_history()
        stats = engine.get_stats()

        assert stats["total_reflections"] == 0
        assert stats["resolved_reflections"] == 0

    def test_confidence_estimation(self):
        """信心度估算逻辑。"""
        engine = ReflectionEngine(user_id="test_user")

        # 短根因 -> 较低信心
        short_record = engine.reflect_on_failure(
            task_type="test",
            original_goal="测试",
            execution_result={"error": "err"},
        )

        assert short_record.confidence >= 0.0
        assert short_record.confidence <= 1.0
