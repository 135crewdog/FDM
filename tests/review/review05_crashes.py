"""Additional crash perturbations, including wheel reappearance; not a replacement gate.
PYTHONPATH=build/native/patched .venv/bin/python tests/review/review05_crashes.py
"""
import sys,json,math
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tests/gates'))
import sim05 as S
import evaluate_05 as E
B=R/'build/review05';B.mkdir(exist_ok=True)
print(S.native.describe(),flush=True)
# More widely separated attitude perturbations than the gate's tiny repeats.
original=S.G5['G3d']['draws'][0][:]
for model in ['c172x','737','ah1s']:
 for sc in ['banked','nose']:
  for bank in [-15.,0.,15.]:
   # Change only the already configured initial bank, through the scenario dictionary in memory.
   spec=S.G5['G3d']['scenarios'][sc];p='ic/phi-deg';old=spec['ic'].get(p,0);spec['ic'][p]=old+bank
   path=B/'crash.f64';S.crash(model,sc,0,1200,S.CONFIGS['c2-mid-g'],path);spec['ic'][p]=old
   r=E.Run(path);m=E.crash_metrics(path)
   # Contacts resuming after a gap while already substantially compressed.
   resumed=[]
   for j,u in enumerate(r.meta['units']):
    if not r.bogey[j]:continue
    idx=((~r.wow[:-1,j])&r.wow[1:,j]).nonzero()[0]+1
    resumed.extend(float(r.comp[i,j]) for i in idx)
   print(json.dumps(dict(model=model,scenario=sc,bank_delta=bank,failed=E.judge_crash(m),ground_work_max=m.get('ground_work_max_ft'),closure=m.get('energy_closure_max_ft'),min_h=m.get('min_h_agl_ft'),resumed_compression_max=max(resumed,default=0))),flush=True)
   path.unlink()
