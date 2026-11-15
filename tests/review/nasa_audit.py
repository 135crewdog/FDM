"""Independent NASA archive provenance, full time coverage and pointwise envelope.
Usage: .venv/bin/python tests/review/nasa_audit.py /path/to/NASA.zip
Compares existing outputs, without changing the original NASA tests or metric.
"""
import csv
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[2]
REF=ROOT/'reference/nasa-checkcases/Atmos_02_TumblingBrickNoDamping'
if len(sys.argv)>1:
    with zipfile.ZipFile(sys.argv[1]) as z:
        for name in z.namelist():
            p=REF/Path(name).name
            if p.is_file():
                data=z.read(name)
                print('PROVENANCE',p.name,'identical',data==p.read_bytes(),hashlib.sha256(data).hexdigest())

def load(p):
    return {round(float(r['time']),6):{k:float(v) for k,v in r.items() if k and v not in ('',None)}
            for r in csv.DictReader(p.open())}

refs={p.stem:load(p) for p in sorted(REF.glob('*.csv'))}
variables=['bodyAngularRateWrtEi_deg_s_'+v for v in ['Roll','Pitch','Yaw']]+[
    'eulerAngle_deg_Roll','eulerAngle_deg_Pitch','eulerAngle_deg_Yaw',
    'gePosition_ft_X','gePosition_ft_Y','altitudeMsl_ft']
expected={round(i/10,6) for i in range(301)}
for p in sorted((ROOT/'out').glob('Atmos_02_wasm*.csv')):
    run=load(p)
    assert set(run)==expected,(p.name,len(run))
    for var in variables:
        keys=[k for k,r in refs.items() if var in r[0]]
        def delta(a,b):
            return (a-b+180)%360-180 if var.startswith('eulerAngle') else a-b
        coverage={k:len(expected & refs[k].keys()) for k in keys}
        distances={k:max(abs(delta(run[t][var],refs[k][t][var])) for t in expected & refs[k].keys()) for k in keys}
        outside=[]
        for t in sorted(expected):
            anchor=refs[keys[0]][t][var]
            values=[delta(refs[k][t][var],anchor) for k in keys if t in refs[k]]
            lo,hi=min(values),max(values)
            value=delta(run[t][var],anchor)
            excess=max(lo-value,value-hi,0)
            if excess>1e-12: outside.append((t,excess))
        print('RESULT',json.dumps(dict(run=p.name,variable=var,samples=len(run),
            max_distances=distances,reference_matched_samples=coverage,outside_envelope_samples=len(outside),
            max_envelope_excess=max((v for t,v in outside),default=0))))
