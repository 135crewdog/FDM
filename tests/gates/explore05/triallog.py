"""Every fixture trial made before the session-05 gates are frozen is appended here (GATES-05.md lists them).
One JSON line per trial: what was tried, with which settings, and what came out. JSBSim's default integrators only."""
import json
import time
from pathlib import Path

LOG = Path(__file__).resolve().parents[3] / "results/05-fixture-trials.jsonl"


def log(what, **fields):
    rec = dict(when=time.strftime("%Y-%m-%dT%H:%M:%S"), what=what, **fields)
    with LOG.open("a") as s:
        s.write(json.dumps(rec) + "\n")
    return rec
