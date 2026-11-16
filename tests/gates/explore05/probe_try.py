"""Fixture exploration (JSBSim DEFAULT integrators only): do the synthetic forced-flight probes behave as their exact
answers say, and does the measuring code work? Logged. usage: ... probe_try.py [hz ...]"""
import math
import sys
import tempfile
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
import sim05  # noqa: E402
from triallog import log  # noqa: E402
REF = {"properties": {}}
S = Path("/tmp/claude-0/-home-user-FDM/0bbef996-2fa3-51f1-933b-53a1a733c414/scratchpad")


def exact(case, t):
    if case["kind"] == "damping":
        return case["p0_rad_s"] * np.exp(-case["rate_per_s"] * t), None
    w, z = case["omega_rad_s"], case["zeta"]
    wd = w * math.sqrt(1 - z * z)
    e = np.exp(-z * w * t)
    phi = case["phi0_rad"] * e * (np.cos(wd * t) + z * w / wd * np.sin(wd * t))
    p = -case["phi0_rad"] * e * (w * w / wd) * np.sin(wd * t)
    return p, phi


for hz in [int(a) for a in sys.argv[1:]] or [480, 960, 1200]:
    for name, case in sim05.G5["G7"]["probe_cases"].items():
        for where in ("core", "external"):
            root = tempfile.mkdtemp(prefix="probe05-")
            out = S / "probe.f64"
            sim05.forced_probe(name, where, hz, REF, out, root)
            a = np.fromfile(out, dtype="<f8").reshape(-1, len(sim05.PROBE_COLS))
            t, p, phi = a[:, 0], a[:, 1], a[:, 4]
            pe, phie = exact(case, t)
            if case["kind"] == "damping":
                err, amp, peak = np.abs(p - pe).max() / case["p0_rad_s"], case["p0_rad_s"], np.abs(p).max() / case["p0_rad_s"]
            else:
                err, amp, peak = np.abs(phi - phie).max() / case["phi0_rad"], case["phi0_rad"], np.abs(phi).max() / case["phi0_rad"]
            rec = dict(case=name, where=where, hz=hz, rows=len(a), max_error_over_initial=float(err), peak_over_initial=float(peak),
                       other_axes_max=float(np.abs(a[:, [2, 3, 5, 6]]).max()), end_value=float((p if case["kind"] == "damping" else phi)[-1]))
            log("synthetic forced-flight probe, JSBSim defaults", **rec)
            print(rec)
