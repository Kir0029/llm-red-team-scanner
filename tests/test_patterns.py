"""Tests for pattern loader."""


from scanner.patterns import PatternLoader
from scanner.patterns.loader import Pattern


class TestPattern:
    """Tests for Pattern dataclass."""

    def test_pattern_creation(self) -> None:
        data = {
            "id": "test-001",
            "name": "Test Pattern",
            "category": "jailbreak",
            "type": "test",
            "severity": 7,
            "description": "A test pattern",
            "payload": "test payload",
            "tags": ["test"],
        }
        p = Pattern(data)
        assert p.id == "test-001"
        assert p.severity == 7
        assert p.category == "jailbreak"

    def test_pattern_to_dict(self) -> None:
        data = {
            "id": "test-002",
            "name": "Test",
            "category": "test",
            "type": "test",
            "severity": 5,
            "description": "desc",
            "payload": "pay",
        }
        p = Pattern(data)
        d = p.to_dict()
        assert d["id"] == "test-002"
        assert d["severity"] == 5
        assert isinstance(d, dict)


class TestPatternLoader:
    """Tests for PatternLoader."""

    def test_load_all_returns_15_patterns(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_all()
        assert len(patterns) == 15

    def test_load_all_returns_pattern_objects(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_all()
        assert all(isinstance(p, Pattern) for p in patterns)

    def test_load_category_prompt_injection(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_category("prompt_injection")
        assert len(patterns) == 5
        assert all(p.category == "prompt_injection" for p in patterns)

    def test_load_category_jailbreak(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_category("jailbreak")
        assert len(patterns) == 5
        assert all(p.category == "jailbreak" for p in patterns)

    def test_load_category_data_leakage(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_category("data_leakage")
        assert len(patterns) == 3
        assert all(p.category == "data_leakage" for p in patterns)

    def test_load_category_tool_abuse(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_category("tool_abuse")
        assert len(patterns) == 2
        assert all(p.category == "tool_abuse" for p in patterns)

    def test_load_category_nonexistent(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_category("nonexistent")
        assert patterns == []

    def test_load_all_unique_ids(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_all()
        ids = [p.id for p in patterns]
        assert len(ids) == len(set(ids))

    def test_load_all_severities_in_range(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_all()
        assert all(1 <= p.severity <= 10 for p in patterns)

    def test_load_all_have_payload(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_all()
        assert all(p.payload for p in patterns)

    def test_load_all_have_description(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_all()
        assert all(p.description for p in patterns)
