"""Rerun the exact 550-trial compression diagnostic under baseline/scratch builds.
Uses frozen scenarios/draws; changes no gate or patch. Also tests the separate
f16_test / AB4 / STRUCTURE-friction interaction at 120 and 240 Hz.
"""
import argparse
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/gates/diag'))
import blowup_cause as B

def matrix(config,runs):
    cfg=B.R.CONFIGS[config]
    for scenario in ['hard_forward','hard','inverted','banked','nose']:
        for model in B.G['aircraft']:
            records=[]
            for hz in [480,1000]:
                for run in range(runs):
                    r=B.one(cfg,model,scenario,hz,run)
                    records.append(dict(hz=hz,run=run,**r))
            print('CASE '+json.dumps(dict(config=config,scenario=scenario,model=model,
                native=B.native.key_info(),records=records)),flush=True)

def f16():
    for hz in [120,240,480,1000]:
        for remove_friction in [False,True]:
            f=B.native.new_fdm(dt=1/hz)
            assert f.load_script('scripts/f16_test.xml',1/hz)
            f['simulation/integrator/rate/rotational']=5
            assert f.run_ic()
            changed=False;bad=None;comp=0;first_absurd=None
            for _ in range(132*hz):
                if remove_friction and not changed and f.get_sim_time()>=127:
                    changed=True
                    for i in range(3,10):
                        for p in ['static_friction_coeff','dynamic_friction_coeff']:
                            f[f'contact/unit[{i}]/{p}']=0
                f.run()
                c=max(f[f'gear/unit[{i}]/compression-ft'] for i in range(3))
                if math.isfinite(c):comp=max(comp,c)
                if c>10 and first_absurd is None:first_absurd=f.get_sim_time()
                w=[f['velocities/'+p+'-rad_sec'] for p in 'pqr']
                if not all(map(math.isfinite,w)) or max(map(abs,w))>1e6:
                    bad=f.get_sim_time();break
            print('F16 '+json.dumps(dict(hz=hz,remove_structure_friction_at_127=remove_friction,
                runaway=bad,max_bogey_compression_ft=comp,first_bogey_over_10ft=first_absurd,
                native=B.native.key_info())),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default='floor');p.add_argument('--runs',type=int,default=11)
    p.add_argument('--only-f16',action='store_true');a=p.parse_args()
    if not a.only_f16:matrix(a.config,a.runs)
    f16()
