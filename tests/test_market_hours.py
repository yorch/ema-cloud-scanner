"""
Comprehensive tests for market hours functionality including holidays and early closes.
"""

from datetime import datetime, time

import pytest

from ema_cloud_lib.market_hours import MarketHours


class TestMarketHoursBasic:
    """Test basic market hours utility methods."""

    def test_is_market_open_during_regular_hours(self):
        """Test market is detected as open during regular hours."""
        # 11:30 AM on a Wednesday
        test_time = datetime(2025, 1, 8, 11, 30, 0)  # Wednesday, not a holiday
        assert MarketHours.is_market_open(test_time) is True

    def test_is_market_open_before_open(self):
        """Test market is closed before 9:30 AM."""
        # 9:00 AM on a Wednesday
        test_time = datetime(2025, 1, 8, 9, 0, 0)
        assert MarketHours.is_market_open(test_time) is False

    def test_is_market_open_after_close(self):
        """Test market is closed after 4:00 PM."""
        # 5:00 PM on a Wednesday
        test_time = datetime(2025, 1, 8, 17, 0, 0)
        assert MarketHours.is_market_open(test_time) is False

    def test_is_market_open_weekend(self):
        """Test market is closed on weekends."""
        # Saturday
        saturday = datetime(2025, 1, 11, 11, 0, 0)
        assert MarketHours.is_market_open(saturday) is False

        # Sunday
        sunday = datetime(2025, 1, 12, 11, 0, 0)
        assert MarketHours.is_market_open(sunday) is False

    def test_is_extended_hours_pre_market(self):
        """Test pre-market hours detection."""
        # 7:00 AM on a Wednesday
        test_time = datetime(2025, 1, 8, 7, 0, 0)
        assert MarketHours.is_extended_hours(test_time) is True

    def test_is_extended_hours_after_hours(self):
        """Test after-hours detection."""
        # 5:00 PM on a Wednesday
        test_time = datetime(2025, 1, 8, 17, 0, 0)
        assert MarketHours.is_extended_hours(test_time) is True

    def test_is_extended_hours_during_market(self):
        """Test extended hours returns False during regular market hours."""
        # 11:30 AM on a Wednesday
        test_time = datetime(2025, 1, 8, 11, 30, 0)
        assert MarketHours.is_extended_hours(test_time) is False

    def test_time_to_close_during_market_hours(self):
        """Test time_to_close calculation during market hours."""
        # 11:30 AM on a Wednesday
        test_time = datetime(2025, 1, 8, 11, 30, 0)
        time_remaining = MarketHours.time_to_close(test_time)

        assert time_remaining is not None
        # Should be 4.5 hours until close (4:00 PM)
        expected_seconds = 4.5 * 3600
        assert abs(time_remaining.total_seconds() - expected_seconds) < 60

    def test_time_to_close_when_market_closed(self):
        """Test time_to_close returns None when market is closed."""
        # 6:00 PM on a Wednesday
        test_time = datetime(2025, 1, 8, 18, 0, 0)
        time_remaining = MarketHours.time_to_close(test_time)

        assert time_remaining is None

    def test_time_to_open_before_market(self):
        """Test time_to_open before market opens."""
        # 8:00 AM on a Wednesday
        test_time = datetime(2025, 1, 8, 8, 0, 0)
        time_remaining = MarketHours.time_to_open(test_time)

        assert time_remaining is not None
        # Should be 1.5 hours until open (9:30 AM)
        expected_seconds = 1.5 * 3600
        assert abs(time_remaining.total_seconds() - expected_seconds) < 60

    def test_time_to_open_when_market_open(self):
        """Test time_to_open returns None when market is already open."""
        # 11:30 AM on a Wednesday
        test_time = datetime(2025, 1, 8, 11, 30, 0)
        time_remaining = MarketHours.time_to_open(test_time)

        assert time_remaining is None


