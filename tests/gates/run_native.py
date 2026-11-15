"""Gate measurements in NATIVE JSBSim (the answer key). It only measures; tests/gates/evaluate.py judges.
usage: PYTHONPATH=build/native/<source> python tests/gates/run_native.py <config> [ground] [nasa] [rigid] [flights]
Output: out/gates/<config>/{ground,rigid}.native.jsonl, nasa-<hz>.native.csv, flight-<model>.native.csv
The same procedures, in the same order, are in run_wasm.ts. Definitions: gates.json and GATES.md.
"""
import csv
import json
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pylib"))
import native  # noqa: E402
import numpy as np  # noqa: E402

REPO = native.REPO
G = json.loads((HERE / "gates.json").read_text())
CONFIGS = json.loads((HERE / "configs.json").read_text())
NASA_ROOT = REPO / "jsbsim-data/check_cases/NASA_EOM_2015"
NASA_COLS = json.loads((HERE.parent / "nasa/columns.json").read_text())


def apply_config(f, cfg):
    """Set the configuration's properties. Each must already exist (a missing patch must not pass silently)."""
    pm = f.get_property_manager()
    for p, v in cfg["properties"].items():
        if not pm.hasNode(p):
            raise RuntimeError(f"property {p} does not exist in this build (wrong source for this configuration?)")
        f[p] = v
        if f[p] != v:
            raise RuntimeError(f"property {p} did not take the value {v} (reads {f[p]})")


def getters(f, names):
    pm = f.get_property_manager()
    for n in names:
        if not pm.hasNode(n):
            raise RuntimeError(f"property {n} does not exist")
    return [pm.get_node(n).get_double_value for n in names]


def ground_trial(cfg, model, scenario, hz):
    """G1-G3: one aircraft, one scenario, one step rate. dt is set before the model is loaded."""
    sc = G["scenarios"][scenario]
    rec = dict(model=model, scenario=scenario, hz=hz, seconds=sc["seconds"])
    f = native.new_fdm(dt=1.0 / hz)
    if not f.load_model(model):
        raise RuntimeError("load_model failed")
    if not f.load_ic(G["aircraft"][model], True):
        raise RuntimeError("load_ic failed")
    for p, v in sc["ic"].items():
        f[p] = v
    apply_config(f, cfg)
    if not f.run_ic():
        raise RuntimeError("run_ic failed")
    pm = f.get_property_manager()
    n_units = int(f["gear/num-units"])
    # Every contact point: BOGEY (gear/unit[k]/WOW) and STRUCTURE (contact/unit[k]/WOW). Not gear/wow.
    bogey = [p for p in (f"gear/unit[{k}]/WOW" for k in range(n_units)) if pm.hasNode(p)]
    struct = [p for p in (f"contact/unit[{k}]/WOW" for k in range(n_units)) if pm.hasNode(p)]
    if len(bogey) + len(struct) != n_units:
        raise RuntimeError("could not find a WOW property for every contact point")
    names = G["state"]
    state = getters(f, names)
    ir = [names.index(p) for p in G["body_rates"]]
    ie = [names.index(p) for p in G["ecef"]]
    gb, gs = getters(f, bogey), getters(f, struct)
    steps = round(sc["seconds"] * hz)
    tail_start = steps - round(G["G1"]["tail_seconds"] * hz)
    first_nonfinite = nonfinite_property = first_runaway = first_contact = None
    peak = tail_rate = tail_disp = 0.0
    bogey_steps = struct_steps = done = 0
    tail_always_contact = True
    ref = up = None
    t0 = time.perf_counter()
    for k in range(1, steps + 1):
        more = f.run()
        done = k
        t = k / hz
        v = [g() for g in state]
        bad = [names[j] for j, x in enumerate(v) if not math.isfinite(x)]
        if bad:
            first_nonfinite, nonfinite_property = t, bad[0]
            break
        cb = any(g() > 0.5 for g in gb)
        cs = any(g() > 0.5 for g in gs)
        bogey_steps += cb
        struct_steps += cs
        if (cb or cs) and first_contact is None:
            first_contact = t
        w = max(abs(v[j]) for j in ir)
        if w > G["runaway_rate_rad_s"] and first_runaway is None:
            first_runaway = t
        peak = max(peak, w)
        if k >= tail_start:
            pos = [v[j] for j in ie]
            if k == tail_start:
                ref = pos
                r = math.sqrt(sum(x * x for x in pos))
                up = [x / r for x in pos]
            d = [a - b for a, b in zip(pos, ref)]
            dv = sum(a * b for a, b in zip(d, up))
            tail_disp = max(tail_disp, math.sqrt(max(0.0, sum(a * a for a in d) - dv * dv)))
            tail_rate = max(tail_rate, w)
            tail_always_contact = tail_always_contact and (cb or cs)
        if not more:
            break
    rec.update(steps=steps, steps_done=done, first_nonfinite=first_nonfinite, nonfinite_property=nonfinite_property,
               first_runaway=first_runaway, first_contact=first_contact, bogey_contact_steps=bogey_steps,
               structure_contact_steps=struct_steps, contact_points=dict(bogey=len(bogey), structure=len(struct)),
               peak_rate=peak, tail_max_rate=tail_rate, tail_max_horizontal_displacement_ft=tail_disp,
               tail_always_in_contact=bool(tail_always_contact and done == steps),
               end_time=f.get_sim_time(), end_h_agl_ft=v[names.index("position/h-agl-ft")],
               wall_us_per_step=(time.perf_counter() - t0) * 1e6 / max(done, 1))
    return rec


