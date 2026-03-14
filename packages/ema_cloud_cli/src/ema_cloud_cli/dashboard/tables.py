"""
Table setup and rendering helpers for the terminal dashboard.
"""

from textual.css.query import NoMatches
from textual.widgets import DataTable

from ema_cloud_lib.types.display import ETFDisplayData, HoldingDisplayData, SignalDisplayData


def setup_etf_table(app) -> None:
    """Setup ETF overview table columns."""
    try:
        table = app.query_one("#etf-table", DataTable)
    except NoMatches:
        return
    table.add_column("Symbol", key="symbol", width=8)
    table.add_column("Sector", key="sector", width=18)
    table.add_column("Price", key="price", width=10)
    table.add_column("Change", key="change", width=9)
    table.add_column("Trend", key="trend", width=10)
    table.add_column("Strength", key="strength", width=9)
    table.add_column("MTF", key="mtf", width=12)
    table.add_column("RSI", key="rsi", width=7)
    table.add_column("ADX", key="adx", width=7)
    table.add_column("Sigs", key="signals", width=5)


def setup_signals_table(app) -> None:
    """Setup signals table columns."""
    try:
        table = app.query_one("#signals-table", DataTable)
    except NoMatches:
        return
    table.add_column("Time", key="time", width=9)
    table.add_column("Sym", key="symbol", width=6)
    table.add_column("Dir", key="direction", width=5)
    table.add_column("Signal", key="signal", width=22)
    table.add_column("Price", key="price", width=9)
    table.add_column("Str", key="strength", width=8)


def setup_holdings_table(app) -> None:
    """Setup holdings table columns."""
    try:
        table = app.query_one("#holdings-table", DataTable)
    except NoMatches:
        return
    table.add_column("Symbol", key="symbol", width=8)
    table.add_column("Company", key="company", width=20)
    table.add_column("Weight", key="weight", width=8)
    table.add_column("Price", key="price", width=10)
    table.add_column("Trend", key="trend", width=6)
    table.add_column("Signal", key="signal", width=16)


def update_etf_table(app, etf_data: dict[str, ETFDisplayData]) -> None:
    """Refresh the ETF table with current data."""
    try:
        table = app.query_one("#etf-table", DataTable)
    except NoMatches:
        return
    table.clear()

    sorted_etfs = sorted(etf_data.values(), key=lambda x: x.trend_strength, reverse=True)

    for etf in sorted_etfs:
        if etf.trend == "bullish":
            trend_text = "🟢 BULL"
        elif etf.trend == "bearish":
            trend_text = "🔴 BEAR"
        else:
            trend_text = "⚪ FLAT"

        change_text = f"{etf.change_pct:+.2f}%"
        strength_text = f"{etf.trend_strength:.0f}%"

        # MTF column formatting
        if etf.mtf and etf.mtf.enabled:
            bias_symbol = (
                "🟢" if etf.mtf.bias == "long" else "🔴" if etf.mtf.bias == "short" else "⚪"
            )
            confidence_short = (
                etf.mtf.confidence.replace("_", "")[:4].upper() if etf.mtf.confidence else "---"
            )
            mtf_text = f"{bias_symbol} {confidence_short}"
        else:
            mtf_text = "-"

        rsi_text = f"{etf.rsi:.1f}" if etf.rsi is not None else "-"
        adx_text = f"{etf.adx:.1f}" if etf.adx is not None else "-"
        signals_text = str(etf.signals_count)

        table.add_row(
            etf.symbol,
            etf.sector[:16],
            f"${etf.price:.2f}",
            change_text,
            trend_text,
            strength_text,
            mtf_text,
            rsi_text,
            adx_text,
            signals_text,
            key=etf.symbol,
        )


def update_signals_table(
    app,
    signals: list[SignalDisplayData],
    *,
    max_rows: int = 15,
) -> None:
    """Refresh the signals table with current data."""
    try:
        table = app.query_one("#signals-table", DataTable)
    except NoMatches:
        return
    table.clear()

    for i, signal in enumerate(signals[:max_rows]):
        dir_text = "🟢 ↑" if signal.direction == "long" else "🔴 ↓"
        signal_type = signal.signal_type[:20]

        table.add_row(
            signal.timestamp.strftime("%H:%M:%S"),
            signal.symbol,
            dir_text,
            signal_type,
            f"${signal.price:.2f}",
            signal.strength[:6],
            key=f"sig-{i}",
        )


def update_holdings_table(
    app,
    holdings: list[HoldingDisplayData],
) -> None:
    """Refresh the holdings table with current data."""
    try:
        table = app.query_one("#holdings-table", DataTable)
    except NoMatches:
        return
    table.clear()

    if not holdings:
        table.add_row("-", "No holdings data", "-", "-", "-", "-", key="holdings-empty")
        return

    for holding in holdings:
        if holding.direction == "long":
            trend_text = "🟢"
        elif holding.direction == "short":
            trend_text = "🔴"
        else:
            trend_text = "⚪"

        weight_text = f"{holding.weight:.1f}%" if holding.weight is not None else "-"
        price_text = f"${holding.price:.2f}" if holding.price is not None else "-"
        signal_text = holding.signal_type[:14] if holding.signal_type else "-"

        table.add_row(
            holding.symbol,
            (holding.company or holding.symbol)[:18],
            weight_text,
            price_text,
            trend_text,
            signal_text,
            key=f"holding-{holding.symbol}",
        )
