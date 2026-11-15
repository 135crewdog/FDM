"""Diagnostic (not a gate): why does the c310 not settle at 120 Hz with AB4 body rates even with
integrator-aware friction (candidate 1)?  Ablation: remove ALL friction, change one integrator, change the rate.
usage: PYTHONPATH=build/native/patched python tests/gates/diag/c310_rest.py
Reads: largest |p|, |q|, |r| (rad/s) in the last 10 s of 60 s at rest."""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "pylib"))
import native  # noqa: E402
G = json.loads((HERE.parent / "gates.json").read_text())


def run(model, hz, rate, aware, nofric=False, trans=None, secs=60):
    f = native.new_fdm(dt=1 / hz)
    f.load_model(model)
    f.load_ic(G["aircraft"][model], True)
    f["simulation/integrator/rate/rotational"] = rate
    f["simulation/integrator/position/rotational"] = 7
    f["simulation/integrator/friction-aware"] = aware
    if trans:
        f["simulation/integrator/rate/translational"] = trans
    f.run_ic()
    if nofric:
        pm = f.get_property_manager()
        for k in range(int(f["gear/num-units"])):
            for base in ("gear", "contact"):
                for c in ("static_friction_coeff", "dynamic_friction_coeff", "rolling_friction_coeff"):
                    if pm.hasNode(f"{base}/unit[{k}]/{c}"):
                        f[f"{base}/unit[{k}]/{c}"] = 0.0
    mx = [0.0, 0.0, 0.0]
    for k in range(secs * hz):
        f.run()
        if k >= (secs - 10) * hz:
            for i, p in enumerate("pqr"):
                mx[i] = max(mx[i], abs(f[f"velocities/{p}-rad_sec"]))
    return "p %.1e  q %.1e  r %.1e" % tuple(mx)


print("#", native.describe())
print("# c310 at rest, Buss 2 attitude; largest body rates (rad/s) in the last 10 s of 60 s")
for label, args in [
    ("120 Hz, AB4 rates, friction-aware 1 (candidate 1)         ", dict(hz=120, rate=5, aware=1)),
    ("120 Hz, AB4 rates, friction-aware 1, ALL friction removed ", dict(hz=120, rate=5, aware=1, nofric=True)),
    ("120 Hz, AB4 rates, friction-aware 0, ALL friction removed ", dict(hz=120, rate=5, aware=0, nofric=True)),
    ("120 Hz, AB3 rates, friction-aware 1                       ", dict(hz=120, rate=4, aware=1)),
    ("120 Hz, AB4 rates, friction-aware 1, translation by Euler ", dict(hz=120, rate=5, aware=1, trans=1)),
    ("150 Hz, AB4 rates, friction-aware 1                       ", dict(hz=150, rate=5, aware=1)),
    ("240 Hz, AB4 rates, friction-aware 1                       ", dict(hz=240, rate=5, aware=1)),
]:
    print(label, run("c310", **args), flush=True)
