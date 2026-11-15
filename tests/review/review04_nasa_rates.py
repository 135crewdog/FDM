"""Native NASA cross-check, including a prospective 1200/1440 Hz midpoint option.
Diagnostic only; no gate or tolerance is changed.
"""
import csv
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/pylib'))
import native

COLS=json.loads((ROOT/'tests/nasa/columns.json').read_text())
CONFIGS=json.loads((ROOT/'tests/gates/configs.json').read_text())
def reference(name):
    p=ROOT/f'reference/nasa-checkcases/Atmos_02_TumblingBrickNoDamping/Atmos_02_{name}.csv'
    return {round(float(r['time']),6):r for r in csv.DictReader(p.open())}
refs=[reference(x) for x in ['sim_01','sim_04']]
for config in ['floor','c3-ab4','c2-mid']:
    for hz in [480,960,1000,1200,1440]:
        f=native.new_fdm(ROOT/'jsbsim-data/check_cases/NASA_EOM_2015')
        assert f.load_script('scripts/Atmos_02.xml',1/hz)
        for p,v in CONFIGS[config]['properties'].items():
            assert f.get_property_manager().hasNode(p),p
            f[p]=v
        assert f.run_ic()
        error={};n=0
        for k in range(30*hz+1):
            if k%(hz//10)==0:
                t=round(k/hz,6);n+=1
                for name,prop,kind in COLS:
                    if not name.startswith(('bodyAngular','eulerAngle')):continue
                    value=f[prop]*180/math.pi if kind=='deg' else f[prop]
                    assert math.isfinite(value)
                    for ref in refs:
                        d=value-float(ref[t][name])
                        if name.startswith('eulerAngle'):d=(d+180)%360-180
                        error[name]=max(error.get(name,0),abs(d))
            if k<30*hz:assert f.run()
        print('RESULT '+json.dumps(dict(config=config,hz=hz,samples=n,max_errors=error,
              native=native.key_info())),flush=True)
