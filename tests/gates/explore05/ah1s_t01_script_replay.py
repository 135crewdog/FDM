"""Trial 1: replay scripts/ah1s_flight_test.xml's common part (spool-up, lift-off, hover) by hand at 480 Hz."""
import sys
from ah1s_common import new_sim, ramp, Recorder, snap, log_trial

hz = int(sys.argv[1]) if len(sys.argv) > 1 else 480
T = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
f = new_sim(hz)
rec = Recorder()
n = int(T * hz)
hover = None
state = {}
for i in range(n):
    t = f["simulation/sim-time-sec"]
    # governor 0 -> 1 from t=1 over 5 s
    f["fcs/rpm-governor-active-norm"] = ramp(t, 1.0, 5.0, 0.0, 1.0)
    h = f["position/h-agl-ft"]
    if hover is None and h >= 50:
        hover = t
        state = dict(col=f["fcs/collective-cmd-norm"], ele=f["fcs/elevator-cmd-norm"], ail=f["fcs/aileron-cmd-norm"])
    if t >= 10:
        yaw = ramp(t, 10.0, 3.0, 0.0, 1.0)
        f["ap/afcs/yaw-channel-active-norm"] = yaw
    if hover is not None:
        f["fcs/collective-cmd-norm"] = ramp(t, hover, 5.0, state["col"], 0.615)
        f["fcs/elevator-cmd-norm"] = ramp(t, hover, 5.0, state["ele"], -0.1558)
        f["fcs/aileron-cmd-norm"] = ramp(t, hover, 5.0, state["ail"], 0.19095)
        f["fcs/rudder-cmd-norm"] = 0.39
    elif t >= 15:
        f["fcs/collective-cmd-norm"] = ramp(t, 15.0, 10.0, 0.35, 0.615)
        f["fcs/elevator-cmd-norm"] = ramp(t, 15.0, 20.0, 0.0, -0.18)
        f["fcs/aileron-cmd-norm"] = ramp(t, 15.0, 20.0, 0.0, 0.22)
        f["fcs/rudder-cmd-norm"] = ramp(t, 15.0, 3.0, 0.35, 0.39)
        f["ap/afcs/manual/phi-trim-rad"] = -0.049254
        f["ap/afcs/manual/theta-trim-rad"] = -0.006428
        f["ap/afcs/pitch-channel-active-norm"] = ramp(t, 15.0, 3.0, 0.0, 1.0)
        f["ap/afcs/roll-channel-active-norm"] = ramp(t, 15.0, 3.0, 0.0, 1.0)
    elif t >= 10:
        f["fcs/collective-cmd-norm"] = ramp(t, 10.0, 3.0, 0.0, 0.35)
        f["fcs/rudder-cmd-norm"] = ramp(t, 10.0, 3.0, 0.0, 0.35)
    f.run()
    rec.step(f)
    if i % hz == 0:
        print(snap(f))
print(snap(f))
r = rec.result(f)
log_trial("t01 replay of ah1s_flight_test.xml common part by hand (spool-up, lift-off, hover at ~75 ft); no landing attempted",
          script="ah1s_t01_script_replay.py", hz=hz, dt=1.0 / hz, sim_time=T, **r)
print(r)
