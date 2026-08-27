"""Agent Behavior Evaluator Tests."""

import json
import os
import time

import pytest

from app.evaluation import (
    AgentEvaluator,
    EvaluationReport,
    EvaluationMetrics,
    RunRecord,
)


# ---------------------------------------------------------------------------
# AgentEvaluator Tests
# ---------------------------------------------------------------------------

class TestAgentEvaluator:
    """Agent行为评估器测试。"""

    def test_start_and_end_run(self):
        evaluator = AgentEvaluator(config_id="test")
        evaluator.start_run("run_1", agent_id="coordinator", task="分析数据")
        evaluator.end_run("run_1", success=True, response_quality=0.9)

        record = evaluator.get_run("run_1")
        assert record is not None
        assert record["success"] is True
        assert record["agent_id"] == "coordinator"
        assert record["response_quality"] == 0.9
        assert record["latency_ms"] >= 0

    def test_record_step(self):
        evaluator = AgentEvaluator()
        evaluator.start_run("run_1")
        evaluator.record_step("run_1", tool="parser", success=True, tokens_used=100)
        evaluator.record_step("run_1", tool="memory", success=True, tokens_used=50)
        evaluator.record_step("run_1", tool="llm", success=False, tokens_used=200,
                               error="timeout")
        evaluator.end_run("run_1", success=True)

        record = evaluator.get_run("run_1")
        assert record["steps"] == 3
        assert record["tools_used"] == ["parser", "memory", "llm"]
        assert len(record["tool_errors"]) == 1
        assert record["tokens_used"] == 350

    def test_record_step_without_start(self):
        evaluator = AgentEvaluator()
        evaluator.record_step("nonexistent", tool="test")
        # Should not raise, just log a warning
        assert evaluator.get_run("nonexistent") is None

    def test_end_run_without_start(self):
        evaluator = AgentEvaluator()
        evaluator.end_run("nonexistent")
        assert evaluator.get_run("nonexistent") is None

    def test_multiple_runs(self):
        evaluator = AgentEvaluator()
        for i in range(5):
            evaluator.start_run(f"run_{i}")
            evaluator.end_run(f"run_{i}", success=(i < 4), response_quality=0.8)

        all_runs = evaluator.get_all_runs()
        assert len(all_runs) == 5

    def test_tokens_and_cost_tracking(self):
        evaluator = AgentEvaluator(cost_per_1k_tokens=0.003)
        evaluator.start_run("run_1")
        evaluator.record_step("run_1", tokens_used=500)
        evaluator.end_run("run_1", tokens_used=500)

        record = evaluator.get_run("run_1")
        assert record["tokens_used"] == 1000
        expected_cost = (1000 / 1000.0) * 0.003
        assert record["cost_estimate"] == pytest.approx(expected_cost, abs=0.0001)

    def test_latency_tracking(self):
        evaluator = AgentEvaluator()
        evaluator.start_run("run_1")
        time.sleep(0.05)
        evaluator.end_run("run_1", success=True)

        record = evaluator.get_run("run_1")
        assert record["latency_ms"] >= 40  # Allow some tolerance


# ---------------------------------------------------------------------------
# EvaluationMetrics Tests
# ---------------------------------------------------------------------------

