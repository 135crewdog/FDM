"""Session 05: one table of every configuration against every gate the decision is judged on, per step rate.
usage: python tests/gates/summary_05.py floor floor-g c3-ab4 c3-ab4-g c2-mid c2-mid-g
It only collects verdicts and numbers that the judges already produced:
  G2d, G8, G3d, G7   out/gates05/<config>/summary.json                      (evaluate_05.py, via run-05.sh)
  G1, G4, G5b, G6    at 480 and 1000 Hz: out/gates/<config>/verdict*.json   (the frozen evaluators, via run.sh, run-later.sh)
                     at 960 and 1200 Hz: out/shadow05/<hz>/out/gates/<config>/verdict*.json  (the same frozen
                     evaluators run at that rate by run-rates-05.sh; G6 there is parity flown at that rate)
A configuration passes at a step rate only if all eight pass (the session's decision rule).
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CONFIGS = json.loads((HERE / "configs.json").read_text())
W = {True: "pass", False: "**FAIL**", None: "not measured"}


def load_eval(root):
    """The frozen evaluate_04 of a tree (the repository or a shadow copy): it reads the measurements of that tree."""
    name = "ev04_" + str(abs(hash(str(root))))
    for m in ("evaluate", "evaluate_04"):
        sys.modules.pop(m, None)
    sys.path.insert(0, str(root / "tests/gates"))
    try:
        spec = importlib.util.spec_from_file_location(name, root / "tests/gates/evaluate_04.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod


def old_gates(config, hz):
    root = REPO if hz in (480, 1000) else REPO / f"out/shadow05/{hz}"
    d = root / "out/gates" / config
    if not (d / "verdict04.json").exists() or not (d / "verdict.json").exists():
        return None
    v4 = json.loads((d / "verdict04.json").read_text())
    v = json.loads((d / "verdict.json").read_text())["verdicts"]
    L = load_eval(root)
    _, worst1 = L.g1_at(config)
    _, num4 = L.g4_at(config)
    worst5 = 0.0
    for p in L.PLATFORMS:
        for r in L.jsonl(d / f"rigidb.{p}.jsonl") or []:
            if r["hz"] == hz and r["spin"] not in L.G["G5"]["report_only_spins"]:
                worst5 = max(worst5, float("inf") if ("error" in r or not r.get("finite_after_start", r.get("finite", True))) else max(r.get("energy_drift_after_start", r.get("energy_drift", 0)), r.get("momentum_magnitude_drift_after_start", r.get("momentum_magnitude_drift", 0))))
    k = str(hz)
    return dict(G1=v4["G1"].get(k), G4=v4["G4"].get(k), G5b=v4["G5b"].get(k), G6=v["G6"], g1=worst1.get(hz), g4=num4.get(hz), g5=worst5)


def main(configs):
    lines = ["| configuration | step rate | G1 Rest (rad/s) | G4 NASA (deg/s) | G5b Energy drift | G6 Parity | G2d Landing | G8 Repeated contact | G3d Crash containment | G7 Forced flight | **passes at this rate** |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    detail = []
    for c in configs:
        sp = REPO / "out/gates05" / c / "summary.json"
        new = json.loads(sp.read_text()) if sp.exists() else None
        for hz in CONFIGS[c]["rates_05"]:
            o = old_gates(c, hz)
            cells, ok_all = [], True
            if o is None:
                cells += ["not measured"] * 4
                ok_all = None
            else:
                cells.append(f"{W[o['G1']]} {o['g1']:.0e}")
                cells.append(f"{W[o['G4']]} {o['g4'][0]:.1e}")
                cells.append(f"{W[o['G5b']]} {o['g5']:.1e}")
                cells.append(W[o["G6"]])
                ok_all = all(o[g] is True for g in ("G1", "G4", "G5b", "G6"))
            for g in ("G2d", "G8", "G3d", "G7"):
                if new is None or str(hz) not in new["rates"]:
                    cells.append("not measured")
                    ok_all = None
                    continue
                per = new["rates"][str(hz)]
                ok = all(per[p][g]["passed"] for p in ("native", "wasm"))
                counts = []
                for p in ("native", "wasm"):
                    rows = per[p][g]["rows"]
                    counts.append(f"{sum(1 for r in rows if not (r.get('bad') or r.get('failed_runs')))}/{len(rows)}")
                    for r in rows:
                        if r.get("bad") or r.get("failed_runs"):
                            what = r.get("what") or f"{r['model']} {r.get('case') or r.get('scenario')}"
                            why = "; ".join(r["bad"]) if not r.get("failed_runs") else f"{r['failed_runs']}/{r['runs']} runs: " + "; ".join(r.get("first_bad", []))
                            detail.append(f"- `{c}` {hz} Hz {g} {p}: {what}: {why}")
                cells.append(f"{W[ok]} {' / '.join(counts)}")
                ok_all = (ok_all and ok) if ok_all is not None else None
            lines.append(f"| `{c}` | {hz} Hz | " + " | ".join(cells) + f" | **{'PASS' if ok_all else 'not complete' if ok_all is None else 'FAIL'}** |")
    print("# Session 05: every configuration against every gate of the decision, per step rate")
    print()
    print("Limits: G1 body rates below 1e-6 rad/s at rest; G4 within 2e-6 deg/s of NASA; G5b energy and momentum drift below 1e-6; G6 as frozen. "
          "G2d, G8, G3d, G7: GATES-05.md; cells show cases good, native / WebAssembly. `-g` = the strut limits of patch 0004 switched on.")
    print()
    print("\n".join(lines))
    print()
    print("## Every failed case of the new gates")
    print("\n".join(detail) if detail else "none")


if __name__ == "__main__":
    main(sys.argv[1:])
