"""Tests for history module."""

import tempfile
from pathlib import Path

from scanner.core.history import HistoryManager, ScanHistoryEntry


class TestScanHistoryEntry:
    """Tests for ScanHistoryEntry."""

    def test_creation(self) -> None:
        entry = ScanHistoryEntry(
            timestamp="2024-01-01T00:00:00",
            model="test-model",
            total_patterns=10,
            scanned=10,
            vulnerable=2,
            refused=5,
            partial=3,
            errors=0,
            risk_level="MEDIUM",
            duration_seconds=45.5,
        )
        assert entry.model == "test-model"
        assert entry.vulnerable == 2
        assert entry.risk_level == "MEDIUM"

    def test_to_dict(self) -> None:
        entry = ScanHistoryEntry(
            timestamp="2024-01-01T00:00:00",
            model="test-model",
            total_patterns=10,
            scanned=10,
            vulnerable=2,
            refused=5,
            partial=3,
            errors=0,
            risk_level="MEDIUM",
            duration_seconds=45.5,
        )
        d = entry.to_dict()
        assert d["model"] == "test-model"
        assert d["vulnerable"] == 2

    def test_from_dict(self) -> None:
        data = {
            "timestamp": "2024-01-01T00:00:00",
            "model": "test-model",
            "total_patterns": 10,
            "scanned": 10,
            "vulnerable": 2,
            "refused": 5,
            "partial": 3,
            "errors": 0,
            "risk_level": "MEDIUM",
            "duration_seconds": 45.5,
        }
        entry = ScanHistoryEntry.from_dict(data)
        assert entry.model == "test-model"
        assert entry.vulnerable == 2


class TestHistoryManager:
    """Tests for HistoryManager."""

    def test_add_and_get_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HistoryManager(tmpdir)
            entry = ScanHistoryEntry(
                timestamp="2024-01-01T00:00:00",
                model="test-model",
                total_patterns=10,
                scanned=10,
                vulnerable=2,
                refused=5,
                partial=3,
                errors=0,
                risk_level="MEDIUM",
                duration_seconds=45.5,
            )
            manager.add_entry(entry)

            entries = manager.get_entries()
            assert len(entries) == 1
            assert entries[0].model == "test-model"

    def test_get_entries_with_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HistoryManager(tmpdir)

            for i in range(5):
                entry = ScanHistoryEntry(
                    timestamp=f"2024-01-0{i+1}T00:00:00",
                    model=f"model-{i % 2}",
                    total_patterns=10,
                    scanned=10,
                    vulnerable=0,
                    refused=10,
                    partial=0,
                    errors=0,
                    risk_level="LOW",
                    duration_seconds=30.0,
                )
                manager.add_entry(entry)

            # Filter by model
            entries = manager.get_entries(model="model-0")
            assert len(entries) == 3

            entries = manager.get_entries(model="model-1")
            assert len(entries) == 2

    def test_get_latest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HistoryManager(tmpdir)

            for i in range(3):
                entry = ScanHistoryEntry(
                    timestamp=f"2024-01-0{i+1}T00:00:00",
                    model="test-model",
                    total_patterns=10,
                    scanned=10,
                    vulnerable=0,
                    refused=10,
                    partial=0,
                    errors=0,
                    risk_level="LOW",
                    duration_seconds=30.0,
                )
                manager.add_entry(entry)

            latest = manager.get_latest()
            assert latest is not None
            assert latest.timestamp == "2024-01-03T00:00:00"

    def test_get_model_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HistoryManager(tmpdir)

            for i in range(3):
                entry = ScanHistoryEntry(
                    timestamp=f"2024-01-0{i+1}T00:00:00",
                    model="test-model",
                    total_patterns=10,
                    scanned=10,
                    vulnerable=i,
                    refused=10 - i,
                    partial=0,
                    errors=0,
                    risk_level="LOW",
                    duration_seconds=30.0 + i * 10,
                )
                manager.add_entry(entry)

            stats = manager.get_model_stats("test-model")
            assert stats["total_scans"] == 3
            # refused values: 10, 9, 8 -> avg = 9.0
            assert stats["avg_refused_pct"] == 9.0
            # vulnerable values: 0, 1, 2 -> avg = 1.0
            assert stats["avg_compromised_pct"] == 1.0
            # duration: 30, 40, 50 -> avg = 40.0
            assert stats["avg_duration"] == 40.0

    def test_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HistoryManager(tmpdir)

            for i in range(3):
                entry = ScanHistoryEntry(
                    timestamp=f"2024-01-0{i+1}T00:00:00",
                    model="test-model",
                    total_patterns=10,
                    scanned=10,
                    vulnerable=0,
                    refused=10,
                    partial=0,
                    errors=0,
                    risk_level="LOW",
                    duration_seconds=30.0,
                )
                manager.add_entry(entry)

            count = manager.clear()
            assert count == 3

            entries = manager.get_entries()
            assert len(entries) == 0

    def test_empty_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HistoryManager(tmpdir)

            entries = manager.get_entries()
            assert len(entries) == 0

            latest = manager.get_latest()
            assert latest is None

            stats = manager.get_model_stats("nonexistent")
            assert stats["total_scans"] == 0

    def test_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = HistoryManager(tmpdir)

            for i in range(10):
                entry = ScanHistoryEntry(
                    timestamp=f"2024-01-0{i+1:02d}T00:00:00",
                    model="test-model",
                    total_patterns=10,
                    scanned=10,
                    vulnerable=0,
                    refused=10,
                    partial=0,
                    errors=0,
                    risk_level="LOW",
                    duration_seconds=30.0,
                )
                manager.add_entry(entry)

            entries = manager.get_entries(limit=5)
            assert len(entries) == 5
