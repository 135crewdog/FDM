"""Compare two step logs column by column. Strict: a broken log can never pass.

usage: python tests/parity/compare.py a.csv b.csv [--gate] [--json]

It REFUSES to compare (exit code 2, message on stderr) when:
  - the headers differ, or a log has no rows;
  - the logs have different numbers of rows (nothing is truncated to the shorter log);
  - any value in either log is NaN or infinite, or cannot be parsed;
  - the time columns differ (first column, if it is simulation/sim-time-sec or "time"; tolerance 1e-9 s).
With --gate it also FAILS (exit code 1) when a column differs by more than its tolerance. The tolerances
are the ones written down by the independent review (REVIEW-codex-02.md, "Tests to add") for smooth
controlled flight:
  positions (position/..., ft)                 1e-4
  velocities (..-fps, ..-kts)                  1e-5
  forces, moments, propulsion                  1e-5 + 1e-7 * max |reference|
  everything else (rates, attitudes, angles,
  surface positions)                           1e-7
Without --gate the differences are only reported (exit code 0), for runs that are expected to differ.
"""
import csv
import json
import math
import sys

TIME_NAMES = ("simulation/sim-time-sec", "time")
TIME_TOL = 1e-9


class LogError(Exception):
    pass


def wrapped(name):
    """Angles that may wrap (psi is reported in [0, 2pi): 0 and 6.283 are the same heading)."""
    return name in ("attitude/psi-rad", "attitude/phi-rad")


def tolerance(name, scale):
    if name in TIME_NAMES:
        return TIME_TOL
    if name.startswith("position/"):
        return 1e-4
    if name.endswith("-fps") or name.endswith("-kts"):
        return 1e-5
    if name.startswith(("forces/", "moments/", "propulsion/")):
        return 1e-5 + 1e-7 * scale
    return 1e-7


def load(p):
    try:
        return _load(p)
    except OSError as e:
        raise LogError(f"{p}: cannot read ({e.strerror})")


def _load(p):
    with open(p) as f:
        r = csv.reader(f)
        try:
            head = next(r)
        except StopIteration:
            raise LogError(f"{p}: empty file")
        rows = []
        for n, row in enumerate(r, start=2):
            if not row:
                continue
            if len(row) != len(head):
                raise LogError(f"{p}: line {n} has {len(row)} values, header has {len(head)}")
            try:
                vals = [float(x) for x in row]
            except ValueError as e:
                raise LogError(f"{p}: line {n}: {e}")
            for name, v in zip(head, vals):
                if not math.isfinite(v):
                    raise LogError(f"{p}: line {n}: {name} is {v} (non-finite values are never compared)")
            rows.append(vals)
    if not rows:
        raise LogError(f"{p}: no data rows")
    return head, rows


def compare(a, b):
    ha, ra = load(a)
    hb, rb = load(b)
    if ha != hb:
        raise LogError(f"different columns: {sorted(set(ha) ^ set(hb)) or 'same names, different order'}")
    if len(ra) != len(rb):
        raise LogError(f"different lengths: {len(ra)} rows in {a}, {len(rb)} rows in {b}")
    n = len(ra)
    if ha[0] in TIME_NAMES:
        for i in range(n):
            if abs(ra[i][0] - rb[i][0]) > TIME_TOL:
                raise LogError(f"time columns differ at row {i}: {ra[i][0]!r} vs {rb[i][0]!r}")
    res = {"rows": n, "columns": {}, "gate_failures": []}
    for j, name in enumerate(ha):
        worst_abs, worst_rel, at = 0.0, 0.0, None
        peak = max(abs(r[j]) for r in ra)
        scale = max(peak, 1e-3)
        first_div = None
        for i in range(n):
            d = abs(ra[i][j] - rb[i][j])
            if wrapped(name):
                d = abs((ra[i][j] - rb[i][j] + math.pi) % (2 * math.pi) - math.pi)
            rel = d / scale  # relative to the column largest magnitude, floored at 1e-3
            if d > worst_abs:
                worst_abs, at = d, ra[i][0]
            worst_rel = max(worst_rel, rel)
            if first_div is None and rel > 1e-6:
                first_div = ra[i][0]
        tol = tolerance(name, peak)
        res["columns"][name] = {"max_abs": worst_abs, "max_rel": worst_rel, "at_time": at,
                                "first_time_rel_gt_1e-6": first_div, "tolerance": tol, "within": worst_abs <= tol}
        if worst_abs > tol:
            res["gate_failures"].append(name)
    return res


def main(argv):
    args = [x for x in argv if not x.startswith("--")]
    gate = "--gate" in argv
    try:
        res = compare(args[0], args[1])
    except LogError as e:
        print(f"REFUSED: {e}")
        print(f"compare.py: refused to compare: {e}", file=sys.stderr)
        return 2
    if "--json" in argv:
        print(json.dumps(res, indent=1))
    else:
        print(f"rows: {res['rows']} vs {res['rows']}")
        print(f"{'column':28s} {'max_abs':>12s} {'max_rel':>10s} {'at t=':>9s} {'1st rel>1e-6':>12s}" + (f" {'tolerance':>10s}  ok" if gate else ""))
        for k, v in res["columns"].items():
            line = f"{k:28s} {v['max_abs']:12.3e} {v['max_rel']:10.2e} {v['at_time'] if v['at_time'] is not None else '-':>9} {str(v['first_time_rel_gt_1e-6']):>12s}"
            if gate:
                line += f" {v['tolerance']:10.1e}  {'ok' if v['within'] else 'OUT OF TOLERANCE'}"
            print(line)
    if gate:
        if res["gate_failures"]:
            print(f"GATE FAIL: {len(res['gate_failures'])} column(s) out of tolerance: {', '.join(res['gate_failures'])}")
            return 1
        print("GATE PASS: every column within tolerance")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
