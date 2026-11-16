"""Session 05 gates (GATES-05.md), measurements in NATIVE JSBSim. The procedures are in sim05.py; every run is
measured by evaluate_05.py right after it is made (the raw rows are large and are deleted unless KEEP_RAW=1).
usage: PYTHONPATH=build/native/<source> python tests/gates/run_native_05.py <config> <hz> <part> [--models a,b]
  part: landing | g8 | crash | probe | fast          (a reference configuration takes: landing g8, or fast)
Output: out/gates05/<config>/<hz>/native/metrics-<part>[-<models>].jsonl (+ small files the judge compares)
"""
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sim05  # noqa: E402
import evaluate_05 as E  # noqa: E402

native, G5, CONFIGS = sim05.native, sim05.G5, sim05.CONFIGS


def cases_for(model):
    return G5["G2d"].get("cases_by_aircraft", {}).get(model, G5["G2d"]["cases"])


def jobs(part, models):
    """(file stem, function to call with the output path) for every run of a part."""
    out = []
    if part == "landing":
        for m in models or G5["G2d"]["aircraft"]:
            for c in cases_for(m):
                out.append((f"landing-{m}-{c}", (lambda p, m=m, c=c: (sim05.heli_landing(c, HZ, CFG, p) if m == "ah1s" else sim05.landing(m, c, HZ, CFG, p)))))
    elif part == "g8":
        for m in models or G5["G8"]["aircraft"]:
            for c in G5["G8"]["cases"]:
                out.append((f"g8-{m}-{c}", (lambda p, m=m, c=c: sim05.landing(m, c, HZ, CFG, p))))
        if not REFERENCE and not models:
            out.append(("g8-release", lambda p: sim05.release_probe(HZ, CFG, p, tempfile.mkdtemp(prefix="fdm-g8-"))))
    elif part == "crash":
        for m in models or list(G5["G3d"]["aircraft"]):
            for sc in G5["G3d"]["scenarios"]:
                for run in range(len(G5["G3d"]["draws"])):
                    out.append((f"crash-{m}-{sc}-{run}", (lambda p, m=m, sc=sc, run=run: sim05.crash(m, sc, run, HZ, CFG, p))))
    elif part == "probe":
        for c in G5["G7"]["probe_cases"]:
            for where in G5["G7"]["where"]:
                out.append((f"probe-{c}-{where}", (lambda p, c=c, where=where: sim05.forced_probe(c, where, HZ, CFG, p, tempfile.mkdtemp(prefix="fdm-g7-")))))
    elif part == "fast":
        for m in models or list(G5["G7"]["fast_points"]):
            out.append((f"fast-{m}", (lambda p, m=m: sim05.fast_flight(m, HZ, CFG, p))))
    else:
        raise SystemExit(f"unknown part {part}")
    return out


def main():
    global HZ, CFG, REFERENCE
    args = sys.argv[1:]
    models = None
    if "--models" in args:
        i = args.index("--models")
        models = args[i + 1].split(",")
        del args[i:i + 2]
    name, HZ, part = args[0], int(args[1]), args[2]
    CFG = CONFIGS[name]
    REFERENCE = name.startswith("ref05-")
    if native.key_name() != CFG["source"]:
        raise SystemExit(f"configuration {name} needs the '{CFG['source']}' native build (set PYTHONPATH=build/native/{CFG['source']})")
    out = native.REPO / "out/gates05" / name / str(HZ) / "native"
    out.mkdir(parents=True, exist_ok=True)
    (out / "info.json").write_text(json.dumps(dict(config=name, hz=HZ, properties=CFG["properties"], **native.key_info()), indent=1))
    tag = part + ("-" + "-".join(models) if models else "")
    print(f"# session 05 gates, native, {name} at {HZ} Hz, {tag}: {native.describe()}", flush=True)
    with (out / f"metrics-{tag}.jsonl").open("w") as s:
        for stem, fn in jobs(part, models):
            raw = out / f"{stem}.f64"
            try:
                fn(raw)
                rec = E.measure(raw, keep=bool(os.environ.get("KEEP_RAW")))
            except Exception as e:  # noqa: BLE001  recorded; the judge counts it as a failure
                rec = dict(file=stem, kind="error", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-600:])
            if rec is not None:
                s.write(json.dumps(rec) + "\n")
                s.flush()
            print(stem, "error" if rec and rec.get("kind") == "error" else "ok", flush=True)
    shutil.rmtree(native.SCRATCH, ignore_errors=True)


if __name__ == "__main__":
    main()
