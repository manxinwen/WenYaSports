"""Guardrails: Agent 输出安全与质量约束模块。

核心价值：
1. 输出格式校验：确保 Agent 输出符合预期 Schema
2. 内容安全检查：过滤有害内容、PII 泄露检测
3. 质量守门：低于标准的输出触发重试或降级
4. 可配置规则：支持按场景定制守卫规则

面试展示点：
- 体现了"Agent 不是裸奔的 LLM，而是受控的系统"的工程理念
- 展示了生产级 Agent 系统的安全意识
- 多层防御策略：格式→内容→质量→合规

Architecture:
    Agent Output → [Format Check] → [Content Filter] → [Quality Gate] → [Final Output]
                        ↓                ↓                ↓
                     Invalid?       Unsafe?          Below Threshold?
                        ↓                ↓                ↓
                    Retry/        Sanitize/         Retry with
                    Fallback      Flag Content       Better Prompt
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class GuardResult:
    """守卫检查结果。"""
    passed: bool
    check_type: str
    issues: List[str] = field(default_factory=list)
    sanitized_output: Optional[str] = None
    severity: str = "info"  # info, warning, error, critical
    check_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "check_type": self.check_type,
            "issues": self.issues,
            "sanitized_output": self.sanitized_output,
            "severity": self.severity,
            "check_time_ms": self.check_time_ms,
        }


# ---------------------------------------------------------------------------
# 预定义规则
# ---------------------------------------------------------------------------

# PII 检测模式
_PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("email", re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")),
    ("phone_cn", re.compile(r"1[3-9]\d{9}")),
    ("id_card", re.compile(r"\d{17}[\dXx]")),
    ("credit_card", re.compile(r"\d{16}")),
]

# 有害内容关键词（可配置）
_HARMFUL_KEYWORDS: List[str] = [
    "自杀", "自残", "暴力", "色情", "赌博", "毒品",
    "suicide", "kill", "violence", "pornography",
]

# 不允许的输出模式
_BLOCKED_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("sql_injection", re.compile(r"(\bDROP\b|\bDELETE\b|\bINSERT\b).*(\bTABLE\b|\bFROM\b|\bINTO\b)", re.IGNORECASE)),
    ("path_traversal", re.compile(r"(\.\.[\\/]){2,}")),
    ("code_injection", re.compile(r"<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)),
]


# ---------------------------------------------------------------------------
# Guard 检查器集合
# ---------------------------------------------------------------------------

class FormatGuard:
    """输出格式守卫。

    检查项：
    - JSON 格式合法性
    - 必填字段存在性
    - 输出长度约束
    """

    @staticmethod
    def check(
        output: str,
        expected_format: str = "text",
        required_fields: Optional[List[str]] = None,
        max_length: int = 10000,
        min_length: int = 1,
    ) -> GuardResult:
        """检查输出格式。

        Args:
            output: Agent 输出文本
            expected_format: 期望格式 ("json", "text", "markdown")
            required_fields: JSON 模式下的必填字段
            max_length: 最大长度
            min_length: 最小长度

        Returns:
            守卫结果
        """
        start = time.time()
        issues: List[str] = []
        passed = True

        # 长度检查
        output_len = len(output)
        if output_len < min_length:
            issues.append(f"输出过短: {output_len} < {min_length}")
            passed = False
        if output_len > max_length:
            issues.append(f"输出过长: {output_len} > {max_length}")
            passed = False

        # JSON 格式检查
        if expected_format == "json" and passed:
            try:
                data = json.loads(output)
                if required_fields:
                    missing = [f for f in required_fields if f not in data]
                    if missing:
                        issues.append(f"缺少必填字段: {missing}")
                        passed = False
            except json.JSONDecodeError as exc:
                issues.append(f"JSON 格式错误: {exc}")
                passed = False

        elapsed = (time.time() - start) * 1000
        return GuardResult(
            passed=passed,
            check_type="format",
            issues=issues,
            severity="error" if not passed else "info",
            check_time_ms=round(elapsed, 2),
        )


class ContentGuard:
    """内容安全守卫。

    检查项：
    - PII（个人身份信息）泄露
    - 有害内容关键词
    - 注入攻击模式
    """

    @staticmethod
    def check(
        output: str,
        detect_pii: bool = True,
        block_harmful: bool = True,
        block_injection: bool = True,
    ) -> GuardResult:
        """检查内容安全性。

        Args:
            output: Agent 输出文本
            detect_pii: 是否检测 PII
            block_harmful: 是否过滤有害内容
            block_injection: 是否拦截注入攻击

        Returns:
            守卫结果（含脱敏后的输出）
        """
        start = time.time()
        issues: List[str] = []
        sanitized = output
        passed = True

        # PII 检测与脱敏
        if detect_pii:
            for pii_type, pattern in _PII_PATTERNS:
                matches = pattern.findall(output)
                if matches:
                    issues.append(f"检测到 {len(matches)} 处 {pii_type} 类型 PII")
                    # 脱敏
                    sanitized = pattern.sub(f"[{pii_type.upper()}]", sanitized)
                    passed = False

        # 有害内容检查
        if block_harmful:
            lower_output = output.lower()
            found_keywords = [kw for kw in _HARMFUL_KEYWORDS if kw.lower() in lower_output]
            if found_keywords:
                issues.append(f"检测到有害内容关键词: {found_keywords}")
                passed = False

        # 注入攻击检查
        if block_injection:
            for pattern_name, pattern in _BLOCKED_PATTERNS:
                if pattern.search(output):
                    issues.append(f"检测到 {pattern_name} 攻击模式")
                    passed = False

        elapsed = (time.time() - start) * 1000
        return GuardResult(
            passed=passed,
            check_type="content",
            issues=issues,
            sanitized_output=sanitized if sanitized != output else None,
            severity="critical" if not passed else "info",
            check_time_ms=round(elapsed, 2),
        )


class QualityGuard:
    """输出质量守卫。

    检查项：
    - 最小信息量（非空泛内容）
    - 结构完整性
    - 语言连贯性
    """

    @staticmethod
    def check(
        output: str,
        min_info_density: float = 0.1,
        require_structure: bool = False,
    ) -> GuardResult:
        """检查输出质量。

        Args:
            output: Agent 输出文本
            min_info_density: 最小信息密度（独特词汇比例）
            require_structure: 是否要求结构化输出

        Returns:
            守卫结果
        """
        start = time.time()
        issues: List[str] = []
        passed = True

        # 信息密度检查
        words = re.findall(r"[\u4e00-\u9fff\w]+", output)
        if len(words) > 0:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < min_info_density:
                issues.append(f"信息密度过低: {unique_ratio:.1%} < {min_info_density:.1%}")
                passed = False

        # 结构检查
        if require_structure:
            has_headers = bool(re.search(r"^#{1,6}\s+", output, re.MULTILINE))
            has_lists = bool(re.search(r"^\s*[-*]\s+", output, re.MULTILINE))
            has_numbered = bool(re.search(r"^\s*\d+[.、)]\s+", output, re.MULTILINE))
            if not (has_headers or has_lists or has_numbered):
                issues.append("缺少结构化标记（标题/列表/编号）")
                passed = False

        # 重复内容检查
        sentences = re.split(r"[。.!?！？]", output)
        unique_sentences = set(s.strip() for s in sentences if s.strip())
        if len(sentences) > 2 and len(unique_sentences) < len(sentences) * 0.5:
            issues.append("内容重复率过高")
            passed = False

        elapsed = (time.time() - start) * 1000
        return GuardResult(
            passed=passed,
            check_type="quality",
            issues=issues,
            severity="warning" if not passed else "info",
            check_time_ms=round(elapsed, 2),
        )


# ---------------------------------------------------------------------------
# Guardrails 主实现
# ---------------------------------------------------------------------------

class Guardrails:
    """Agent 输出安全与质量守卫引擎。

    支持多层守卫链，按顺序检查：
    1. 格式守卫（格式合法性、长度约束）
    2. 内容守卫（PII 检测、有害内容过滤、注入拦截）
    3. 质量守卫（信息密度、结构完整性）

    Usage:
        guardrails = Guardrails()
        result = guardrails.guard(
            output=agent_response,
            context={"scene": "sports_analysis"},
        )
        if not result.passed:
            # 处理不合格输出
            pass
    """

    def __init__(
        self,
        enable_format_guard: bool = True,
        enable_content_guard: bool = True,
        enable_quality_guard: bool = True,
        custom_rules: Optional[List[Callable]] = None,
    ):
        self.enable_format_guard = enable_format_guard
        self.enable_content_guard = enable_content_guard
        self.enable_quality_guard = enable_quality_guard
        self.custom_rules = custom_rules or []
        self._check_count = 0
        self._blocked_count = 0
        self._total_check_time_ms = 0.0

    def guard(
        self,
        output: str,
        context: Optional[Dict[str, Any]] = None,
        expected_format: str = "text",
    ) -> GuardResult:
        """执行完整的守卫检查链。

        Args:
            output: 待检查的 Agent 输出
            context: 上下文信息（场景、用户等）
            expected_format: 期望的输出格式

        Returns:
            综合守卫结果
        """
        self._check_count += 1
        all_issues: List[str] = []
        sanitized = output
        all_passed = True
        total_start = time.time()

        # 1. 格式守卫
        if self.enable_format_guard:
            format_result = FormatGuard.check(output, expected_format=expected_format)
            if not format_result.passed:
                all_issues.extend(format_result.issues)
                all_passed = False

        # 2. 内容守卫
        if self.enable_content_guard:
            content_result = ContentGuard.check(output)
            if not content_result.passed:
                all_issues.extend(content_result.issues)
                all_passed = False
                if content_result.sanitized_output:
                    sanitized = content_result.sanitized_output

        # 3. 质量守卫
        if self.enable_quality_guard:
            quality_result = QualityGuard.check(output)
            if not quality_result.passed:
                all_issues.extend(quality_result.issues)
                all_passed = False

        # 4. 自定义规则
        for rule in self.custom_rules:
            try:
                custom_result = rule(output, context)
                if isinstance(custom_result, GuardResult) and not custom_result.passed:
                    all_issues.extend(custom_result.issues)
                    all_passed = False
            except Exception as exc:
                logger.warning("Custom guard rule failed: %s", exc)

        if not all_passed:
            self._blocked_count += 1

        total_elapsed = (time.time() - total_start) * 1000
        self._total_check_time_ms += total_elapsed

        return GuardResult(
            passed=all_passed,
            check_type="composite",
            issues=all_issues,
            sanitized_output=sanitized if sanitized != output else None,
            severity=self._determine_severity(all_issues, all_passed),
            check_time_ms=round(total_elapsed, 2),
        )

    def _determine_severity(self, issues: List[str], passed: bool) -> str:
        """根据问题类型判断严重程度。"""
        if passed:
            return "info"
        critical_keywords = ["PII", "注入", "injection", "SQL", "有害"]
        for issue in issues:
            if any(kw.lower() in issue.lower() for kw in critical_keywords):
                return "critical"
        return "warning"

    def get_stats(self) -> Dict[str, Any]:
        """获取守卫统计信息。"""
        return {
            "total_checks": self._check_count,
            "blocked_checks": self._blocked_count,
            "pass_rate": (
                (self._check_count - self._blocked_count) / self._check_count * 100
                if self._check_count > 0
                else 0
            ),
            "avg_check_time_ms": (
                self._total_check_time_ms / self._check_count
                if self._check_count > 0
                else 0
            ),
            "format_guard_enabled": self.enable_format_guard,
            "content_guard_enabled": self.enable_content_guard,
            "quality_guard_enabled": self.enable_quality_guard,
            "custom_rules_count": len(self.custom_rules),
        }

    def reset_stats(self) -> None:
        """重置统计。"""
        self._check_count = 0
        self._blocked_count = 0
        self._total_check_time_ms = 0.0