def run_ground(cfg, out):
    with (out / "ground.native.jsonl").open("w") as s:
        for model in G["aircraft"]:
            for scenario in G["scenarios"]:
                for hz in G["rates_hz"]:
                    try:
                        rec = ground_trial(cfg, model, scenario, hz)
                    except Exception as e:  # an exception is recorded; the evaluator counts it as a failure
                        rec = dict(model=model, scenario=scenario, hz=hz, error=f"{type(e).__name__}: {e}")
                    s.write(json.dumps(rec) + "\n")
                    s.flush()
                    print("ground", model, scenario, hz, "error" if "error" in rec else "ok", flush=True)


def conv(kind, v):
    return v * (180.0 / math.pi) if kind == "deg" else (math.fmod(v + 180.0, 360.0) - 180 if kind == "yaw" else v)


def run_nasa(cfg, out):
    """G4: NASA check case 02 with JSBSim's own unchanged files; dt given to load_script (before the model loads)."""
    for hz in G["G4"]["rates_hz"]:
        every = hz // 10
        assert every * 10 == hz
        f = native.new_fdm(NASA_ROOT)
        if not f.load_script("scripts/Atmos_02.xml", 1.0 / hz):
            raise RuntimeError("load_script failed")
        apply_config(f, cfg)
        if not f.run_ic():
            raise RuntimeError("run_ic failed")
        get = getters(f, [c[1] for c in NASA_COLS])
        with (out / f"nasa-{hz}.native.csv").open("w") as s:
            s.write(",".join(c[0] for c in NASA_COLS) + "\n")
            for k in range(G["G4"]["seconds"] * hz + 1):
                if k % every == 0:
                    s.write(",".join(repr(float(k / hz if c[0] == "time" else conv(c[2], g()))) for c, g in zip(NASA_COLS, get)) + "\n")
                if k < G["G4"]["seconds"] * hz:
                    f.run()
        print("nasa", hz, "ok", flush=True)


def rigid_root():
    root = Path(tempfile.mkdtemp(prefix="fdm-gates-rigid-"))
    shutil.copytree(NASA_ROOT / "aircraft/brick", root / "aircraft/brick")
    (root / "aircraft/brick_poi").mkdir()
    shutil.copy(HERE / "fixtures/brick_poi.xml", root / "aircraft/brick_poi/brick_poi.xml")
    shutil.copy(NASA_ROOT / "aircraft/brick/reset_Atmos_02.xml", root / "aircraft/brick_poi/reset_Atmos_02.xml")
    return root


INERTIA = ["inertia/ixx-slugs_ft2", "inertia/iyy-slugs_ft2", "inertia/izz-slugs_ft2",
           "inertia/ixy-slugs_ft2", "inertia/ixz-slugs_ft2", "inertia/iyz-slugs_ft2"]
OMEGA_I = ["velocities/pi-rad_sec", "velocities/qi-rad_sec", "velocities/ri-rad_sec"]


