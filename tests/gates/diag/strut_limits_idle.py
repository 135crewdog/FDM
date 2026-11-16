"""Session 05, step 3: do the strut limits of patch 0004 ever act in a landing within the aircraft's limits?
Flies every G2d landing with the floor's integrators and the limits switched on, and reads the patch's three
counters at the end of each. (The frozen runner does not record them; it is used unchanged, and the simulation it
created is picked up from tests/pylib/native.py.) Native.
usage: PYTHONPATH=build/native/patched .venv/bin/python tests/gates/diag/strut_limits_idle.py [hz ...]
"""
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import sim05  # noqa: E402

native, G5 = sim05.native, sim05.G5
made = []
_new = native.new_fdm


def new_fdm(*a, **k):
    f = _new(*a, **k)
    made.append(f)
    return f


native.new_fdm = new_fdm
CFG = sim05.CONFIGS["floor-g"]
COUNTERS = ["projection-floored", "force-capped", "travel-exceeded"]
tmp = Path(tempfile.mkdtemp(prefix="fdm-strut-"))
print("# Strut-limit counters at the end of every G2d landing (floor's integrators, limits on)")
print(f"# {native.describe()}")
print("| step rate | landings | landings in which a limit acted | counters summed (projection floored, force capped, travel exceeded) |")
print("|---|---|---|---|")
for hz in [int(a) for a in sys.argv[1:]] or [480, 1000]:
    n = acted = 0
    total = [0.0, 0.0, 0.0]
    for model in G5["G2d"]["aircraft"]:
        for case in G5["G2d"].get("cases_by_aircraft", {}).get(model, G5["G2d"]["cases"]):
            made.clear()
            out = tmp / "x.f64"
            (sim05.heli_landing(case, hz, CFG, out) if model == "ah1s" else sim05.landing(model, case, hz, CFG, out))
            f = made[-1]
            assert f["gear/strut-limits/enabled"] == 1
            c = [f[f"gear/strut-limits/{k}"] for k in COUNTERS]
            n += 1
            acted += any(x > 0 for x in c)
            total = [a + b for a, b in zip(total, c)]
            if any(x > 0 for x in c):
                print(f"  {model} {case}: {c}")
    print(f"| {hz} Hz | {n} | {acted} | {total[0]:.0f}, {total[1]:.0f}, {total[2]:.0f} |", flush=True)