class TestEvaluationMetrics:
    """评估指标计算测试。"""

    def test_compute_metrics_success_rate(self):
        evaluator = AgentEvaluator()
        evaluator.start_run("r1")
        evaluator.end_run("r1", success=True)
        evaluator.start_run("r2")
        evaluator.end_run("r2", success=True)
        evaluator.start_run("r3")
        evaluator.end_run("r3", success=False)

        metrics = evaluator.compute_metrics()
        assert metrics.total_tasks == 3
        assert metrics.successful_tasks == 2
        assert metrics.failed_tasks == 1
        assert metrics.task_success_rate == pytest.approx(2 / 3, abs=0.01)

    def test_compute_metrics_steps(self):
        evaluator = AgentEvaluator()
        evaluator.start_run("r1")
        evaluator.record_step("r1", tool="a")
        evaluator.record_step("r1", tool="b")
        evaluator.end_run("r1", success=True)

        evaluator.start_run("r2")
        evaluator.record_step("r2", tool="c")
        evaluator.end_run("r2", success=True)

        metrics = evaluator.compute_metrics()
        assert metrics.avg_steps_per_task == pytest.approx(1.5, abs=0.01)

    def test_compute_metrics_tool_accuracy(self):
        evaluator = AgentEvaluator()
        evaluator.start_run("r1")
        evaluator.record_step("r1", tool="a", success=True)
        evaluator.record_step("r1", tool="b", success=False, error="fail")
        evaluator.end_run("r1", success=True)

        metrics = evaluator.compute_metrics()
        # 2 tools, 1 error => accuracy = (2-1)/2 = 0.5
        assert metrics.tool_accuracy_rate == pytest.approx(0.5, abs=0.01)

    def test_compute_metrics_empty(self):
        evaluator = AgentEvaluator()
        metrics = evaluator.compute_metrics()
        assert metrics.total_tasks == 0
        assert metrics.task_success_rate == 0.0

    def test_compute_metrics_latency_percentiles(self):
        evaluator = AgentEvaluator()
        for i in range(20):
            evaluator.start_run(f"r{i}")
            evaluator.end_run(f"r{i}", success=True)

        metrics = evaluator.compute_metrics()
        assert metrics.p95_latency_ms >= 0
        assert metrics.p99_latency_ms >= 0
        assert metrics.avg_latency_ms <= metrics.p95_latency_ms if metrics.avg_latency_ms > 0 else True

    def test_compute_quality_grade(self):
        evaluator = AgentEvaluator(config_id="test")
        for i in range(10):
            evaluator.start_run(f"r{i}")
            evaluator.record_step(f"r{i}", tool="t", success=True)
            evaluator.end_run(f"r{i}", success=True, response_quality=0.95)

        report = evaluator.generate_report()
        assert "grade" in report.summary

    def test_compute_grade_f(self):
        evaluator = AgentEvaluator()
        evaluator.start_run("r1")
        evaluator.end_run("r1", success=False, response_quality=0.1)

        report = evaluator.generate_report()
        assert report.summary["grade"] in ["D", "F"]


# ---------------------------------------------------------------------------
# EvaluationReport Tests
# ---------------------------------------------------------------------------

