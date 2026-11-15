"""Compare JSBSim runs of NASA check case 02 against NASA's six-sim solutions.
usage: python tests/nasa/compare.py out/Atmos_02_wasm.csv [out/Atmos_02_native.csv]"""
import csv, glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "..", "reference", "nasa-checkcases", "Atmos_02_TumblingBrickNoDamping")
VARS = ["gePosition_ft_X", "gePosition_ft_Y", "altitudeMsl_ft", "longitude_deg",
        "eulerAngle_deg_Yaw", "eulerAngle_deg_Pitch", "eulerAngle_deg_Roll",
        "bodyAngularRateWrtEi_deg_s_Roll", "bodyAngularRateWrtEi_deg_s_Pitch", "bodyAngularRateWrtEi_deg_s_Yaw"]

def load(p):
    with open(p) as f:
        r = csv.DictReader(f)
        return {round(float(row["time"]), 6): {k: float(v) for k, v in row.items() if v not in ("", None) and k} for row in r}

def angdiff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0

def maxdiff(A, B, var):
    m, n = 0.0, 0
    for t, ra in A.items():
        rb = B.get(t)
        if rb is None or var not in ra or var not in rb:
            continue
        d = angdiff(ra[var], rb[var]) if "euler" in var else ra[var] - rb[var]
        m, n = max(m, abs(d)), n + 1
    return m if n else None

fmt = lambda x: f"{'-':>10s}" if x is None else f"{x:10.3g}"

sims = {os.path.basename(p)[9:15]: load(p) for p in sorted(glob.glob(os.path.join(REF, "*.csv")))}
runs = {os.path.basename(p): load(p) for p in sys.argv[1:]}
keys = list(sims)
for r, run in runs.items():
    print(f"\n{r}: max |difference| over 0..30 s (NASA spread = largest difference between any two NASA sims)")
    print(f"{'variable':34s}{'NASA spread':>12s}" + "".join(f"{'vs ' + k:>10s}" for k in keys) + "  inside spread?")
    for v in VARS:
        sp = [x for a in keys for b in keys if a < b for x in [maxdiff(sims[a], sims[b], v)] if x is not None]
        ds = [d for k in keys for d in [maxdiff(run, sims[k], v)] if d is not None]
        inside = "yes" if max(ds) <= max(sp) else "NO"
        print(f"{v:34s}{max(sp):12.3g}" + "".join(fmt(maxdiff(run, sims[k], v)) for k in keys) + f"  {inside}")
if len(runs) == 2:
    a, b = list(runs.values())
    print("\n%s vs %s, max |diff|:" % tuple(runs))
    for v in VARS:
        print(f"  {v:34s}{maxdiff(a, b, v):.3e}")
