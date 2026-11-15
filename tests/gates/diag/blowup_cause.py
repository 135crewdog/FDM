"""What comes just before a run blows up? (Diagnostic, not a gate. Native JSBSim.)
usage: PYTHONPATH=build/native/<source> python tests/gates/diag/blowup_cause.py <config> [runs=11]

JSBSim computes a wheel's strut compression (FGLGear.cpp, BOGEY contacts) as
    compressLength = height * normalZ / LGearProj
where LGearProj is the projection of the gear leg on the ground normal, and then divides the strut force by that
projection again. Nothing limits the result. When the leg is nearly parallel to the ground (aircraft rolled or
pitched towards 90 deg) or the wheel is far below the surface (aircraft tipped over or inverted, body through the
ground), the "compression" is tens to thousands of feet and the force is millions of pounds for one step.

This script checks how many failing runs are preceded by such a compression. For every run of the hard landings and
the impacts it records the largest BOGEY compression and the largest gear force before the run fails (runaway or
non-finite, G2's definition) or ends. Real struts in these aircraft travel about a foot.
"""
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_native as R  # noqa: E402

native, G = R.native, R.G
G4 = json.loads((HERE.parent / "gates-04.json").read_text())
GB = json.loads((HERE.parent / "gates-04b.json").read_text())
G["scenarios"]["hard_forward"] = GB["G2c"]["scenario_definition"]
ABSURD_FT = 10.0


def one(cfg, model, scenario, hz, run):
    sc = G["scenarios"][scenario]
    ic = dict(sc["ic"])
    for p, d in zip(G4["repeats"]["perturbed_properties"], G4["repeats"]["draws"][run]):
        ic[p] = ic[p] + d
    f = native.new_fdm(dt=1.0 / hz)
    f.load_model(model)
    f.load_ic(G["aircraft"][model], True)
    for p, v in ic.items():
        f[p] = v
    R.apply_config(f, cfg)
    f.run_ic()
    pm = f.get_property_manager()
    n = int(f["gear/num-units"])
    bogey = R.getters(f, [f"gear/unit[{k}]/compression-ft" for k in range(n) if pm.hasNode(f"gear/unit[{k}]/compression-ft")])
    rates = R.getters(f, G["body_rates"])
    force = R.getters(f, ["forces/fbx-gear-lbs", "forces/fby-gear-lbs", "forces/fbz-gear-lbs"])
    weight = f["inertia/weight-lbs"]
    r = dict(failed=False, max_comp=0.0, max_force_g=0.0)
    for _ in range(round(sc["seconds"] * hz)):
        try:
            f.run()
        except Exception:
            r["failed"] = True
            break
        w = [g() for g in rates]
        if not all(math.isfinite(x) for x in w) or max(abs(x) for x in w) > G["runaway_rate_rad_s"]:
            r["failed"] = True
            break
        c = max((g() for g in bogey), default=0.0)
        if math.isfinite(c):
            r["max_comp"] = max(r["max_comp"], c)
        fm = math.sqrt(sum(g() ** 2 for g in force))
        if math.isfinite(fm):
            r["max_force_g"] = max(r["max_force_g"], fm / weight)
    return r


def main():
    config = sys.argv[1]
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 11
    cfg = R.CONFIGS[config]
    print(f"# What precedes a blow-up: configuration `{config}`")
    print()
    print(f"Native JSBSim: {native.describe()}")
    print(f"Runs 0 to {runs - 1} of gates-04.json at 480 and 1000 Hz. 'Absurd compression' = some wheel (BOGEY) reported a strut compression of")
    print(f"more than {ABSURD_FT:g} ft at a step before the run failed or ended. 'Largest gear force' is the total ground-reaction force at one")
    print("step, in multiples of the aircraft's weight.")
    print()
    print("| scenario | aircraft | failed runs | failed runs with an absurd compression first | finite runs | finite runs with an absurd compression | largest compression in any run, ft | largest gear force in any run, x weight |")
    print("|---|---|---|---|---|---|---|---|")
    tot_fail = tot_fail_abs = 0
    for scenario, label in [("hard_forward", "G2c forward hard landing"), ("hard", "G2b backward or sideways"), ("inverted", "G3 inverted"), ("banked", "G3 banked"), ("nose", "G3 nose-first")]:
        for model in G["aircraft"]:
            rs = [one(cfg, model, scenario, hz, k) for hz in (480, 1000) for k in range(runs)]
            fail = [r for r in rs if r["failed"]]
            fin = [r for r in rs if not r["failed"]]
            tot_fail += len(fail)
            tot_fail_abs += sum(r["max_comp"] > ABSURD_FT for r in fail)
            print(f"| {label} | {model} | {len(fail)} | {sum(r['max_comp'] > ABSURD_FT for r in fail)} | {len(fin)} | {sum(r['max_comp'] > ABSURD_FT for r in fin)} | "
                  f"{max(r['max_comp'] for r in rs):.3g} | {max(r['max_force_g'] for r in rs):.3g} |", flush=True)
    print()
    print(f"Total: {tot_fail_abs} of {tot_fail} failed runs were preceded by a wheel compression of more than {ABSURD_FT:g} ft.")


if __name__ == "__main__":
    main()
