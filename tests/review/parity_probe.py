"""Native open-loop flight parity; shared initial state and exact binary controls.
Inputs depend on integer steps only, avoiding feedback and libm differences.
"""
import csv
import json
import os
from pathlib import Path
import tempfile
os.environ['JSBSIM_DEBUG']='0'
import jsbsim
ROOT=Path(__file__).resolve().parents[2]
C=json.loads((Path(__file__).with_name('parity_config.json')).read_text())
out=ROOT/'out/review'; out.mkdir(parents=True,exist_ok=True)
os.chdir(tempfile.mkdtemp(prefix='codex-parity-'))
for model in C['models']:
    for integ in C['integrators']:
        f=jsbsim.FGFDMExec(str(ROOT/'jsbsim-data')); f.set_debug_level(0)
        f.set_dt(1/C['hz']); assert f.load_model(model); f.disable_output()
        for p,v in C['initial'].items(): f[p]=v
        f['simulation/integrator/rate/rotational']=integ
        assert f.run_ic()
        for p in C['properties']:
            assert f.get_property_manager().hasNode(p),p
        with (out/f'{model}-{integ}-native.csv').open('w') as s:
            w=csv.writer(s); w.writerow(C['properties'])
            w.writerow([f[p] for p in C['properties']])
            for k in range(C['hz']*C['seconds']):
                for p,n in [('fcs/elevator-cmd-norm',128),('fcs/aileron-cmd-norm',256),('fcs/rudder-cmd-norm',512)]:
                    f[p]=((k//n)%3-1)/128
                assert f.run()
                w.writerow([f[p] for p in C['properties']])
        print(model,integ,'native complete')
