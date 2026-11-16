"""Fixture exploration (JSBSim defaults, native): which way does each control move the aircraft? In approach
configuration at 500 ft, one control is stepped for 1 s and the body rate it produces is read. Logged."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
import sim05  # noqa: E402
from triallog import log  # noqa: E402
REF = {"properties": {}}
for model in sys.argv[1:] or ["c172x", "c310", "737", "f16"]:
    ac = sim05.G5["aircraft"][model]; ap = ac["approach"]
    out = {}
    for ctl, rate in (("fcs/elevator-cmd-norm", "velocities/q-rad_sec"), ("fcs/aileron-cmd-norm", "velocities/p-rad_sec"), ("fcs/rudder-cmd-norm", "velocities/r-rad_sec")):
        ic = {"ic/psi-true-deg": 0.0, "ic/phi-deg": 0.0, "ic/theta-deg": ap["alpha_deg"], "ic/vn-fps": ap["vt_fps"], "ic/ve-fps": 0.0, "ic/vd-fps": 0.0, "ic/h-agl-ft": 500.0}
        res = []
        for step in (0.0, 0.2):
            f = sim05.start(model, 480, REF, ic, ac["preset"], ac["engines"], ap["throttle"])
            f["fcs/elevator-cmd-norm"] = ap["elevator"]
            for k in range(480):
                if k >= 240:
                    f[ctl] = (ap["elevator"] if "elevator" in ctl else 0.0) + step
                f.run()
            res.append((f[rate], f["attitude/phi-deg"], f["attitude/theta-deg"], f["attitude/psi-deg"], f["velocities/v-down-fps"]))
        out[ctl] = dict(rate_change_per_0p2=res[1][0] - res[0][0], baseline_after_1s=dict(rate=res[0][0], phi=res[0][1], theta=res[0][2], psi=res[0][3], vdown=res[0][4]))
    log("control sign test: +0.2 step for 0.5 s at approach condition, body-rate change against no step, defaults", model=model, result=out)
    print(model, {k: round(v["rate_change_per_0p2"], 4) for k, v in out.items()}, "baseline(elevator run):", {k: round(v, 3) for k, v in out["fcs/elevator-cmd-norm"]["baseline_after_1s"].items()})
