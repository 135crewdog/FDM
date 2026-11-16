"""Independent native spot checks without editing the frozen gates.
PYTHONPATH=build/native/patched .venv/bin/python tests/review/review05_native.py [nasa|springs|fixtures|envelope]
"""
import sys,json,tempfile,math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tests/gates'))
import sim05 as S
import evaluate_05 as E
import run_native as N
import evaluate as Old
O=R/'results/review-codex-05';B=R/'build/review05';B.mkdir(exist_ok=True)
print(S.native.describe(),flush=True)
mode=sys.argv[1]
if mode=='nasa':
 N.G['G4']['rates_hz']=[960,1200,1440]
 N.run_nasa(S.CONFIGS['c2-mid-g'],B)
 for hz in N.G['G4']['rates_hz']:
  run=Old.nasa_csv(B/f'nasa-{hz}.native.csv')
  for name in Old.G['G4']['references']:
   ref=Old.nasa_csv(Old.NASA_REF/f'Atmos_02_{name}.csv');ts=sorted(set(run)&set(ref))
   print(json.dumps(dict(hz=hz,ref=name,samples=len(ts),rate_error_deg_s=max(abs(run[t][c]-ref[t][c]) for t in ts for c in Old.RATES),attitude_error_deg=max(abs((run[t][c]-ref[t][c]+180)%360-180) for t in ts for c in Old.ANGLES))),flush=True)
elif mode=='springs':
 for z in [.3,.01]:
  for omega in [20,100,200,400,800,1200]:
   case=dict(kind='spring',omega_rad_s=omega,zeta=z,p0_rad_s=0.,phi0_rad=.01,seconds=max(.2,12/(z*omega)))
   S.G5['G7']['probe_cases']['review']=case;E.G5['G7']['probe_cases']['review']=case
   for cfg,hz in [('c2-mid-g',1200),('c3-ab4-g',960)]:
    for where in ['core','external']:
     p=B/'spring.f64';S.forced_probe('review',where,hz,S.CONFIGS[cfg],p,B/'probe')
     m=E.probe_metrics(p)
     print(json.dumps(dict(config=cfg,hz=hz,zeta=z,omega=omega,where=where,metrics=m)),flush=True)
elif mode=='fixtures':
 # Capture the fixture's actual simulation and check release initialization and final measurements.
 made=[];orig=S.native.new_fdm
 def new(*a,**kw):
  f=orig(*a,**kw);made.append(f);return f
 S.native.new_fdm=new
 for model,case in [('c172x','limit'),('737','limit'),('ah1s','hard')]:
  p=B/f'landing-{model}.f64';made.clear()
  (S.heli_landing(case,1200,S.CONFIGS['c2-mid-g'],p) if model=='ah1s' else S.landing(model,case,1200,S.CONFIGS['c2-mid-g'],p))
  f=made[-1];m=E.landing_metrics(p)
  print('landing',json.dumps(m),flush=True)
  print('limit counters',model,[f['gear/strut-limits/'+s] for s in ['projection-floored','force-capped','travel-exceeded']],flush=True)
  p.unlink()
 for hz,cfg in [(1200,'c2-mid-g'),(9600,'ref05-ground-patched-g'),(19200,'ref05-ground-patched-g')]:
  p=B/f'skip-{hz}.f64'
  S.landing('c172x','skip',hz,S.CONFIGS[cfg],p)
  r=E.Run(p);np.save(B/f'skip-{hz}.npy',E.samples(r));print('skip',hz,E.landing_metrics(p)['contact_episodes'],flush=True);p.unlink()
 for aa,bb in [(1200,9600),(9600,19200)]:
  a=np.load(B/f'skip-{aa}.npy');b=np.load(B/f'skip-{bb}.npy');n=min(len(a),len(b));d=np.abs(E.wrap(a[:n,1:4]-b[:n,1:4]))*180/math.pi
  print('skip comparison',aa,bb,dict(max_att_deg=float(d.max()),end_att_deg=float(d[-1].max()),end_rate=float(np.abs(a[n-1,4:7]-b[n-1,4:7]).max()),max_time_mismatch=float(abs(a[:n,0]-b[:n,0]).max())),flush=True)
elif mode=='envelope':
 import envelope05 as V
 for model,kts in [('f16',800),('c310',220)]:
  r=V.point(model,kts);a=r['alpha_deg'];dw=.001;da=.02
  D=np.column_stack([(V.state(model,kts,a,pqr=tuple(dw if i==j else 0 for i in range(3)))[0]-V.state(model,kts,a,pqr=tuple(-dw if i==j else 0 for i in range(3)))[0])/(2*dw) for j in range(3)])
  S0=np.column_stack([(V.state(model,kts,a+da)[0]-V.state(model,kts,a-da)[0])/(2*math.radians(da)),(V.state(model,kts,a,beta=da)[0]-V.state(model,kts,a,beta=-da)[0])/(2*math.radians(da))])
  print(model,json.dumps(r),'central D',D.tolist(),'central S',S0.tolist(),flush=True)
