"""Historical tracking for scan results."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ScanHistoryEntry:
    """A single entry in scan history."""

    timestamp: str
    model: str
    total_patterns: int
    scanned: int
    vulnerable: int
    refused: int
    partial: int
    errors: int
    risk_level: str
    duration_seconds: float
    file_path: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "model": self.model,
            "total_patterns": self.total_patterns,
            "scanned": self.scanned,
            "vulnerable": self.vulnerable,
            "refused": self.refused,
            "partial": self.partial,
            "errors": self.errors,
            "risk_level": self.risk_level,
            "duration_seconds": self.duration_seconds,
            "file_path": self.file_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScanHistoryEntry":
        """Create from dictionary."""
        return cls(
            timestamp=data.get("timestamp", ""),
            model=data.get("model", ""),
            total_patterns=data.get("total_patterns", 0),
            scanned=data.get("scanned", 0),
            vulnerable=data.get("vulnerable", 0),
            refused=data.get("refused", 0),
            partial=data.get("partial", 0),
            errors=data.get("errors", 0),
            risk_level=data.get("risk_level", "UNKNOWN"),
            duration_seconds=data.get("duration_seconds", 0),
            file_path=data.get("file_path"),
        )


class HistoryManager:
    """Manage scan history."""

    def __init__(self, history_dir: str | Path | None = None) -> None:
        if history_dir is None:
            history_dir = Path.home() / ".scanner" / "history"
        self.history_dir = Path(history_dir)
        self.history_file = self.history_dir / "history.json"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Create history directory if it doesn't exist."""
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> list[dict]:
        """Load history from file."""
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _save(self, entries: list[dict]) -> None:
        """Save history to file."""
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    def add_entry(self, entry: ScanHistoryEntry) -> None:
        """Add a scan entry to history."""
        entries = self._load()
        entries.append(entry.to_dict())
        self._save(entries)

    def get_entries(
        self,
        model: str | None = None,
        limit: int = 50,
    ) -> list[ScanHistoryEntry]:
        """Get scan history entries.

        Args:
            model: Filter by model name (partial match)
            limit: Max entries to return

        Returns:
            List of ScanHistoryEntry objects
        """
        entries = self._load()

        if model:
            entries = [
                e for e in entries
                if model.lower() in e.get("model", "").lower()
            ]

        # Return most recent first
        return [
            ScanHistoryEntry.from_dict(e)
            for e in reversed(entries[-limit:])
        ]

    def get_latest(self, model: str | None = None) -> ScanHistoryEntry | None:
        """Get the most recent scan entry."""
        entries = self.get_entries(model=model, limit=1)
        return entries[0] if entries else None

    def get_model_stats(self, model: str) -> dict:
        """Get statistics for a specific model.

        Returns:
            Dict with total_scans, avg_refused, avg_compromised, etc.
        """
        entries = [
            e for e in self._load()
            if model.lower() in e.get("model", "").lower()
        ]

        if not entries:
            return {"total_scans": 0}

        total = len(entries)
        avg_refused = sum(e.get("refused", 0) for e in entries) / total
        avg_compromised = sum(e.get("vulnerable", 0) for e in entries) / total
        avg_duration = sum(e.get("duration_seconds", 0) for e in entries) / total

        return {
            "total_scans": total,
            "avg_refused_pct": avg_refused,
            "avg_compromised_pct": avg_compromised,
            "avg_duration": avg_duration,
            "last_scan": entries[-1].get("timestamp", ""),
        }

    def clear(self) -> int:
        """Clear all history. Returns number of entries removed."""
        count = len(self._load())
        self._save([])
        return count
