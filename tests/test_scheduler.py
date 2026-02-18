import pytest

from app.scheduler import interval_to_cron


class TestIntervalToCron:
    def test_minutes(self):
        assert interval_to_cron("30m") == "*/30 * * * *"
        assert interval_to_cron("1m") == "*/1 * * * *"
        assert interval_to_cron("59m") == "*/59 * * * *"

    def test_hours(self):
        assert interval_to_cron("2h") == "0 */2 * * *"
        assert interval_to_cron("1h") == "0 */1 * * *"
        assert interval_to_cron("23h") == "0 */23 * * *"

    def test_daily(self):
        assert interval_to_cron("1d") == "0 0 * * *"

    def test_whitespace_tolerance(self):
        assert interval_to_cron(" 30m ") == "*/30 * * * *"

    def test_case_insensitive(self):
        assert interval_to_cron("30M") == "*/30 * * * *"
        assert interval_to_cron("2H") == "0 */2 * * *"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            interval_to_cron("abc")
        with pytest.raises(ValueError):
            interval_to_cron("100x")
        with pytest.raises(ValueError):
            interval_to_cron("")

    def test_minute_out_of_range(self):
        with pytest.raises(ValueError):
            interval_to_cron("0m")
        with pytest.raises(ValueError):
            interval_to_cron("60m")

    def test_hour_out_of_range(self):
        with pytest.raises(ValueError):
            interval_to_cron("0h")
        with pytest.raises(ValueError):
            interval_to_cron("24h")

    def test_day_not_one_raises(self):
        with pytest.raises(ValueError):
            interval_to_cron("2d")
        with pytest.raises(ValueError):
            interval_to_cron("7d")
