"""Independent session-05 history, energy-oracle and result-provenance audit.
Run: .venv/bin/python tests/review/review05_audit.py
"""
import sys,json,subprocess,hashlib
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(R/'tests/gates'))
import evaluate_05 as E
print('HEAD',subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip())
frozen=['tests/gates/'+s for s in ['gates-05.json','sim05.py','sim05.ts','run_native_05.py','run_wasm_05.ts','evaluate_05.py']]+['GATES-05.md']
print('frozen diff',subprocess.check_output(['git','diff','888654f','HEAD','--',*frozen],cwd=R,text=True) or 'empty')
for ref in ['888654f','a8d5df9','eb15890']:
 print(subprocess.check_output(['git','show','-s','--format=%h %cI %s',ref],cwd=R,text=True).strip())
for p in sorted((R/'results').glob('05*fixture-trials*.jsonl')):
 records=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
 print(p.name,len(records),'fields',sorted(set().union(*(r.keys() for r in records))))
# Feed the production energy routine an independently constructed Euler damper trajectory.
# Unit mass/inertia, nonrotating planet, zero translation. p[n+1]=(1-a)*p[n].
# R_N = -a*(1-a)/(2*(2-a))*p0^2*(1-(1-a)^(2N))/W.
for hz in [480,1200,9600]:
 lam,p0,N,W=180.,.5,hz,32.174049
 a=lam/hz;n=np.arange(N+1);p=p0*(1-a)**n
 run=E.Run.__new__(E.Run);names=E.G5['columns'];run.cols={v:i for i,v in enumerate(names)}
 run.a=np.zeros((N+1,len(names)));run.t=n/hz;run.W=W;run.m=1.
 run.meta={'inertia':{'ixx':1.,'iyy':1.,'izz':1.,'ixy':0.,'ixz':0.,'iyz':0.}}
 run.a[:,run.cols['velocities/p-rad_sec']]=p
 for src in ['total','aero']:
  run.a[:,run.cols[f'moments/l-{src}-lbsft']]=-lam*p
 out=run.energy();pred=-a*(1-a)/(2*(2-a))*p0*p0*(1-(1-a)**(2*N))/W
 print('Euler damper closure',{'hz':hz,'measured_ft':out['closure'][-1],'derived_ft':pred,'difference':out['closure'][-1]-pred})
 assert abs(out['closure'][-1]-pred)<1e-15
# Report provenance in every committed main report (hash lines, not runtime assertions).
for p in sorted((R/'results').glob('05-*.txt')):
 if any(s in p.name for s in ['new-','rates-1200-gates-c2-mid-g','containment-','gates-c2-mid-g']):
  lines=[l[:650] for l in p.read_text().splitlines() if 'fdm-wasm-' in l or ('module sha256' in l)]
  print(p.name,*lines[:4],sep='\n  ')
