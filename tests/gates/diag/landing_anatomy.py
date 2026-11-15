"""What happens in the hard-landing runs that fail? (Diagnostic, not a gate. Native JSBSim.)
usage: PYTHONPATH=build/native/<source> python tests/gates/diag/landing_anatomy.py <config> [models...]
For G2c (forward) and G2b (as first written) and every run of gates-04.json, at 480 and 1000 Hz, it records what
came before the end of the run or before the first runaway (body rate > 1e6 rad/s) or non-finite value:
  - did the centre of gravity go below the ground (h-agl < 0)?  The 737 has no airframe contact points and the
    ah1s only one, so their bodies can pass through the ground; a wheel that comes back into contact tens of feet
    "deep" then throws the aircraft into the air.
  - did the aircraft tip over (pitch or roll beyond 60 deg)?
  - was it already tumbling before it touched (body rate above 0.5 rad/s before the first contact)?
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
NAMES = G["body_rates"] + ["position/h-agl-ft", "attitude/phi-rad", "attitude/theta-rad"]


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
    wow = R.getters(f, [p for k in range(n) for p in (f"gear/unit[{k}]/WOW", f"contact/unit[{k}]/WOW") if pm.hasNode(p)])
    get = R.getters(f, NAMES)
    touched = False
    r = dict(failed=False, below=False, tipped=False, tumbling_before_touch=False, min_h=math.inf, max_h_after_touch=-math.inf)
    for _ in range(round(sc["seconds"] * hz)):
        try:
            f.run()
        except Exception:
            r["failed"] = True
            break
        v = [g() for g in get]
        if not all(math.isfinite(x) for x in v) or max(abs(x) for x in v[:3]) > G["runaway_rate_rad_s"]:
            r["failed"] = True
            break
        if not touched:
            if any(g() > 0.5 for g in wow):
                touched = True
            elif max(abs(x) for x in v[:3]) > 0.5:
                r["tumbling_before_touch"] = True
        else:
            r["max_h_after_touch"] = max(r["max_h_after_touch"], v[3])
        r["min_h"] = min(r["min_h"], v[3])
        if v[3] < 0:
            r["below"] = True
        if abs(v[4]) > math.radians(60) or abs(v[5]) > math.radians(60):
            r["tipped"] = True
    return r


def main():
    config = sys.argv[1]
    models = sys.argv[2:] or list(G["aircraft"])
    cfg = R.CONFIGS[config]
    runs = len(G4["repeats"]["draws"])
    print(f"# Anatomy of the hard-landing runs: configuration `{config}`")
    print()
    print(f"Native JSBSim: {native.describe()}")
    print(f"{runs} runs per case (gates-04.json). 'Failed' = runaway or non-finite (G2's definition). 'Below ground' = the centre of gravity")
    print("was under the surface at some step before the run ended or failed. 'Tipped' = pitch or roll beyond 60 deg.")
    print("'Thrown' = finite to the end, but the centre of gravity rose more than 100 ft above the ground after touching it.")
    print()
    print("| scenario | aircraft | rate | failed | failed after going below ground | failed without going below ground | finite: stayed above ground and upright | finite: tipped or below ground | finite: thrown above 100 ft | tumbling before the first touch | lowest point of any run, ft |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for scenario, label in (("hard_forward", "G2c forward"), ("hard", "G2b as first written")):
        for model in models:
            for hz in (480, 1000):
                rs = [one(cfg, model, scenario, hz, k) for k in range(runs)]
                fail = [r for r in rs if r["failed"]]
                fin = [r for r in rs if not r["failed"]]
                print(f"| {label} | {model} | {hz} Hz | {len(fail)} | {sum(r['below'] for r in fail)} | {sum(not r['below'] for r in fail)} | "
                      f"{sum(not r['below'] and not r['tipped'] for r in fin)} | {sum(r['below'] or r['tipped'] for r in fin)} | {sum(r['max_h_after_touch'] > 100 for r in fin)} | "
                      f"{sum(r['tumbling_before_touch'] for r in rs)} | {min(r['min_h'] for r in rs):.1f} |", flush=True)


if __name__ == "__main__":
    main()
