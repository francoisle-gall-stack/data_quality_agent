#!/usr/bin/env python3
"""Launch business Streamlit dashboard."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
app = ROOT / "src" / "dq_platform" / "app" / "business_dashboard.py"
sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app)]))
