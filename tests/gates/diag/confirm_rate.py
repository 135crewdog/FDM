"""Confirmation run of one configuration at a step rate the gates do not measure (GATES-04.md: "if the
recommendation lands on 1000 Hz, re-check at 960 Hz"). Not a gate: native JSBSim only, the gates' own procedures
and limits, at the rate given.
usage: PYTHONPATH=build/native/<source> python tests/gates/diag/confirm_rate.py <config> <hz> [floor-config]
"""
import csv
import io
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_native_04b as RB  # noqa: E402
import evaluate_04 as L  # noqa: E402

R4 = RB.R4
R = R4.R
native, G, G4 = R.native, R.G, R4.G4
E = L.E


def nasa(cfg, hz):
    every = hz // 10
    assert every * 10 == hz
    g = G["G4"]
    f = native.new_fdm(R.NASA_ROOT)
    f.load_script("scripts/Atmos_02.xml", 1.0 / hz)
    R.apply_config(f, cfg)
    f.run_ic()
    get = R.getters(f, [c[1] for c in R.NASA_COLS])
    rows = {}
    for k in range(g["seconds"] * hz + 1):
        if k % every == 0:
            rows[round(k / hz, 6)] = {c[0]: (k / hz if c[0] == "time" else R.conv(c[2], gg())) for c, gg in zip(R.NASA_COLS, get)}
        if k < g["seconds"] * hz:
            f.run()
    rate = att = 0.0
    for name in g["references"]:
        ref = E.nasa_csv(E.NASA_REF / f"Atmos_02_{name}.csv")
        ts = [t for t in rows if t in ref]
        rate = max(rate, max(abs(rows[t][c] - ref[t][c]) for t in ts for c in E.RATES))
        att = max(att, max(abs((rows[t][c] - ref[t][c] + 180.0) % 360.0 - 180.0) for t in ts for c in E.ANGLES))
    return rate, att, len(rows)


def main():
    name, hz = sys.argv[1], int(sys.argv[2])
    cfg = R.CONFIGS[name]
    print(f"# Confirmation at {hz} Hz: configuration `{name}` (not a gate; native only)")
    print()
    print(f"- {cfg['role']}")
    print(f"- Native JSBSim: {native.describe()}")
    print()
    g1 = G["G1"]
    worst_rate = worst_disp = 0.0
    ok1 = True
    for model in G["aircraft"]:
        r = R.ground_trial(cfg, model, "rest", hz)
        good = (r["first_nonfinite"] is None and r["tail_always_in_contact"] and r["tail_max_rate"] < g1["max_abs_body_rate_rad_s"]
                and r["tail_max_horizontal_displacement_ft"] < g1["max_horizontal_displacement_ft"])
        ok1 = ok1 and good
        worst_rate, worst_disp = max(worst_rate, r["tail_max_rate"]), max(worst_disp, r["tail_max_horizontal_displacement_ft"])
    print(f"- G1 Rest at {hz} Hz: {'pass' if ok1 else 'FAIL'} (worst body rate {worst_rate:.1e} rad/s, limit 1e-6; worst movement {worst_disp:.1e} ft, limit 0.01)")
    rate, att, n = nasa(cfg, hz)
    g4 = G["G4"]
    print(f"- G4 NASA at {hz} Hz: {'pass' if rate < g4['max_body_rate_error_deg_s'] and att < g4['max_attitude_error_deg'] and n == g4['samples'] else 'FAIL'} "
          f"(rate error {rate:.2e} deg/s, limit 2e-6; attitude error {att:.2e} deg, limit 1e-3; {n} samples)")
    root = R.rigid_root()
    worst = 0.0
    for body in G["G5"]["bodies"]:
        for spin in G["G5"]["spins_deg_s"]:
            if spin in G["G5"]["report_only_spins"]:
                continue
            r = R4.rigidb_trial(cfg, root, body, spin, hz)
            worst = max(worst, math.inf if not r["finite"] else max(r["energy_drift"], r["momentum_magnitude_drift"]))
    print(f"- G5b Rigid body after start-up at {hz} Hz: {'pass' if worst < G4['G5b']['max_relative_drift'] else 'FAIL'} (worst drift {worst:.1e}, limit 1e-6)")
    runs = len(G4["repeats"]["draws"])
    print(f"- Landings and impacts at {hz} Hz, good runs of {runs} (G2's conditions):")
    print()
    scen = [("hard_forward", "G2c forward hard landing"), ("hard", "G2b backward or sideways touchdown")] + [(s, f"G3b {s}") for s in G4["G3b"]["scenarios"]]
    print("| aircraft | " + " | ".join(lbl for _, lbl in scen) + " |")
    print("|---|" + "---|" * len(scen))
    for model in G["aircraft"]:
        cells = []
        for sc, _ in scen:
            good = 0
            for run in range(runs):
                try:
                    good += L.run_ok(R4.repeat_trial(cfg, model, sc, hz, run))
                except Exception:
                    pass
            cells.append(str(good))
        print(f"| {model} | " + " | ".join(cells) + " |", flush=True)


if __name__ == "__main__":
    main()
