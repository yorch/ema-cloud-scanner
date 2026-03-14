"""
Market Hours Utilities

Provides market hours checking and holiday detection for US stock markets (NYSE/NASDAQ).
Uses pandas_market_calendars for accurate holiday and early close handling.
"""

import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal

logger = logging.getLogger(__name__)


class MarketHours:
    """
    Market hours utilities with NYSE holiday calendar support.

    Handles:
    - Regular market hours (9:30 AM - 4:00 PM ET)
    - Pre-market (4:00 AM - 9:30 AM ET)
    - After-hours (4:00 PM - 8:00 PM ET)
    - US market holidays (via NYSE calendar)
    - Early closes (e.g., day before Thanksgiving, Christmas Eve)
    - Weekend detection
    """

    # US Market hours (Eastern Time)
    MARKET_OPEN = time(9, 30)
    MARKET_CLOSE = time(16, 0)
    PRE_MARKET_OPEN = time(4, 0)
    AFTER_HOURS_CLOSE = time(20, 0)

    _nyse_calendar = None

    @classmethod
    def _get_nyse_calendar(cls):
        """Get or create NYSE calendar instance."""
        if cls._nyse_calendar is None:
            cls._nyse_calendar = mcal.get_calendar("NYSE")
        return cls._nyse_calendar

    @classmethod
    def is_market_holiday(cls, check_time: datetime | None = None) -> bool:
        """
        Check if the given date is a market holiday.

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            True if market is closed for a holiday
        """
        if check_time is None:
            check_time = datetime.now()

        # Get NYSE calendar
        nyse = cls._get_nyse_calendar()

        # Check if this date is a valid trading day
        # Get schedule for this specific date
        schedule = nyse.schedule(start_date=check_time.date(), end_date=check_time.date())

        # If schedule is empty, it's a holiday
        return len(schedule) == 0

    @classmethod
    def get_early_close_time(cls, check_time: datetime | None = None) -> time | None:
        """
        Get early close time if the market closes early on this day.

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            Early close time (in ET) if applicable, None otherwise
        """
        if check_time is None:
            check_time = datetime.now()

        # Get NYSE calendar
        nyse = cls._get_nyse_calendar()

        # Get schedule for this specific date
        schedule = nyse.schedule(start_date=check_time.date(), end_date=check_time.date())

        if len(schedule) == 0:
            return None

        # NYSE calendar returns times in UTC
        # Regular close: 4:00 PM ET = 20:00 UTC (EDT) or 21:00 UTC (EST)
        # We check if close is before either, accounting for DST
        market_close_utc = schedule.iloc[0]["market_close"]

        # Convert UTC close time to Eastern Time using proper timezone handling
        et_tz = ZoneInfo("America/New_York")
        close_et = market_close_utc.to_pydatetime().astimezone(et_tz)
        close_time_et: time = close_et.time().replace(second=0, microsecond=0)

        # Regular close is 4:00 PM ET; anything earlier is an early close
        if close_time_et < cls.MARKET_CLOSE:
            return close_time_et

        return None

    @classmethod
    def is_market_open(cls, check_time: datetime | None = None) -> bool:
        """
        Check if market is currently open.

        Accounts for:
        - Weekends
        - Holidays
        - Regular trading hours
        - Early closes

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            True if market is open for trading
        """
        if check_time is None:
            check_time = datetime.now()

        # Check if weekday (Mon=0, Sun=6)
        if check_time.weekday() >= 5:
            return False

        # Check if market holiday
        if cls.is_market_holiday(check_time):
            return False

        current_time = check_time.time()

        # Check for early close
        early_close = cls.get_early_close_time(check_time)
        close_time = early_close if early_close else cls.MARKET_CLOSE

        return cls.MARKET_OPEN <= current_time <= close_time

    @classmethod
    def is_extended_hours(cls, check_time: datetime | None = None) -> bool:
        """
        Check if in extended trading hours (pre-market or after-hours).

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            True if in pre-market or after-hours
        """
        if check_time is None:
            check_time = datetime.now()

        if check_time.weekday() >= 5:
            return False

        # No extended hours on holidays
        if cls.is_market_holiday(check_time):
            return False

        current_time = check_time.time()

        # Check for early close (affects after-hours start time)
        early_close = cls.get_early_close_time(check_time)
        close_time = early_close if early_close else cls.MARKET_CLOSE

        # Pre-market or after-hours
        pre_market = cls.PRE_MARKET_OPEN <= current_time < cls.MARKET_OPEN
        after_hours = close_time < current_time <= cls.AFTER_HOURS_CLOSE

        return pre_market or after_hours

    @classmethod
    def _get_next_trading_day(cls, check_time: datetime) -> datetime:
        """
        Get the next valid trading day (skipping weekends and holidays).

        Args:
            check_time: Starting point to search from

        Returns:
            datetime of next trading day at market open
        """
        nyse = cls._get_nyse_calendar()

        # Start from next day
        search_date = (check_time + timedelta(days=1)).date()

        # Search up to 10 days ahead (covers long holiday weekends)
        end_date = (check_time + timedelta(days=10)).date()

        # Get valid trading days
        schedule = nyse.schedule(start_date=search_date, end_date=end_date)

        if len(schedule) == 0:
            # Fallback: just skip to next weekday (shouldn't happen)
            logger.warning(
                "NYSE calendar returned no trading days in next 10 days from %s. "
                "Using basic weekday fallback (may not account for holidays).",
                check_time.date(),
            )
            next_day = check_time + timedelta(days=1)
            while next_day.weekday() >= 5:
                next_day += timedelta(days=1)
            return next_day.replace(
                hour=cls.MARKET_OPEN.hour,
                minute=cls.MARKET_OPEN.minute,
                second=0,
                microsecond=0,
            )

        # Get first trading day
        next_trading_day = schedule.index[0].date()

        return datetime.combine(next_trading_day, cls.MARKET_OPEN)

    @classmethod
    def time_to_open(cls, check_time: datetime | None = None) -> timedelta | None:
        """
        Get time until market opens.

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            timedelta until market opens, or None if already open
        """
        if check_time is None:
            check_time = datetime.now()

        if cls.is_market_open(check_time):
            return None

        # Check if today is a trading day
        if not cls.is_market_holiday(check_time) and check_time.weekday() < 5:
            # Today is a valid trading day
            open_today = check_time.replace(
                hour=cls.MARKET_OPEN.hour,
                minute=cls.MARKET_OPEN.minute,
                second=0,
                microsecond=0,
            )

            if check_time.time() < cls.MARKET_OPEN:
                # Market hasn't opened yet today
                return open_today - check_time

        # Find next trading day
        next_open = cls._get_next_trading_day(check_time)
        return next_open - check_time

    @classmethod
    def time_to_close(cls, check_time: datetime | None = None) -> timedelta | None:
        """
        Get time until market closes.

        Args:
            check_time: Time to check (defaults to now)

        Returns:
            timedelta until market closes, or None if market is closed
        """
        if check_time is None:
            check_time = datetime.now()

        if not cls.is_market_open(check_time):
            return None

        # Check for early close
        early_close = cls.get_early_close_time(check_time)
        close_time = early_close if early_close else cls.MARKET_CLOSE

        # Calculate time to close today
        close_today = check_time.replace(
            hour=close_time.hour, minute=close_time.minute, second=0, microsecond=0
        )

        return close_today - check_time

    @classmethod
    def get_market_status(
        cls, check_time: datetime | None = None
    ) -> dict[str, str | datetime | None]:
        """
        Get comprehensive market status information.

        Returns:
            dict with keys:
                - status: str ("OPEN", "CLOSED", "PRE_MARKET", "AFTER_HOURS", "HOLIDAY")
                - emoji: str (visual indicator)
                - message: str (human-readable status)
                - time_info: str (time until next event)
                - next_event: datetime | None (next market open/close)
        """
        if check_time is None:
            check_time = datetime.now()

        # Check if weekend
        if check_time.weekday() >= 5:
            next_open = cls._get_next_trading_day(check_time)
            return {
                "status": "CLOSED",
                "emoji": "🔴",
                "message": "MARKET CLOSED",
                "time_info": f"Next: {next_open.strftime('%a %I:%M %p')}",
                "next_event": next_open,
            }

        # Check if holiday
        if cls.is_market_holiday(check_time):
            next_open = cls._get_next_trading_day(check_time)
            return {
                "status": "HOLIDAY",
                "emoji": "🔴",
                "message": "MARKET HOLIDAY",
                "time_info": f"Next: {next_open.strftime('%a %I:%M %p')}",
                "next_event": next_open,
            }

        current_time = check_time.time()

        # Check for early close
        early_close = cls.get_early_close_time(check_time)
        close_time = early_close if early_close else cls.MARKET_CLOSE

        # Market open
        if cls.MARKET_OPEN <= current_time <= close_time:
            time_remaining = cls.time_to_close(check_time)
            if time_remaining:
                hours = int(time_remaining.total_seconds() // 3600)
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                time_str = f"{hours}h {minutes}m to close" if hours > 0 else f"{minutes}m to close"

                # Add early close indicator
                if early_close:
                    time_str = f"{time_str} (early)"
            else:
                time_str = "closing soon"

            return {
                "status": "OPEN",
                "emoji": "🟢",
                "message": "MARKET OPEN",
                "time_info": time_str,
                "next_event": check_time.replace(
                    hour=close_time.hour,
                    minute=close_time.minute,
                    second=0,
                    microsecond=0,
                ),
            }

        # Pre-market
        if cls.PRE_MARKET_OPEN <= current_time < cls.MARKET_OPEN:
            time_remaining = cls.time_to_open(check_time)
            if time_remaining:
                hours = int(time_remaining.total_seconds() // 3600)
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                time_str = f"{hours}h {minutes}m to open" if hours > 0 else f"{minutes}m to open"
            else:
                time_str = "opening soon"

            return {
                "status": "PRE_MARKET",
                "emoji": "🟡",
                "message": "PRE-MARKET",
                "time_info": time_str,
                "next_event": check_time.replace(
                    hour=cls.MARKET_OPEN.hour,
                    minute=cls.MARKET_OPEN.minute,
                    second=0,
                    microsecond=0,
                ),
            }

        # After-hours
        if close_time < current_time <= cls.AFTER_HOURS_CLOSE:
            next_open = cls._get_next_trading_day(check_time)

            return {
                "status": "AFTER_HOURS",
                "emoji": "🟠",
                "message": "AFTER-HOURS",
                "time_info": f"Next: {next_open.strftime('%a %I:%M %p')}",
                "next_event": next_open,
            }

        # Market closed (late night/early morning)
        time_remaining = cls.time_to_open(check_time)
        if time_remaining:
            hours = int(time_remaining.total_seconds() // 3600)
            if hours > 24:
                next_open = check_time + time_remaining
                time_str = f"Next: {next_open.strftime('%a %I:%M %p')}"
            else:
                minutes = int((time_remaining.total_seconds() % 3600) // 60)
                time_str = f"{hours}h {minutes}m to open" if hours > 0 else f"{minutes}m to open"
        else:
            time_str = "closed"

        return {
            "status": "CLOSED",
            "emoji": "🔴",
            "message": "MARKET CLOSED",
            "time_info": time_str,
            "next_event": check_time + time_remaining if time_remaining else None,
        }
