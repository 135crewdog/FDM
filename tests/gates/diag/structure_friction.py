"""Session 05, step 3: the SECOND crash mechanism (REVIEW-codex-04): friction on airframe (STRUCTURE) contact points
with AB4 body rates. Not a gate; a test of an explanation by removing the cause.

JSBSim's own script scripts/f16_test.xml ends with the f16 on the ground on its airframe points (about 127 s).
With AB4 body rates throughout, the review saw the rates pass 1e6 rad/s at 127.98 s (120 Hz) and 128.03 s
(240 Hz), with wheel compression bounded, and no runaway when the airframe points' friction was set to zero.
Here: the same trajectory for AB4 throughout, c3-ab4 (Euler on contact), c2-mid (midpoint) and the floor's
integrators, with the strut limits of patch 0004 off and on, at four step rates; and for AB4 the ablation
(airframe friction coefficients set to zero at 127 s).
usage: PYTHONPATH=build/native/patched .venv/bin/python tests/gates/diag/structure_friction.py
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "pylib"))
import native  # noqa: E402

CONFIGS = json.loads((HERE.parent / "configs.json").read_text())
SETS = {"AB4 throughout": {"simulation/integrator/rate/rotational": 5, "simulation/integrator/position/rotational": 7},
        "c3-ab4": CONFIGS["c3-ab4"]["properties"], "c2-mid": CONFIGS["c2-mid"]["properties"],
        "floor's integrators": {"simulation/integrator/rate/rotational": 1, "simulation/integrator/position/rotational": 7}}
T_END, T_ABLATE = 135.0, 127.0


def run(props, hz, limits, ablate):
    f = native.new_fdm()
    assert f.load_script("scripts/f16_test.xml", 1.0 / hz)
    for p, v in props.items():
        f[p] = v
    if limits:
        f["gear/strut-limits/enabled"] = 1
    assert f.run_ic()
    pm = f.get_property_manager()
    n = int(f["gear/num-units"])
    struct = [k for k in range(n) if pm.hasNode(f"contact/unit[{k}]/WOW")]
    bogey = [k for k in range(n) if pm.hasNode(f"gear/unit[{k}]/WOW")]
    rate = [pm.get_node(f"velocities/{x}-rad_sec").get_double_value for x in "pqr"]
    wow_s = [pm.get_node(f"contact/unit[{k}]/WOW").get_double_value for k in struct]
    wow_b = [pm.get_node(f"gear/unit[{k}]/WOW").get_double_value for k in bogey]
    first = None
    peak = 0.0
    done = False
    s_steps = b_steps = 0
    t = 0.0
    while t < T_END:
        t = f.get_sim_time()
        if ablate and not done and t >= T_ABLATE:
            for k in struct:
                f[f"contact/unit[{k}]/static_friction_coeff"] = 0.0
                f[f"contact/unit[{k}]/dynamic_friction_coeff"] = 0.0
            done = True
        try:
            if not f.run():
                break
        except Exception as e:  # noqa: BLE001
            first = first or (f.get_sim_time(), f"exception: {str(e)[:60]}")
            break
        w = max(abs(g()) for g in rate)
        if t > 120.0:
            s_steps += any(g() > 0.5 for g in wow_s)
            b_steps += any(g() > 0.5 for g in wow_b)
        if not math.isfinite(w) or w > 1e6:
            first = (f.get_sim_time(), "body rate above 1e6 rad/s" if math.isfinite(w) else "non-finite")
            break
        if t > 120.0:
            peak = max(peak, w)
    return first, peak, s_steps, b_steps, f.get_sim_time()


if __name__ == "__main__":
    print("# The f16 at the end of scripts/f16_test.xml (on the ground on its airframe points), native")
    print(f"# {native.describe()}")
    print("| body-rate scheme | strut limits | airframe friction | step rate | first runaway (s) | largest body rate after 120 s (rad/s) | steps with airframe / wheel contact after 120 s |")
    print("|---|---|---|---|---|---|---|")
    for name, props in SETS.items():
        for limits in (False, True):
            for ablate in ((False, True) if name == "AB4 throughout" else (False,)):
                for hz in (120, 240, 480, 1000):
                    first, peak, ss, bs, t = run(props, hz, limits, ablate)
                    print(f"| {name} | {'on' if limits else 'off'} | {'zero from 127 s' if ablate else 'as in the file'} | {hz} Hz | "
                          f"{'none to %.0f s' % t if first is None else '%.3f (%s)' % first} | {peak:.3g} | {ss} / {bs} |", flush=True)
