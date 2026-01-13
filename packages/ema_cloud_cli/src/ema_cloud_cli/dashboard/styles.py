"""
CSS styles for the terminal dashboard.
"""

DASHBOARD_CSS = """
Screen {
    layout: grid;
    grid-size: 1;
    grid-rows: auto 1fr auto auto;
}

Header {
    dock: none;
}

Footer {
    dock: none;
    height: 1;
}

#content {
    layout: horizontal;
}

#etf-container {
    width: 2fr;
    border: solid $primary;
    padding: 0 1;
}

#signals-container {
    width: 1fr;
    border: solid $secondary;
    padding: 0 1;
}

#logs-container {
    width: 1fr;
    border: solid $accent;
    padding: 0 1;
}

#etf-table {
    height: 100%;
}

#signals-table {
    height: 100%;
}

.table-title {
    text-align: center;
    text-style: bold;
    padding: 1 0;
    color: $text;
    background: $surface;
}

#etf-title {
    color: cyan;
}

#signals-title {
    color: magenta;
}

#logs-title {
    color: yellow;
}

#log-viewer {
    height: 100%;
    border: none;
}

#status-bar {
    height: 1;
    padding: 0 1;
    background: $surface;
    color: $text;
}

DataTable {
    height: 1fr;
}

DataTable > .datatable--cursor {
    background: $accent;
}

/* Row styling for trends */
.bullish {
    color: $success;
}

.bearish {
    color: $error;
}

.neutral {
    color: $text-muted;
}

SettingsScreen {
    align: center middle;
}

#settings-panel {
    width: 90%;
    height: 90%;
    border: tall $primary;
    background: $panel;
}

#settings-title {
    text-align: center;
    text-style: bold;
    padding: 1 0;
    color: $text;
    background: $surface;
}

#settings-tabs {
    height: 1fr;
}

.settings-tab {
    padding: 1;
}

.section-title {
    text-style: bold;
    padding: 1 0 0 0;
    color: $text;
}

.form-row {
    layout: horizontal;
    height: auto;
    padding: 0 0 1 0;
}

.form-label {
    width: 30;
    color: $text;
}

.form-control {
    width: 1fr;
}

#active_sectors {
    height: 14;
    border: tall $border;
}

#settings-actions {
    height: auto;
    padding: 1 0;
    align: center middle;
}

#settings-actions Button {
    margin: 0 1;
}
"""
