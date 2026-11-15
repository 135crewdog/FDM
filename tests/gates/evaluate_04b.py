"""Judge one configuration with the corrected hard-landing gate G2c (GATES-04b.md), and print the verdict
per step rate both ways: as first committed (with G2b) and corrected (G2c for the hard landing; G2b read as a
crash case against the floor).
usage: python tests/gates/evaluate_04b.py <config> [--floor <config>]
Needs evaluate_04.py to have run (out/gates/<config>/verdict04.json). Writes verdict04b.json.
"""
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import evaluate_04 as L  # noqa: E402  (frozen)

G, G4 = L.G, L.G4
GB = json.loads((HERE / "gates-04b.json").read_text())
PLATFORMS, RATES, JUDGED, N_RUNS = L.PLATFORMS, L.RATES, L.JUDGED, L.N_RUNS
FROZEN04B = ["tests/gates/gates-04b.json", "tests/gates/run_native_04b.py", "tests/gates/run_wasm_04b.ts", "tests/gates/evaluate_04b.py"]
WORD = L.WORD
missing = []


def forward(config):
    out = {}
    for p in PLATFORMS:
        out[p] = {}
        for model in G["aircraft"]:
            path = REPO / f"out/gates/{config}/forward.{p}.{model}.jsonl"
            if not path.exists():
                missing.append(str(path.relative_to(REPO)))
                return None
            for r in (json.loads(x) for x in path.read_text().splitlines() if x.strip()):
                out[p].setdefault((r["model"], r["hz"]), []).append(r)
    return out


def g2c(fw):
    need = GB["G2c"]["min_fraction_ok"]
    if fw is None:
        return {hz: None for hz in RATES}, ["not measured"], []
    verdict = {hz: True for hz in RATES}
    lines = ["| aircraft | " + " | ".join(f"{hz} Hz" for hz in RATES) + " |", "|---|" + "---|" * len(RATES)]
    notes = []
    for model in G["aircraft"]:
        cells = []
        for hz in RATES:
            parts = []
            for p in PLATFORMS:
                runs = fw[p].get((model, hz), [])
                if len(runs) != N_RUNS:
                    verdict[hz] = None
                    parts.append("?")
                    continue
                ok = sum(L.run_ok(r) for r in runs)
                if ok / N_RUNS < need and verdict[hz] is not None:
                    verdict[hz] = False
                errs = sorted({r["error"] for r in runs if "error" in r})
                if errs:
                    notes.append(f"{model} {hz} Hz {p}: {errs[0]}")
                parts.append(str(ok))
            full = all(x == str(N_RUNS) for x in parts)
            cells.append(("" if full else "**") + " / ".join(parts) + ("" if full else "**"))
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    lines.append(f"| **all five (of {N_RUNS * len(G['aircraft'])})** | " + " | ".join(
        " / ".join(str(sum(sum(L.run_ok(r) for r in fw[p].get((m, hz), [])) for m in G["aircraft"])) for p in PLATFORMS) for hz in RATES) + " |")
    return verdict, lines, notes


def g2b_bad(rep, p, hz):
    sc = G4["G2b"]["scenario"]
    runs = [r for m in G["aircraft"] for r in rep[p].get((m, sc, hz), [])]
    return None if len(runs) != N_RUNS * len(G["aircraft"]) else sum(not L.run_ok(r) for r in runs)


def g2b_as_crash(rep, floor_rep, is_floor):
    n = N_RUNS * len(G["aircraft"])
    allow = math.floor(GB["G2b_as_crash"]["allowance_fraction_of_runs"] * n)
    if rep is None or (not is_floor and floor_rep is None):
        return {hz: None for hz in RATES}, ["not measured"]
    verdict = {hz: True for hz in RATES}
    lines = [f"| rate | platform | bad runs (of {n}) | floor | allowed (floor + {allow}) | verdict |", "|---|---|---|---|---|---|"]
    for hz in RATES:
        for p in PLATFORMS:
            mine = g2b_bad(rep, p, hz)
            base = mine if is_floor else g2b_bad(floor_rep, p, hz)
            if mine is None or base is None:
                verdict[hz] = None
                lines.append(f"| {hz} Hz | {p} | incomplete | | | |")
            elif is_floor:
                lines.append(f"| {hz} Hz | {p} | {mine} | (this is the floor) | - | reference |")
            else:
                good = mine <= base + allow
                if not good and verdict[hz] is not None:
                    verdict[hz] = False
                lines.append(f"| {hz} Hz | {p} | {mine} | {base} | {base + allow} | {'no worse' if good else '**WORSE**'} |")
    return verdict, lines


