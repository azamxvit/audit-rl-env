"""The demo tour (make demo) runs offline and shows all seven scenes."""

import subprocess
import sys

from conftest import ROOT


def test_demo_tour_runs_offline():
    out = subprocess.run(
        [sys.executable, "scripts/demo_tour.py"], cwd=ROOT, capture_output=True, text=True, timeout=120, check=True
    ).stdout
    assert "[8/8]" in out and "policy saw: return=0.0  info={}" in out
    assert "{'accepted': True}, reward 0.0" in out and "'return': 0.998" in out
    assert "flag_all (attack)        4  TP=0 FP=30" in out
