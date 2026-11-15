"""Summarize all 4801 steps and 30 properties; fail on missing/nonfinite data.
Predeclared review limits for this short smooth flight: positions 1e-4 ft,
velocities 1e-5 ft/s, rates/attitude/surface positions 1e-7, force/moment
difference <= 1e-5 + 1e-7*max(|native|). These are review gates, not a game spec.
"""
import csv
import json
import math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
for model in ['c172x','f16']:
    for integ in [1,5]:
        def load(kind):
            with (ROOT/f'out/review/{model}-{integ}-{kind}.csv').open() as stream:
                r=csv.reader(stream); return next(r), [[float(v) for v in row] for row in r]
        props,a=load('native'); p2,b=load('wasm')
        assert props==p2 and len(a)==len(b)==4801
        for j,p in enumerate(props):
            assert all(math.isfinite(row[j]) for row in a+b)
            diff=max(abs(ra[j]-rb[j]) for ra,rb in zip(a,b))
            scale=max(abs(row[j]) for row in a)
            limit=(1e-4 if p.startswith('position/') else 1e-5 if p.endswith('-fps') else
                   1e-5+1e-7*scale if p.startswith(('forces/','moments/','propulsion/')) else 1e-7)
            print(json.dumps(dict(model=model,integrator=integ,property=p,max_abs_diff=diff,
                                  native_max_abs=scale,limit=limit,passed=diff<=limit)))
            assert diff<=limit,(model,integ,p,diff,limit)
