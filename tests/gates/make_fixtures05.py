"""Session 05, fixtures: find, for each fixed-wing aircraft and each descent rate, the angle of attack, elevator and
throttle of a steady descent at its approach speed in landing configuration (JSBSim's defaults, native).

Method: Newton's method on (alpha, elevator, throttle). Each evaluation settles the engines and actuators at that
flight condition (sim05.settle) and reads the forces and the pitching moment that are left over on the initial
conditions. JSBSim's own trim routine is not used: it fails for the c310, and the
WebAssembly binding does not have it. If the descent needs less than idle thrust, the throttle stays at 0 and
only alpha and elevator are solved (the aircraft then gains speed slowly).
usage: PYTHONPATH=build/native/patched .venv/bin/python tests/gates/make_fixtures05.py [model ...]   (prints JSON)
"""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "explore05"))
import sim05  # noqa: E402
from triallog import log  # noqa: E402

HZ = 480


def solve(model, sink, guess):
    a, e, t = guess
    free_t = True
    for it in range(25):
        fx, fz, m, f = sim05.trim_residual(model, sink, HZ, a, e, t)
        if abs(fz) < 1e-6 and abs(m) < 1e-6 and (abs(fx) < 1e-6 or not free_t):
            break
        da, de, dt = 0.05, 0.1, 0.02
        ra = sim05.trim_residual(model, sink, HZ, a + da, e, t)[:3]
        re = sim05.trim_residual(model, sink, HZ, a, e + de, t)[:3]
        if free_t:
            rt = sim05.trim_residual(model, sink, HZ, a, e, t + dt)[:3]
            import numpy as np
            J = np.array([[(ra[i] - r0) / da, (re[i] - r0) / de, (rt[i] - r0) / dt] for i, r0 in enumerate((fx, fz, m))])
            step = np.linalg.solve(J, -np.array([fx, fz, m]))
            a, e, t = a + step[0], e + step[1], t + step[2]
            if t < 0.0:
                t, free_t = 0.0, False
            t = min(t, 1.0)
        else:
            import numpy as np
            J = np.array([[(ra[i] - r0) / da, (re[i] - r0) / de] for i, r0 in ((1, fz), (2, m))])
            step = np.linalg.solve(J, -np.array([fz, m]))
            a, e = a + step[0], e + step[1]
    pm = f.get_property_manager()
    get = lambda p: f[p] if pm.hasNode(p) else None  # noqa: E731
    rec = dict(model=model, sink_fps=sink, iterations=it, alpha_deg=a, elevator=e, throttle=t, throttle_solved=free_t,
               residual=dict(fx_over_w=fx, fz_over_w=fz, m_over_w_ft=m), theta_deg=f["attitude/theta-deg"], vc_kts=f["velocities/vc-kts"],
               v_down_fps=f["velocities/v-down-fps"], thrust=[get("propulsion/engine/thrust-lbs"), get("propulsion/engine[1]/thrust-lbs")],
               rpm=[get("propulsion/engine/engine-rpm"), get("propulsion/engine[1]/engine-rpm")], n2=[get("propulsion/engine/n2"), get("propulsion/engine[1]/n2")],
               flap=[get("fcs/flap-pos-deg"), get("fcs/flap-pos-norm")], gear=get("gear/gear-pos-norm"), elevator_pos_rad=get("fcs/elevator-pos-rad"))
    log("steady-descent trim by Newton on settled initial states (sim05.settle), JSBSim defaults", **rec)
    return rec


def solve_fast(model):
    """Level flight at the fastest point of the envelope, full throttle: alpha and elevator by Newton."""
    import numpy as np
    kts = sim05.G5["G7"]["fast_points"][model]["kts"]
    a, e = 0.0, 0.0
    for it in range(25):
        fz, m, f = sim05.fast_trim_residual(model, HZ, kts, a, e, 1.0)
        if abs(fz) < 1e-6 and abs(m) < 1e-6:
            break
        da, de = 0.05, 0.2
        ra = sim05.fast_trim_residual(model, HZ, kts, a + da, e, 1.0)[:2]
        re = sim05.fast_trim_residual(model, HZ, kts, a, e + de, 1.0)[:2]
        J = np.array([[(ra[i] - r0) / da, (re[i] - r0) / de] for i, r0 in enumerate((fz, m))])
        step = np.linalg.solve(J, -np.array([fz, m]))
        a, e = a + step[0], e + step[1]
    rec = dict(model=model, kts=kts, iterations=it, alpha_deg=float(a), elevator=float(e), throttle=1.0, residual=dict(fz_over_w=fz, m_over_w_ft=m),
               mach=f["velocities/mach"], vc_kts=f["velocities/vc-kts"], thrust=f["propulsion/engine/thrust-lbs"], udot=f["accelerations/udot-ft_sec2"])
    log("fast-point trim (level, full throttle) by Newton on settled initial states, JSBSim defaults", **rec)
    return rec


if __name__ == "__main__":
    if sys.argv[1:2] == ["fast"]:
        out = {}
        for model in sys.argv[2:] or list(sim05.G5["G7"]["fast_points"]):
            r = solve_fast(model)
            out[model] = dict(kts=r["kts"], alpha_deg=round(r["alpha_deg"], 4), elevator=round(r["elevator"], 5), throttle=1.0)
            print(model, r, file=sys.stderr, flush=True)
        print(json.dumps(out, indent=1))
        sys.exit(0)
    out = {}
    for model in sys.argv[1:] or list(sim05.G5["aircraft"]):
        out[model] = {}
        guess = (4.0, 0.0, 0.4)
        for sink in sorted({c["sink_fps"] if c["sink_fps"] != "limit" else sim05.G5["aircraft"][model]["limit_sink_fps"] for c in sim05.G5["landing_cases"].values()}):
            r = solve(model, sink, guess)
            guess = (r["alpha_deg"], r["elevator"], max(r["throttle"], 0.05))
            out[model][f"{sink:g}"] = dict(alpha_deg=round(r["alpha_deg"], 4), elevator=round(r["elevator"], 5), throttle=round(r["throttle"], 4))
            print(model, sink, {k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items() if k not in ("model", "sink_fps")}, file=sys.stderr, flush=True)
    print(json.dumps(out, indent=1))
