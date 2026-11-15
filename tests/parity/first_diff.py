"""Find the first logged step where two runs differ, and how the largest relative
difference grows over time (rounding-level seeds grow; logic bugs jump).
usage: python tests/parity/first_diff.py a.csv b.csv"""
import csv, math, sys
a = list(csv.reader(open(sys.argv[1]))); b = list(csv.reader(open(sys.argv[2])))
h = a[0]; A = [[float(x) for x in r] for r in a[1:]]; B = [[float(x) for x in r] for r in b[1:]]
first = None
for i, (ra, rb) in enumerate(zip(A, B)):
    d = [(h[j], ra[j], rb[j]) for j in range(1, len(h)) if ra[j] != rb[j] and not (h[j] in ("attitude/psi-rad", "attitude/phi-rad") and abs(abs(ra[j] - rb[j]) - 2 * math.pi) < 1e-9)]
    if d:
        first = i
        print(f"first difference at row {i} (t={ra[0]:.6f}):")
        for name, x, y in d:
            ulps = abs(x - y) / (math.ulp(x) if x else 5e-324)
            print(f"  {name:24s} native={x!r} wasm={y!r} diff={x-y:.3e} (~{ulps:.0f} ulp)")
        break
if first is None:
    print("bit-identical"); sys.exit()
print("growth of worst |diff|/max(|x|,1e-3) over time:")
step = max(1, len(A) // 12)
for i in range(first, len(A), step):
    dd = lambda j: abs((A[i][j] - B[i][j] + math.pi) % (2 * math.pi) - math.pi) if h[j] in ("attitude/psi-rad", "attitude/phi-rad") else abs(A[i][j] - B[i][j])
    w = max(dd(j) / max(abs(A[i][j]), 1e-3) for j in range(1, len(h)))
    print(f"  t={A[i][0]:8.3f}  {w:.2e}")
