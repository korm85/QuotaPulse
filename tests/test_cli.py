import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from quotapulse.cli import format_duration, main, sparkline


class CliTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._env = mock.patch.dict(os.environ, {"QUOTAPULSE_DB": os.path.join(self._tmp.name, "q.db")})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()

    def _run(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_record_then_status_shows_account_and_percent(self):
        self._run("record", "codex", "--used-pct", "42", "--resets-in-minutes", "90")
        code, output = self._run("status")
        self.assertEqual(code, 0)
        self.assertIn("codex", output)
        self.assertIn("42%", output)
        # 90 minutes minus the few ms since recording floors to 1h 29m.
        self.assertIn("1h 29m", output)

    def test_record_then_history_reports_min_max_now(self):
        self._run("record", "cursor", "--used-pct", "10")
        self._run("record", "cursor", "--used-pct", "35")
        code, output = self._run("history", "cursor", "--hours", "1")
        self.assertEqual(code, 0)
        self.assertIn("min 10.0%", output)
        self.assertIn("max 35.0%", output)
        self.assertIn("now 35.0%", output)

    def test_collect_without_budget_reports_tokens_only(self):
        projects = os.path.join(self._tmp.name, "projects")
        os.makedirs(projects)
        code, output = self._run("collect", "--projects-dir", projects)
        self.assertEqual(code, 0)
        self.assertIn("0 tokens", output)
        self.assertIn("no --budget-tokens", output)

    def test_record_rejects_percent_out_of_range(self):
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()):
                main(["record", "codex", "--used-pct", "140"])

    def test_sparkline_scales_to_fixed_percent_range(self):
        self.assertEqual(sparkline([0.0, 100.0], width=2), "▁█")
        self.assertEqual(len(sparkline([float(i) for i in range(100)], width=60)), 60)

    def test_format_duration(self):
        self.assertEqual(format_duration(-5), "now")
        self.assertEqual(format_duration(45 * 60), "45m")
        self.assertEqual(format_duration(3 * 3600 + 5 * 60), "3h 05m")
        self.assertEqual(format_duration(2 * 86400 + 4 * 3600), "2d 4h")


if __name__ == "__main__":
    unittest.main()
