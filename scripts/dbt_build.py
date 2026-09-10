#!/usr/bin/env python3
"""Run dbt build."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DBT_DIR = ROOT / "dbt"

env = os.environ.copy()
env["DBT_PROFILES_DIR"] = str(DBT_DIR)
env["DBT_PROJECT_DIR"] = str(DBT_DIR)
env.setdefault("DUCKDB_PATH", str(ROOT / "data" / "warehouse.duckdb"))

cmd = ["dbt", "build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
sys.exit(subprocess.call(cmd, env=env))
