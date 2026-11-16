"""Refine the spring counterexample and the envelope's finite difference sensitivity."""
import sys,json,math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tests/gates'))
import sim05 as S
import envelope05 as V
print(S.native.describe())
B=R/'build/review05';B.mkdir(exist_ok=True)
for cfg,hz in [('c2-mid-g',1200),('c3-ab4-g',960)]:
 for where in ['core','external']:
  S.G5['G7']['probe_cases']['light']=dict(kind='spring',omega_rad_s=100,zeta=.01,p0_rad_s=0.,phi0_rad=.001,seconds=1.)
  p=B/'light.f64';S.forced_probe('light',where,hz,S.CONFIGS[cfg],p,B/'probe-light')
  a=np.fromfile(p,dtype='<f8').reshape(-1,8)
  print('small-angle spring',json.dumps(dict(config=cfg,hz=hz,where=where,omega=100,zeta=.01,seconds=1,phi0=.001,max_phi=float(abs(a[:,4]).max()),end_phi=float(a[-1,4]),max_p=float(abs(a[:,1]).max()))),flush=True)
# Same untrimmed operating point as the report; vary increment and its sign.
model,kts='f16',800;r=V.point(model,kts);a=r['alpha_deg'];base=V.state(model,kts,a)[0]
for dq in [.1,.01,.001,.0001,.00001,-.00001,-.0001,-.001,-.01,-.1]:
 acc,_,f=V.state(model,kts,a,pqr=(0,dq,0))
 print('pitch finite difference',json.dumps(dict(dq=dq,qdot=float(acc[1]),slope=float((acc[1]-base[1])/dq),elevator=f['fcs/elevator-pos-rad'],pitch_rate=f['velocities/q-rad_sec'])),flush=True)
