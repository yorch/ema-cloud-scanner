"""
Tests for market hours indicator functionality.
"""

from datetime import datetime

from ema_cloud_lib.scanner import MarketHours


class TestMarketHours:
    """Test market hours utility methods."""

    def test_time_to_close_during_market_hours(self):
        """Test time_to_close calculation during market hours."""
        # 11:30 AM on a Wednesday
        test_time = datetime(2024, 1, 10, 11, 30, 0)  # Wednesday
        time_remaining = MarketHours.time_to_close(test_time)

        assert time_remaining is not None
        # Should be 4.5 hours until close (4:00 PM)
        expected_seconds = 4.5 * 3600
        assert abs(time_remaining.total_seconds() - expected_seconds) < 60

    def test_time_to_close_when_market_closed(self):
        """Test time_to_close returns None when market is closed."""
        # 6:00 PM on a Wednesday
        test_time = datetime(2024, 1, 10, 18, 0, 0)  # Wednesday
        time_remaining = MarketHours.time_to_close(test_time)

        assert time_remaining is None

    def test_get_market_status_open(self):
        """Test market status during regular hours."""
        # 11:30 AM on a Wednesday
        test_time = datetime(2024, 1, 10, 11, 30, 0)  # Wednesday
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "OPEN"
        assert status["emoji"] == "🟢"
        assert status["message"] == "MARKET OPEN"
        assert "to close" in status["time_info"]

    def test_get_market_status_pre_market(self):
        """Test market status during pre-market hours."""
        # 6:00 AM on a Wednesday
        test_time = datetime(2024, 1, 10, 6, 0, 0)  # Wednesday
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "PRE_MARKET"
        assert status["emoji"] == "🟡"
        assert status["message"] == "PRE-MARKET"
        assert "to open" in status["time_info"]

    def test_get_market_status_after_hours(self):
        """Test market status during after-hours."""
        # 5:00 PM on a Wednesday
        test_time = datetime(2024, 1, 10, 17, 0, 0)  # Wednesday
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "AFTER_HOURS"
        assert status["emoji"] == "🟠"
        assert status["message"] == "AFTER-HOURS"
        assert "Next:" in status["time_info"]

    def test_get_market_status_weekend(self):
        """Test market status on weekend."""
        # 11:00 AM on a Saturday (Jan 13, 2024)
        # Note: Monday Jan 15 is MLK Day (holiday), so next trading day is Tuesday
        test_time = datetime(2024, 1, 13, 11, 0, 0)  # Saturday
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "CLOSED"
        assert status["emoji"] == "🔴"
        assert status["message"] == "MARKET CLOSED"
        assert "Next:" in status["time_info"]
        assert "Tue" in status["time_info"]  # Tuesday (Mon is MLK Day)

    def test_get_market_status_late_night(self):
        """Test market status during late night/early morning."""
        # 2:00 AM on a Wednesday
        test_time = datetime(2024, 1, 10, 2, 0, 0)  # Wednesday
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "CLOSED"
        assert status["emoji"] == "🔴"
        assert status["message"] == "MARKET CLOSED"
        assert status["time_info"]

    def test_get_market_status_market_opening(self):
        """Test market status at market open time."""
        # Exactly 9:30 AM on a Wednesday
        test_time = datetime(2024, 1, 10, 9, 30, 0)  # Wednesday
        status = MarketHours.get_market_status(test_time)

        assert status["status"] == "OPEN"
        assert status["emoji"] == "🟢"

    def test_get_market_status_market_closing(self):
        """Test market status at market close time."""
        # Exactly 4:00 PM on a Wednesday
        test_time = datetime(2024, 1, 10, 16, 0, 0)  # Wednesday
        status = MarketHours.get_market_status(test_time)

        # At exactly close time, should still be OPEN
        assert status["status"] == "OPEN"
        assert status["emoji"] == "🟢"
