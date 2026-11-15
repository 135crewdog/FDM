"""Compare two step logs column by column.
usage: python tests/parity/compare.py a.csv b.csv [--json]"""
import csv, json, sys

def load(p):
    with open(p) as f:
        r = csv.reader(f)
        head = next(r)
        return head, [[float(x) for x in row] for row in r if row]

def compare(a, b):
    ha, ra = load(a)
    hb, rb = load(b)
    assert ha == hb, "different columns"
    n = min(len(ra), len(rb))
    res = {"rows_a": len(ra), "rows_b": len(rb), "columns": {}}
    for j, name in enumerate(ha):
        worst_abs, worst_rel, at = 0.0, 0.0, None
        scale = max(max(abs(r[j]) for r in ra[:n]), 1e-3) if n else 1.0
        first_div = None
        for i in range(n):
            d = abs(ra[i][j] - rb[i][j])
            rel = d / scale  # relative to the column largest magnitude, floored at 1e-3
            if d > worst_abs:
                worst_abs, at = d, ra[i][0]
            worst_rel = max(worst_rel, rel)
            if first_div is None and rel > 1e-6:
                first_div = ra[i][0]
        res["columns"][name] = {"max_abs": worst_abs, "max_rel": worst_rel, "at_time": at,
                                "first_time_rel_gt_1e-6": first_div}
    return res

if __name__ == "__main__":
    res = compare(sys.argv[1], sys.argv[2])
    if "--json" in sys.argv:
        print(json.dumps(res, indent=1))
    else:
        print(f"rows: {res['rows_a']} vs {res['rows_b']}")
        print(f"{'column':28s} {'max_abs':>12s} {'max_rel':>10s} {'at t=':>9s} {'1st rel>1e-6':>12s}")
        for k, v in res["columns"].items():
            print(f"{k:28s} {v['max_abs']:12.3e} {v['max_rel']:10.2e} {v['at_time'] if v['at_time'] is not None else '-':>9} {str(v['first_time_rel_gt_1e-6']):>12s}")
