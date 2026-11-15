"""Test the *limited domains* of patch 0003's bit-identity claims.
Two executors from the patched source; native patch-off parity is tested separately.
This is not a claim that mixed air/contact trajectories equal either fixed scheme.
"""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/gates'))
import run_native as R

def contacts(f):
    pm=f.get_property_manager();n=int(f['gear/num-units'])
    return [pm.get_node(p).get_double_value for k in range(n)
        for p in [f'gear/unit[{k}]/WOW',f'contact/unit[{k}]/WOW'] if pm.hasNode(p)]

for model in R.G['aircraft']:
    for hz in [480,1000]:
        sims=[]
        for cfg in ['floor','c3-ab4']:
            f=R.native.new_fdm(dt=1/hz);assert f.load_model(model)
            assert f.load_ic(R.G['aircraft'][model],True)
            R.apply_config(f,R.CONFIGS[cfg]);assert f.run_ic();sims.append(f)
        starts=any(g()>0.5 for g in contacts(sims[0]));first=None;column=None
        for k in range(60*hz):
            for f in sims:assert f.run()
            a,b=[[f[p] for p in R.G['state']] for f in sims]
            if a!=b:
                first=(k+1)/hz;column=next(p for p,x,y in zip(R.G['state'],a,b) if x!=y);break
        print('RESULT '+json.dumps(dict(test='rest',model=model,hz=hz,starts_in_contact=starts,
            equal_full_60s=first is None,first_difference_time=first,column=column)),flush=True)

for hz in [480,1000]:
    sims=[]
    for cfg in ['c1-ab4','c3-ab4']:
        f=R.native.new_fdm(R.NASA_ROOT);assert f.load_script('scripts/Atmos_02.xml',1/hz)
        R.apply_config(f,R.CONFIGS[cfg]);assert f.run_ic();sims.append(f)
    first=None
    for k in range(30*hz):
        for f in sims:assert f.run()
        a,b=[[f[c[1]] for c in R.NASA_COLS] for f in sims]
        if a!=b:first=(k+1)/hz;break
    print('RESULT '+json.dumps(dict(test='NASA airborne',hz=hz,equal_all_steps=first is None,
        first_difference_time=first)),flush=True)
