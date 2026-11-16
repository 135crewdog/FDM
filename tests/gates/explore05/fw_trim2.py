"""Fixture exploration (JSBSim defaults, native): angle of attack and elevator for level flight without JSBSim's
trim routine (which fails for the c310). Solves wdot = 0 and qdot = 0 by Newton's method on (alpha, elevator
command), reading the accelerations of a freshly initialised state (no stepping except one step after the engines
are set running). The throttle is given, not solved.
usage: ... fw_trim2.py <model> <kts> <flap> <throttle>
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pylib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native  # noqa: E402
from triallog import log  # noqa: E402

IC = {"c172x": "reset00", "f16": "reset00", "c310": "reset00", "737": "reset00"}
# Landing configuration. A kinematic component (flaps, gear) reads its state back from its output property, so the
# output property is preset as well as the command; otherwise the flaps would start at zero and travel.
CONFIG = {"c172x": {"fcs/flap-cmd-norm": 1, "fcs/flap-pos-deg": 30},
          "c310": {"fcs/flap-cmd-norm": 1, "fcs/flap-pos-deg": 45, "gear/gear-cmd-norm": 1, "gear/gear-pos-norm": 1},
          "737": {"fcs/flap-cmd-norm": 1, "fcs/flap-pos-norm": 1, "gear/gear-cmd-norm": 1, "gear/gear-pos-norm": 1},
          "f16": {"gear/gear-cmd-norm": 1, "gear/gear-pos-norm": 1}}


def accel(model, kts, thr, alpha, de, hz=480, h=200.0, steps=1):
    f = native.new_fdm(dt=1.0 / hz)
    assert f.load_model(model) and f.load_ic(IC[model], True)
    for p, v in {"ic/h-agl-ft": h, "ic/vc-kts": kts, "ic/psi-true-deg": 0, "ic/phi-deg": 0, "ic/alpha-deg": alpha, "ic/gamma-deg": 0,
                 "fcs/elevator-cmd-norm": de, **CONFIG[model]}.items():
        f[p] = v
    assert f.run_ic()
    for i in range(4):
        if f.get_property_manager().hasNode(f"fcs/throttle-cmd-norm[{i}]"):
            f[f"fcs/throttle-cmd-norm[{i}]"] = thr
            f[f"fcs/throttle-pos-norm[{i}]"] = thr
    f["propulsion/set-running"] = -1
    for i in range(4):
        if f.get_property_manager().hasNode(f"fcs/throttle-cmd-norm[{i}]"):
            f[f"fcs/throttle-cmd-norm[{i}]"] = thr
            f[f"fcs/throttle-pos-norm[{i}]"] = thr
    for _ in range(steps):
        f.run()
    return f["accelerations/wdot-ft_sec2"], f["accelerations/qdot-rad_sec2"], f["accelerations/udot-ft_sec2"], f


def solve(model, kts, thr):
    a, de = 4.0, 0.0
    for it in range(12):
        w0, q0, u0, f = accel(model, kts, thr, a, de)
        if abs(w0) < 1e-6 and abs(q0) < 1e-8:
            break
        wa, qa, _, _ = accel(model, kts, thr, a + 0.01, de)
        wd, qd, _, _ = accel(model, kts, thr, a, de + 0.001)
        j = [[(wa - w0) / 0.01, (wd - w0) / 0.001], [(qa - q0) / 0.01, (qd - q0) / 0.001]]
        det = j[0][0] * j[1][1] - j[0][1] * j[1][0]
        a -= (j[1][1] * w0 - j[0][1] * q0) / det
        de -= (-j[1][0] * w0 + j[0][0] * q0) / det
    pm = f.get_property_manager()
    get = lambda p: f[p] if pm.hasNode(p) else None  # noqa: E731
    rec = dict(model=model, kts=kts, throttle=thr, iterations=it, alpha_deg=a, elevator_cmd=de, wdot=w0, qdot=q0, udot=u0,
               theta_deg=f["attitude/theta-deg"], vt_fps=f["velocities/vt-fps"], elevator_pos_rad=get("fcs/elevator-pos-rad"),
               thrust=[get("propulsion/engine/thrust-lbs"), get("propulsion/engine[1]/thrust-lbs")],
               rpm=[get("propulsion/engine/engine-rpm"), get("propulsion/engine[1]/engine-rpm")], n2=[get("propulsion/engine/n2")],
               flap=[get("fcs/flap-pos-deg"), get("fcs/flap-pos-norm")], gear=get("gear/gear-pos-norm"))
    log("level-flight alpha and elevator by Newton on fresh initial states (no JSBSim trim), landing configuration preset, defaults", **rec)
    return rec


if __name__ == "__main__":
    a = sys.argv[1:]
    r = solve(a[0], float(a[1]), float(a[2]))
    print(r)
