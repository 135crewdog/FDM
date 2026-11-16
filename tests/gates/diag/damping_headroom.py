"""Session 05, after the gates (a diagnostic, not a gate): how much headroom does each passing configuration have
under a stiff damping moment? G7 judges a damper of 180 per second. Here the damping rate is raised until G7's own
two stability conditions fail (grows above 1.05 times its start, or is not below 1% after 10 time constants), for
the moment computed inside JSBSim ("core") and written from outside before every step ("external", one step late,
the way the game's wing-strip forces arrive). Native; G7's probe procedure is used unchanged.
usage: PYTHONPATH=build/native/patched .venv/bin/python tests/gates/diag/damping_headroom.py
"""
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import sim05  # noqa: E402
import evaluate_05 as E  # noqa: E402

RATES = [180, 250, 300, 360, 430, 500, 600, 720, 860, 1000, 1200, 1500, 1800, 2200, 2600]
RUNS = [("c3-ab4-g", 960), ("c3-ab4-g", 1000), ("c2-mid-g", 1200), ("c2-mid-g", 960), ("floor-g", 960), ("floor-g", 1200)]
tmp = Path(tempfile.mkdtemp(prefix="fdm-headroom-"))
L = sim05.G5["G7"]["limits"]
print("# Largest damping rate (per second) that passes G7's stability conditions; G7 itself judges 180; the fastest measured on the test aircraft is 89")
print(f"# {sim05.native.describe()}")
print("| configuration | step rate | moment computed inside JSBSim | moment written from outside every step | theory (rate x step below) |")
print("|---|---|---|---|---|")
for name, hz in RUNS:
    cfg = sim05.CONFIGS[name]
    best = {}
    for where in ("core", "external"):
        ok_up_to = None
        for lam in RATES:
            sim05.G5["G7"]["probe_cases"]["sweep"] = {"kind": "damping", "rate_per_s": float(lam), "p0_rad_s": 0.5, "phi0_rad": 0.0, "seconds": 1.0}
            E.G5["G7"]["probe_cases"]["sweep"] = sim05.G5["G7"]["probe_cases"]["sweep"]
            out = tmp / "p.f64"
            sim05.forced_probe("sweep", where, hz, cfg, out, tempfile.mkdtemp(prefix="fdm-hr-"))
            m = E.probe_metrics(out)
            good = (m.get("error") is None and m.get("finite") and m.get("complete") and m["peak_over_initial"] <= L["max_peak_over_initial"]
                    and m["late_max_over_initial"] is not None and m["late_max_over_initial"] <= L["settled_fraction"])
            if not good:
                break
            ok_up_to = lam
        best[where] = ok_up_to
    ab4 = name.startswith("c3")
    print(f"| `{name}` | {hz} Hz | {best['core']} | {best['external']} | {'AB4: 0.3 -> %d' % (0.3 * hz) if ab4 else 'Euler-like: 2 -> %d (1 when one step late -> %d)' % (2 * hz, hz)} |", flush=True)
