"""One table of several configurations against every gate, with the numbers (Markdown).
usage: python tests/gates/summary.py floor c1-ab4 c1-ab3 ...      (reads out/gates/<config>/; run the gates first)
It only summarises measurements already judged by evaluate.py; it applies the same definitions."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import evaluate as E  # noqa: E402

G = E.G


def cell(v):
    return {True: "**PASS**", False: "**FAIL**", None: "reference"}[v]


def main(configs):
    rows = {k: [] for k in ["G1 Rest", "G2 Hard landing", "G3 Extreme impacts", "G4 NASA case 02", "G5 Rigid body", "G6 Parity", "Cost"]}
    for c in configs:
        verdict = json.loads((REPO / f"out/gates/{c}/verdict.json").read_text())["verdicts"]
        data = E.ground(c)
        # G1
        bad, worst = [], 0.0
        for p in E.PLATFORMS:
            for (model, hz), r in E.pick(data[p], "rest").items():
                ok = "error" not in r and r["first_nonfinite"] is None and r["tail_always_in_contact"] and r["tail_max_rate"] < G["G1"]["max_abs_body_rate_rad_s"] and r["tail_max_horizontal_displacement_ft"] < G["G1"]["max_horizontal_displacement_ft"]
                worst = max(worst, r.get("tail_max_rate", float("inf")))
                if not ok and (model, hz) not in bad:
                    bad.append((model, hz))
        rows["G1 Rest"].append(f"{cell(verdict['G1'])}<br>{20 - len(bad)} of 20 settle; worst rate {worst:.1e} rad/s" + ("<br>fails: " + ", ".join(f"{m} {hz} Hz" for m, hz in bad[:4]) + (" ..." if len(bad) > 4 else "") if bad else ""))
        # G2
        fails = {}
        for p in E.PLATFORMS:
            for (model, hz), r in E.pick(data[p], "hard").items():
                if E.runaway(r) or r.get("first_contact") is None:
                    fails.setdefault((model, hz), []).append(p)
        by_model = {}
        for (model, hz), ps in sorted(fails.items()):
            by_model.setdefault(model, []).append(f"{hz}{'*' if len(ps) < len(E.PLATFORMS) else ''}")
        rows["G2 Hard landing"].append(f"{cell(verdict['G2'])}<br>{20 - len(fails)} of 20 stay finite" + ("<br>fails: " + "; ".join(f"{m} at {', '.join(v)} Hz" for m, v in by_model.items()) if fails else ""))
        # G3
        n = {p: len(E.g3_set(data, p)) for p in E.PLATFORMS}
        rows["G3 Extreme impacts"].append(f"{cell(verdict['G3']) if verdict['G3'] is not None else 'reference'}<br>runaways of 60: {n['native']} native, {n['wasm-jsbsim-weh']} WebAssembly")
        # G4
        refs = {name: E.nasa_csv(E.NASA_REF / f"Atmos_02_{name}.csv") for name in G["G4"]["references"]}
        parts = []
        for hz in G["G4"]["rates_hz"]:
            rate = att = 0.0
            for p in E.PLATFORMS:
                run = E.nasa_csv(REPO / f"out/gates/{c}/nasa-{hz}.{p}.csv")
                for ref in refs.values():
                    ts = [t for t in run if t in ref]
                    rate = max(rate, max(abs(run[t][k] - ref[t][k]) for t in ts for k in E.RATES))
                    att = max(att, max(abs((run[t][k] - ref[t][k] + 180.0) % 360.0 - 180.0) for t in ts for k in E.ANGLES))
            parts.append(f"{hz} Hz: rate {rate:.1e} deg/s, attitude {att:.1e} deg")
        rows["G4 NASA case 02"].append(f"{cell(verdict['G4'])}<br>" + "<br>".join(parts))
        # G5
        g5 = G["G5"]
        idx = {p: {(r["body"], r["spin"], r["hz"]): r for r in E.jsonl(REPO / f"out/gates/{c}/rigid.{p}.jsonl")} for p in E.PLATFORMS}
        parts = []
        for hz in g5["rates_hz"]:
            nbad = total = 0
            worst = 0.0
            for body in g5["bodies"]:
                for spin in g5["spins_deg_s"]:
                    if spin in g5["report_only_spins"]:
                        continue
                    total += 1
                    d = 0.0
                    for p in E.PLATFORMS:
                        r = idx[p][(body, spin, hz)]
                        d = max(d, float("inf") if ("error" in r or not r["finite"]) else max(r["energy_drift"], r["momentum_magnitude_drift"]))
                    nbad += not d < g5["max_relative_drift"]
                    worst = max(worst, d)
            parts.append(f"{hz} Hz: {total - nbad} of {total} within 1e-6; worst drift {worst:.1e}")
        rows["G5 Rigid body"].append(f"{cell(verdict['G5'])}<br>" + "<br>".join(parts))
        # G6
        worst = 0.0
        for model in G["G6"]["models"]:
            for p in E.PARITY_PLATFORMS:
                res = E.parity.compare(str(REPO / f"out/gates/{c}/flight-{model}.native.csv"), str(REPO / f"out/gates/{c}/flight-{model}.{p}.csv"))
                worst = max(worst, max(v["max_abs"] / v["tolerance"] for v in res["columns"].values()))
        rows["G6 Parity"].append(f"{cell(verdict['G6'])}<br>largest difference is {worst:.0e} of its tolerance")
        # cost
        cost = {(r["kind"], r["model"], r["hz"]): r["median_us_per_step"] for r in E.jsonl(REPO / f"out/gates/{c}/cost.wasm-jsbsim-weh.jsonl")}
        rows["Cost"].append("no gate<br>" + "<br>".join(f"{m} {k}, 1000 Hz: {cost[(k, m, 1000)]:.1f} us" for k in ("flight", "ground at rest") for m in ("c172x", "f16")))
    print("| Gate | " + " | ".join(f"`{c}`" for c in configs) + " |")
    print("|---|" + "---|" * len(configs))
    for k, v in rows.items():
        print(f"| {k} | " + " | ".join(v) + " |")
    print()
    print("`*` after a rate in G2: that run failed on one platform only (native or WebAssembly), the other stayed finite.")


if __name__ == "__main__":
    main(sys.argv[1:])
