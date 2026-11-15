"""Judge one configuration against the gates in gates.json, from the measurements in out/gates/<config>/.
usage: python tests/gates/evaluate.py <config> [--floor <config>]
It prints a report (Markdown tables) and writes out/gates/<config>/verdict.json. A gate that was not
fully measured on every required platform is INCOMPLETE, never PASS. Exit code: 0 if every gate could be
judged, 2 if something is missing. (Pass or fail is in the report, not in the exit code.)
"""
import csv
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "parity"))
import compare as parity  # noqa: E402

G = json.loads((HERE / "gates.json").read_text())
CONFIGS = json.loads((HERE / "configs.json").read_text())
NASA_REF = REPO / "reference/nasa-checkcases/Atmos_02_TumblingBrickNoDamping"
PLATFORMS = ["native", "wasm-jsbsim-weh"]            # every gate must hold on both
PARITY_PLATFORMS = ["wasm-jsbsim-weh", "wasm-jsbsim"]  # G6: each WebAssembly variant against native
FROZEN = ["tests/gates/gates.json", "tests/gates/run_native.py", "tests/gates/run_wasm.ts", "tests/gates/evaluate.py",
          "tests/gates/fixtures/brick_poi.xml", "tests/parity/compare.py", "GATES.md"]
missing = []


def jsonl(path):
    if not path.exists():
        missing.append(str(path.relative_to(REPO)))
        return None
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def e(x, digits=2):
    return "-" if x is None else f"{x:.{digits}e}"


def runaway(r):
    """G3's definition: a body rate above 1e6 rad/s, a non-finite value, or an exception."""
    return "error" in r or r.get("first_nonfinite") is not None or r.get("first_runaway") is not None


def ground(config):
    return {p: jsonl(REPO / f"out/gates/{config}/ground.{p}.jsonl") for p in PLATFORMS}


def pick(recs, scenario):
    return {(r["model"], r["hz"]): r for r in recs if r["scenario"] == scenario}


def g1(data):
    g = G["G1"]
    ok_all, lines, fails = True, [], []
    lines.append("| aircraft | " + " | ".join(f"{hz} Hz" for hz in G["rates_hz"]) + " |")
    lines.append("|---|" + "---|" * len(G["rates_hz"]))
    for model in G["aircraft"]:
        cells = []
        for hz in G["rates_hz"]:
            worst_rate = worst_disp = 0.0
            good = True
            for p in PLATFORMS:
                if data[p] is None:
                    return None, ["not measured on " + p], []
                r = pick(data[p], g["scenario"]).get((model, hz))
                if r is None or "error" in r:
                    good = False
                    fails.append(f"{model} {hz} Hz {p}: {'not run' if r is None else r['error']}")
                    continue
                worst_rate = max(worst_rate, r["tail_max_rate"])
                worst_disp = max(worst_disp, r["tail_max_horizontal_displacement_ft"])
                why = []
                if r["first_nonfinite"] is not None or r["steps_done"] != r["steps"]:
                    why.append(f"non-finite {r['nonfinite_property']} at {r['first_nonfinite']} s" if r["first_nonfinite"] is not None else "ended early")
                if not r["tail_always_in_contact"]:
                    why.append("not on the ground throughout the last 10 s")
                if not r["tail_max_rate"] < g["max_abs_body_rate_rad_s"]:
                    why.append(f"rate {e(r['tail_max_rate'])} rad/s")
                if not r["tail_max_horizontal_displacement_ft"] < g["max_horizontal_displacement_ft"]:
                    why.append(f"moved {e(r['tail_max_horizontal_displacement_ft'])} ft")
                if why:
                    good = False
                    fails.append(f"{model} {hz} Hz {p}: " + ", ".join(why))
            ok_all = ok_all and good
            cells.append(f"{'ok' if good else '**FAIL**'} {e(worst_rate, 1)} / {e(worst_disp, 1)}")
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    return ok_all, lines, fails


