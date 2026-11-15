"""Self-test of tests/parity/compare.py with synthetic logs: every bad log must be refused or failed.
usage: python tests/parity/selftest_compare.py     (exit code 1 if the comparator lets anything through)
Built from the independent review's probe (tests/review/comparator_probe.py), which showed the old
comparator reporting zero difference, exit code 0, for a one-row NaN log."""
import subprocess
import sys
import tempfile
from pathlib import Path

CMP = Path(__file__).with_name("compare.py")
HEAD = "simulation/sim-time-sec,position/h-sl-ft,velocities/q-rad_sec"
GOOD = [(0.0, 1000.0, 0.10), (0.1, 1001.0, 0.11), (0.2, 1002.0, 0.12)]


def text(rows, head=HEAD):
    return head + "\n" + "".join(",".join(str(v) for v in r) + "\n" for r in rows)


def mod(i, j, v):
    rows = [list(r) for r in GOOD]
    rows[i][j] = v
    return rows

# name, candidate log text, extra args, expected exit code
CASES = [
    ("identical logs", text(GOOD), [], 0),
    ("identical logs, --gate", text(GOOD), ["--gate"], 0),
    ("difference inside tolerance, --gate", text(mod(1, 2, 0.11 + 5e-8)), ["--gate"], 0),
    ("NaN in candidate", text(mod(1, 2, float("nan"))), [], 2),
    ("+Inf in candidate", text(mod(2, 1, float("inf"))), [], 2),
    ("-Inf in candidate", text(mod(2, 1, float("-inf"))), ["--gate"], 2),
    ("truncated candidate (one row, NaN): the review's probe", text([(0.0, 1000.0, float("nan"))]), [], 2),
    ("truncated candidate (finite)", text(GOOD[:2]), [], 2),
    ("candidate longer", text(GOOD + [(0.3, 1003.0, 0.13)]), [], 2),
    ("time-shifted candidate", text([(t + 0.05, h, q) for t, h, q in GOOD]), [], 2),
    ("different header", text(GOOD, HEAD.replace("q-rad_sec", "p-rad_sec")), [], 2),
    ("columns in a different order", text([(t, q, h) for t, h, q in GOOD], "simulation/sim-time-sec,velocities/q-rad_sec,position/h-sl-ft"), [], 2),
    ("missing value in a row", HEAD + "\n0.0,1000.0,0.10\n0.1,1001.0\n0.2,1002.0,0.12\n", [], 2),
    ("text where a number belongs", HEAD + "\n0.0,1000.0,0.10\n0.1,oops,0.11\n0.2,1002.0,0.12\n", [], 2),
    ("header only", HEAD + "\n", [], 2),
    ("empty file", "", [], 2),
    ("rate out of tolerance, --gate", text(mod(1, 2, 0.11 + 2e-7)), ["--gate"], 1),
    ("position out of tolerance, --gate", text(mod(2, 1, 1002.0 + 2e-4)), ["--gate"], 1),
    ("rate out of tolerance, no --gate (report only)", text(mod(1, 2, 0.11 + 2e-7)), [], 0),
]

failed = 0
with tempfile.TemporaryDirectory(prefix="fdm-compare-selftest-") as d:
    ref = Path(d) / "ref.csv"
    ref.write_text(text(GOOD))
    for name, cand_text, extra, want in CASES:
        cand = Path(d) / "cand.csv"
        cand.write_text(cand_text)
        for order in ("ref,cand", "cand,ref"):
            a, b = (ref, cand) if order == "ref,cand" else (cand, ref)
            p = subprocess.run([sys.executable, str(CMP), str(a), str(b), *extra], text=True, capture_output=True)
            ok = p.returncode == want
            failed += not ok
            print(f"{'PASS' if ok else 'FAIL'}  {name} ({order}): exit {p.returncode}, expected {want}")
print(f"# {'all comparator self-tests passed' if not failed else str(failed) + ' comparator self-test(s) FAILED'}")
sys.exit(1 if failed else 0)
