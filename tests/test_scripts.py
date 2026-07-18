"""Pytest-facing v3 integration test."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v3_smoke_suite() -> None:
    subprocess.run([sys.executable, "tests/run_smoke.py"], cwd=ROOT, check=True)
