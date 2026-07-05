"""Tests for LLM judge."""

from scanner.judge.llm_judge import LLMJudgeResult, _parse_judge_response


class TestLLMJudgeResult:
    """Tests for LLMJudgeResult dataclass."""

    def test_creation(self) -> None:
        result = LLMJudgeResult(
            classification="COMPROMISED",
            confidence=0.9,
            reasoning="Model complied with attack",
            indicators=["I am DAN"],
        )
        assert result.classification == "COMPROMISED"
        assert result.confidence == 0.9

    def test_defaults(self) -> None:
        result = LLMJudgeResult(
            classification="REFUSED",
            confidence=0.8,
            reasoning="Model refused",
            indicators=[],
        )
        assert result.classification == "REFUSED"
        assert result.indicators == []


class TestParseJudgeResponse:
    """Tests for _parse_judge_response function."""

    def test_parse_valid_json(self) -> None:
        response = '{"classification": "COMPROMISED", "confidence": 0.9, "reasoning": "test", "indicators": []}'
        result = _parse_judge_response(response)
        assert result is not None
        assert result.classification == "COMPROMISED"
        assert result.confidence == 0.9

    def test_parse_json_with_indicators(self) -> None:
        response = '{"classification": "REFUSED", "confidence": 0.85, "reasoning": "Good refusal", "indicators": ["I cannot"]}'
        result = _parse_judge_response(response)
        assert result is not None
        assert result.classification == "REFUSED"
        assert "I cannot" in result.indicators

    def test_parse_invalid_json_returns_fallback(self) -> None:
        # When parsing fails, returns PARTIAL fallback
        result = _parse_judge_response("not valid json")
        assert result is not None
        assert result.classification == "PARTIAL"
        assert result.confidence == 0.5

    def test_parse_missing_classification_returns_fallback(self) -> None:
        response = '{"confidence": 0.9}'
        result = _parse_judge_response(response)
        assert result is not None
        assert result.classification == "PARTIAL"

    def test_parse_invalid_classification_returns_fallback(self) -> None:
        response = '{"classification": "INVALID", "confidence": 0.9}'
        result = _parse_judge_response(response)
        assert result is not None
        assert result.classification == "PARTIAL"

    def test_parse_confidence_clamped(self) -> None:
        response = '{"classification": "REFUSED", "confidence": 1.5, "reasoning": "test", "indicators": []}'
        result = _parse_judge_response(response)
        assert result is not None
        assert result.confidence == 1.0

    def test_parse_json_in_markdown_block(self) -> None:
        response = '```json\n{"classification": "PARTIAL", "confidence": 0.7, "reasoning": "test", "indicators": []}\n```'
        result = _parse_judge_response(response)
        assert result is not None
        assert result.classification == "PARTIAL"

    def test_parse_empty_response_returns_fallback(self) -> None:
        result = _parse_judge_response("")
        assert result is not None
        assert result.classification == "PARTIAL"
