"""Judge one configuration against the later gates of session 04 (gates-04.json, GATES-04.md), and put the
verdicts next to the frozen gates' per step rate.
usage: python tests/gates/evaluate_04.py <config> [--floor <config>]
Reads out/gates/<config>/: rigidb.*.jsonl and repeat.*.jsonl (run_native_04.py, run_wasm_04.ts), and the frozen
runners' ground.*.jsonl, nasa-*.csv and verdict.json (tests/gates/run.sh must have run first).
Prints a report (Markdown) and writes out/gates/<config>/verdict04.json. A gate that was not fully measured on
both platforms is INCOMPLETE, never PASS. Exit code 2 if something is missing.
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
import evaluate as E  # noqa: E402  (frozen; its definitions are reused, not changed)

G = E.G
G4 = json.loads((HERE / "gates-04.json").read_text())
PLATFORMS = E.PLATFORMS
RATES = G["rates_hz"]
JUDGED = G4["judged_rates_hz"]
FROZEN04 = ["tests/gates/gates-04.json", "tests/gates/run_native_04.py", "tests/gates/run_wasm_04.ts", "tests/gates/evaluate_04.py", "GATES-04.md"]
missing = []
WORD = {True: "PASS", False: "FAIL", None: "INCOMPLETE"}


def jsonl(path):
    if not path.exists():
        missing.append(str(path.relative_to(REPO)))
        return None
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def e(x, d=1):
    return "-" if x is None else f"{x:.{d}e}"


# ---------------------------------------------------------------- G5b
def g5b(config):
    """-> {hz: verdict}, table lines, failures"""
    g5, tol = G["G5"], G4["G5b"]["max_relative_drift"]
    rates = g5["report_only_rates_hz"] + g5["rates_hz"]
    data = {p: jsonl(REPO / f"out/gates/{config}/rigidb.{p}.jsonl") for p in PLATFORMS}
    if any(v is None for v in data.values()):
        return {hz: None for hz in rates}, ["not measured"], []
    idx = {p: {(r["body"], r["spin"], r["hz"]): r for r in data[p]} for p in PLATFORMS}
    verdict = {hz: True for hz in rates}
    lines = ["| body | spin (deg/s) | " + " | ".join(f"{hz} Hz" for hz in rates) + " |", "|---|---|" + "---|" * len(rates)]
    fails = []
    for body in g5["bodies"]:
        for spin, w in g5["spins_deg_s"].items():
            gated = spin not in g5["report_only_spins"]
            cells = []
            for hz in rates:
                dT = dH = 0.0
                bad = False
                for p in PLATFORMS:
                    r = idx[p].get((body, spin, hz))
                    if r is None or "error" in r or not r["finite"]:
                        bad = True
                        continue
                    dT, dH = max(dT, r["energy_drift"]), max(dH, r["momentum_magnitude_drift"])
                good = not bad and dT < tol and dH < tol
                if gated and not good:
                    verdict[hz] = False
                    fails.append(f"{body} {spin} {hz} Hz: " + ("blew up or not run" if bad else f"energy {e(dT, 2)}, |H| {e(dH, 2)}"))
                cells.append(f"{('ok' if good else '**FAIL**') if gated else ''} {'blew up (non-finite)' if bad else e(dT) + ' / ' + e(dH)}".strip())
            lines.append(f"| {body} | {spin}{'' if gated else ' (not gated)'} {w} | " + " | ".join(cells) + " |")
    return verdict, lines, fails


# ---------------------------------------------------------------- repeated runs
def repeats(config):
    """-> {platform: {(model, scenario, hz): [records]}} or None"""
    out = {}
    for p in PLATFORMS:
        out[p] = {}
        for model in G["aircraft"]:
            recs = jsonl(REPO / f"out/gates/{config}/repeat.{p}.{model}.jsonl")
            if recs is None:
                return None
            for r in recs:
                out[p].setdefault((r["model"], r["scenario"], r["hz"]), []).append(r)
    return out


N_RUNS = len(G4["repeats"]["draws"])


def run_ok(r):
    """G2's conditions for one run: finite, no runaway, ran to the end, touched the ground."""
    return "error" not in r and r["first_nonfinite"] is None and r["first_runaway"] is None and r["steps_done"] == r["steps"] and r["first_contact"] is not None