def rigid_trial(cfg, root, body, spin, hz):
    """G5: torque-free body. Rotational kinetic energy T = w.Jw/2 and |H| = |Jw| must stay constant
    (w = inertial angular velocity in body axes). Also reported, native only: the direction of H in the
    inertial frame, which depends on the attitude integrator."""
    g5 = G["G5"]
    f = native.new_fdm(root, dt=1.0 / hz)
    if not f.load_model(body):
        raise RuntimeError("load_model failed")
    if not f.load_ic("reset_Atmos_02", True):
        raise RuntimeError("load_ic failed")
    f["ic/h-sl-ft"] = g5["ic_altitude_ft"]
    for p, w in zip(("ic/p-rad_sec", "ic/q-rad_sec", "ic/r-rad_sec"), g5["spins_deg_s"][spin]):
        f[p] = math.radians(w)
    apply_config(f, cfg)
    if not f.run_ic():
        raise RuntimeError("run_ic failed")
    ixx, iyy, izz, ixy, ixz, iyz = (f[p] for p in INERTIA)
    # JSBSim's sign convention for the reported products (FGMassBalance.h): GetIxy = -J(1,2), GetIxz = +J(1,3),
    # GetIyz = -J(2,3). Checked against FGMassBalance::GetJ just below, so a wrong sign cannot go unnoticed.
    J = np.array([[ixx, -ixy, ixz], [-ixy, iyy, -iyz], [ixz, -iyz, izz]])
    Jn = np.asarray(f.get_mass_balance().get_J(), dtype=float).reshape(3, 3)
    if not np.allclose(J, Jn, rtol=1e-12, atol=0):
        raise RuntimeError(f"inertia from properties does not match FGMassBalance::GetJ: {J} vs {Jn}")
    if np.linalg.eigvalsh(J).min() <= 0:
        raise RuntimeError("inertia matrix is not positive definite")
    get_w = getters(f, OMEGA_I)
    get_epa = getters(f, ["position/epa-rad"])[0]
    prop = f.get_propagate()

    def sample():
        w = np.array([g() for g in get_w])
        hb = J @ w
        e = get_epa()
        ti2ec = np.array([[math.cos(e), math.sin(e), 0.0], [-math.sin(e), math.cos(e), 0.0], [0.0, 0.0, 1.0]])
        tec2b = np.asarray(prop.get_Tec2b(), dtype=float).reshape(3, 3)
        return w, 0.5 * float(w @ hb), float(np.linalg.norm(hb)), ti2ec.T @ (tec2b.T @ hb)

    w0, T0, H0, Hi0 = sample()
    dT = dH = ddir = 0.0
    finite = True
    steps = g5["seconds"] * hz
    for _ in range(steps):
        f.run()
        w, T, H, Hi = sample()
        if not (math.isfinite(T) and math.isfinite(H) and np.all(np.isfinite(Hi))):
            finite = False
            break
        dT = max(dT, abs(T - T0) / T0)
        dH = max(dH, abs(H - H0) / H0)
        c = float(np.linalg.norm(np.cross(Hi, Hi0))) / (float(np.linalg.norm(Hi)) * float(np.linalg.norm(Hi0)))
        ddir = max(ddir, math.asin(min(1.0, c)) if float(Hi @ Hi0) > 0 else math.pi)
    h_end = f["position/h-agl-ft"]
    return dict(body=body, spin=spin, hz=hz, seconds=g5["seconds"], finite=finite, initial_rate_deg_s=[math.degrees(x) for x in w0],
                energy0=T0, momentum0=H0, energy_drift=dT, momentum_magnitude_drift=dH, momentum_direction_drift_rad=ddir,
                end_h_agl_ft=h_end, total_moment_lbsft=[f[p] for p in ("moments/l-total-lbsft", "moments/m-total-lbsft", "moments/n-total-lbsft")])


def run_rigid(cfg, out):
    root = rigid_root()
    g5 = G["G5"]
    with (out / "rigid.native.jsonl").open("w") as s:
        for body in g5["bodies"]:
            for spin in g5["spins_deg_s"]:
                for hz in g5["report_only_rates_hz"] + g5["rates_hz"]:
                    try:
                        rec = rigid_trial(cfg, root, body, spin, hz)
                    except Exception as e:
                        rec = dict(body=body, spin=spin, hz=hz, error=f"{type(e).__name__}: {e}")
                    s.write(json.dumps(rec) + "\n")
                    s.flush()
                    print("rigid", body, spin, hz, "error" if "error" in rec else "ok", flush=True)
    shutil.rmtree(root, ignore_errors=True)


def run_flights(cfg, out):
    """G6, native side: the review's open-loop controlled flights with this configuration's integrators."""
    g6 = G["G6"]
    for model in g6["models"]:
        f = native.new_fdm(dt=1.0 / g6["hz"])
        if not f.load_model(model):
            raise RuntimeError("load_model failed")
        for p, v in g6["initial"].items():
            f[p] = v
        apply_config(f, cfg)
        if not f.run_ic():
            raise RuntimeError("run_ic failed")
        get = getters(f, g6["properties"])
        with (out / f"flight-{model}.native.csv").open("w") as s:
            w = csv.writer(s)
            w.writerow(g6["properties"])
            w.writerow([repr(g()) for g in get])
            for k in range(g6["hz"] * g6["seconds"]):
                for p, n in g6["controls"]:
                    f[p] = ((k // n) % 3 - 1) / 128
                if not f.run():
                    raise RuntimeError("run returned False")
                w.writerow([repr(g()) for g in get])
        print("flight", model, "ok", flush=True)


def main():
    name = sys.argv[1]
    cfg = CONFIGS[name]
    want = sys.argv[2:] or ["ground", "nasa", "rigid", "flights"]
    key = native.key_name()
    if key != cfg["source"] and not os.environ.get("GATES_ALLOW_KEY_MISMATCH"):
        raise SystemExit(f"configuration {name} needs the '{cfg['source']}' native build, but this is '{key}' (set PYTHONPATH=build/native/{cfg['source']})")
    out = REPO / "out/gates" / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "native.info.json").write_text(json.dumps(dict(config=name, properties=cfg["properties"], **native.key_info()), indent=1))
    print(f"# gates, native, configuration {name}: {native.describe()}", flush=True)
    for part in want:
        {"ground": run_ground, "nasa": run_nasa, "rigid": run_rigid, "flights": run_flights}[part](cfg, out)


if __name__ == "__main__":
    main()
