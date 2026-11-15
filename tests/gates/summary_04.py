"""One table of several configurations against the gates the decision is judged on (GATES-04.md), per judged step
rate, with the numbers.
usage: python tests/gates/summary_04.py floor c1-ab3 ...     (run tests/gates/run.sh and run-later.sh first)
It only summarises measurements; the verdicts are evaluate.py's and evaluate_04.py's (out/gates/<config>/verdict*.json)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import evaluate_04 as L  # noqa: E402

E, G, G4 = L.E, L.G, L.G4
W = {True: "**PASS**", False: "**FAIL**", None: "incomplete"}


def cost(c):
    p = REPO / f"out/gates/{c}/cost.wasm-jsbsim-weh.jsonl"
    if not p.exists():
        return "not measured"
    d = {(r["kind"], r["model"], r["hz"]): r["median_us_per_step"] for r in map(json.loads, p.read_text().splitlines())}
    return " / ".join(f"{d[(k, 'c172x', 1000)]:.1f}" for k in ("flight", "ground at rest")) + " us"


def main(configs):
    rows = []
    for c in configs:
        v = json.loads((REPO / f"out/gates/{c}/verdict04.json").read_text())
        old = json.loads((REPO / f"out/gates/{c}/verdict.json").read_text())["verdicts"]
        rep = L.repeats(c)
        _, worst1 = L.g1_at(c)
        _, num4 = L.g4_at(c)
        rb = {p: {(r["body"], r["spin"], r["hz"]): r for r in L.jsonl(REPO / f"out/gates/{c}/rigidb.{p}.jsonl")} for p in L.PLATFORMS}
        for hz in L.JUDGED:
            k = str(hz)
            g2 = [sum(sum(L.run_ok(r) for r in rep[p][(m, G4["G2b"]["scenario"], hz)]) for m in G["aircraft"]) for p in L.PLATFORMS]
            g3 = [sum(L.g3b_counts(rep, p, hz).values()) for p in L.PLATFORMS]
            worst5 = 0.0
            for p in L.PLATFORMS:
                for (body, spin, h), r in rb[p].items():
                    if h == hz and spin not in G["G5"]["report_only_spins"]:
                        worst5 = max(worst5, float("inf") if ("error" in r or not r["finite"]) else max(r["energy_drift"], r["momentum_magnitude_drift"]))
            n2 = L.N_RUNS * len(G["aircraft"])
            n3 = L.N_RUNS * len(G["aircraft"]) * len(G4["G3b"]["scenarios"])
            rows.append([f"`{c}`", f"{hz} Hz",
                         f"{W[v['G1'][k]]} {worst1[hz]:.0e} rad/s",
                         f"{W[v['G2b'][k]]} {g2[0]} / {g2[1]} of {n2}",
                         (f"reference {g3[0]} / {g3[1]} of {n3}" if v["G3b"] == "reference" else f"{W[v['G3b'][k]]} {g3[0]} / {g3[1]} of {n3}"),
                         f"{W[v['G4'][k]]} {num4[hz][0]:.1e} deg/s, {num4[hz][1]:.1e} deg",
                         f"{W[v['G5b'][k]]} {worst5:.1e}",
                         W[v["G6"]],
                         f"**{'PASS' if v['decision'][k] else 'FAIL' if v['decision'][k] is False else 'incomplete'}**",
                         " ".join(f"{g}:{'P' if old[g] else ('ref' if old[g] is None else 'F')}" for g in ("G1", "G2", "G3", "G4", "G5", "G6")),
                         cost(c)])
    head = ["configuration", "step rate", "G1 Rest (worst rate)", "G2b Hard landing x21 (good runs, native / WebAssembly)",
            "G3b Impacts x21 (runaway runs, native / WebAssembly)", "G4 NASA (rate error, attitude error)", "G5b Rigid body after start-up (worst drift)",
            "G6 Parity", "all", "session 03 gates, all rates (P pass, F fail)", "cost, c172x 1000 Hz, flight / ground"]
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for r in rows:
        print("| " + " | ".join(r) + " |")
    print()
    print("Limits: G1 body rates < 1e-6 rad/s; G2b every run good; G3b runaway runs at most the floor's + 15; G4 rate error < 2e-6 deg/s and attitude error < 1e-3 deg; G5b drift < 1e-6; G6 within the parity tolerances.")


if __name__ == "__main__":
    main(sys.argv[1:])
