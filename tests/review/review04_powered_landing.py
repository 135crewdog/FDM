"""Exploratory approach/landing diagnostic, NOT a replacement acceptance gate.

737: 140 kt forward, 3 deg pitch, flap command 1, running engines at idle,
gear down. Start at 40 ft AGL; 5/10/15/30 ft/s descent, 480/1000 Hz.
An identical pitch controller holds 3 deg before touchdown, then gently lowers
the nose; controls are reported, not tuned per integrator. No aircraft XML is
changed. This is a simulator fixture, not validated real-aircraft performance.
Run with PYTHONPATH=build/native/patched .venv/bin/python ...
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/pylib'))
import native

CONFIGS=json.loads((ROOT/'tests/gates/configs.json').read_text())

def trial(config,hz,descent,controlled=True):
    f=native.new_fdm(dt=1/hz)
    assert f.load_model('737')
    assert f.load_ic('reset00',True)
    for p,v in {'ic/h-agl-ft':40,'ic/phi-deg':0,'ic/theta-deg':3,
                'ic/psi-true-deg':0,'ic/vn-fps':140*1.687809857,
                'ic/ve-fps':0,'ic/vd-fps':descent,
                'fcs/flap-cmd-norm':1,'fcs/flap-pos-norm':1,
                'gear/gear-cmd-norm':1,'gear/gear-pos-norm':1,
                'fcs/throttle-cmd-norm[0]':0,'fcs/throttle-cmd-norm[1]':0,
                'propulsion/engine[0]/set-running':1,'propulsion/engine[1]/set-running':1}.items():f[p]=v
    for p,v in CONFIGS[config]['properties'].items():
        assert f.get_property_manager().hasNode(p),p
        f[p]=v
    assert f.run_ic()
    f.get_propulsion().init_running(-1)
    n=int(f['gear/num-units']);pm=f.get_property_manager()
    wow=[pm.get_node(f'gear/unit[{i}]/WOW').get_double_value for i in range(n)]
    first_touch=None;touch_state=None;failed=None;min_h=math.inf;max_h_after=-math.inf
    max_bank=max_pitch=max_comp=max_force=0.0;max_gear_load=0.0
    trace=[]
    initial={p:f[p] for p in ['velocities/u-fps','velocities/v-fps','velocities/w-fps',
              'attitude/theta-deg','position/h-agl-ft','fcs/flap-pos-norm',
              'propulsion/engine[0]/n2','propulsion/engine[1]/n2']}
    for k in range(25*hz):
        if controlled:
            target=3.0 if first_touch is None else max(0,3-(f.get_sim_time()-first_touch)*1.5)
            # A pitch-rate damper plus attitude hold. Negative elevator pitches up.
            cmd=0.12*(f['attitude/theta-deg']-target)+0.9*f['velocities/q-rad_sec']
            f['fcs/elevator-cmd-norm']=max(-0.5,min(0.5,cmd))
        if first_touch is not None:
            f['fcs/left-brake-cmd-norm']=0.2;f['fcs/right-brake-cmd-norm']=0.2
        try:f.run()
        except Exception as e:failed='exception '+str(e);break
        t=f.get_sim_time()
        v=[f[p] for p in ['position/h-agl-ft','attitude/phi-deg','attitude/theta-deg',
             'velocities/p-rad_sec','velocities/q-rad_sec','velocities/r-rad_sec',
             'velocities/u-fps','velocities/v-fps','velocities/w-fps',
             'forces/fbx-gear-lbs','forces/fby-gear-lbs','forces/fbz-gear-lbs']]
        if not all(map(math.isfinite,v)):failed='nonfinite';break
        if max(map(abs,v[3:6]))>1e6:failed='rate runaway';break
        contact=any(g()>0.5 for g in wow)
        if contact and first_touch is None:
            first_touch=t
            touch_state={p:f[p] for p in ['velocities/u-fps','velocities/v-down-fps',
                'attitude/theta-deg','fcs/flap-pos-norm','propulsion/engine[0]/n2',
                'propulsion/engine[1]/n2']}
        min_h=min(min_h,v[0]);max_bank=max(max_bank,abs(v[1]));max_pitch=max(max_pitch,abs(v[2]))
        if first_touch is not None:max_h_after=max(max_h_after,v[0])
        max_comp=max(max_comp,*(f[f'gear/unit[{i}]/compression-ft'] for i in range(n)))
        max_force=max(max_force,math.hypot(*v[9:12])/f['inertia/weight-lbs'])
        if k%max(1,hz//10)==0:trace.append([t]+v[:9]+[int(contact),f['fcs/flap-pos-norm'],f['fcs/elevator-cmd-norm']])
    rec=dict(config=config,hz=hz,descent_fps=descent,controlled=controlled,
             native=native.key_info(),initial=initial,first_touch=first_touch,touch_state=touch_state,
             failed=failed,end_time=f.get_sim_time(),min_h_agl_ft=min_h,
             max_h_after_touch_ft=max_h_after,max_bank_deg=max_bank,max_pitch_deg=max_pitch,
             max_bogey_compression_ft=max_comp,max_gear_force_weights=max_force,
             end_h_agl_ft=f['position/h-agl-ft'],end_theta_deg=f['attitude/theta-deg'],
             end_speed_kts=f['velocities/vtrue-kts'])
    return rec,trace

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--configs',nargs='+',default=['floor','c3-ab4','c2-mid'])
    a.add_argument('--trace-dir',type=Path);args=a.parse_args()
    for cfg in args.configs:
        for hz in [480,1000]:
            for down in [5,10,15,30]:
                rec,trace=trial(cfg,hz,down)
                if args.trace_dir:
                    args.trace_dir.mkdir(parents=True,exist_ok=True)
                    (args.trace_dir/f'737-{cfg}-{hz}-{down}.json').write_text(json.dumps(trace))
                print('RESULT '+json.dumps(rec),flush=True)
