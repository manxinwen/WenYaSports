"""Agent Behavior Evaluator: Agent行为评估框架。

核心能力：
1. Task Success Rate: 任务成功率
2. Step Efficiency: 每任务平均步骤数
3. Tool Usage Accuracy: 工具使用准确率
4. Response Quality Scoring: 响应质量评分
5. Latency Tracking: 延迟追踪
6. Cost Tracking: Token使用量估算

设计理念：
- 可观测性优先：每个关键指标都有明确的计算方法
- A/B测试：支持在不同Agent配置间进行对比
- JSON导出：评估结果可导出为JSON供外部分析

Architecture:
    Agent Run
        ↓
    ┌──────────────────┐
    │  AgentEvaluator   │
    │  - Metric Tracker │
    │  - Run Logger     │
    └──────────────────┘
        ↓
    ┌──────────────────┐
    │  EvaluationReport │ → JSON Export
    └──────────────────┘
        ↓
    A/B Comparison
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------

@dataclass
class RunRecord:
    """单次Agent运行记录。"""
    run_id: str
    timestamp: float = field(default_factory=time.time)
    agent_id: str = ""
    task: str = ""
    success: bool = False
    steps: int = 0
    tools_used: List[str] = field(default_factory=list)
    tool_errors: List[str] = field(default_factory=list)
    response_quality: float = 0.0
    latency_ms: float = 0.0
    tokens_used: int = 0
    cost_estimate: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationMetrics:
    """评估指标集。"""
    task_success_rate: float = 0.0
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    avg_steps_per_task: float = 0.0
    avg_latency_ms: float = 0.0
    avg_response_quality: float = 0.0
    tool_accuracy_rate: float = 0.0
    total_tokens: int = 0
    total_cost_estimate: float = 0.0
    avg_tokens_per_task: float = 0.0
    avg_cost_per_task: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0


@dataclass
class EvaluationReport:
    """评估报告。"""
    config_id: str
    created_at: float = field(default_factory=time.time)
    metrics: EvaluationMetrics = field(default_factory=EvaluationMetrics)
    run_records: List[Dict[str, Any]] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "config_id": self.config_id,
            "created_at": self.created_at,
            "metrics": asdict(self.metrics),
            "run_records": self.run_records,
            "summary": self.summary,
            "notes": self.notes,
        }

    def to_json(self, indent: int = 2) -> str:
        """序列化为JSON字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def export_to_file(self, filepath: str) -> None:
        """导出到JSON文件。"""
        import os
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json())


# ---------------------------------------------------------------------------
# Agent Evaluator (Agent行为评估器)
# ---------------------------------------------------------------------------

