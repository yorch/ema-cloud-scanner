#!/usr/bin/env python
"""
Development runner for EMA Cloud Scanner.

Allows running the scanner without installing packages.

Usage (with venv activated):
    python run.py [args...]

Usage (without activation):
    .venv/bin/python run.py [args...]

Examples:
    python run.py --once
    python run.py --style swing --etfs XLK XLF
    python run.py --help
"""
import sys
from pathlib import Path

# Add package sources to path
root = Path(__file__).parent
sys.path.insert(0, str(root / "packages/ema_cloud_lib/src"))
sys.path.insert(0, str(root / "packages/ema_cloud_cli/src"))

from ema_cloud_cli.cli import run

if __name__ == "__main__":
    run()