def g2b(rep):
    sc, need = G4["G2b"]["scenario"], G4["G2b"]["min_fraction_ok"]
    if rep is None:
        return {hz: None for hz in RATES}, ["not measured"], []
    verdict = {hz: True for hz in RATES}
    lines = ["| aircraft | " + " | ".join(f"{hz} Hz" for hz in RATES) + " |", "|---|" + "---|" * len(RATES)]
    notes = []
    for model in G["aircraft"]:
        cells = []
        for hz in RATES:
            parts = []
            for p in PLATFORMS:
                runs = rep[p].get((model, sc, hz), [])
                if len(runs) != N_RUNS:
                    verdict[hz] = None
                    parts.append("?")
                    continue
                ok = sum(run_ok(r) for r in runs)
                if ok / N_RUNS < need and verdict[hz] is not None:
                    verdict[hz] = False
                never = sum(1 for r in runs if "error" not in r and r["first_contact"] is None and r["first_nonfinite"] is None)
                if never:
                    notes.append(f"{model} {hz} Hz {p}: {never} run(s) never touched the ground (counted as failures)")
                parts.append(str(ok))
            cells.append(("" if all(x == str(N_RUNS) for x in parts) else "**") + " / ".join(parts) + ("" if all(x == str(N_RUNS) for x in parts) else "**"))
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    tot = []
    for hz in RATES:
        tot.append(" / ".join(str(sum(sum(run_ok(r) for r in rep[p].get((m, sc, hz), [])) for m in G["aircraft"])) for p in PLATFORMS))
    lines.append(f"| **all five (of {N_RUNS * len(G['aircraft'])})** | " + " | ".join(tot) + " |")
    return verdict, lines, notes


def g3b_counts(rep, p, hz):
    """runaway runs per case at one rate on one platform, G3's definition of a runaway"""
    out = {}
    for model in G["aircraft"]:
        for sc in G4["G3b"]["scenarios"]:
            runs = rep[p].get((model, sc, hz), [])
            if len(runs) != N_RUNS:
                return None
            out[(model, sc)] = sum(E.runaway(r) for r in runs)
    return out


