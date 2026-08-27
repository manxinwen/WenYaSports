"""Guardrails 单元测试。

验证输出安全守卫的核心能力：
1. 格式检查：JSON 合法性、长度约束
2. 内容安全：PII 检测/脱敏、有害内容过滤、注入拦截
3. 质量守卫：信息密度、结构检查
4. 综合守卫链：多层级联检查
"""

import json

import pytest

from app.agents.guardrails import (
    GuardResult,
    Guardrails,
    FormatGuard,
    ContentGuard,
    QualityGuard,
)


# ---------------------------------------------------------------------------
# FormatGuard 测试
# ---------------------------------------------------------------------------

class TestFormatGuard:
    """格式守卫测试。"""

    def test_valid_json_output(self):
        """合法 JSON 输出。"""
        output = json.dumps({"status": "ok", "data": [1, 2, 3]})
        result = FormatGuard.check(output, expected_format="json")
        assert result.passed is True

    def test_invalid_json_output(self):
        """非法 JSON 输出。"""
        result = FormatGuard.check("not json {", expected_format="json")
        assert result.passed is False
        assert any("JSON" in issue for issue in result.issues)

    def test_json_missing_fields(self):
        """缺少必填字段。"""
        output = json.dumps({"status": "ok"})
        result = FormatGuard.check(
            output, expected_format="json", required_fields=["status", "data", "error"]
        )
        assert result.passed is False

    def test_text_output_length_ok(self):
        """文本长度合规。"""
        result = FormatGuard.check("Hello world", expected_format="text")
        assert result.passed is True

    def test_output_too_short(self):
        """输出过短。"""
        result = FormatGuard.check("", expected_format="text", min_length=1)
        assert result.passed is False

    def test_output_too_long(self):
        """输出过长。"""
        result = FormatGuard.check("x" * 100001, max_length=100000)
        assert result.passed is False


# ---------------------------------------------------------------------------
# ContentGuard 测试
# ---------------------------------------------------------------------------

class TestContentGuard:
    """内容安全守卫测试。"""

    def test_clean_content_passes(self):
        """清洁内容通过。"""
        result = ContentGuard.check("这是一段关于跑步训练的专业建议。")
        assert result.passed is True

    def test_email_pii_detected(self):
        """检测邮箱 PII。"""
        output = "请联系测试用户 test@example.com 获取详细信息。"
        result = ContentGuard.check(output)
        assert result.passed is False
        assert result.sanitized_output is not None
        assert "EMAIL" in result.sanitized_output

    def test_phone_pii_detected(self):
        """检测手机号 PII。"""
        output = "我的电话是 13812345678，欢迎来电。"
        result = ContentGuard.check(output)
        assert result.passed is False

    def test_harmful_keyword_detected(self):
        """检测有害关键词。"""
        output = "这个方法可以用来制作自杀相关的内容"
        result = ContentGuard.check(output)
        assert result.passed is False

    def test_sql_injection_detected(self):
        """检测 SQL 注入模式。"""
        output = "请执行 DROP TABLE users 来清理数据"
        result = ContentGuard.check(output)
        assert result.passed is False

    def test_script_injection_detected(self):
        """检测脚本注入。"""
        output = '<script>alert("xss")</script> 这是回复内容'
        result = ContentGuard.check(output)
        assert result.passed is False

    def test_pii_disabled(self):
        """禁用 PII 检测。"""
        output = "联系我们 test@example.com"
        result = ContentGuard.check(output, detect_pii=False)
        assert result.passed is True

    def test_content_only_mode(self):
        """仅检查内容（不检查注入）。"""
        output = "可以执行 DROP TABLE 的内容"
        result = ContentGuard.check(output, block_injection=False)
        assert result.passed is True


# ---------------------------------------------------------------------------
# QualityGuard 测试
# ---------------------------------------------------------------------------

class TestQualityGuard:
    """质量守卫测试。"""

    def test_high_quality_passes(self):
        """高质量输出通过。"""
        output = (
            "你的配速从5分40秒提升到5分20秒，心率区间保持在Zone 2。"
            "建议继续保持当前训练量，每周增加1次间歇训练。"
        )
        result = QualityGuard.check(output)
        assert result.passed is True

    def test_low_density_detected(self):
        """低信息密度检测。"""
        output = "好 好 好 是 是 是 对 对 对 嗯 嗯 嗯"
        result = QualityGuard.check(output, min_info_density=0.5)
        assert result.passed is False

    def test_structure_required(self):
        """结构要求检测。"""
        structured = "# 训练建议\n\n1. 增加间歇训练\n2. 保持有氧训练"
        unstructured = "建议增加间歇训练和保持有氧训练。"

        result_structured = QualityGuard.check(structured, require_structure=True)
        result_unstructured = QualityGuard.check(unstructured, require_structure=True)

        assert result_structured.passed is True
        assert result_unstructured.passed is False


# ---------------------------------------------------------------------------
# Guardrails 综合测试
# ---------------------------------------------------------------------------

class TestGuardrails:
    """综合守卫引擎测试。"""

    def test_clean_output_passes_all(self):
        """清洁输出通过全部守卫。"""
        guardrails = Guardrails()
        output = (
            "根据你的跑步数据分析，配速5:20/km，心率150bpm，"
            "处于良好的有氧训练区间。建议每周进行3次跑步训练，"
            "其中包括1次间歇训练和2次有氧跑。"
        )
        result = guardrails.guard(output)
        assert result.passed is True
        assert result.severity == "info"

    def test_pii_output_blocked(self):
        """含 PII 的输出被拦截。"""
        guardrails = Guardrails()
        output = "用户邮箱 test@example.com，手机号13812345678"
        result = guardrails.guard(output)
        assert result.passed is False
        assert result.sanitized_output is not None

    def test_custom_rule_integration(self):
        """自定义规则集成。"""
        def custom_rule(output, context):
            if "禁止词" in output:
                return GuardResult(
                    passed=False,
                    check_type="custom",
                    issues=["检测到禁止词"],
                    severity="critical",
                )
            return GuardResult(passed=True, check_type="custom")

        guardrails = Guardrails(custom_rules=[custom_rule])
        result = guardrails.guard("这是包含禁止词的输出")
        assert result.passed is False

    def test_stats_tracking(self):
        """统计追踪。"""
        guardrails = Guardrails()

        for i in range(10):
            output = f"测试输出 {i}，配速5:30，心率150bpm"
            guardrails.guard(output)

        stats = guardrails.get_stats()
        assert stats["total_checks"] == 10
        assert stats["avg_check_time_ms"] >= 0

    def test_stats_reset(self):
        """统计重置。"""
        guardrails = Guardrails()
        guardrails.guard("测试")
        guardrails.reset_stats()

        stats = guardrails.get_stats()
        assert stats["total_checks"] == 0

    def test_format_only_mode(self):
        """仅格式检查模式。"""
        guardrails = Guardrails(
            enable_content_guard=False,
            enable_quality_guard=False,
        )
        output = json.dumps({"status": "ok"})
        result = guardrails.guard(output, expected_format="json")
        assert result.passed is True

    def test_severity_determination(self):
        """严重程度判断。"""
        guardrails = Guardrails()

        # PII -> critical
        pii_result = guardrails.guard("联系 test@example.com")
        assert pii_result.severity == "critical"

        # 低质量 -> warning
        quality_result = guardrails.guard("嗯嗯好的")
        assert quality_result.severity in ("warning", "info")
