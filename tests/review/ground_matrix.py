"""Independent native 1.3.3 contact stress test; never edits shipped models.
Run: JSBSIM_DEBUG=0 .venv/bin/python tests/review/ground_matrix.py
JSON records are prefixed RESULT to separate JSBSim's own diagnostics.
No acceptance threshold is inferred from finiteness alone.
"""
import json
import math
import os
from pathlib import Path
import tempfile

os.environ['JSBSIM_DEBUG'] = '0'
import jsbsim

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'jsbsim-data'
os.chdir(tempfile.mkdtemp(prefix='codex-ground-'))
RATES = ['velocities/' + x + '-rad_sec' for x in 'pqr']
STATE = RATES + ['position/h-agl-ft', 'velocities/v-north-fps',
                 'velocities/v-east-fps', 'velocities/v-down-fps']

def trial(model, hz, integ, scenario):
    f = jsbsim.FGFDMExec(str(DATA))
    f.set_output_path(os.getcwd())  # session 03: keep JSBSim's output files out of jsbsim-data/ (cwd is a temp dir)
    f.set_debug_level(0)
    f.set_dt(1/hz)
    assert f.load_model(model)
    f.disable_output()
    init = 'initGrnd' if model == 'F450' else ('reset_at_rest' if model == 'c172x' else 'reset00')
    assert f.load_ic(init, True)
    if scenario != 'rest':
        roll, pitch, down, north = {
            'hard': (0, 0, 30, 100),
            'inverted': (180, 0, 80, 100),
            'banked': (75, -15, 80, 100),
            'nose': (10, -75, 100, 20),
        }[scenario]
        for p, v in {'ic/h-agl-ft': 40, 'ic/phi-deg': roll,
                     'ic/theta-deg': pitch, 'ic/vn-fps': north,
                     'ic/ve-fps': 0, 'ic/vd-fps': down}.items():
            f[p] = v
    f['simulation/integrator/rate/rotational'] = integ
    assert f.run_ic()
    initial = {p: f[p] for p in STATE}
    seconds = 60 if scenario == 'rest' else 15
    bad = huge = None
    peak = last_peak = last_sq = 0.0
    tail_n = 0
    contact_steps = 0
    for k in range(round(seconds*hz)):
        if not f.run():
            break
        values = [f[p] for p in STATE]
        if not all(math.isfinite(v) for v in values):
            bad = f.get_sim_time()
            break
        w = max(abs(v) for v in values[:3])
        peak = max(peak, w)
        if w > 1e6 and huge is None:
            huge = f.get_sim_time()
        if f.get_sim_time() >= seconds-10:
            last_peak = max(last_peak, w)
            last_sq += sum(v*v for v in values[:3])
            tail_n += 1
        if f['gear/wow']:
            contact_steps += 1
    return dict(model=model, hz=hz, integrator=integ, scenario=scenario,
                first_nonfinite=bad, first_rate_over_1e6=huge,
                peak_rate=peak, tail_peak_rate=last_peak,
                tail_rate_rms=math.sqrt(last_sq/max(1,tail_n)),
                contact_steps=contact_steps, initial=initial,
                end={p: f[p] for p in STATE}, end_time=f.get_sim_time())

for model in ['c172x', 'f16', 'c310', 'F450', 'ah1s', '737']:
    for scenario in ['rest', 'hard', 'inverted', 'banked', 'nose']:
        for hz in [480, 1000]:
            for integ in [1, 5]:
                try:
                    result = trial(model, hz, integ, scenario)
                except Exception as e:
                    result = dict(model=model, hz=hz, integrator=integ,
                                  scenario=scenario, error=str(e))
                print('RESULT ' + json.dumps(result, allow_nan=True), flush=True)
