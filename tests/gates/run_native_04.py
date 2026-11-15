"""Later gates of session 04, measurements in NATIVE JSBSim. It only measures; evaluate_04.py judges.
usage: PYTHONPATH=build/native/<source> python tests/gates/run_native_04.py <config> [rigidb] [repeat] [--models a,b,...]
Output: out/gates/<config>/rigidb.native.jsonl, repeat.native.<model>.jsonl (one file per aircraft, so that
aircraft can be measured in parallel). The same procedures are in run_wasm_04.ts. Definitions: gates-04.json,
GATES-04.md; everything else comes from the frozen gates.json and the frozen run_native.py.
"""
import json
import math
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_native as R  # noqa: E402  (frozen; reused, not changed)
import numpy as np  # noqa: E402

native = R.native
G = R.G
G4 = json.loads((HERE / "gates-04.json").read_text())


def rigidb_trial(cfg, root, body, spin, hz):
    """G5b: G5's body, spin and set-up; the drift of T = w.Jw/2 and |H| = |Jw| is measured against their values
    at measure_from_seconds, over every later step. The drift from the start (G5's definition) is kept too."""
    g5, g5b = G["G5"], G4["G5b"]
    f = native.new_fdm(root, dt=1.0 / hz)
    if not f.load_model(body):
        raise RuntimeError("load_model failed")
    if not f.load_ic("reset_Atmos_02", True):
        raise RuntimeError("load_ic failed")
    f["ic/h-sl-ft"] = g5["ic_altitude_ft"]
    for p, w in zip(("ic/p-rad_sec", "ic/q-rad_sec", "ic/r-rad_sec"), g5["spins_deg_s"][spin]):
        f[p] = math.radians(w)
    R.apply_config(f, cfg)
    if not f.run_ic():
        raise RuntimeError("run_ic failed")
    ixx, iyy, izz, ixy, ixz, iyz = (f[p] for p in R.INERTIA)
    J = np.array([[ixx, -ixy, ixz], [-ixy, iyy, -iyz], [ixz, -iyz, izz]])
    get_w = R.getters(f, R.OMEGA_I)

    def sample():
        w = np.array([g() for g in get_w])
        hb = J @ w
        return 0.5 * float(w @ hb), float(np.linalg.norm(hb))

    T0, H0 = sample()
    k_ref = round(g5b["measure_from_seconds"] * hz)
    steps = round(g5b["seconds"] * hz)
    Tr = Hr = None
    dT = dH = dT0 = dH0 = 0.0
    finite = True
    for k in range(1, steps + 1):
        f.run()
        T, H = sample()
        if not (math.isfinite(T) and math.isfinite(H)):
            finite = False
            break
        dT0 = max(dT0, abs(T - T0) / T0)
        dH0 = max(dH0, abs(H - H0) / H0)
        if k == k_ref:
            Tr, Hr = T, H
        elif k > k_ref:
            dT = max(dT, abs(T - Tr) / Tr)
            dH = max(dH, abs(H - Hr) / Hr)
    return dict(body=body, spin=spin, hz=hz, seconds=g5b["seconds"], measure_from_seconds=g5b["measure_from_seconds"], finite=finite,
                energy_drift=dT, momentum_magnitude_drift=dH, energy_drift_from_start=dT0, momentum_magnitude_drift_from_start=dH0,
                end_h_agl_ft=f["position/h-agl-ft"])


def run_rigidb(cfg, out, _models):
    root = R.rigid_root()
    g5 = G["G5"]
    with (out / "rigidb.native.jsonl").open("w") as s:
        for body in g5["bodies"]:
            for spin in g5["spins_deg_s"]:
                for hz in g5["report_only_rates_hz"] + g5["rates_hz"]:
                    try:
                        rec = rigidb_trial(cfg, root, body, spin, hz)
                    except Exception as e:
                        rec = dict(body=body, spin=spin, hz=hz, error=f"{type(e).__name__}: {e}")
                    s.write(json.dumps(rec) + "\n")
                    s.flush()
                    print("rigidb", body, spin, hz, "error" if "error" in rec else "ok", flush=True)
    shutil.rmtree(root, ignore_errors=True)


