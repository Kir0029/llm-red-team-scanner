"""Tests for scoring calculator."""

from scanner.scoring.calculator import (
    RiskScore,
    calculate_risk_score,
    get_risk_color,
    get_risk_emoji,
)


class TestCalculateRiskScore:
    """Tests for calculate_risk_score function."""

    def test_returns_risk_score(self) -> None:
        result = calculate_risk_score(severity=5, classification="PARTIAL", category="test")
        assert isinstance(result, RiskScore)

    def test_refused_gives_low_score(self) -> None:
        result = calculate_risk_score(severity=9, classification="REFUSED", category="jailbreak")
        # REFUSED gives success=0.0, but impact_bias adds 0.4 for jailbreak
        assert result.score <= 1.0
        assert result.level == "LOW"

    def test_compromised_high_severity(self) -> None:
        result = calculate_risk_score(severity=9, classification="COMPROMISED", category="jailbreak")
        assert result.score >= 9.0

    def test_compromised_medium_severity(self) -> None:
        result = calculate_risk_score(severity=5, classification="COMPROMISED", category="prompt_injection")
        assert 5.0 <= result.score <= 6.0

    def test_partial_gives_medium_score(self) -> None:
        result = calculate_risk_score(severity=5, classification="PARTIAL", category="prompt_injection")
        assert 2.0 <= result.score <= 3.5

    def test_score_never_exceeds_10(self) -> None:
        result = calculate_risk_score(severity=10, classification="COMPROMISED", category="data_leakage")
        assert result.score <= 10.0

    def test_score_never_below_0(self) -> None:
        result = calculate_risk_score(severity=1, classification="REFUSED", category="tool_abuse")
        assert result.score >= 0.0

    def test_data_leakage_higher_impact(self) -> None:
        injection = calculate_risk_score(7, "COMPROMISED", "prompt_injection")
        leakage = calculate_risk_score(7, "COMPROMISED", "data_leakage")
        assert leakage.score > injection.score

    def test_jailbreak_higher_than_injection(self) -> None:
        injection = calculate_risk_score(7, "COMPROMISED", "prompt_injection")
        jailbreak = calculate_risk_score(7, "COMPROMISED", "jailbreak")
        assert jailbreak.score > injection.score

    def test_level_critical(self) -> None:
        result = calculate_risk_score(severity=10, classification="COMPROMISED", category="jailbreak")
        assert result.level == "CRITICAL"

    def test_level_high(self) -> None:
        result = calculate_risk_score(severity=8, classification="COMPROMISED", category="prompt_injection")
        assert result.level == "HIGH"

    def test_level_medium(self) -> None:
        # Need severity=5, COMPROMISED, prompt_injection to get MEDIUM
        result = calculate_risk_score(severity=5, classification="COMPROMISED", category="prompt_injection")
        assert result.level == "MEDIUM"

    def test_level_low(self) -> None:
        result = calculate_risk_score(severity=1, classification="REFUSED", category="test")
        assert result.level == "LOW"

    def test_success_indicator(self) -> None:
        compromised = calculate_risk_score(5, "COMPROMISED", "test")
        partial = calculate_risk_score(5, "PARTIAL", "test")
        refused = calculate_risk_score(5, "REFUSED", "test")
        assert compromised.success_indicator == 1.0
        assert partial.success_indicator == 0.5
        assert refused.success_indicator == 0.0


class TestGetRiskColor:
    """Tests for get_risk_color function."""

    def test_critical_color(self) -> None:
        assert get_risk_color("CRITICAL") == "bold red"

    def test_high_color(self) -> None:
        assert get_risk_color("HIGH") == "red"

    def test_medium_color(self) -> None:
        assert get_risk_color("MEDIUM") == "yellow"

    def test_low_color(self) -> None:
        assert get_risk_color("LOW") == "green"

    def test_unknown_color(self) -> None:
        assert get_risk_color("UNKNOWN") == "white"


class TestGetRiskEmoji:
    """Tests for get_risk_emoji function."""

    def test_critical_emoji(self) -> None:
        assert get_risk_emoji("CRITICAL") == "🔴"

    def test_high_emoji(self) -> None:
        assert get_risk_emoji("HIGH") == "🟠"

    def test_medium_emoji(self) -> None:
        assert get_risk_emoji("MEDIUM") == "🟡"

    def test_low_emoji(self) -> None:
        assert get_risk_emoji("LOW") == "🟢"

    def test_unknown_emoji(self) -> None:
        assert get_risk_emoji("UNKNOWN") == "⚪"
