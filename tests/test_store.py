import tempfile
import unittest
from pathlib import Path

from quotapulse.store import Snapshot, Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self._tmp.name) / "nested" / "q.db")

    def tearDown(self):
        self.store.close()
        self._tmp.cleanup()

    def test_latest_returns_newest_snapshot(self):
        self.store.add(Snapshot(account="codex", ts=100.0, source="manual", used_pct=10.0))
        self.store.add(Snapshot(account="codex", ts=200.0, source="manual", used_pct=20.0))
        latest = self.store.latest("codex")
        self.assertEqual(latest.used_pct, 20.0)
        self.assertIsNone(self.store.latest("missing"))

    def test_history_filters_by_time_and_orders_oldest_first(self):
        for ts, pct in [(300.0, 30.0), (100.0, 10.0), (200.0, 20.0)]:
            self.store.add(Snapshot(account="cursor", ts=ts, source="manual", used_pct=pct))
        history = self.store.history("cursor", since=150.0)
        self.assertEqual([s.used_pct for s in history], [20.0, 30.0])

    def test_accounts_are_distinct_and_sorted(self):
        self.store.add(Snapshot(account="codex", ts=1.0, source="manual", used_pct=1.0))
        self.store.add(Snapshot(account="claude", ts=2.0, source="manual", used_pct=2.0))
        self.store.add(Snapshot(account="codex", ts=3.0, source="manual", used_pct=3.0))
        self.assertEqual(self.store.accounts(), ["claude", "codex"])


if __name__ == "__main__":
    unittest.main()