class TestEvaluationReport:
    """评估报告测试。"""

    def test_generate_report(self):
        evaluator = AgentEvaluator(config_id="test_config")
        evaluator.start_run("r1", agent_id="agent1", task="task1")
        evaluator.end_run("r1", success=True, response_quality=0.9)

        report = evaluator.generate_report(notes="测试备注")
        assert isinstance(report, EvaluationReport)
        assert report.config_id == "test_config"
        assert report.notes == "测试备注"
        assert len(report.run_records) == 1
        assert report.metrics.total_tasks == 1

    def test_report_to_dict(self):
        evaluator = AgentEvaluator()
        evaluator.start_run("r1")
        evaluator.end_run("r1", success=True)

        report = evaluator.generate_report()
        d = report.to_dict()
        assert "config_id" in d
        assert "metrics" in d
        assert "run_records" in d
        assert "summary" in d

    def test_report_to_json(self):
        evaluator = AgentEvaluator()
        evaluator.start_run("r1")
        evaluator.end_run("r1", success=True)

        report = evaluator.generate_report()
        json_str = report.to_json()
        data = json.loads(json_str)
        assert isinstance(data, dict)

    def test_report_export_to_file(self, tmp_path):
        filepath = str(tmp_path / "report.json")
        evaluator = AgentEvaluator()
        evaluator.start_run("r1")
        evaluator.end_run("r1", success=True)

        report = evaluator.generate_report()
        report.export_to_file(filepath)

        assert os.path.exists(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["config_id"] == evaluator.config_id


# ---------------------------------------------------------------------------
# A/B Test Tests
# ---------------------------------------------------------------------------

class TestABTest:
    """A/B测试对比测试。"""

    def test_compare_configs(self):
        config_a = AgentEvaluator(config_id="A")
        config_b = AgentEvaluator(config_id="B")

        # Config A: 高成功率，低质量
        for i in range(5):
            config_a.start_run(f"a_{i}")
            config_a.end_run(f"a_{i}", success=True, response_quality=0.6)

        # Config B: 低成功率，高质量
        for i in range(5):
            config_b.start_run(f"b_{i}")
            config_b.end_run(f"b_{i}", success=(i < 3), response_quality=0.95)

        comparison = AgentEvaluator.compare(config_a, config_b)
        assert comparison["config_a"] == "A"
        assert comparison["config_b"] == "B"
        assert "comparisons" in comparison
        assert "overall_winner" in comparison

    def test_compare_with_clear_winner(self):
        config_a = AgentEvaluator(config_id="winner")
        config_b = AgentEvaluator(config_id="loser")

        for i in range(10):
            config_a.start_run(f"a_{i}")
            config_a.record_step(f"a_{i}", tool="t", success=True)
            config_a.end_run(f"a_{i}", success=True, response_quality=0.98)

        for i in range(10):
            config_b.start_run(f"b_{i}")
            config_b.record_step(f"b_{i}", tool="t", success=False, error="fail")
            config_b.end_run(f"b_{i}", success=False, response_quality=0.2)

        comparison = AgentEvaluator.compare(config_a, config_b)
        assert comparison["overall_winner"] == "A"
        assert comparison["a_wins"] > comparison["b_wins"]

    def test_compare_with_tie(self):
        config_a = AgentEvaluator(config_id="A")
        config_b = AgentEvaluator(config_id="B")

        for i in range(5):
            config_a.start_run(f"a_{i}")
            config_a.end_run(f"a_{i}", success=True, response_quality=0.8)

        for i in range(5):
            config_b.start_run(f"b_{i}")
            config_b.end_run(f"b_{i}", success=True, response_quality=0.8)

        comparison = AgentEvaluator.compare(config_a, config_b)
        assert comparison["overall_winner"] == "TIE"

    def test_export_all_to_json(self):
        evaluator = AgentEvaluator(config_id="export_test")
        evaluator.start_run("r1", agent_id="test_agent")
        evaluator.end_run("r1", success=True, response_quality=0.9)

        json_str = evaluator.export_to_json()
        data = json.loads(json_str)
        assert data["config_id"] == "export_test"
        assert len(data["records"]) == 1


# ---------------------------------------------------------------------------
# Utility Tests
# ---------------------------------------------------------------------------

class TestAgentEvaluatorUtility:
    """实用方法测试。"""

    def test_clear(self):
        evaluator = AgentEvaluator()
        evaluator.start_run("r1")
        evaluator.end_run("r1", success=True)
        assert len(evaluator.get_all_runs()) == 1

        evaluator.clear()
        assert len(evaluator.get_all_runs()) == 0

    def test_get_nonexistent_run(self):
        evaluator = AgentEvaluator()
        assert evaluator.get_run("nonexistent") is None

    def test_config_id(self):
        evaluator = AgentEvaluator(config_id="my_config")
        assert evaluator.config_id == "my_config"

    def test_cost_per_token(self):
        evaluator = AgentEvaluator(cost_per_1k_tokens=0.01)
        evaluator.start_run("r1")
        evaluator.record_step("r1", tokens_used=1000)
        evaluator.end_run("r1")

        record = evaluator.get_run("r1")
        assert record["cost_estimate"] == pytest.approx(0.01, abs=0.001)

    def test_metadata_in_start_run(self):
        evaluator = AgentEvaluator()
        evaluator.start_run("r1", metadata={"user": "u1", "env": "test"})
        evaluator.end_run("r1", success=True)

        record = evaluator.get_run("r1")
        assert record["metadata"]["user"] == "u1"
        assert record["metadata"]["env"] == "test"