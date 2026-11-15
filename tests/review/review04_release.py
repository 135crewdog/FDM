"""Synthetic zero-impulse contact/release test of history restart accuracy.

Spherical J=I, Mx=10*cos(2*pi*5*t), p(0)=0. Exact answer:
p=10*sin(2*pi*5*t)/(2*pi*5). A virtually force-free wheel (k=1e-6,
zero damping/friction) touches for 1/60 s every 1/5 s. Terrain follows
the wheel only to create the known contact flag; this is NOT a landing model.
It isolates switching/restarting without a significant contact moment.
"""
import json
import math
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/pylib'))
import native

xml='''<fdm_config version="2.0" release="BETA">
<planet><rotation_rate>0</rotation_rate></planet><metrics/>
<mass_balance><ixx unit="SLUG*FT2">1</ixx><iyy unit="SLUG*FT2">1</iyy>
<izz unit="SLUG*FT2">1</izz><emptywt unit="LBS">32.174049</emptywt></mass_balance>
<ground_reactions><contact type="BOGEY" name="flag-probe"><location unit="IN"><x>0</x><y>0</y><z>-12</z></location>
<static_friction>0</static_friction><dynamic_friction>0</dynamic_friction><rolling_friction>0</rolling_friction>
<spring_coeff unit="LBS/FT">0.000001</spring_coeff><damping_coeff unit="LBS/FT/SEC">0</damping_coeff>
<max_steer unit="DEG">0</max_steer><brake_group>NONE</brake_group></contact></ground_reactions>
<aerodynamics><axis name="ROLL"><function name="sinusoidal-moment"><product><value>10</value>
<cos><product><value>31.41592653589793</value><property>simulation/sim-time-sec</property></product></cos>
</product></function></axis></aerodynamics></fdm_config>'''
root=Path(tempfile.mkdtemp(prefix='review04-release-'));p=root/'aircraft/probe';p.mkdir(parents=True)
(p/'probe.xml').write_text(xml)
for hz in [480,960,1920]:
    for mode in ['air-ab4','restart','keep','euler']:
        f=native.new_fdm(root,dt=1/hz);assert f.load_model('probe')
        assert f.get_property_manager().hasNode('simulation/integrator/rate/rotational-on-contact')
        f['ic/h-sl-ft']=100000
        f['simulation/integrator/rate/rotational']=1 if mode=='euler' else 5
        f['simulation/integrator/position/rotational']=7
        if mode in ['restart','keep']:
            f['simulation/integrator/rate/rotational-on-contact']=1
            f['simulation/integrator/rate/contact-release-mode']=int(mode=='restart')
        assert f.run_ic()
        max_error=gear_moment=extra_contact=0.;bad_alignment=0
        gp=f.get_property_manager();contact=gp.get_node('gear/unit/WOW').get_double_value
        for k in range(10*hz):
            touched=contact()>0.5
            before=f['velocities/pi-rad_sec'];d=f['accelerations/pidot-rad_sec2']
            phase=k%(hz//5)
            if mode!='air-ab4' and phase<hz//60:
                terrain=f['position/h-sl-ft']-math.cos(f['attitude/phi-rad'])+0.001
            else:terrain=f['position/h-sl-ft']-1000
            f['position/terrain-elevation-asl-ft']=terrain
            assert f.run()
            now=f['velocities/pi-rad_sec']
            expected=10*math.sin(2*math.pi*5*f.get_sim_time())/(2*math.pi*5)
            max_error=max(max_error,abs(now-expected))
            gear_moment=max(gear_moment,abs(f['moments/l-gear-lbsft']))
            if mode in ['restart','keep']:
                active=f['simulation/integrator/rate/contact-active']>0.5
                bad_alignment+=active!=touched
                if active:extra_contact=max(extra_contact,abs(now-before-d/hz))
        print('RESULT '+json.dumps(dict(mode=mode,hz=hz,max_rate_error=max_error,
            final_rate=f['velocities/pi-rad_sec'],switches=f['simulation/integrator/rate/contact-switches'],
            max_gear_moment=gear_moment,alignment_errors=bad_alignment,
            max_euler_step_residual_on_contact=extra_contact)),flush=True)