class AgentEvaluator:
    """Agent行为评估器。

    追踪Agent运行过程中的各项指标，生成评估报告，
    支持A/B测试对比不同配置的表现。

    Usage:
        evaluator = AgentEvaluator(config_id="baseline")
        evaluator.start_run("run_001", agent_id="coordinator", task="分析跑步数据")
        evaluator.record_step("run_001", tool="parser", success=True)
        evaluator.end_run("run_001", success=True, response_quality=0.9)
        report = evaluator.generate_report()
        print(report.to_json())
    """

    def __init__(self, config_id: str = "default",
                 cost_per_1k_tokens: float = 0.002):
        """初始化评估器。

        Args:
            config_id: 配置标识符（用于A/B对比）
            cost_per_1k_tokens: 每1k tokens的成本估算（美元）
        """
        self.config_id = config_id
        self._cost_per_1k_tokens = cost_per_1k_tokens
        self._records: Dict[str, RunRecord] = {}
        self._timers: Dict[str, float] = {}
        self._events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    # ------------------------------------------------------------------
    # 运行记录
    # ------------------------------------------------------------------
    def start_run(self, run_id: str, agent_id: str = "",
                   task: str = "", metadata: Optional[Dict[str, Any]] = None) -> None:
        """开始一次Agent运行。

        Args:
            run_id: 运行标识符
            agent_id: Agent标识符
            task: 任务描述
            metadata: 额外元数据
        """
        self._records[run_id] = RunRecord(
            run_id=run_id,
            agent_id=agent_id,
            task=task,
            metadata=metadata or {},
        )
        self._timers[run_id] = time.time()

    def record_step(self, run_id: str, tool: str = "",
                    success: bool = True, tokens_used: int = 0,
                    error: str = "") -> None:
        """记录一个执行步骤。

        Args:
            run_id: 运行标识符
            tool: 使用的工具名
            success: 是否成功
            tokens_used: 该步骤使用的tokens
            error: 错误信息（如有）
        """
        if run_id not in self._records:
            logger.warning("run_id '%s' not found, step not recorded", run_id)
            return

        record = self._records[run_id]
        record.steps += 1
        record.tokens_used += tokens_used

        if tool:
            record.tools_used.append(tool)
        if not success:
            record.tool_errors.append(error or tool)

        self._events[run_id].append({
            "step": record.steps,
            "tool": tool,
            "success": success,
            "tokens": tokens_used,
            "error": error,
        })

    def end_run(self, run_id: str, success: bool = True,
                 response_quality: float = 0.0,
                 tokens_used: int = 0,
                 metadata_update: Optional[Dict[str, Any]] = None) -> None:
        """结束一次Agent运行。

        Args:
            run_id: 运行标识符
            success: 任务是否成功
            response_quality: 响应质量评分（0.0-1.0）
            tokens_used: 运行总tokens（会与步骤中的累加）
            metadata_update: 更新元数据
        """
        if run_id not in self._records:
            logger.warning("run_id '%s' not found, end_run ignored", run_id)
            return

        record = self._records[run_id]
        record.success = success
        record.response_quality = response_quality

        # 计算延迟
        if run_id in self._timers:
            elapsed = (time.time() - self._timers.pop(run_id)) * 1000
            record.latency_ms = round(elapsed, 2)

        # 累加tokens
        if tokens_used > 0:
            record.tokens_used += tokens_used

        # 估算成本
        record.cost_estimate = round(
            (record.tokens_used / 1000.0) * self._cost_per_1k_tokens, 6
        )

        if metadata_update:
            record.metadata.update(metadata_update)

    # ------------------------------------------------------------------
    # 指标计算
    # ------------------------------------------------------------------
    def compute_metrics(self) -> EvaluationMetrics:
        """计算所有评估指标。

        Returns:
            EvaluationMetrics 对象
        """
        records = list(self._records.values())
        total = len(records)

        if total == 0:
            return EvaluationMetrics()

        successful = sum(1 for r in records if r.success)
        failed = total - successful

        # 成功率
        success_rate = successful / total if total > 0 else 0.0

        # 平均步骤数
        avg_steps = sum(r.steps for r in records) / total if total > 0 else 0.0

        # 平均延迟
        latencies = [r.latency_ms for r in records if r.latency_ms > 0]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0

        # P95/P99 延迟
        p95_latency = self._percentile(latencies, 95) if latencies else 0.0
        p99_latency = self._percentile(latencies, 99) if latencies else 0.0

        # 平均响应质量
        qualities = [r.response_quality for r in records if r.response_quality > 0]
        avg_quality = sum(qualities) / len(qualities) if qualities else 0.0

        # 工具使用准确率
        total_tools = sum(len(r.tools_used) for r in records)
        total_errors = sum(len(r.tool_errors) for r in records)
        tool_accuracy = (total_tools - total_errors) / total_tools if total_tools > 0 else 0.0

        # Token和成本
        total_tokens = sum(r.tokens_used for r in records)
        total_cost = sum(r.cost_estimate for r in records)
        avg_tokens = total_tokens / total if total > 0 else 0.0
        avg_cost = total_cost / total if total > 0 else 0.0

        return EvaluationMetrics(
            task_success_rate=round(success_rate, 6),
            total_tasks=total,
            successful_tasks=successful,
            failed_tasks=failed,
            avg_steps_per_task=round(avg_steps, 2),
            avg_latency_ms=round(avg_latency, 2),
            avg_response_quality=round(avg_quality, 6),
            tool_accuracy_rate=round(tool_accuracy, 6),
            total_tokens=total_tokens,
            total_cost_estimate=round(total_cost, 6),
            avg_tokens_per_task=round(avg_tokens, 2),
            avg_cost_per_task=round(avg_cost, 6),
            p95_latency_ms=round(p95_latency, 2),
            p99_latency_ms=round(p99_latency, 2),
        )

    def _percentile(self, values: List[float], pct: float) -> float:
        """计算百分位数。"""
        if not values:
            return 0.0
        sorted_vals = sorted(values)
        k = (pct / 100.0) * (len(sorted_vals) - 1)
        f = int(k)
        c = f + 1
        if c >= len(sorted_vals):
            return sorted_vals[f]
        d0 = sorted_vals[f] * (c - k)
        d1 = sorted_vals[c] * (k - f)
        return d0 + d1

    # ------------------------------------------------------------------
    # 报告生成
    # ------------------------------------------------------------------
    def generate_report(self, notes: str = "") -> EvaluationReport:
        """生成完整的评估报告。

        Args:
            notes: 备注说明

        Returns:
            EvaluationReport 对象
        """
        metrics = self.compute_metrics()
        run_dicts = [
            {
                "run_id": r.run_id,
                "agent_id": r.agent_id,
                "task": r.task,
                "success": r.success,
                "steps": r.steps,
                "tools_used": r.tools_used,
                "tool_errors": r.tool_errors,
                "response_quality": r.response_quality,
                "latency_ms": r.latency_ms,
                "tokens_used": r.tokens_used,
                "cost_estimate": r.cost_estimate,
                "timestamp": r.timestamp,
            }
            for r in self._records.values()
        ]

        summary = self._build_summary(metrics)

        return EvaluationReport(
            config_id=self.config_id,
            metrics=metrics,
            run_records=run_dicts,
            summary=summary,
            notes=notes,
        )

    def _build_summary(self, metrics: EvaluationMetrics) -> Dict[str, Any]:
        """构建报告摘要。"""
        highlights = []

        if metrics.task_success_rate >= 0.9:
            highlights.append("任务成功率优秀 (>=90%)")
        elif metrics.task_success_rate >= 0.7:
            highlights.append("任务成功率良好 (>=70%)")
        else:
            highlights.append("任务成功率需要改进 (<70%)")

        if metrics.avg_latency_ms > 0:
            if metrics.avg_latency_ms < 1000:
                highlights.append("响应速度快 (<1s)")
            elif metrics.avg_latency_ms < 5000:
                highlights.append("响应速度可接受 (<5s)")
            else:
                highlights.append("响应速度较慢 (>5s)")

        if metrics.tool_accuracy_rate >= 0.9:
            highlights.append("工具使用准确")

        return {
            "highlights": highlights,
            "grade": self._compute_grade(metrics),
            "config_id": self.config_id,
            "evaluation_timestamp": time.time(),
        }

    def _compute_grade(self, metrics: EvaluationMetrics) -> str:
        """计算总体评级。"""
        score = 0
        score += min(metrics.task_success_rate * 40, 40)
        score += min(metrics.tool_accuracy_rate * 25, 25)
        score += min(metrics.avg_response_quality * 20, 20)

        if metrics.avg_latency_ms > 0:
            speed_score = max(0, 15 - metrics.avg_latency_ms / 1000)
            score += speed_score

        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    # ------------------------------------------------------------------
    # A/B 测试
    # ------------------------------------------------------------------
    @staticmethod
    def compare(config_a: "AgentEvaluator", config_b: "AgentEvaluator") -> Dict[str, Any]:
        """对比两个配置的评估结果（A/B测试）。

        Args:
            config_a: 配置A的评估器
            config_b: 配置B的评估器

        Returns:
            对比结果字典
        """
        metrics_a = config_a.compute_metrics()
        metrics_b = config_b.compute_metrics()

        comparisons = []
        metric_names = [
            ("task_success_rate", "任务成功率", True),
            ("avg_steps_per_task", "平均步骤数", False),
            ("avg_latency_ms", "平均延迟", False),
            ("avg_response_quality", "响应质量", True),
            ("tool_accuracy_rate", "工具准确率", True),
            ("total_cost_estimate", "总成本", False),
        ]

        for field_name, display_name, higher_is_better in metric_names:
            val_a = getattr(metrics_a, field_name)
            val_b = getattr(metrics_b, field_name)

            if val_a == 0 and val_b == 0:
                continue

            if higher_is_better:
                if val_a > val_b:
                    winner = "A"
                    diff = val_a - val_b
                elif val_b > val_a:
                    winner = "B"
                    diff = val_b - val_a
                else:
                    winner = "TIE"
                    diff = 0.0
            else:
                if val_a < val_b:
                    winner = "A"
                    diff = val_b - val_a
                elif val_b < val_a:
                    winner = "B"
                    diff = val_a - val_b
                else:
                    winner = "TIE"
                    diff = 0.0

            comparisons.append({
                "metric": display_name,
                "field": field_name,
                "config_a": val_a,
                "config_b": val_b,
                "winner": winner,
                "difference": round(diff, 6),
                "higher_is_better": higher_is_better,
            })

        # 汇总判断
        a_wins = sum(1 for c in comparisons if c["winner"] == "A")
        b_wins = sum(1 for c in comparisons if c["winner"] == "B")

        if a_wins > b_wins:
            overall_winner = "A"
        elif b_wins > a_wins:
            overall_winner = "B"
        else:
            overall_winner = "TIE"

        return {
            "config_a": config_a.config_id,
            "config_b": config_b.config_id,
            "comparisons": comparisons,
            "overall_winner": overall_winner,
            "a_wins": a_wins,
            "b_wins": b_wins,
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # 实用方法
    # ------------------------------------------------------------------
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """获取单次运行的详细记录。"""
        record = self._records.get(run_id)
        if record is None:
            return None
        return {
            "run_id": record.run_id,
            "agent_id": record.agent_id,
            "task": record.task,
            "success": record.success,
            "steps": record.steps,
            "tools_used": record.tools_used,
            "tool_errors": record.tool_errors,
            "response_quality": record.response_quality,
            "latency_ms": record.latency_ms,
            "tokens_used": record.tokens_used,
            "cost_estimate": record.cost_estimate,
            "metadata": record.metadata,
            "events": self._events.get(run_id, []),
        }

    def get_all_runs(self) -> List[str]:
        """获取所有运行ID列表。"""
        return list(self._records.keys())

    def clear(self) -> None:
        """清空所有记录。"""
        self._records.clear()
        self._timers.clear()
        self._events.clear()

    def export_to_json(self) -> str:
        """导出所有记录为JSON字符串。"""
        data = {
            "config_id": self.config_id,
            "records": [
                {
                    "run_id": r.run_id,
                    "agent_id": r.agent_id,
                    "task": r.task,
                    "success": r.success,
                    "steps": r.steps,
                    "tools_used": r.tools_used,
                    "tool_errors": r.tool_errors,
                    "response_quality": r.response_quality,
                    "latency_ms": r.latency_ms,
                    "tokens_used": r.tokens_used,
                    "cost_estimate": r.cost_estimate,
                    "timestamp": r.timestamp,
                    "metadata": r.metadata,
                }
                for r in self._records.values()
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)