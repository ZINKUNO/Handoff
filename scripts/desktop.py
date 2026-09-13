#!/usr/bin/env python3
# Copyright (c) 2026 ZINKUNO
# SPDX-License-Identifier: MIT
"""Open Handoff as a desktop app: `python scripts/desktop.py`."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from handoff.desktop import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
