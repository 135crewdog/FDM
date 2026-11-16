"""Inspect what repeated run_ic really preserves, using the native release or a source build."""
import sys,json
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'tests/gates'))
import sim05 as S
print(S.native.describe())
for model in ['c172x','737','f16']:
 ac=S.G5['aircraft'][model];ic,theta,tr=S.approach_ic(model,6)
 ic['ic/h-agl-ft']=S.wheel_ground_h(model,1200,ic)+6
 f=S.start(model,1200,{'properties':{}},ic,ac['preset'],True,tr['throttle'])
 S.settle(f,model,1200,tr)
 for _ in range(300):f.run()
 names=['simulation/sim-time-sec','position/h-agl-ft','velocities/v-down-fps','velocities/p-rad_sec','propulsion/engine/thrust-lbs','propulsion/engine/engine-rpm','propulsion/engine/n2','fcs/elevator-pos-rad','fcs/flap-pos-deg','simulation/integrator/rate/rotational']
 names=[p for p in names if f.get_property_manager().hasNode(p)]
 before={p:f[p] for p in names};f.run_ic();after={p:f[p] for p in names}
 print(json.dumps(dict(model=model,before=before,after=after)),flush=True)