def g2(data):
    ok_all, lines, fails = True, [], []
    lines.append("| aircraft | " + " | ".join(f"{hz} Hz" for hz in G["rates_hz"]) + " |")
    lines.append("|---|" + "---|" * len(G["rates_hz"]))
    for model in G["aircraft"]:
        cells = []
        for hz in G["rates_hz"]:
            good, note = True, ""
            for p in PLATFORMS:
                if data[p] is None:
                    return None, ["not measured on " + p], []
                r = pick(data[p], G["G2"]["scenario"]).get((model, hz))
                if r is None or "error" in r:
                    why = "not run" if r is None else r["error"]
                elif r["first_nonfinite"] is not None:
                    why = f"non-finite at {r['first_nonfinite']:.3f} s" + (f" (rates > 1e6 from {r['first_runaway']:.3f} s)" if r["first_runaway"] is not None else "")
                elif r["first_runaway"] is not None:
                    why = f"rates > 1e6 rad/s at {r['first_runaway']:.3f} s"
                elif r["steps_done"] != r["steps"]:
                    why = "ended early"
                elif r["first_contact"] is None:
                    why = "INVALID: never touched the ground"
                else:
                    why = ""
                if why:
                    good = False
                    note = why
                    fails.append(f"{model} {hz} Hz {p}: {why}")
            ok_all = ok_all and good
            n_bad = sum(1 for f in fails if f.startswith(f"{model} {hz} Hz "))
            cells.append("finite" if good else f"**FAIL** {note}" + ("" if n_bad == len(PLATFORMS) else " (one platform only; see below)"))
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    return ok_all, lines, fails


def g3_set(data, p):
    out = {}
    for sc in G["G3"]["scenarios"]:
        for (model, hz), r in pick(data[p], sc).items():
            if runaway(r):
                t = r.get("first_runaway") if r.get("first_runaway") is not None else r.get("first_nonfinite")
                out[(model, sc, hz)] = "exception" if "error" in r else f"{t:.3f} s"
    return out


def g3(data, floor_data, is_floor):
    n_trials = len(G["aircraft"]) * len(G["G3"]["scenarios"]) * len(G["rates_hz"])
    ok_all, lines, detail = True, [], []
    lines.append("| platform | runaways (of %d) | floor | new compared with the floor | verdict |" % n_trials)
    lines.append("|---|---|---|---|---|")
    for p in PLATFORMS:
        if data[p] is None:
            return None, ["not measured on " + p], []
        n = sum(1 for sc in G["G3"]["scenarios"] for _ in pick(data[p], sc))
        if n != n_trials:
            return None, [f"{p}: {n} of {n_trials} trials present"], []
        mine = g3_set(data, p)
        if is_floor:
            lines.append(f"| {p} | {len(mine)} | (this is the floor) | - | reference |")
        else:
            if floor_data is None or floor_data[p] is None:
                return None, ["the floor has not been measured on " + p], []
            base = g3_set(floor_data, p)
            new = sorted(set(mine) - set(base))
            good = len(mine) <= len(base)
            ok_all = ok_all and good
            lines.append(f"| {p} | {len(mine)} | {len(base)} | {len(new)} | {'no worse' if good else '**WORSE**'} |")
            if new:
                detail.append(f"{p}, runaway here but not in the floor: " + "; ".join(f"{m} {sc} {hz} Hz ({mine[(m, sc, hz)]})" for m, sc, hz in new))
        detail.append(f"{p}, all runaways: " + ("; ".join(f"{m} {sc} {hz} Hz ({v})" for (m, sc, hz), v in sorted(mine.items())) or "none"))
    return (None if is_floor else ok_all), lines, detail


def nasa_csv(path):
    with open(path) as f:
        return {round(float(r["time"]), 6): {k: float(v) for k, v in r.items() if k and v not in ("", None)} for r in csv.DictReader(f)}


RATES = ["bodyAngularRateWrtEi_deg_s_Roll", "bodyAngularRateWrtEi_deg_s_Pitch", "bodyAngularRateWrtEi_deg_s_Yaw"]
ANGLES = ["eulerAngle_deg_Roll", "eulerAngle_deg_Pitch", "eulerAngle_deg_Yaw"]
POSITIONS = ["gePosition_ft_X", "gePosition_ft_Y", "gePosition_ft_Z", "altitudeMsl_ft", "longitude_deg", "latitude_deg"]


