"""Fixture exploration (JSBSim DEFAULT integrators against the reference at 9600 Hz): the real aircraft at the fastest
point of their envelope with small doublets. Does the fixture fly (stays in its envelope, finite), and how far are
JSBSim's defaults at the gate's step rates from the reference? Logged. usage: ... fast_try.py [model ...]"""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
import sim05  # noqa: E402
from triallog import log  # noqa: E402
S = Path("/tmp/claude-0/-home-user-FDM/0bbef996-2fa3-51f1-933b-53a1a733c414/scratchpad")
REF = {"properties": {"simulation/integrator/rate/rotational": 5, "simulation/integrator/position/rotational": 7}}
DEF = {"properties": {}}
cols = sim05.G5["G7"]["flight_columns"]


def run(model, hz, cfg):
    out = S / "fast.f64"
    sim05.fast_flight(model, hz, cfg, out)
    return np.fromfile(out, dtype="<f8").reshape(-1, len(cols))


def wrap(d):
    return (d + np.pi) % (2 * np.pi) - np.pi


for model in sys.argv[1:] or list(sim05.G5["G7"]["fast_points"]):
    ref = run(model, 9600, REF)
    ref2 = run(model, 4800, REF)
    print(model, "reference: rows", len(ref), "finite", bool(np.isfinite(ref).all()), "alpha range deg", np.degrees(ref[:, 11]).min().round(2), np.degrees(ref[:, 11]).max().round(2),
          "beta max deg", np.degrees(np.abs(ref[:, 12])).max().round(2), "max rate rad/s", np.abs(ref[:, 1:4]).max().round(3), "phi/theta range deg", np.degrees(ref[:, 4]).min().round(1), np.degrees(ref[:, 4]).max().round(1),
          np.degrees(ref[:, 5]).min().round(1), np.degrees(ref[:, 5]).max().round(1), "vc end", ref[-1, 13].round(1), "h end", ref[-1, 10].round(0))
    for label, hz, cfg in (("reference at 4800", 4800, REF), ("defaults", 480, DEF), ("defaults", 960, DEF), ("defaults", 1200, DEF), ("defaults", 9600, DEF)):
        a = ref2 if label.startswith("reference") else run(model, hz, cfg)
        n = min(len(a), len(ref))
        drate = np.abs(a[:n, 1:4] - ref[:n, 1:4]).max()
        datt = np.degrees(np.abs(wrap(a[:n, 4:7] - ref[:n, 4:7])).max())
        rec = dict(model=model, run=label, hz=hz, rows=len(a), finite=bool(np.isfinite(a).all()), max_rate_diff_rad_s=float(drate), max_attitude_diff_deg=float(datt),
                   end_attitude_diff_deg=float(np.degrees(np.abs(wrap(a[n - 1, 4:7] - ref[n - 1, 4:7])).max())))
        log("fast-flight fixture against the 9600 Hz reference (AB4 rates, Buss 2 attitude)", **rec)
        print("  ", rec)
