import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from quotapulse.claude_usage import window_totals

NOW = datetime(2026, 10, 7, 12, 0, 0, tzinfo=timezone.utc).timestamp()


def _line(ts: str, message_id: str | None = None, usage: dict | None = None) -> str:
    message: dict = {}
    if message_id:
        message["id"] = message_id
    if usage is not None:
        message["usage"] = usage
    return json.dumps({"timestamp": ts, "message": message})


class WindowTotalsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.projects = Path(self._tmp.name) / "projects"
        (self.projects / "-home-user-app").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_sums_only_entries_inside_window_and_dedupes_message_ids(self):
        usage = {
            "input_tokens": 10,
            "output_tokens": 20,
            "cache_creation_input_tokens": 30,
            "cache_read_input_tokens": 40,
        }
        recent = "2026-10-07T10:00:00Z"
        lines = [
            _line(recent, "msg-1", usage),
            _line(recent, "msg-1", usage),  # same streamed reply logged again
            _line("2026-10-06T01:00:00Z", "msg-old", usage),  # outside the 5h window
            _line(recent, None, None),  # user line, no usage
            "not json at all",
        ]
        (self.projects / "-home-user-app" / "session.jsonl").write_text("\n".join(lines), encoding="utf-8")

        totals = window_totals(self.projects, now=NOW)

        self.assertEqual(totals.input, 10)
        self.assertEqual(totals.output, 20)
        self.assertEqual(totals.cache_creation, 30)
        self.assertEqual(totals.cache_read, 40)
        self.assertEqual(totals.total, 100)

    def test_missing_projects_dir_gives_zero(self):
        totals = window_totals(Path(self._tmp.name) / "nope", now=NOW)
        self.assertEqual(totals.total, 0)


if __name__ == "__main__":
    unittest.main()