def g4(config):
    g = G["G4"]
    ok_all, lines, fails, offsets = True, [], [], []
    lines.append("| platform | rate | reference | samples | worst body-rate error, deg/s (gate < %g) | worst attitude error, deg (gate < %g) | verdict |" % (g["max_body_rate_error_deg_s"], g["max_attitude_error_deg"]))
    lines.append("|---|---|---|---|---|---|---|")
    refs = {name: nasa_csv(NASA_REF / f"Atmos_02_{name}.csv") for name in g["references"]}
    for p in PLATFORMS:
        for hz in g["rates_hz"]:
            path = REPO / f"out/gates/{config}/nasa-{hz}.{p}.csv"
            if not path.exists():
                missing.append(str(path.relative_to(REPO)))
                return None, ["not measured: " + path.name], [], []
            run = nasa_csv(path)
            for name, ref in refs.items():
                times = [t for t in run if t in ref]
                finite = all(math.isfinite(v) for t in times for v in run[t].values())
                rate = max(abs(run[t][c] - ref[t][c]) for t in times for c in RATES) if finite and times else float("nan")
                att = max(abs((run[t][c] - ref[t][c] + 180.0) % 360.0 - 180.0) for t in times for c in ANGLES) if finite and times else float("nan")
                good = finite and len(run) == g["samples"] and len(times) == g["samples"] and rate < g["max_body_rate_error_deg_s"] and att < g["max_attitude_error_deg"]
                ok_all = ok_all and good
                lines.append(f"| {p} | {hz} Hz | {name} | {len(times)}/{g['samples']} | {e(rate)} | {e(att)} | {'ok' if good else '**FAIL**'} |")
                if not good:
                    fails.append(f"{p} {hz} Hz vs {name}: rate {e(rate)} deg/s, attitude {e(att)} deg, {len(times)} samples")
                if p == "native" and finite and times:
                    offsets.append(f"{hz} Hz vs {name}: " + ", ".join(f"{c} {max(abs(run[t][c] - ref[t][c]) for t in times):.3g}" for c in POSITIONS if c in ref[times[0]])
                                   + (f"; at t=0: X {run[0.0]['gePosition_ft_X'] - ref[0.0]['gePosition_ft_X']:.4f} ft" if "gePosition_ft_X" in ref[0.0] else ""))
    return ok_all, lines, fails, offsets


def g5(config):
    g = G["G5"]
    tol = g["max_relative_drift"]
    ok_all, lines, fails, extra = True, [], [], []
    rates = g["report_only_rates_hz"] + g["rates_hz"]
    lines.append("| body | spin (deg/s) | " + " | ".join(f"{hz} Hz{'' if hz in g['rates_hz'] else ' (not gated)'}" for hz in rates) + " |")
    lines.append("|---|---|" + "---|" * len(rates))
    data = {p: jsonl(REPO / f"out/gates/{config}/rigid.{p}.jsonl") for p in PLATFORMS}
    if any(v is None for v in data.values()):
        return None, ["not measured"], [], []
    idx = {p: {(r["body"], r["spin"], r["hz"]): r for r in data[p]} for p in PLATFORMS}
    worst_dir = 0.0
    for body in g["bodies"]:
        for spin, w in g["spins_deg_s"].items():
            gated_spin = spin not in g["report_only_spins"]
            cells = []
            for hz in rates:
                gated = gated_spin and hz in g["rates_hz"]
                dT = dH = 0.0
                bad = False
                for p in PLATFORMS:
                    r = idx[p].get((body, spin, hz))
                    if r is None or "error" in r or not r["finite"]:
                        bad = True
                        if gated:
                            fails.append(f"{body} {spin} {hz} Hz {p}: {'not run' if r is None else r.get('error', 'non-finite')}")
                        continue
                    dT, dH = max(dT, r["energy_drift"]), max(dH, r["momentum_magnitude_drift"])
                    if gated and p == "native":
                        worst_dir = max(worst_dir, r["momentum_direction_drift_rad"])
                good = not bad and dT < tol and dH < tol
                if gated and not good and not bad:
                    fails.append(f"{body} {spin} {hz} Hz: energy {e(dT)}, |H| {e(dH)}")
                if gated:
                    ok_all = ok_all and good
                cells.append(f"{('ok' if good else '**FAIL**') if gated else ''} {'blew up (non-finite)' if bad else e(dT, 1) + ' / ' + e(dH, 1)}".strip())
            lines.append(f"| {body} | {spin}{'' if gated_spin else ' (not gated)'} {w} | " + " | ".join(cells) + " |")
    extra.append(f"Reported, not gated: largest change of the direction of the angular momentum in the inertial frame over the gated cases (native): {e(worst_dir)} rad = {e(math.degrees(worst_dir))} deg. It depends on the attitude integrator (see G4).")
    return ok_all, lines, fails, extra


