"""Two diagnostics (not gates) behind explanations in REPORT-03.
usage: PYTHONPATH=build/native/patched python tests/gates/diag/creep_and_startup.py

1. Does the slow creep at rest with the 2010 formula (patch mode 2) come from the Earth's rotation?
   Prediction: creep speed = (b0 - 1) * dt * (horizontal part of the centripetal acceleration), b0 = 1.5 for
   the AB2 translational integrator. The horizontal part is W^2 * R * sin(lat) * cos(lat): zero at the equator
   and at the poles, largest at 45 degrees. So the creep in 10 s should follow sin(lat)*cos(lat).
2. Is the energy change of a torque-free body with AB4 body rates a start-up effect (JSBSim starts the
   multistep history with copies of the first derivative), rather than a steady drift?
   Printed: relative energy change after 4 steps, at 1, 10, 30 and 60 s, and the largest over 60 s."""
import json
import math
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "pylib"))
sys.path.insert(0, str(HERE.parent))
import native  # noqa: E402
import run_native as R  # noqa: E402
G = R.G
print("#", native.describe())
print("# 1. c172x at rest, 120 Hz, AB4 body rates, Buss 2; horizontal movement in the last 10 s of 60 s (ft)")
print("latitude   mode 1 (candidate 1)   mode 2 (2010 formula)   prediction for mode 2")
W, RE = 7.292115e-5, 20925646.0
for lat in (0, 20, 45, 70):
    out = []
    for mode in (1, 2):
        f = native.new_fdm(dt=1 / 120)
        f.load_model("c172x")
        f.load_ic("reset_at_rest", True)
        f["ic/lat-geod-deg"] = lat
        f["simulation/integrator/rate/rotational"] = 5
        f["simulation/integrator/position/rotational"] = 7
        f["simulation/integrator/friction-aware"] = mode
        f.run_ic()
        get = [f.get_property_manager().get_node(p).get_double_value for p in G["ecef"]]
        ref = None
        disp = 0.0
        for k in range(1, 60 * 120 + 1):
            f.run()
            if k >= 50 * 120:
                pos = [g() for g in get]
                if ref is None:
                    ref = pos
                    r = math.sqrt(sum(x * x for x in pos))
                    up = [x / r for x in pos]
                d = [a - b for a, b in zip(pos, ref)]
                dv = sum(a * b for a, b in zip(d, up))
                disp = max(disp, math.sqrt(max(0.0, sum(a * a for a in d) - dv * dv)))
        out.append(disp)
    pred = 0.5 * (1 / 120) * W * W * RE * abs(math.sin(math.radians(lat)) * math.cos(math.radians(lat))) * 10
    print(f"{lat:5d} deg      {out[0]:.2e}              {out[1]:.2e}               {pred:.2e}", flush=True)

print()
print("# 2. brick, spin F (200, 100, -50 deg/s), torque-free; relative change of rotational kinetic energy")
print("rate     body rates   after 4 steps   at 1 s      at 10 s     at 30 s     at 60 s     largest in 60 s")
root = R.rigid_root()
import numpy as np  # noqa: E402
for hz in (480, 1000):
    for rate, name in ((5, "AB4"), (4, "AB3")):
        f = native.new_fdm(root, dt=1 / hz)
        f.load_model("brick")
        f.load_ic("reset_Atmos_02", True)
        f["ic/h-sl-ft"] = 100000
        for p, w in zip(("ic/p-rad_sec", "ic/q-rad_sec", "ic/r-rad_sec"), (200, 100, -50)):
            f[p] = math.radians(w)
        f["simulation/integrator/rate/rotational"] = rate
        f["simulation/integrator/position/rotational"] = 7
        f.run_ic()
        J = np.asarray(f.get_mass_balance().get_J(), dtype=float).reshape(3, 3)
        get = [f.get_property_manager().get_node(p).get_double_value for p in R.OMEGA_I]
        T = lambda: 0.5 * float(np.array([g() for g in get]) @ J @ np.array([g() for g in get]))
        T0 = T()
        worst = at4 = 0.0
        at = {}
        for k in range(1, 60 * hz + 1):
            f.run()
            d = (T() - T0) / T0
            worst = max(worst, abs(d))
            if k == 4:
                at4 = d
            if k in (hz, 10 * hz, 30 * hz, 60 * hz):
                at[k // hz] = d
        print(f"{hz:5d} Hz   {name}          {at4:+.2e}       " + "   ".join(f"{at[t]:+.2e}" for t in (1, 10, 30, 60)) + f"   {worst:.2e}", flush=True)
