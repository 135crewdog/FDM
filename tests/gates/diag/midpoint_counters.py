"""Candidate 2 (implicit midpoint body rates, patch 0002): how often each path of the scheme is taken.
(Diagnostic, not a gate. Native JSBSim, patched build: PYTHONPATH=build/native/patched.)
usage: python tests/gates/diag/midpoint_counters.py
Runs the gates' own workloads with simulation/integrator/rate/rotational = 10 and Buss 2 attitude, and reads the
counters that patch 0002 adds (simulation/integrator/midpoint/*) at the end of every run.
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
PROPS = {"simulation/integrator/rate/rotational": 10, "simulation/integrator/position/rotational": 7}
COUNTERS = ["steps", "newton-iterations", "max-newton-iterations", "split-steps", "rounding-exits", "euler-fallbacks", "not-converged", "singular-jacobian"]


def read(f):
    return {c: f[f"simulation/integrator/midpoint/{c}"] for c in COUNTERS}


def add(total, c, thrown, nonfinite):
    for k in COUNTERS:
        total[k] = max(total.get(k, 0), c[k]) if k == "max-newton-iterations" else total.get(k, 0) + c[k]
    total["runs"] = total.get("runs", 0) + 1
    total["exceptions"] = total.get("exceptions", 0) + thrown
    total["non-finite runs"] = total.get("non-finite runs", 0) + nonfinite


def ground(model, scenario, hz, friction_aware):
    sc = G["scenarios"][scenario]
    f = native.new_fdm(dt=1.0 / hz)
    f.load_model(model)
    f.load_ic(G["aircraft"][model], True)
    for p, v in sc["ic"].items():
        f[p] = v
    for p, v in PROPS.items():
        f[p] = v
    f["simulation/integrator/friction-aware"] = friction_aware
    f.run_ic()
    get = R.getters(f, G["body_rates"])
    thrown = nonfinite = 0
    for _ in range(round(sc["seconds"] * hz)):
        try:
            f.run()
        except Exception:
            thrown = 1
            break
        if not all(math.isfinite(g()) for g in get):
            nonfinite = 1
            break
    return read(f), thrown, nonfinite


def rigid(root, body, spin, hz):
    g5 = G["G5"]
    f = native.new_fdm(root, dt=1.0 / hz)
    f.load_model(body)
    f.load_ic("reset_Atmos_02", True)
    f["ic/h-sl-ft"] = g5["ic_altitude_ft"]
    for p, w in zip(("ic/p-rad_sec", "ic/q-rad_sec", "ic/r-rad_sec"), g5["spins_deg_s"][spin]):
        f[p] = math.radians(w)
    for p, v in PROPS.items():
        f[p] = v
    f.run_ic()
    thrown = 0
    for _ in range(g5["seconds"] * hz):
        try:
            f.run()
        except Exception:
            thrown = 1
            break
    return read(f), thrown, 0


def main():
    print("# Candidate 2, implicit midpoint body rates: paths taken (patch 0002's counters)")
    print()
    print(f"Native JSBSim: {native.describe()}")
    print("Workloads: the gates' own, run 0, at 480 and 1000 Hz (rigid body also at 120 and 240 Hz). 'Split steps' are steps solved in")
    print("more than one part because the body would turn more than 1 rad in the step. 'Rounding exits' are Newton solves accepted")
    print("at the looser tolerance (1e-8 of the rates). 'Euler fallbacks' are steps taken by Euler because the rates or moments")
    print("were non-finite or enormous. 'Exceptions' are steps where Newton failed and the pull request's code throws.")
    print()
    print("| workload | runs | midpoint steps | Newton iterations per step (mean) | most in one solve | split steps | rounding exits | Euler fallbacks | exceptions (not converged / singular) | runs that went non-finite |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    rows = []
    root = R.rigid_root()
    t = {}
    for body in G["G5"]["bodies"]:
        for spin in G["G5"]["spins_deg_s"]:
            for hz in (120, 240, 480, 1000):
                add(t, *rigid(root, body, spin, hz))
    rows.append(("G5 torque-free tumbling, 2 bodies x 8 spins x 4 rates", t))
    for fa in (0, 1):
        for label, scenarios in (("G1 rest", ["rest"]), ("G2c forward hard landing", ["hard_forward"]), ("G2b backward or sideways touchdown", ["hard"]),
                                 ("G3 extreme impacts", G["G3"]["scenarios"])):
            t = {}
            for model in G["aircraft"]:
                for sc in scenarios:
                    for hz in (480, 1000):
                        add(t, *ground(model, sc, hz, fa))
            rows.append((f"{label}, 5 aircraft, 480 and 1000 Hz, {'friction-aware' if fa else 'friction as in JSBSim'}", t))
    for label, t in rows:
        print(f"| {label} | {t['runs']} | {t['steps']:.0f} | {t['newton-iterations'] / max(t['steps'], 1):.2f} | {t['max-newton-iterations']:.0f} | {t['split-steps']:.0f} | "
              f"{t['rounding-exits']:.0f} | {t['euler-fallbacks']:.0f} | {t['exceptions']} ({t['not-converged']:.0f} / {t['singular-jacobian']:.0f}) | {t['non-finite runs']} |", flush=True)


if __name__ == "__main__":
    main()
