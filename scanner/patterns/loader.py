"""Pattern loading logic for LLM Red Team Scanner."""

import json
from pathlib import Path

from scanner.core.exceptions import PatternError


class Pattern:
    """Attack pattern data class."""

    def __init__(self, data: dict[str, object]) -> None:
        self.id: str = str(data.get("id", "unknown"))
        self.name: str = str(data.get("name", "Unknown"))
        self.category: str = str(data.get("category", "unknown"))
        self.type: str = str(data.get("type", "single_turn"))
        self.severity: int = int(data.get("severity", 5))
        self.description: str = str(data.get("description", ""))
        self.payload: str = str(data.get("payload", ""))
        self.expected_behavior: str = str(data.get("expected_behavior", ""))
        self.success_indicators: list[str] = list(data.get("success_indicators", []))
        self.references: list[str] = list(data.get("references", []))
        self.owasp_reference: str = str(data.get("owasp_reference", ""))
        self.tags: list[str] = list(data.get("tags", []))
        self._raw = data

        # Multi-turn fields
        self.turns: list[dict[str, str]] = list(data.get("turns", []))
        self.max_turns: int = int(data.get("max_turns", 1))
        self.max_backtracks: int = int(data.get("max_backtracks", 0))

    def to_dict(self) -> dict[str, object]:
        """Convert pattern to dictionary."""
        return self._raw

    def __repr__(self) -> str:
        return f"Pattern(id={self.id!r}, category={self.category!r})"


class PatternLoader:
    """Load attack patterns from JSON files.

    Supports:
    - Single JSON file with one pattern
    - JSON file with "patterns" array
    - Directory scanning (recursive)
    """

    def __init__(self, data_dir: str | Path | None = None) -> None:
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        self.data_dir = Path(data_dir)

    def load_all(self) -> list[Pattern]:
        """Load all patterns from data directory.

        Returns:
            List of Pattern objects

        Raises:
            PatternError: If any pattern file is invalid
        """
        patterns: list[Pattern] = []
        for json_file in sorted(self.data_dir.rglob("*.json")):
            patterns.extend(self.load_file(json_file))
        return patterns

    def load_category(self, category: str) -> list[Pattern]:
        """Load patterns for a specific category.

        Args:
            category: Category name (e.g., 'jailbreak', 'prompt_injection')

        Returns:
            List of Pattern objects for that category
        """
        category_dir = self.data_dir / category
        if not category_dir.exists():
            return []

        patterns: list[Pattern] = []
        for json_file in sorted(category_dir.glob("*.json")):
            patterns.extend(self.load_file(json_file))
        return patterns

    def load_file(self, file_path: str | Path) -> list[Pattern]:
        """Load patterns from a JSON file.

        Args:
            file_path: Path to JSON file

        Returns:
            List of Pattern objects

        Raises:
            PatternError: If file is invalid or contains invalid patterns
        """
        path = Path(file_path)

        if not path.exists():
            raise PatternError(f"Pattern file not found: {path}")

        if not path.suffix.lower() == ".json":
            raise PatternError(f"Not a JSON file: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise PatternError(f"Invalid JSON in {path}: {e}") from e

        # Handle both single pattern and array formats
        if isinstance(data, dict):
            pattern_list = data.get("patterns", [data])
        elif isinstance(data, list):
            pattern_list = data
        else:
            raise PatternError(f"Invalid pattern format in {path}")

        patterns: list[Pattern] = []
        for i, p in enumerate(pattern_list):
            try:
                pattern = Pattern(p)
                patterns.append(pattern)
            except Exception as e:
                raise PatternError(f"Invalid pattern #{i + 1} in {path}: {e}") from e

        return patterns

    def load_patterns(self, pattern_ids: list[str]) -> list[Pattern]:
        """Load specific patterns by ID.

        Args:
            pattern_ids: List of pattern IDs to load

        Returns:
            List of matching Pattern objects
        """
        all_patterns = self.load_all()
        return [p for p in all_patterns if p.id in pattern_ids]