def g3b(rep, floor_rep, is_floor):
    n_cases = len(G["aircraft"]) * len(G4["G3b"]["scenarios"])
    n = n_cases * N_RUNS
    allow = math.floor(G4["G3b"]["allowance_fraction_of_runs"] * n)
    if rep is None or (not is_floor and floor_rep is None):
        return {hz: None for hz in RATES}, ["not measured" if rep is None else "the floor has not been measured"], []
    verdict = {hz: True for hz in RATES}
    lines = [f"| rate | platform | runaway runs (of {n}) | floor | allowed (floor + {allow}) | verdict |", "|---|---|---|---|---|---|"]
    detail = []
    for hz in RATES:
        for p in PLATFORMS:
            mine = g3b_counts(rep, p, hz)
            if mine is None:
                verdict[hz] = None
                lines.append(f"| {hz} Hz | {p} | incomplete | | | |")
                continue
            total = sum(mine.values())
            if is_floor:
                lines.append(f"| {hz} Hz | {p} | {total} | (this is the floor) | - | reference |")
                continue
            base = g3b_counts(floor_rep, p, hz)
            if base is None:
                verdict[hz] = None
                lines.append(f"| {hz} Hz | {p} | {total} | incomplete | | |")
                continue
            good = total <= sum(base.values()) + allow
            if not good and verdict[hz] is not None:
                verdict[hz] = False
            lines.append(f"| {hz} Hz | {p} | {total} | {sum(base.values())} | {sum(base.values()) + allow} | {'no worse' if good else '**WORSE**'} |")
            diff = [(k, mine[k], base[k]) for k in mine if abs(mine[k] - base[k]) > N_RUNS // 4]
            if diff:
                detail.append(f"{hz} Hz {p}, cases that differ from the floor by more than {N_RUNS // 4} runs (here / floor): " + "; ".join(f"{m} {sc} {a}/{b}" for (m, sc), a, b in diff))
    return verdict, lines, detail


def g3b_cases(rep):
    """per-case table: runaway runs of N_RUNS, native / WebAssembly"""
    lines = ["| aircraft, impact | " + " | ".join(f"{hz} Hz" for hz in RATES) + " |", "|---|" + "---|" * len(RATES)]
    for model in G["aircraft"]:
        for sc in G4["G3b"]["scenarios"]:
            cells = []
            for hz in RATES:
                cells.append(" / ".join(str(sum(E.runaway(r) for r in rep[p].get((model, sc, hz), []))) for p in PLATFORMS))
            lines.append(f"| {model}, {sc} | " + " | ".join(cells) + " |")
    return lines


# ---------------------------------------------------------------- the frozen gates, read per step rate
def g1_at(config):
    """G1's own conditions (gates.json), applied to the runs at one step rate."""
    data = E.ground(config)
    g = G["G1"]
    out, worst = {}, {}
    for hz in RATES:
        v, w = True, 0.0
        for p in PLATFORMS:
            if data[p] is None:
                v = None
                break
            for model in G["aircraft"]:
                r = E.pick(data[p], g["scenario"]).get((model, hz))
                ok = (r is not None and "error" not in r and r["first_nonfinite"] is None and r["steps_done"] == r["steps"] and r["tail_always_in_contact"]
                      and r["tail_max_rate"] < g["max_abs_body_rate_rad_s"] and r["tail_max_horizontal_displacement_ft"] < g["max_horizontal_displacement_ft"])
                w = max(w, r.get("tail_max_rate", math.inf) if r else math.inf)
                v = v and ok
        out[hz], worst[hz] = v, w
    return out, worst


def g4_at(config):
    """G4's own conditions (gates.json), per step rate. Rates G4 does not measure give None."""
    g = G["G4"]
    refs = {name: E.nasa_csv(E.NASA_REF / f"Atmos_02_{name}.csv") for name in g["references"]}
    out, num = {}, {}
    for hz in g["rates_hz"]:
        v, rate, att = True, 0.0, 0.0
        for p in PLATFORMS:
            path = REPO / f"out/gates/{config}/nasa-{hz}.{p}.csv"
            if not path.exists():
                missing.append(str(path.relative_to(REPO)))
                v = None
                break
            run = E.nasa_csv(path)
            for ref in refs.values():
                ts = [t for t in run if t in ref]
                finite = all(math.isfinite(x) for t in ts for x in run[t].values())
                rr = max(abs(run[t][c] - ref[t][c]) for t in ts for c in E.RATES) if finite and ts else math.inf
                aa = max(abs((run[t][c] - ref[t][c] + 180.0) % 360.0 - 180.0) for t in ts for c in E.ANGLES) if finite and ts else math.inf
                rate, att = max(rate, rr), max(att, aa)
                v = v and finite and len(run) == g["samples"] and len(ts) == g["samples"] and rr < g["max_body_rate_error_deg_s"] and aa < g["max_attitude_error_deg"]
        out[hz], num[hz] = v, (rate, att)
    return out, num


def main():
    config = sys.argv[1]
    floor = sys.argv[sys.argv.index("--floor") + 1] if "--floor" in sys.argv else "floor"
    cfg = E.CONFIGS[config]
    is_floor = config == floor
    print(f"# Later gates (session 04): configuration `{config}`")
    print()
    print(f"- Role: {cfg['role']}")
    print(f"- Source: JSBSim v1.3.3 {cfg['source']}; properties: " + ", ".join(f"`{k}` = {v}" for k, v in cfg["properties"].items()))
    for p in PLATFORMS:
        info = REPO / f"out/gates/{config}/{p}.info04.json"
        if info.exists():
            d = json.loads(info.read_text())
            what = d.get("build") or f"native JSBSim {d['version']} [{d['key']}] module sha256 {str(d['module_sha256'])[:16]}"
            patches = ", ".join(f"{x['file']} {x['sha256'][:12]}" for x in d.get("patches", [])) or "none"
            print(f"- {p}: {what}; patches: {patches}")
    sha = hashlib.sha256((HERE / "gates-04.json").read_bytes()).hexdigest()
    commit = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%h %cI", "--"] + FROZEN04, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--"] + FROZEN04, capture_output=True, text=True).stdout.strip()
    print(f"- Later-gate definitions: gates-04.json sha256 {sha[:16]}; last commit touching the later-gate files: {commit or 'NOT COMMITTED'}{' (UNCOMMITTED CHANGES: ' + dirty.replace(chr(10), '; ') + ')' if dirty else ''}")
    print(f"- Judged at {' and '.join(str(x) for x in JUDGED)} Hz; {' and '.join(str(x) for x in G4['reported_rates_hz'])} Hz are reported only.")
    print()

    v5, lines, fails = g5b(config)
    print("## G5b Rigid body after start-up: " + ", ".join(f"{hz} Hz {WORD[v5[hz]]}" for hz in JUDGED))
    print(f"G5's bodies and spins, 60 s. Each cell: worst of native and WebAssembly, relative drift of rotational kinetic energy / of the magnitude of angular momentum, measured against their values at {G4['G5b']['measure_from_seconds']:g} s (gate: both < {G4['G5b']['max_relative_drift']:g}).")
    print()
    print("\n".join(lines))
    E.show(fails)
    print()

    rep = repeats(config)
    floor_rep = None if is_floor else (repeats(floor) if (REPO / f"out/gates/{floor}").exists() else None)
    v2, lines, notes = g2b(rep)
    print("## G2b Hard landing, repeated: " + ", ".join(f"{hz} Hz {WORD[v2[hz]]}" for hz in JUDGED))
    print(f"G2's hard landing, {N_RUNS} runs per case (1 unperturbed, {N_RUNS - 1} with the start moved by up to 1e-6 ft, 1e-6 ft/s, 1e-6 deg). Each cell: runs that stay finite, without runaway, native / WebAssembly, of {N_RUNS}. Gate: every run, on both.")
    print()
    print("\n".join(lines))
    E.show(notes)
    print()

    v3, lines, detail = g3b(rep, floor_rep, is_floor)
    print("## G3b Extreme impacts, repeated: " + ("REFERENCE (this is the floor)" if is_floor and rep is not None else ", ".join(f"{hz} Hz {WORD[v3[hz]]}" for hz in JUDGED)))
    print(f"G3's impacts, {N_RUNS} runs per case. Runaway runs (rates > 1e6 rad/s, non-finite or exception) are counted per step rate and compared with the floor's count plus an allowance of {G4['G3b']['allowance_fraction_of_runs']:.0%} of the runs.")
    print()
    print("\n".join(lines))
    for d in detail:
        print(f"- {d}")
    if rep is not None:
        print()
        print(f"Runaway runs per case, native / WebAssembly, of {N_RUNS}:")
        print()
        print("\n".join(g3b_cases(rep)))
    print()

    v1, worst1 = g1_at(config)
    v4, num4 = g4_at(config)
    old = REPO / f"out/gates/{config}/verdict.json"
    v6 = json.loads(old.read_text())["verdicts"]["G6"] if old.exists() else None
    if not old.exists():
        missing.append(str(old.relative_to(REPO)))
    print("## Verdict per step rate")
    print("G1 and G4 are the frozen gates read at one step rate (same measurements, same limits). G6 is measured at 480 Hz and applies to the configuration. G3b for the floor is the reference and counts as passed.")
    print()
    print("| step rate | G1 Rest | G2b Hard landing x" + str(N_RUNS) + " | G3b Impacts x" + str(N_RUNS) + " | G4 NASA | G5b Rigid body | G6 Parity | all |")
    print("|---|---|---|---|---|---|---|---|")
    decision = {}
    for hz in RATES:
        g3v = True if (is_floor and rep is not None) else v3[hz]
        cells = [WORD[v1[hz]], WORD[v2[hz]], ("reference" if is_floor and rep is not None else WORD[v3[hz]]),
                 (WORD[v4[hz]] if hz in v4 else "not measured"), WORD[v5[hz]], WORD[v6]]
        if hz in JUDGED:
            parts = [v1[hz], v2[hz], g3v, v4.get(hz), v5[hz], v6]
            decision[hz] = None if any(x is None for x in parts) else all(parts)
            cells.append(f"**{WORD[decision[hz]]}**")
            print(f"| **{hz} Hz (judged)** | " + " | ".join(cells) + " |")
        else:
            cells.append("reported only")
            print(f"| {hz} Hz | " + " | ".join(cells) + " |")
    print()
    print("Numbers behind G1 and G4 at the judged rates: " + "; ".join(
        f"{hz} Hz: rest rate {e(worst1[hz])} rad/s, NASA rate error {e(num4[hz][0])} deg/s, attitude error {e(num4[hz][1])} deg" for hz in JUDGED if hz in num4))
    if missing:
        print()
        print("Missing measurements: " + ", ".join(sorted(set(missing))))
    out = REPO / f"out/gates/{config}/verdict04.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    key = lambda d: {str(k): v for k, v in d.items()}  # noqa: E731
    out.write_text(json.dumps(dict(config=config, G1=key(v1), G2b=key(v2), G3b=("reference" if is_floor else key(v3)), G4=key(v4), G5b=key(v5), G6=v6,
                                   decision=key(decision), missing=sorted(set(missing)), gates04_sha256=sha), indent=1))
    return 2 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
