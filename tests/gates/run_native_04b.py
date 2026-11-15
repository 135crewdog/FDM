"""G2c (GATES-04b.md), measurements in NATIVE JSBSim. It only measures.
usage: PYTHONPATH=build/native/<source> python tests/gates/run_native_04b.py <config> [--models a,b,...]
Output: out/gates/<config>/forward.native.<model>.jsonl
The trial itself is the frozen run_native_04.repeat_trial (same set-up, same per-step checks, same perturbation
draws); only the scenario differs: the heading is set to north first, so that "100 ft/s north" really is forward.
The start is checked: body velocity must be (100, 0, 30) ft/s, or the run is recorded as an error.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_native_04 as R4  # noqa: E402  (frozen; reused, not changed)

R = R4.R
native, G = R.native, R.G
GB = json.loads((HERE / "gates-04b.json").read_text())
G2C = GB["G2c"]
G["scenarios"][G2C["scenario"]] = G2C["scenario_definition"]   # in memory only; gates.json is not touched


def start_velocity(cfg, model, hz):
    """Body-axis velocity right after the initial conditions of the unperturbed run (ft/s)."""
    f = native.new_fdm(dt=1.0 / hz)
    f.load_model(model)
    f.load_ic(G["aircraft"][model], True)
    for p, v in G2C["scenario_definition"]["ic"].items():
        f[p] = v
    R.apply_config(f, cfg)
    f.run_ic()
    return [f["velocities/u-fps"], f["velocities/v-fps"], f["velocities/w-fps"]]


def main():
    args = sys.argv[1:]
    models = list(G["aircraft"])
    if "--models" in args:
        i = args.index("--models")
        models = args[i + 1].split(",")
        del args[i:i + 2]
    name = args[0]
    cfg = R.CONFIGS[name]
    if native.key_name() != cfg["source"]:
        raise SystemExit(f"configuration {name} needs the '{cfg['source']}' native build (set PYTHONPATH=build/native/{cfg['source']})")
    out = R.REPO / "out/gates" / name
    out.mkdir(parents=True, exist_ok=True)
    print(f"# G2c, native, configuration {name}: {native.describe()}", flush=True)
    want, tol = G2C["required_start_body_velocity_fps"], G2C["start_body_velocity_tolerance_fps"]
    for model in models:
        with (out / f"forward.native.{model}.jsonl").open("w") as s:
            for hz in G["rates_hz"]:
                uvw = start_velocity(cfg, model, hz)
                forward = all(abs(a - b) <= tol for a, b in zip(uvw, want))
                for run in range(len(R4.G4["repeats"]["draws"])):
                    try:
                        if not forward:
                            raise RuntimeError(f"start is not a forward landing: body velocity {uvw}")
                        rec = R4.repeat_trial(cfg, model, G2C["scenario"], hz, run)
                    except Exception as e:
                        rec = dict(model=model, scenario=G2C["scenario"], hz=hz, run=run, error=f"{type(e).__name__}: {e}")
                    rec["start_body_velocity_fps"] = uvw
                    s.write(json.dumps(rec) + "\n")
                s.flush()
                print("forward", model, hz, "done", flush=True)


if __name__ == "__main__":
    main()
