"""Tests for pattern loader."""

import json
import tempfile
from pathlib import Path

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

    def test_load_all_returns_62_patterns(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_all()
        assert len(patterns) == 62

    def test_load_all_returns_pattern_objects(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_all()
        assert all(isinstance(p, Pattern) for p in patterns)

    def test_load_category_prompt_injection(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_category("prompt_injection")
        assert len(patterns) == 11
        assert all(p.category == "prompt_injection" for p in patterns)

    def test_load_category_jailbreak(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_category("jailbreak")
        assert len(patterns) == 13
        assert all(p.category == "jailbreak" for p in patterns)

    def test_load_category_data_leakage(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_category("data_leakage")
        assert len(patterns) == 9
        assert all(p.category == "data_leakage" for p in patterns)

    def test_load_category_tool_abuse(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_category("tool_abuse")
        assert len(patterns) == 2
        assert all(p.category == "tool_abuse" for p in patterns)

    def test_load_category_encoding(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_category("encoding")
        assert len(patterns) == 16
        assert all(p.category == "encoding" for p in patterns)

    def test_load_category_multilingual(self) -> None:
        loader = PatternLoader()
        patterns = loader.load_category("multilingual")
        assert len(patterns) == 10
        assert all(p.category == "multilingual" for p in patterns)

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

    def test_load_custom_file(self) -> None:
        """Test loading custom pattern from file."""
        custom_pattern = {
            "patterns": [
                {
                    "id": "custom_test_001",
                    "name": "Custom Test Pattern",
                    "category": "jailbreak",
                    "type": "single_turn",
                    "severity": 5,
                    "description": "A custom test pattern",
                    "payload": "custom test payload",
                    "tags": ["custom", "test"],
                }
            ]
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(custom_pattern, f)
            temp_path = f.name

        try:
            loader = PatternLoader()
            patterns = loader.load_custom(temp_path)
            assert len(patterns) == 1
            assert patterns[0].id == "custom_test_001"
        finally:
            Path(temp_path).unlink()

    def test_load_custom_directory(self) -> None:
        """Test loading custom patterns from directory."""
        custom_dir = tempfile.mkdtemp()
        custom_pattern = {
            "patterns": [
                {
                    "id": "custom_dir_001",
                    "name": "Custom Dir Pattern",
                    "category": "encoding",
                    "type": "single_turn",
                    "severity": 6,
                    "description": "A custom directory pattern",
                    "payload": "custom dir payload",
                    "tags": ["custom", "dir"],
                }
            ]
        }

        pattern_file = Path(custom_dir) / "test_pattern.json"
        pattern_file.write_text(json.dumps(custom_pattern))

        try:
            loader = PatternLoader()
            patterns = loader.load_custom(custom_dir)
            assert len(patterns) == 1
            assert patterns[0].id == "custom_dir_001"
        finally:
            pattern_file.unlink()
            Path(custom_dir).rmdir()

    def test_load_custom_nonexistent(self) -> None:
        """Test loading custom pattern from nonexistent path."""
        loader = PatternLoader()
        try:
            loader.load_custom("/nonexistent/path")
            assert False, "Should have raised PatternError"
        except Exception as e:
            assert "not found" in str(e).lower()

    def test_validate_pattern_valid(self) -> None:
        """Test pattern validation with valid pattern."""
        valid_pattern = {
            "id": "valid_001",
            "name": "Valid Pattern",
            "category": "jailbreak",
            "payload": "test payload",
            "severity": 5,
        }
        is_valid, error = PatternLoader.validate_pattern(valid_pattern)
        assert is_valid
        assert error == ""

    def test_validate_pattern_missing_fields(self) -> None:
        """Test pattern validation with missing fields."""
        invalid_pattern = {
            "name": "Missing ID",
            "category": "jailbreak",
        }
        is_valid, error = PatternLoader.validate_pattern(invalid_pattern)
        assert not is_valid
        assert "id" in error.lower()

    def test_validate_pattern_invalid_category(self) -> None:
        """Test pattern validation with invalid category."""
        invalid_pattern = {
            "id": "invalid_cat",
            "name": "Invalid Category",
            "category": "invalid_category",
            "payload": "test",
        }
        is_valid, error = PatternLoader.validate_pattern(invalid_pattern)
        assert not is_valid
        assert "category" in error.lower()

    def test_validate_pattern_invalid_severity(self) -> None:
        """Test pattern validation with invalid severity."""
        invalid_pattern = {
            "id": "invalid_sev",
            "name": "Invalid Severity",
            "category": "jailbreak",
            "payload": "test",
            "severity": 15,
        }
        is_valid, error = PatternLoader.validate_pattern(invalid_pattern)
        assert not is_valid
        assert "severity" in error.lower()

    def test_load_with_custom_dirs(self) -> None:
        """Test PatternLoader with custom directories."""
        custom_dir = tempfile.mkdtemp()
        custom_pattern = {
            "patterns": [
                {
                    "id": "custom_init_001",
                    "name": "Custom Init Pattern",
                    "category": "multilingual",
                    "type": "single_turn",
                    "severity": 4,
                    "description": "Custom init pattern",
                    "payload": "custom init payload",
                    "tags": ["custom"],
                }
            ]
        }

        pattern_file = Path(custom_dir) / "custom.json"
        pattern_file.write_text(json.dumps(custom_pattern))

        try:
            loader = PatternLoader(custom_dirs=[custom_dir])
            patterns = loader.load_all()
            # Should include both built-in and custom patterns
            custom_patterns = [p for p in patterns if p.id == "custom_init_001"]
            assert len(custom_patterns) == 1
        finally:
            pattern_file.unlink()
            Path(custom_dir).rmdir()