class TestMarketHoursHolidays:
    """Test holiday detection functionality."""

    def test_is_market_holiday_new_years_day(self):
        """Test New Year's Day 2025 (Wednesday) is detected as holiday."""
        test_time = datetime(2025, 1, 1, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is True

    def test_is_market_holiday_mlk_day(self):
        """Test MLK Day 2025 (Monday) is detected as holiday."""
        test_time = datetime(2025, 1, 20, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is True

    def test_is_market_holiday_presidents_day(self):
        """Test Presidents' Day 2025 (Monday) is detected as holiday."""
        test_time = datetime(2025, 2, 17, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is True

    def test_is_market_holiday_good_friday(self):
        """Test Good Friday 2025 is detected as holiday."""
        test_time = datetime(2025, 4, 18, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is True

    def test_is_market_holiday_memorial_day(self):
        """Test Memorial Day 2025 (Monday) is detected as holiday."""
        test_time = datetime(2025, 5, 26, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is True

    def test_is_market_holiday_juneteenth(self):
        """Test Juneteenth 2025 (Thursday) is detected as holiday."""
        test_time = datetime(2025, 6, 19, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is True

    def test_is_market_holiday_independence_day(self):
        """Test Independence Day 2025 (Friday) is detected as holiday."""
        test_time = datetime(2025, 7, 4, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is True

    def test_is_market_holiday_labor_day(self):
        """Test Labor Day 2025 (Monday) is detected as holiday."""
        test_time = datetime(2025, 9, 1, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is True

    def test_is_market_holiday_thanksgiving(self):
        """Test Thanksgiving 2025 (Thursday) is detected as holiday."""
        test_time = datetime(2025, 11, 27, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is True

    def test_is_market_holiday_christmas(self):
        """Test Christmas 2025 (Thursday) is detected as holiday."""
        test_time = datetime(2025, 12, 25, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is True

    def test_is_not_holiday_regular_day(self):
        """Test regular trading day is not detected as holiday."""
        # Thursday, January 2, 2025 (day after New Year's)
        test_time = datetime(2025, 1, 2, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is False

    def test_is_not_holiday_christmas_eve(self):
        """Test Christmas Eve 2025 is NOT a holiday (but has early close)."""
        test_time = datetime(2025, 12, 24, 11, 0, 0)
        assert MarketHours.is_market_holiday(test_time) is False

    def test_is_market_open_returns_false_on_holiday(self):
        """Test is_market_open returns False on holidays."""
        # Christmas 2025
        test_time = datetime(2025, 12, 25, 11, 0, 0)
        assert MarketHours.is_market_open(test_time) is False

    def test_is_extended_hours_returns_false_on_holiday(self):
        """Test is_extended_hours returns False on holidays."""
        # Christmas 2025 at pre-market time
        test_time = datetime(2025, 12, 25, 7, 0, 0)
        assert MarketHours.is_extended_hours(test_time) is False


class TestMarketHoursEarlyClose:
    """Test early close detection functionality."""

    def test_get_early_close_time_july_3rd(self):
        """Test July 3rd 2025 (day before Independence Day) early close detection."""
        test_time = datetime(2025, 7, 3, 10, 0, 0)
        early_close = MarketHours.get_early_close_time(test_time)

        assert early_close is not None
        # Should be 1:00 PM ET (13:00)
        assert early_close == time(13, 0)

    def test_get_early_close_time_black_friday(self):
        """Test Black Friday 2025 (Nov 28) early close detection."""
        test_time = datetime(2025, 11, 28, 10, 0, 0)
        early_close = MarketHours.get_early_close_time(test_time)

        assert early_close is not None
        # Should be 1:00 PM ET (13:00)
        assert early_close == time(13, 0)

    def test_get_early_close_time_christmas_eve(self):
        """Test Christmas Eve 2025 (Dec 24) early close detection."""
        test_time = datetime(2025, 12, 24, 10, 0, 0)
        early_close = MarketHours.get_early_close_time(test_time)

        assert early_close is not None
        # Should be 1:00 PM ET (13:00)
        assert early_close == time(13, 0)

    def test_get_early_close_time_regular_day(self):
        """Test regular trading day returns None for early close."""
        # Regular Thursday
        test_time = datetime(2025, 1, 2, 10, 0, 0)
        early_close = MarketHours.get_early_close_time(test_time)

        assert early_close is None

    def test_get_early_close_time_holiday(self):
        """Test holiday returns None for early close."""
        # Christmas Day (full closure, not early close)
        test_time = datetime(2025, 12, 25, 10, 0, 0)
        early_close = MarketHours.get_early_close_time(test_time)

        assert early_close is None

    def test_is_market_open_respects_early_close(self):
        """Test is_market_open returns False after early close time."""
        # Black Friday at 2:00 PM (after 1:00 PM early close)
        test_time = datetime(2025, 11, 28, 14, 0, 0)
        assert MarketHours.is_market_open(test_time) is False

    def test_is_market_open_before_early_close(self):
        """Test is_market_open returns True before early close time."""
        # Black Friday at 11:00 AM (before 1:00 PM early close)
        test_time = datetime(2025, 11, 28, 11, 0, 0)
        assert MarketHours.is_market_open(test_time) is True

    def test_time_to_close_on_early_close_day(self):
        """Test time_to_close accounts for early close."""
        # Black Friday at 11:00 AM (2 hours until 1:00 PM close)
        test_time = datetime(2025, 11, 28, 11, 0, 0)
        time_remaining = MarketHours.time_to_close(test_time)

        assert time_remaining is not None
        # Should be 2 hours until early close
        expected_seconds = 2 * 3600
        assert abs(time_remaining.total_seconds() - expected_seconds) < 60


class TestMarketStatus:
    """Test get_market_status comprehensive functionality."""

    def test_get_market_status_open(self):
        """Test market status during regular hours."""
        # 11:30 AM on a Wednesday
        test_time = datetime(2025, 1, 8, 11, 30, 0)
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "OPEN"
        assert status["emoji"] == "🟢"
        assert status["message"] == "MARKET OPEN"
        assert "to close" in status["time_info"]
        assert status["next_event"] is not None

    def test_get_market_status_pre_market(self):
        """Test market status during pre-market hours."""
        # 6:00 AM on a Wednesday
        test_time = datetime(2025, 1, 8, 6, 0, 0)
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "PRE_MARKET"
        assert status["emoji"] == "🟡"
        assert status["message"] == "PRE-MARKET"
        assert "to open" in status["time_info"]

    def test_get_market_status_after_hours(self):
        """Test market status during after-hours."""
        # 5:00 PM on a Wednesday
        test_time = datetime(2025, 1, 8, 17, 0, 0)
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "AFTER_HOURS"
        assert status["emoji"] == "🟠"
        assert status["message"] == "AFTER-HOURS"
        assert "Next:" in status["time_info"]

    def test_get_market_status_weekend(self):
        """Test market status on weekend."""
        # 11:00 AM on a Saturday
        test_time = datetime(2025, 1, 11, 11, 0, 0)
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "CLOSED"
        assert status["emoji"] == "🔴"
        assert status["message"] == "MARKET CLOSED"
        assert "Next:" in status["time_info"]
        assert "Mon" in status["time_info"]

    def test_get_market_status_holiday(self):
        """Test market status on holiday."""
        # Christmas 2025 at 11:00 AM
        test_time = datetime(2025, 12, 25, 11, 0, 0)
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "HOLIDAY"
        assert status["emoji"] == "🔴"
        assert status["message"] == "MARKET HOLIDAY"
        assert "Next:" in status["time_info"]
        assert status["next_event"] is not None

    def test_get_market_status_early_close_shows_indicator(self):
        """Test market status shows early close indicator."""
        # Black Friday at 11:00 AM (early close day)
        test_time = datetime(2025, 11, 28, 11, 0, 0)
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "OPEN"
        assert status["emoji"] == "🟢"
        # Should indicate early close in time_info
        assert "(early)" in status["time_info"]

    def test_get_market_status_late_night(self):
        """Test market status during late night/early morning."""
        # 2:00 AM on a Wednesday
        test_time = datetime(2025, 1, 8, 2, 0, 0)
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "CLOSED"
        assert status["emoji"] == "🔴"
        assert status["message"] == "MARKET CLOSED"
        assert status["time_info"]

    def test_get_market_status_at_market_open(self):
        """Test market status at exactly 9:30 AM."""
        # Exactly 9:30 AM on a Wednesday
        test_time = datetime(2025, 1, 8, 9, 30, 0)
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "OPEN"
        assert status["emoji"] == "🟢"

    def test_get_market_status_at_market_close(self):
        """Test market status at exactly 4:00 PM."""
        # Exactly 4:00 PM on a Wednesday
        test_time = datetime(2025, 1, 8, 16, 0, 0)
        status = MarketHours.get_market_status(test_time)

        # At exactly close time, should still be OPEN
        assert status["status"] == "OPEN"
        assert status["emoji"] == "🟢"


class TestNextTradingDay:
    """Test next trading day calculation with holiday skipping."""

    def test_time_to_open_skips_weekend(self):
        """Test time_to_open skips weekend correctly."""
        # Friday evening after market close
        test_time = datetime(2025, 1, 10, 18, 0, 0)  # Friday 6 PM
        time_remaining = MarketHours.time_to_open(test_time)

        assert time_remaining is not None
        # Should skip to Monday morning
        # Approximately 63.5 hours (Friday 6 PM to Monday 9:30 AM)
        expected_seconds = 63.5 * 3600
        assert abs(time_remaining.total_seconds() - expected_seconds) < 3600

    def test_time_to_open_skips_holiday(self):
        """Test time_to_open skips holidays correctly."""
        # Day before MLK Day (Sunday evening, Jan 19)
        # Next trading day is Tuesday Jan 21 (skipping MLK Day Monday)
        test_time = datetime(2025, 1, 19, 18, 0, 0)  # Sunday 6 PM
        time_remaining = MarketHours.time_to_open(test_time)

        assert time_remaining is not None
        # Should skip weekend AND Monday holiday, go to Tuesday 9:30 AM
        # Sunday 6 PM to Tuesday 9:30 AM = 39.5 hours
        expected_min = 38 * 3600  # At least 38 hours
        expected_max = 41 * 3600  # At most 41 hours
        assert expected_min < time_remaining.total_seconds() < expected_max

    def test_get_market_status_holiday_shows_next_trading_day(self):
        """Test market status on holiday shows correct next trading day."""
        # MLK Day 2025 (Monday, Jan 20)
        test_time = datetime(2025, 1, 20, 11, 0, 0)
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "HOLIDAY"
        # Next trading day should be Tuesday
        assert status["next_event"] is not None
        assert status["next_event"].weekday() == 1  # Tuesday
        assert "Tue" in status["time_info"]


# ===========================================================================
# DST Handling
# ===========================================================================


class TestDSTHandling:
    """Market hours DST handling should use zoneinfo, not month approximation."""

    def test_early_close_during_est(self):
        """Early close detection during EST (winter) should work correctly."""
        christmas_eve = datetime(2025, 12, 24, 10, 0)
        early_close = MarketHours.get_early_close_time(christmas_eve)

        if early_close is not None:
            assert early_close.hour == 13, (
                f"Christmas Eve early close should be 1 PM ET, got {early_close}"
            )

    def test_early_close_during_edt(self):
        """Early close detection during EDT (summer) should work correctly."""
        july_3 = datetime(2025, 7, 3, 10, 0)
        early_close = MarketHours.get_early_close_time(july_3)

        if early_close is not None:
            assert early_close.hour == 13, (
                f"July 3rd early close should be 1 PM ET, got {early_close}"
            )

    def test_regular_day_no_early_close(self):
        """Regular trading days should not have early close."""
        regular_day = datetime(2025, 6, 10, 10, 0)
        early_close = MarketHours.get_early_close_time(regular_day)
        assert early_close is None, "Regular trading day should have no early close"

    def test_march_dst_transition_boundary(self):
        """Days around March DST transition should be handled correctly."""
        march_7 = datetime(2025, 3, 7, 10, 0)
        assert MarketHours.is_market_open(march_7), "March 7 at 10 AM should be market open"

        march_10 = datetime(2025, 3, 10, 10, 0)
        assert MarketHours.is_market_open(march_10), "March 10 at 10 AM should be market open"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
