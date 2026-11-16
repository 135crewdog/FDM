"""Session 05, after the independent review's verdict (a diagnostic, not a gate): does the stiff-moment headroom
measured with dampers (damping_headroom.py) also hold for SPRINGS? A roll moment -k*angle - c*rate on a body of unit
inertia, natural frequency w and damping ratio z, 10 s. Exact answer: an oscillation whose envelope is exp(-z*w*t).
Reported: "died away" if the oscillation is below 1% of its start in the last second; otherwise its size there
divided by the exact envelope's (1.00 = right; above 1 = the scheme adds energy); "blew up" = non-finite, or the
body turned past 3 rad (it starts at 0.2). G7's probe procedure is used
unchanged, with the moment computed inside JSBSim ("core") and written from outside every step ("external").
Native. usage: PYTHONPATH=build/native/patched .venv/bin/python tests/gates/diag/spring_headroom.py
"""
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import sim05  # noqa: E402

RUNS = [("c2-mid-g", 1200), ("c3-ab4-g", 960), ("floor-g", 1200)]
OMEGAS = [10, 20, 40, 80, 160]
ZETAS = [0.3, 0.1, 0.03, 0.0]
SECONDS = 10.0
tmp = Path(tempfile.mkdtemp(prefix="fdm-spring-"))
print("# Springs: size of the oscillation in the last second, relative to the exact answer's (1.00 = right)")
print(f"# {sim05.native.describe()}")
for where in ("core", "external"):
    print()
    print(f"## Moment {'computed inside JSBSim' if where == 'core' else 'written from outside before every step (one step late)'}")
    print("| configuration | step rate | damping ratio | " + " | ".join(f"{w} rad/s" for w in OMEGAS) + " |")
    print("|---|---|---|" + "---|" * len(OMEGAS))
    for name, hz in RUNS:
        cfg = sim05.CONFIGS[name]
        for z in ZETAS:
            cells = []
            for w in OMEGAS:
                sim05.G5["G7"]["probe_cases"]["sweep"] = {"kind": "spring", "omega_rad_s": float(w), "zeta": float(z), "p0_rad_s": 0.0, "phi0_rad": 0.2, "seconds": SECONDS}
                out = tmp / "p.f64"
                sim05.forced_probe("sweep", where, hz, cfg, out, tempfile.mkdtemp(prefix="fdm-sp-"))
                a = np.fromfile(out, dtype="<f8").reshape(-1, len(sim05.PROBE_COLS))
                t, phi = a[:, 0] - a[0, 0], a[:, 4]
                start = 0.2
                last = t >= SECONDS - max(1.0, 2.0 * math.pi / w)
                if not np.isfinite(a).all() or len(a) < SECONDS * hz or np.abs(phi).max() > 3.0:
                    cells.append("**blew up**")      # non-finite, or the body turned past 3 rad (it started at 0.2)
                    continue
                size = np.abs(phi[last]).max()
                exact = start * math.exp(-z * w * (SECONDS - max(1.0, 2.0 * math.pi / w)))
                if size < 0.01 * start:
                    cells.append("died away")        # below 1% of its start, as the exact answer is or soon will be
                elif exact < 0.001 * start:
                    cells.append(f"**did not die away** ({size:.2g} rad left)")   # the exact answer has
                else:
                    cells.append(f"{size / exact:.2f}")
            print(f"| `{name}` | {hz} Hz | {z:g} | " + " | ".join(cells) + " |", flush=True)
