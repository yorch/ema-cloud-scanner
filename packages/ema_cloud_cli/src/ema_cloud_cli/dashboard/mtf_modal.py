"""
Multi-Timeframe Analysis detail modal for the dashboard.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from ema_cloud_lib.types.display import ETFDisplayData


class MTFModal(ModalScreen):
    """
    Modal screen displaying detailed multi-timeframe analysis.

    Shows:
    - Overall MTF alignment and confidence
    - Trading bias (long/short/neutral)
    - Timeframe-by-timeframe breakdown
    - Bullish/Bearish/Neutral counts
    - Alignment percentage
    - Actionable trading recommendations
    """

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    CSS = """
    MTFModal {
        align: center middle;
    }

    #mtf-dialog {
        width: 80;
        max-height: 90%;
        border: thick $primary;
        background: $panel;
        padding: 1 2;
        overflow-y: auto;
    }

    #mtf-title {
        text-align: center;
        text-style: bold;
        padding: 0 0 1 0;
        color: $accent;
    }

    .mtf-section {
        padding: 0 0 1 0;
    }

    .section-title {
        text-style: bold;
        color: $secondary;
        padding: 0 0 0 0;
    }

    .mtf-row {
        layout: horizontal;
        height: auto;
        padding: 0 2;
    }

    .mtf-label {
        width: 25;
        color: $text-muted;
    }

    .mtf-value {
        width: 1fr;
        color: $text;
        text-style: bold;
    }

    .mtf-bullish {
        color: $success;
    }

    .mtf-bearish {
        color: $error;
    }

    .mtf-neutral {
        color: $warning;
    }

    .mtf-very-high {
        color: $success;
        text-style: bold;
    }

    .mtf-high {
        color: $success;
    }

    .mtf-moderate {
        color: $warning;
    }

    .mtf-low {
        color: $error;
    }

    #button-container {
        height: auto;
        padding: 1 0 0 0;
        align: center middle;
    }

    #close-button {
        min-width: 16;
    }
    """

    def __init__(self, etf_data: ETFDisplayData):
        super().__init__()
        self.etf_data = etf_data

    def compose(self) -> ComposeResult:
        with Vertical(id="mtf-dialog"):
            yield Label(f"Multi-Timeframe Analysis - {self.etf_data.symbol}", id="mtf-title")

            # Overview Section
            with Vertical(classes="mtf-section"):
                yield Label("Overview", classes="section-title")
                yield Static(id="mtf-overview")

            # Timeframe Breakdown Section
            with Vertical(classes="mtf-section"):
                yield Label("Timeframe Analysis", classes="section-title")
                yield Static(id="mtf-breakdown")

            # Trading Recommendation Section
            with Vertical(classes="mtf-section"):
                yield Label("Trading Guidance", classes="section-title")
                yield Static(id="mtf-guidance")

            # Close button
            with Vertical(id="button-container"):
                yield Button("Close", id="close-button", variant="primary")

    def on_mount(self) -> None:
        """Initialize MTF display."""
        self.update_mtf_display()

    def update_mtf_display(self) -> None:
        """Update all MTF analysis displays."""
        mtf = self.etf_data.mtf

        if not mtf or not mtf.enabled:
            # No MTF data available
            overview_widget = self.query_one("#mtf-overview", Static)
            overview_widget.update(
                "  [dim]Multi-timeframe analysis is not enabled.[/dim]\n"
                "  [dim]Enable MTF in settings to see timeframe alignment.[/dim]"
            )
            return

        # Update overview
        overview_widget = self.query_one("#mtf-overview", Static)

        # Determine alignment color
        alignment_class = self._get_alignment_class(mtf.alignment)
        confidence_class = self._get_confidence_class(mtf.confidence)
        bias_class = self._get_bias_class(mtf.bias)

        overview_content = (
            f"  [dim]Alignment:[/dim]      [{alignment_class}]{mtf.alignment.replace('_', ' ').title()}[/{alignment_class}]\n"
            f"  [dim]Confidence:[/dim]     [{confidence_class}]{mtf.confidence.replace('_', ' ').title()}[/{confidence_class}]\n"
            f"  [dim]Trading Bias:[/dim]   [{bias_class}]{mtf.bias.upper()}[/{bias_class}]\n"
            f"  [dim]Alignment %:[/dim]    [bold]{mtf.alignment_pct:.1f}%[/bold]\n"
        )
        overview_widget.update(overview_content)

        # Update breakdown
        breakdown_widget = self.query_one("#mtf-breakdown", Static)
        breakdown_content = (
            f"  [mtf-bullish]🟢 Bullish:[/mtf-bullish]    {mtf.bullish_count}/{mtf.total_timeframes} timeframes\n"
            f"  [mtf-bearish]🔴 Bearish:[/mtf-bearish]    {mtf.bearish_count}/{mtf.total_timeframes} timeframes\n"
            f"  [mtf-neutral]⚪ Neutral:[/mtf-neutral]    {mtf.neutral_count}/{mtf.total_timeframes} timeframes\n"
            f"\n  [dim]{mtf.summary}[/dim]"
        )
        breakdown_widget.update(breakdown_content)

        # Update guidance
        guidance_widget = self.query_one("#mtf-guidance", Static)
        guidance_content = self._generate_trading_guidance(mtf)
        guidance_widget.update(guidance_content)

    def _get_alignment_class(self, alignment: str | None) -> str:
        """Get CSS class for alignment display."""
        if not alignment:
            return "mtf-neutral"
        alignment_lower = alignment.lower()
        if "bull" in alignment_lower:
            return "mtf-bullish"
        elif "bear" in alignment_lower:
            return "mtf-bearish"
        return "mtf-neutral"

    def _get_confidence_class(self, confidence: str | None) -> str:
        """Get CSS class for confidence display."""
        if not confidence:
            return "mtf-low"

        confidence_lower = confidence.lower()
        if "very_high" in confidence_lower:
            return "mtf-very-high"
        elif "high" in confidence_lower:
            return "mtf-high"
        elif "moderate" in confidence_lower:
            return "mtf-moderate"
        else:
            return "mtf-low"

    def _get_bias_class(self, bias: str | None) -> str:
        """Get CSS class for bias display."""
        if not bias:
            return "mtf-neutral"

        bias_lower = bias.lower()
        if bias_lower == "long":
            return "mtf-bullish"
        elif bias_lower == "short":
            return "mtf-bearish"
        else:
            return "mtf-neutral"

    def _generate_trading_guidance(self, mtf) -> str:
        """Generate actionable trading recommendations based on MTF analysis."""
        confidence_lower = (mtf.confidence or "").lower()
        bias_lower = (mtf.bias or "").lower()
        alignment_pct = mtf.alignment_pct

        guidance_lines = []

        # Overall recommendation
        if alignment_pct >= 80:
            if bias_lower == "long":
                guidance_lines.append("  ✅ [mtf-very-high]STRONG BULLISH SETUP[/mtf-very-high]")
                guidance_lines.append("     Look for pullback entries on lower timeframes")
            elif bias_lower == "short":
                guidance_lines.append("  ✅ [mtf-very-high]STRONG BEARISH SETUP[/mtf-very-high]")
                guidance_lines.append("     Look for rally entries on lower timeframes")
        elif alignment_pct >= 60:
            if bias_lower == "long":
                guidance_lines.append("  ⚠️  [mtf-high]MODERATE BULLISH BIAS[/mtf-high]")
                guidance_lines.append("     Wait for confirmation on entry timeframe")
            elif bias_lower == "short":
                guidance_lines.append("  ⚠️  [mtf-high]MODERATE BEARISH BIAS[/mtf-high]")
                guidance_lines.append("     Wait for confirmation on entry timeframe")
        else:
            guidance_lines.append("  ❌ [mtf-low]MIXED SIGNALS - STAY SIDELINED[/mtf-low]")
            guidance_lines.append("     Wait for better timeframe alignment")

        guidance_lines.append("")

        # Confidence-based guidance ("high" matches both "high" and "very_high")
        if "high" in confidence_lower:
            guidance_lines.append("  📊 [dim]High confidence trade setup[/dim]")
            guidance_lines.append("     Consider standard position sizing")
        elif "moderate" in confidence_lower:
            guidance_lines.append("  📊 [dim]Moderate confidence - reduce risk[/dim]")
            guidance_lines.append("     Consider 50% position sizing")
        else:
            guidance_lines.append("  📊 [dim]Low confidence - avoid or paper trade[/dim]")
            guidance_lines.append("     Not recommended for real capital")

        guidance_lines.append("")
        guidance_lines.append("  💡 [dim]Pro Tip: Only trade WITH the higher timeframe trend[/dim]")

        return "\n".join(guidance_lines)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "close-button":
            self.dismiss()
