"""Native comparison of existing body-rate and attitude integrators against NASA.
This only selects public integrator properties; JSBSim is not patched.
"""
import csv
import json
import math
import os
from pathlib import Path
import tempfile
os.environ['JSBSIM_DEBUG']='0'
import jsbsim
ROOT=Path(__file__).resolve().parents[2]
REF=ROOT/'reference/nasa-checkcases/Atmos_02_TumblingBrickNoDamping/Atmos_02_sim_01.csv'
reference={round(float(r['time']),6):r for r in csv.DictReader(REF.open())}
cols=json.loads((ROOT/'tests/nasa/columns.json').read_text())
os.chdir(tempfile.mkdtemp(prefix='codex-nasa-'))
for rate in [1,3,4,5]:
    for attitude in [1,6,7]:
        f=jsbsim.FGFDMExec(str(ROOT/'jsbsim-data/check_cases/NASA_EOM_2015'))
        f.set_output_path(os.getcwd())  # session 03: keep JSBSim's output files out of jsbsim-data/ (cwd is a temp dir)
        f.set_debug_level(0)
        assert f.load_script('scripts/Atmos_02.xml',1/480)
        f.disable_output()
        f['simulation/integrator/rate/rotational']=rate
        f['simulation/integrator/position/rotational']=attitude
        assert f.run_ic()
        error={}
        for k in range(30*480+1):
            if k%48==0:
                ref=reference[round(k/480,6)]
                for name,prop,kind in cols:
                    if not name.startswith(('bodyAngular','eulerAngle')): continue
                    value=f[prop]*180/math.pi if kind=='deg' else f[prop]
                    delta=value-float(ref[name])
                    if name.startswith('eulerAngle'):delta=(delta+180)%360-180
                    error[name]=max(error.get(name,0),abs(delta))
            if k<30*480: assert f.run()
        print('RESULT '+json.dumps(dict(rate_integrator=rate,attitude_integrator=attitude,
              max_error_vs_sim01=error)),flush=True)