def g6(config):
    ok_all, lines, fails = True, [], []
    lines.append("| flight | WebAssembly variant | rows | columns out of tolerance | largest difference | verdict |")
    lines.append("|---|---|---|---|---|---|")
    for model in G["G6"]["models"]:
        for p in PARITY_PLATFORMS:
            a = REPO / f"out/gates/{config}/flight-{model}.native.csv"
            b = REPO / f"out/gates/{config}/flight-{model}.{p}.csv"
            if not a.exists() or not b.exists():
                missing.append(str((b if a.exists() else a).relative_to(REPO)))
                return None, ["not measured: " + (b if a.exists() else a).name], []
            try:
                res = parity.compare(str(a), str(b))
            except parity.LogError as err:
                ok_all = False
                fails.append(f"{model} {p}: refused: {err}")
                lines.append(f"| {model} | {p} | - | - | - | **FAIL** (refused: {err}) |")
                continue
            worst = max(res["columns"].items(), key=lambda kv: kv[1]["max_abs"] / kv[1]["tolerance"])
            good = not res["gate_failures"]
            ok_all = ok_all and good
            lines.append(f"| {model} | {p} | {res['rows']} | {len(res['gate_failures'])} of {len(res['columns'])} | {worst[0]} {e(worst[1]['max_abs'])} (tolerance {e(worst[1]['tolerance'], 0)}) | {'ok' if good else '**FAIL**'} |")
            if not good:
                fails.append(f"{model} {p}: " + ", ".join(res["gate_failures"]))
    return ok_all, lines, fails


def cost(config):
    recs = jsonl(REPO / f"out/gates/{config}/cost.wasm-jsbsim-weh.jsonl")
    if recs is None:
        missing.pop()
        return ["not measured"]
    lines = ["| workload | aircraft | rate | median us/step | min | max |", "|---|---|---|---|---|---|"]
    lines += [f"| {r['kind']} | {r['model']} | {r['hz']} Hz | {r['median_us_per_step']:.2f} | {r['min_us_per_step']:.2f} | {r['max_us_per_step']:.2f} |" for r in recs]
    return lines


def show(items, cap=8):
    for f in items[:cap]:
        print(f"- {f}")
    if len(items) > cap:
        print(f"- ... and {len(items) - cap} more (every trial is in out/gates/<config>/*.jsonl)")


def verdict_word(v):
    return {True: "PASS", False: "FAIL", None: "INCOMPLETE"}[v]