def repeat_trial(cfg, model, scenario, hz, run):
    """G2b/G3b: G2's set-up and per-step checks (frozen run_native.ground_trial), with the run's perturbation added
    to the scenario's initial conditions. Only what the two gates need is kept."""
    sc = G["scenarios"][scenario]
    rp = G4["repeats"]
    ic = dict(sc["ic"])
    for p, d in zip(rp["perturbed_properties"], rp["draws"][run]):
        ic[p] = ic[p] + d
    f = native.new_fdm(dt=1.0 / hz)
    if not f.load_model(model):
        raise RuntimeError("load_model failed")
    if not f.load_ic(G["aircraft"][model], True):
        raise RuntimeError("load_ic failed")
    for p, v in ic.items():
        f[p] = v
    R.apply_config(f, cfg)
    if not f.run_ic():
        raise RuntimeError("run_ic failed")
    pm = f.get_property_manager()
    n_units = int(f["gear/num-units"])
    wow = [p for k in range(n_units) for p in (f"gear/unit[{k}]/WOW", f"contact/unit[{k}]/WOW") if pm.hasNode(p)]
    if len(wow) != n_units:
        raise RuntimeError("could not find a WOW property for every contact point")
    names = G["state"]
    state = R.getters(f, names)
    ir = [names.index(p) for p in G["body_rates"]]
    gw = R.getters(f, wow)
    steps = round(sc["seconds"] * hz)
    first_nonfinite = nonfinite_property = first_runaway = first_contact = None
    peak = 0.0
    done = contact_steps = 0
    for k in range(1, steps + 1):
        more = f.run()
        done = k
        v = [g() for g in state]
        if not math.isfinite(sum(v)):  # cheap test first; the per-quantity test below decides
            bad = [names[j] for j, x in enumerate(v) if not math.isfinite(x)]
            if bad:
                first_nonfinite, nonfinite_property = k / hz, bad[0]
                break
        if any(g() > 0.5 for g in gw):
            contact_steps += 1
            if first_contact is None:
                first_contact = k / hz
        w = max(abs(v[j]) for j in ir)
        if w > G["runaway_rate_rad_s"] and first_runaway is None:
            first_runaway = k / hz
        peak = max(peak, w)
        if not more:
            break
    return dict(model=model, scenario=scenario, hz=hz, run=run, ic=ic, steps=steps, steps_done=done, first_nonfinite=first_nonfinite,
                nonfinite_property=nonfinite_property, first_runaway=first_runaway, first_contact=first_contact,
                contact_steps=contact_steps, peak_rate=peak)


def run_repeat(cfg, out, models):
    scenarios = [G4["G2b"]["scenario"]] + G4["G3b"]["scenarios"]
    for model in models:
        with (out / f"repeat.native.{model}.jsonl").open("w") as s:
            for scenario in scenarios:
                for hz in G["rates_hz"]:
                    for run in range(len(G4["repeats"]["draws"])):
                        try:
                            rec = repeat_trial(cfg, model, scenario, hz, run)
                        except Exception as e:  # an exception is recorded; the evaluator counts it as a failure
                            rec = dict(model=model, scenario=scenario, hz=hz, run=run, error=f"{type(e).__name__}: {e}")
                        s.write(json.dumps(rec) + "\n")
                    s.flush()
                    print("repeat", model, scenario, hz, "done", flush=True)


def main():
    args = sys.argv[1:]
    models = list(G["aircraft"])
    if "--models" in args:
        i = args.index("--models")
        models = args[i + 1].split(",")
        del args[i:i + 2]
    name = args[0]
    cfg = R.CONFIGS[name]
    want = args[1:] or ["rigidb", "repeat"]
    key = native.key_name()
    if key != cfg["source"]:
        raise SystemExit(f"configuration {name} needs the '{cfg['source']}' native build, but this is '{key}' (set PYTHONPATH=build/native/{cfg['source']})")
    out = R.REPO / "out/gates" / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "native.info04.json").write_text(json.dumps(dict(config=name, properties=cfg["properties"], **native.key_info()), indent=1))
    print(f"# later gates, native, configuration {name}: {native.describe()}", flush=True)
    for part in want:
        {"rigidb": run_rigidb, "repeat": run_repeat}[part](cfg, out, models)


if __name__ == "__main__":
    main()
