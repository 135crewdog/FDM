"""Candidate 3 (patch 0003): how the switch between the in-air and the on-contact body-rate scheme behaves on
touch-down, release and bouncing. (Diagnostic, not a gate. Native JSBSim, patched build.)
usage: PYTHONPATH=build/native/patched python tests/gates/diag/contact_switch.py

For every step it compares what the body rates did with an Euler step of the derivative that step integrated:
    extra = (rates after - rates before) - dt * derivative
On contact the scheme is Euler, so extra is zero by construction. In smooth flight a multistep scheme differs from
Euler by a small, legitimate amount. The question is the first step back in the air: an "extra impulse" there is a
kick that comes from extrapolating old ground forces, not from any force acting now.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_native as R  # noqa: E402

native, G = R.native, R.G
GB = json.loads((HERE.parent / "gates-04b.json").read_text())
G["scenarios"]["hard_forward"] = GB["G2c"]["scenario_definition"]
# a drop that bounces: level, no forward speed, 5 ft/s down from 3 ft above the resting height
G["scenarios"]["bounce"] = {"seconds": 10, "ic": {"ic/psi-true-deg": 0, "ic/h-agl-ft": 8, "ic/phi-deg": 2, "ic/theta-deg": 3, "ic/vn-fps": 0, "ic/ve-fps": 0, "ic/vd-fps": 5}}
WI = ["velocities/pi-rad_sec", "velocities/qi-rad_sec", "velocities/ri-rad_sec"]
WD = ["accelerations/pidot-rad_sec2", "accelerations/qidot-rad_sec2", "accelerations/ridot-rad_sec2"]
VARIANTS = ["c3-ab4-fa", "c3x-ab4-fa-keep", "c3x-ab4-fa-hold", "c3-ab3-fa"]


def run(config, model, scenario, hz):
    cfg = R.CONFIGS[config]
    sc = G["scenarios"][scenario]
    f = native.new_fdm(dt=1.0 / hz)
    f.load_model(model)
    f.load_ic(G["aircraft"][model], True)
    for p, v in sc["ic"].items():
        f[p] = v
    R.apply_config(f, cfg)
    f.run_ic()
    pm = f.get_property_manager()
    n = int(f["gear/num-units"])
    wow = R.getters(f, [p for k in range(n) for p in (f"gear/unit[{k}]/WOW", f"contact/unit[{k}]/WOW") if pm.hasNode(p)])
    gw, gd = R.getters(f, WI), R.getters(f, WD)
    active = R.getters(f, ["simulation/integrator/rate/contact-active"])[0]
    dt = 1.0 / hz
    w0, d0, c0 = [g() for g in gw], [g() for g in gd], any(g() > 0.5 for g in wow)
    touch = release = 0
    ex_touch = ex_release = ex_contact = ex_air = 0.0
    rel_release = 0.0
    last_ground_d = 0.0
    switch_times, prev_active = [], active() > 0.5
    finite = True
    for k in range(1, round(sc["seconds"] * hz) + 1):
        f.run()
        w1, d1, c1 = [g() for g in gw], [g() for g in gd], any(g() > 0.5 for g in wow)
        if not all(math.isfinite(x) for x in w1 + d1):
            finite = False
            break
        extra = math.sqrt(sum((b - a - dt * d) ** 2 for a, b, d in zip(w0, w1, d0)))
        dmag = math.sqrt(sum(d * d for d in d0))
        a1 = active() > 0.5
        if a1 != prev_active:
            switch_times.append(k * dt)
        # the step just taken integrated d0, computed with contact state c0; cprev is the contact state one step earlier
        if c0:
            ex_contact = max(ex_contact, extra)
            last_ground_d = dmag
            if k > 1 and not cprev:
                touch += 1
                ex_touch = max(ex_touch, extra)
        else:
            if k > 1 and cprev:
                release += 1
                ex_release = max(ex_release, extra)
                if last_ground_d > 0:
                    rel_release = max(rel_release, extra / (dt * last_ground_d))
            elif not a1 and not prev_active:
                ex_air = max(ex_air, extra)
        cprev, prev_active = c0, a1
        w0, d0, c0 = w1, d1, c1
    gaps = [b - a for a, b in zip(switch_times, switch_times[1:])]
    return dict(finite=finite, touch=touch, release=release, switches=f["simulation/integrator/rate/contact-switches"],
                shortest_gap_steps=(min(gaps) * hz if gaps else None), ex_touch=ex_touch, ex_release=ex_release, rel_release=rel_release,
                ex_contact=ex_contact, ex_air=ex_air)


def main():
    print("# Candidate 3: behaviour of the switch on touch-down, release and bouncing")
    print()
    print(f"Native JSBSim: {native.describe()}")
    print("Variants: `c3-ab4-fa` (the candidate: history restarted on release, no hold), `c3x-ab4-fa-keep` (history kept on release),")
    print("`c3x-ab4-fa-hold` (on-contact scheme held 0.1 s after the last contact), `c3-ab3-fa` (AB3 in the air).")
    print("'Extra' is the change of the body rates in one step minus an Euler step of the derivative that step integrated, in rad/s.")
    print("'Release kick' is the largest extra on a first step back in the air, as a fraction of one step of the last ground moment.")
    print()
    print("| aircraft, scenario, rate | variant | touch-downs | releases | scheme changes | shortest time between changes (steps) | largest extra on a touch-down step | largest extra on a first step in the air | release kick | largest extra in ordinary flight steps |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for model, scenario, hz in [("c172x", "bounce", 480), ("c172x", "hard_forward", 480), ("c172x", "hard_forward", 1000), ("f16", "hard_forward", 480),
                                ("c310", "hard_forward", 480), ("737", "hard_forward", 480), ("ah1s", "bounce", 480)]:
        for v in VARIANTS:
            r = run(v, model, scenario, hz)
            gap = "-" if r["shortest_gap_steps"] is None else f"{r['shortest_gap_steps']:.0f}"
            print(f"| {model}, {scenario}, {hz} Hz | `{v}` | {r['touch']} | {r['release']} | {r['switches']:.0f} | {gap} | {r['ex_touch']:.1e} | {r['ex_release']:.1e} | "
                  f"{r['rel_release']:.2f} | {r['ex_air']:.1e} |{'' if r['finite'] else ' (went non-finite)'}", flush=True)


if __name__ == "__main__":
    main()
