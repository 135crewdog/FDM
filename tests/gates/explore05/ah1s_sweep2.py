"""Sweep 2 (480 Hz): target sinks 2..12 with kp=0.08 ki=0.3 yaw-rate gain 0.3; position-hold gains; release variants; hover time."""
import sys
from ah1s_common import HEAD, row
from ah1s_dev import run

base = dict(col0=0.611, kp=0.08, ki=0.3, yaw_rate_gain=0.3, verbose=0)
cases = []
for s in (2.0, 4.0, 6.0, 8.0, 10.0, 12.0):
    cases.append(("baseline", dict(sink=s)))
for s in (2.0, 10.0):
    cases.append(("pos gains x2 (ku=kv=0.02 kx=ky=0.004)", dict(sink=s, ku=0.02, kv=0.02, kx=0.004, ky=0.004)))
    cases.append(("pos gains x4 (ku=kv=0.04 kx=ky=0.008)", dict(sink=s, ku=0.04, kv=0.04, kx=0.008, ky=0.008)))
for s in (4.0, 10.0):
    cases.append(("release=keep (only collective lowered)", dict(sink=s, release="keep")))
    cases.append(("col_down_tc=0.5", dict(sink=s, col_down_tc=0.5)))
    cases.append(("col_down_tc=5", dict(sink=s, col_down_tc=5.0)))
for th in (3.0, 9.0):
    cases.append(("t_hover=%g" % th, dict(sink=6.0, t_hover=th)))
print(HEAD)
for name, c in cases:
    kw = dict(base)
    kw.update(c)
    r, f = run("sweep2: " + name, **kw)
    print(row(name, 480, c["sink"], r), "end h=%.2f phi=%.2f th=%.2f psi=%.1f" % (r["end"]["h"], r["end"]["phi"], r["end"]["theta"], r["end"]["psi"]))
    sys.stdout.flush()