def main():
    config = sys.argv[1]
    floor = sys.argv[sys.argv.index("--floor") + 1] if "--floor" in sys.argv else "floor"
    cfg = CONFIGS[config]
    is_floor = config == floor
    print(f"# Gates: configuration `{config}`")
    print()
    print(f"- Role: {cfg['role']}")
    print(f"- Source: JSBSim v1.3.3 {cfg['source']}; properties: " + ", ".join(f"`{k}` = {v}" for k, v in cfg["properties"].items()))
    for p in PLATFORMS + ["wasm-jsbsim"]:
        info = REPO / f"out/gates/{config}/{p}.info.json"
        if info.exists():
            d = json.loads(info.read_text())
            what = d.get("build") or f"native JSBSim {d['version']} [{d['key']}] module sha256 {str(d['module_sha256'])[:16]}"
            patches = ", ".join(f"{x['file']} {x['sha256'][:12]}" for x in d.get("patches", [])) or "none"
            print(f"- {p}: {what}; patches: {patches}")
    sha = hashlib.sha256((HERE / "gates.json").read_bytes()).hexdigest()
    commit = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%h %cI", "--"] + FROZEN, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--"] + FROZEN, capture_output=True, text=True).stdout.strip()
    print(f"- Gate definitions: gates.json sha256 {sha[:16]}; last commit touching the frozen gate files: {commit or 'NOT COMMITTED'}{' (UNCOMMITTED CHANGES: ' + dirty.replace(chr(10), '; ') + ')' if dirty else ''}")
    print()
    data = ground(config)
    floor_data = None if is_floor else ground(floor) if (REPO / f"out/gates/{floor}").exists() else None
    verdicts = {}

    v, lines, fails = g1(data)
    verdicts["G1"] = v
    print(f"## G1 Rest: {verdict_word(v)}")
    print("60 s on the gear. Each cell: worst of native and WebAssembly, largest body rate in the last 10 s (rad/s, gate < 1e-6) / largest horizontal movement in the last 10 s (ft, gate < 0.01).")
    print()
    print("\n".join(lines))
    show(fails)
    print()

    v, lines, fails = g2(data)
    verdicts["G2"] = v
    print(f"## G2 Hard landing: {verdict_word(v)}")
    print("40 ft, 100 ft/s forward, 30 ft/s down, level; 15 s. Gate: every state finite, no body rate above 1e6 rad/s, on native and WebAssembly.")
    print()
    print("\n".join(lines))
    show(fails)
    print()

    v, lines, detail = g3(data, floor_data, is_floor)
    verdicts["G3"] = v
    print(f"## G3 Extreme impacts: {'REFERENCE (this is the floor)' if is_floor and lines and 'not measured' not in lines[0] else verdict_word(v)}")
    print("Inverted, banked and nose-first impacts; 15 s; 5 aircraft x 3 scenarios x 4 rates. Not pass/fail on its own: the count of runaways (rates > 1e6 rad/s, NaN or exception) must be no higher than the floor's.")
    print()
    print("\n".join(lines))
    for d in detail:
        print(f"- {d}")
    print()

    v, lines, fails, offsets = g4(config)
    verdicts["G4"] = v
    print(f"## G4 NASA case 02: {verdict_word(v)}")
    print()
    print("\n".join(lines))
    show(fails, 4)
    if offsets:
        print()
        print("Position differences (native; reported, not gated; largest over 30 s). Cause: `brick.xml` gives the planet an equatorial radius of 20925646.9951 ft, so the run starts 0.67 ft further from the Earth's centre than NASA's sims (REVIEW-codex-02); the offset is there at t = 0 and stays in ECEF X.")
        for o in offsets:
            print(f"- {o}")
    print()

    v, lines, fails, extra = g5(config)
    verdicts["G5"] = v
    print(f"## G5 Torque-free rigid body: {verdict_word(v)}")
    print("60 s of free tumbling. Each cell: worst of native and WebAssembly, relative drift of rotational kinetic energy / of the magnitude of angular momentum (gate: both < 1e-6 at 480 and 1000 Hz).")
    print()
    print("\n".join(lines))
    show(fails)
    for x in extra:
        print(f"- {x}")
    print()

    v, lines, fails = g6(config)
    verdicts["G6"] = v
    print(f"## G6 Parity, WebAssembly against native of the same source: {verdict_word(v)}")
    print()
    print("\n".join(lines))
    show(fails)
    print()

    print("## Cost per step in Node (no gate)")
    print()
    print("\n".join(cost(config)))
    print()
    print("## Summary")
    print()
    print("| G1 Rest | G2 Hard landing | G3 Extreme impacts | G4 NASA | G5 Rigid body | G6 Parity |")
    print("|---|---|---|---|---|---|")
    print("| " + " | ".join(("reference" if (k == "G3" and is_floor and verdicts[k] is None and not missing) else verdict_word(verdicts[k])) for k in ["G1", "G2", "G3", "G4", "G5", "G6"]) + " |")
    if missing:
        print()
        print("Missing measurements: " + ", ".join(sorted(set(missing))))
    out = REPO / f"out/gates/{config}/verdict.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(config=config, verdicts=verdicts, missing=sorted(set(missing)), gates_sha256=sha), indent=1))
    return 2 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
