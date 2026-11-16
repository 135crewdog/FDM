"""Fixture exploration (JSBSim defaults, native): level-flight trim of each fixed-wing aircraft in its landing
configuration, to get the angle of attack, elevator and throttle that an approach at that speed needs.
usage: PYTHONPATH=build/native/patched .venv/bin/python tests/gates/explore05/fw_trim.py <model> <kts> [flap] [gamma_deg]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "pylib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native  # noqa: E402
from triallog import log  # noqa: E402

IC = {"c172x": "reset00", "f16": "reset00", "c310": "reset00", "737": "reset00"}


def trim(model, kts, flap=1.0, gamma=0.0, h=200.0, hz=480):
    f = native.new_fdm(dt=1.0 / hz)
    assert f.load_model(model) and f.load_ic(IC[model], True)
    f["ic/h-agl-ft"] = h
    f["ic/vc-kts"] = kts
    f["ic/gamma-deg"] = gamma
    f["ic/psi-true-deg"] = 0
    f["ic/phi-deg"] = 0
    f["fcs/flap-cmd-norm"] = flap
    f["fcs/flap-pos-norm"] = flap
    f["gear/gear-cmd-norm"] = 1
    f["gear/gear-pos-norm"] = 1
    assert f.run_ic()
    f["propulsion/set-running"] = -1
    ok = True
    try:
        f.do_trim(1)  # longitudinal
    except Exception as e:  # noqa: BLE001
        ok = False
        err = str(e)
    pm = f.get_property_manager()
    get = lambda p: f[p] if pm.hasNode(p) else None  # noqa: E731
    rec = dict(model=model, kts=kts, flap=flap, gamma_deg=gamma, h_agl=h, hz=hz, trimmed=ok,
               alpha_deg=get("aero/alpha-deg"), theta_deg=get("attitude/theta-deg"),
               elevator_cmd=get("fcs/elevator-cmd-norm"), pitch_trim_cmd=get("fcs/pitch-trim-cmd-norm"),
               elevator_pos_rad=get("fcs/elevator-pos-rad"), throttle=[get("fcs/throttle-cmd-norm"), get("fcs/throttle-cmd-norm[1]")],
               flap_pos=[get("fcs/flap-pos-norm"), get("fcs/flap-pos-deg")], gear_pos=get("gear/gear-pos-norm"),
               u_fps=get("velocities/u-fps"), w_fps=get("velocities/w-fps"), vd_fps=get("velocities/v-down-fps"),
               vt_fps=get("velocities/vt-fps"), weight=get("inertia/weight-lbs"),
               thrust=[get("propulsion/engine/thrust-lbs"), get("propulsion/engine[1]/thrust-lbs")],
               n2=[get("propulsion/engine/n2"), get("propulsion/engine[1]/n2")],
               rpm=[get("propulsion/engine/engine-rpm"), get("propulsion/engine[1]/engine-rpm")],
               running=[get("propulsion/engine/set-running"), get("propulsion/engine[1]/set-running")],
               udot=get("accelerations/udot-ft_sec2"), wdot=get("accelerations/wdot-ft_sec2"), qdot=get("accelerations/qdot-rad_sec2"))
    if not ok:
        rec["error"] = err
    log("level trim in landing configuration (do_trim longitudinal), JSBSim defaults", **rec)
    return rec


if __name__ == "__main__":
    a = sys.argv[1:]
    r = trim(a[0], float(a[1]), float(a[2]) if len(a) > 2 else 1.0, float(a[3]) if len(a) > 3 else 0.0)
    for k, v in r.items():
        print(f"  {k}: {v}")
