"""Native counterpart to ground_spot.ts, including the same script-loading path."""
import json
import math
import os
from pathlib import Path
import tempfile
os.environ['JSBSIM_DEBUG']='0'
import jsbsim
ROOT=Path(__file__).resolve().parents[2]
os.chdir(tempfile.mkdtemp(prefix='codex-spot-'))
props=['velocities/'+p+'-rad_sec' for p in 'pqr']+['position/h-agl-ft',
       'velocities/v-north-fps','velocities/v-east-fps','velocities/v-down-fps']
for model,scenario,seconds in [('c172x','rest',60),('737','hard',15),('ah1s','inverted',15)]:
    for hz in [480,1000]:
        for integrator in [1,5]:
            f=jsbsim.FGFDMExec(str(ROOT/'jsbsim-data'))
            f.set_output_path(os.getcwd())  # session 03: keep JSBSim's output files out of jsbsim-data/ (cwd is a temp dir)
            f.set_debug_level(0)
            init='reset_at_rest' if model=='c172x' else 'reset00'
            script=Path('spot.xml').resolve()
            script.write_text(f'<runscript name="review"><use aircraft="{model}" initialize="{init}"/><run start="0" end="100" dt="{1/hz}"/></runscript>')
            assert f.load_script(str(script),1/hz);f.disable_output()
            if scenario!='rest':
                for p,v in {'ic/h-agl-ft':40,'ic/phi-deg':180 if scenario=='inverted' else 0,
                            'ic/theta-deg':0,'ic/vn-fps':100,'ic/ve-fps':0,
                            'ic/vd-fps':80 if scenario=='inverted' else 30}.items():f[p]=v
            f['simulation/integrator/rate/rotational']=integrator
            assert f.run_ic()
            initial=[f[p] for p in props]
            bad=None;tail=0
            for k in range(seconds*hz):
                assert f.run()
                values=[f[p] for p in props]
                if not all(math.isfinite(v) for v in values):bad=f.get_sim_time();break
                if f.get_sim_time()>=seconds-10:tail=max(tail,*map(abs,values[:3]))
            print('RESULT '+json.dumps(dict(model=model,scenario=scenario,hz=hz,integrator=integrator,
                initial=initial,first_nonfinite=bad,tail_peak_rate=tail,end_time=f.get_sim_time(),
                end=[f[p] for p in props])),flush=True)
