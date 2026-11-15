"""Test 5: effect of the AB4 rotational-rate integrator (rate/rotational = 5) vs JSBSim's default (1).
Compares two step logs of the same script and splits the differences into on-ground (gear/wow = 1)
and airborne phases. usage: compare.py default.csv ab4.csv"""
import csv, sys
def load(p):
    r = list(csv.reader(open(p))); h = r[0]
    return h, [[float(x) for x in row] for row in r[1:] if row]
h, A = load(sys.argv[1]); _, B = load(sys.argv[2])
n = min(len(A), len(B)); iw = h.index("gear/wow"); it = 0
print(f"rows: default {len(A)}, AB4 {len(B)}; end time {A[n-1][0]:.2f} s")
ground = [i for i in range(n) if A[i][iw] > 0.5 or B[i][iw] > 0.5]
air = [i for i in range(n) if not (A[i][iw] > 0.5 or B[i][iw] > 0.5)]
wow_flip = [A[i][0] for i in range(1, n) if (A[i][iw] > 0.5) != (A[i-1][iw] > 0.5)]
wow_flip_b = [B[i][0] for i in range(1, n) if (B[i][iw] > 0.5) != (B[i-1][iw] > 0.5)]
print(f"steps on ground: {len(ground)}, airborne: {len(air)}")
print(f"weight-on-wheels changes at t = default {[round(t,3) for t in wow_flip][:6]} / AB4 {[round(t,3) for t in wow_flip_b][:6]}")
print(f"{'column':24s} {'max |diff| ground':>18s} {'max |diff| air':>15s} {'final default':>15s} {'final AB4':>15s}")
for j, name in enumerate(h):
    if j == it or name == "gear/wow":
        continue
    g = max((abs(A[i][j] - B[i][j]) for i in ground), default=0.0)
    a = max((abs(A[i][j] - B[i][j]) for i in air), default=0.0)
    print(f"{name:24s} {g:18.3e} {a:15.3e} {A[n-1][j]:15.6g} {B[n-1][j]:15.6g}")
