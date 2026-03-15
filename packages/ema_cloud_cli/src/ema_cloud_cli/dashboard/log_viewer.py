"""
Log viewer widget for displaying application logs.
"""

import logging
from collections import deque

from textual.widgets import RichLog


class LogViewer(RichLog):
    """
    Custom log viewer widget that displays application logs.
    """

    def __init__(self, max_lines: int = 100, **kwargs):
        super().__init__(max_lines=max_lines, wrap=False, highlight=True, markup=True, **kwargs)
        self.max_lines = max_lines

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        # Add a welcome message to verify the widget is working
        self.write("[dim]Log viewer ready. Waiting for log messages...[/dim]")


class TextualLogHandler(logging.Handler):
    """
    Custom logging handler that sends log records to the LogViewer widget.
    """

    def __init__(self, log_viewer: LogViewer):
        super().__init__()
        self.log_viewer = log_viewer
        self._log_buffer: deque[str] = deque(maxlen=100)
        self._is_active = True

        # Set formatter for consistent log format
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )
        self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the log viewer."""
        if not self._is_active:
            return

        try:
            msg = self.format(record)

            # Color code by log level
            if record.levelno >= logging.ERROR:
                styled_msg = f"[bold red]{msg}[/bold red]"
            elif record.levelno >= logging.WARNING:
                styled_msg = f"[bold yellow]{msg}[/bold yellow]"
            elif record.levelno >= logging.INFO:
                styled_msg = f"[cyan]{msg}[/cyan]"
            else:
                styled_msg = f"[dim]{msg}[/dim]"

            # Add to buffer for when viewer becomes available
            self._log_buffer.append(styled_msg)

            # Write to viewer if available
            # RichLog widget uses write() method for adding content
            try:
                if self.log_viewer:
                    self.log_viewer.write(styled_msg)
            except (AttributeError, RuntimeError):
                # Silently fail if widget is not ready
                pass

        except (AttributeError, RuntimeError, ValueError):
            self.handleError(record)

    def flush_buffer(self) -> None:
        """Flush buffered logs to the viewer."""
        if self.log_viewer and self._log_buffer:
            for msg in self._log_buffer:
                self.log_viewer.write(msg)
            self._log_buffer.clear()

    def deactivate(self) -> None:
        """Deactivate the handler."""
        self._is_active = False