def main():
    config = sys.argv[1]
    floor = sys.argv[sys.argv.index("--floor") + 1] if "--floor" in sys.argv else "floor"
    is_floor = config == floor
    cfg = L.E.CONFIGS[config]
    v04p = REPO / f"out/gates/{config}/verdict04.json"
    if not v04p.exists():
        print(f"error: run tests/gates/run-later.sh {config} first", file=sys.stderr)
        return 2
    v04 = json.loads(v04p.read_text())
    sha = hashlib.sha256((HERE / "gates-04b.json").read_bytes()).hexdigest()
    commit = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%h %cI", "--"] + FROZEN04B, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--"] + FROZEN04B, capture_output=True, text=True).stdout.strip()
    print(f"# Corrected hard-landing gate G2c: configuration `{config}`")
    print()
    print(f"- Role: {cfg['role']}")
    print(f"- G2c definition: gates-04b.json sha256 {sha[:16]}; last commit touching the G2c files: {commit or 'NOT COMMITTED'}{' (UNCOMMITTED CHANGES: ' + dirty.replace(chr(10), '; ') + ')' if dirty else ''}")
    print()
    fw = forward(config)
    v2c, lines, notes = g2c(fw)
    print("## G2c Hard landing, forward, repeated: " + ", ".join(f"{hz} Hz {WORD[v2c[hz]]}" for hz in JUDGED))
    print(f"As G2b, but every aircraft is first turned to face north, so it really moves forward at 100 ft/s (body velocity 100, 0, 30 ft/s; checked). Each cell: good runs, native / WebAssembly, of {N_RUNS}. Gate: every run, on both.")
    print()
    print("\n".join(lines))
    L.E.show(sorted(set(notes)))
    print()
    rep = L.repeats(config)
    floor_rep = None if is_floor else (L.repeats(floor) if (REPO / f"out/gates/{floor}").exists() else None)
    vcr, lines = g2b_as_crash(rep, floor_rep, is_floor)
    print("## G2b read as a crash case, compared with the floor: " + ("REFERENCE (this is the floor)" if is_floor and rep is not None else ", ".join(f"{hz} Hz {WORD[vcr[hz]]}" for hz in JUDGED)))
    print("G2b's touchdown is backward or sideways for four of the five aircraft (GATES-04b.md). Its bad runs are counted per step rate and compared with the floor's count plus 5% of the runs, as G3b does.")
    print()
    print("\n".join(lines))
    print()
    print("## Verdict per step rate, both ways")
    print()
    print("| step rate | G1 Rest | G2c Forward hard landing x" + str(N_RUNS) + " | G2b as a crash case | G3b Impacts x" + str(N_RUNS) + " | G4 NASA | G5b Rigid body | G6 Parity | all, corrected (G2c) | all, as first committed (G2b must be 21 of 21) |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    corrected = {}
    for hz in RATES:
        k = str(hz)
        g3 = True if v04["G3b"] == "reference" else v04["G3b"][k]
        gcr = True if (is_floor and rep is not None) else vcr[hz]
        cells = [WORD[v04["G1"][k]], WORD[v2c[hz]], "reference" if is_floor and rep is not None else WORD[vcr[hz]],
                 "reference" if v04["G3b"] == "reference" else WORD[v04["G3b"][k]],
                 WORD[v04["G4"][k]] if k in v04["G4"] else "not measured", WORD[v04["G5b"][k]], WORD[v04["G6"]]]
        if hz in JUDGED:
            parts = [v04["G1"][k], v2c[hz], gcr, g3, v04["G4"].get(k), v04["G5b"][k], v04["G6"]]
            corrected[hz] = None if any(x is None for x in parts) else all(parts)
            cells += [f"**{WORD[corrected[hz]]}**", WORD[v04["decision"][k]]]
            print(f"| **{hz} Hz (judged)** | " + " | ".join(cells) + " |")
        else:
            cells += ["reported only", "reported only"]
            print(f"| {hz} Hz | " + " | ".join(cells) + " |")
    if missing:
        print()
        print("Missing measurements: " + ", ".join(sorted(set(missing))))
    key = lambda d: {str(k): v for k, v in d.items()}  # noqa: E731
    (REPO / f"out/gates/{config}/verdict04b.json").write_text(json.dumps(dict(
        config=config, G2c=key(v2c), G2b_as_crash=("reference" if is_floor else key(vcr)), decision_corrected=key(corrected),
        decision_as_first_committed=v04["decision"], missing=sorted(set(missing)), gates04b_sha256=sha), indent=1))
    return 2 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
