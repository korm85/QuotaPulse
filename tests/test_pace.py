import unittest

from quotapulse.pace import forecast


class ForecastTests(unittest.TestCase):
    def test_no_points_gives_no_forecast(self):
        fc = forecast([], threshold=80, now=1000)
        self.assertIsNone(fc.rate_pct_per_hour)
        self.assertIsNone(fc.reaches_threshold_at)

    def test_steady_burn_projects_when_threshold_is_hit(self):
        # 10% -> 20% over 600s is 60%/h. From 20% to 80% takes one hour.
        points = [(0.0, 10.0), (600.0, 20.0)]
        fc = forecast(points, threshold=80, now=600, window_s=3600)
        self.assertAlmostEqual(fc.rate_pct_per_hour, 60.0)
        self.assertAlmostEqual(fc.reaches_threshold_at, 600 + 3600)

    def test_drop_means_only_points_after_it_count(self):
        # Before the drop the slope is steep. After it, 5% -> 10% over 100s is 180%/h.
        points = [(0.0, 90.0), (100.0, 95.0), (200.0, 5.0), (300.0, 10.0)]
        fc = forecast(points, threshold=80, now=300)
        self.assertAlmostEqual(fc.rate_pct_per_hour, 180.0)

    def test_flat_usage_never_reaches_threshold(self):
        points = [(0.0, 30.0), (600.0, 30.0)]
        fc = forecast(points, threshold=80, now=600)
        self.assertEqual(fc.rate_pct_per_hour, 0.0)
        self.assertIsNone(fc.reaches_threshold_at)

    def test_already_past_threshold_reports_now(self):
        points = [(0.0, 85.0), (600.0, 90.0)]
        fc = forecast(points, threshold=80, now=600)
        self.assertEqual(fc.reaches_threshold_at, 600)

    def test_old_points_outside_window_are_ignored(self):
        points = [(0.0, 10.0), (10000.0, 50.0)]
        fc = forecast(points, threshold=80, now=10000, window_s=1800)
        self.assertIsNone(fc.rate_pct_per_hour)


if __name__ == "__main__":
    unittest.main()
