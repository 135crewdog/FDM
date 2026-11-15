"""Native f16_test diagnostic ablations, isolated copies of model data.
Baseline unchanged. Ablations begin at 127 s, before the first impact, so all
variants follow the identical baseline trajectory up to the intervention.
Run: JSBSIM_DEBUG=0 .venv/bin/python tests/review/crash_probe.py
"""
import collections
import csv
import json
import math
import os
from pathlib import Path
import tempfile

os.environ['JSBSIM_DEBUG'] = '0'
import jsbsim
ROOT = Path(__file__).resolve().parents[2]
PROPS = (['position/h-agl-ft', 'gear/wow'] +
         ['velocities/'+p+'-rad_sec' for p in 'pqr'] +
         ['accelerations/'+p+'dot-rad_sec2' for p in 'pqr'] +
         ['moments/'+p+'-'+q+'-lbsft' for q in ['total','gear','aero'] for p in 'lmn'] +
         ['forces/fb'+p+'-gear-lbs' for p in 'xyz'] +
         ['forces/fb'+p+'-aero-lbs' for p in 'xyz'] +
         ['contact/unit'+('' if i == 0 else f'[{i}]')+'/'+p
          for i in range(3,10) for p in ['WOW','compression-ft','compression-velocity-fps']])
OUT = ROOT/'results/review-codex-02'
os.chdir(tempfile.mkdtemp(prefix='codex-crash-'))

def trial(hz, variant):
    f = jsbsim.FGFDMExec(str(ROOT/'jsbsim-data'))
    f.set_output_path(os.getcwd())  # session 03: keep JSBSim's output files out of jsbsim-data/ (cwd is a temp dir)
    f.set_debug_level(0)
    assert f.load_script('scripts/f16_test.xml',1/hz)
    f.disable_output()
    f['simulation/integrator/rate/rotational'] = 5
    assert f.run_ic()
    # Check the actual available properties; absent properties must not read as 0.
    props = [p for p in PROPS if f.get_property_manager().hasNode(p)]
    ring = collections.deque(maxlen=100)
    first_contact = first_huge = first_bad = None
    changed = False
    while f.get_sim_time() < 132:
        if not changed and f.get_sim_time() >= 127:
            changed = True
            if variant == 'euler-at-127':
                f['simulation/integrator/rate/rotational'] = 1
            if variant == 'no-structure-friction-at-127':
                for i in range(3,10):
                    for p in ['static_friction_coeff','dynamic_friction_coeff']:
                        name = f'contact/unit[{i}]/{p}'
                        assert f.get_property_manager().hasNode(name), name
                        f[name] = 0
            if variant == 'zero-velocity-at-127':
                # Reset state with RunIC is deliberately NOT used: it would reset hidden state.
                raise RuntimeError('not implemented')
        f.run()
        row = [f.get_sim_time()] + [f[p] for p in props]
        ring.append(row)
        contacts = [f[f'contact/unit[{i}]/WOW'] for i in range(3,10)]
        if any(contacts) and first_contact is None: first_contact = f.get_sim_time()
        w = max(abs(f['velocities/'+p+'-rad_sec']) for p in 'pqr')
        if w>1e6 and first_huge is None: first_huge = f.get_sim_time()
        if not all(math.isfinite(v) for v in row):
            first_bad = f.get_sim_time()
            break
    path = OUT/f'crash-{hz}-{variant}.csv'
    with path.open('w') as stream:
        writer=csv.writer(stream); writer.writerow(['time']+props); writer.writerows(ring)
    print('RESULT '+json.dumps(dict(hz=hz,variant=variant,first_structure_contact=first_contact,
          first_rate_over_1e6=first_huge,first_nonfinite=first_bad,
          final_rates=[f['velocities/'+p+'-rad_sec'] for p in 'pqr'],trace=path.name)),flush=True)

for hz in [120,240,480,1000]:
    for variant in ['baseline','no-structure-friction-at-127','euler-at-127']:
        trial(hz,variant)
