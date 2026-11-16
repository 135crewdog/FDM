"""Fragility checks of the final recipe at 480 Hz (liftoff start unless noted). Each run is logged by trial()."""
import sys
from ah1s_common import HEAD, row
from ah1s_landing import trial

cases = [
    ("no pitch/roll AFCS (PITCH_ROLL_AFCS=0)", 6.0, "liftoff", dict(PITCH_ROLL_AFCS=0.0)),
    ("no position hold (KU=KV=KX=KY=0)", 6.0, "liftoff", dict(KU=0.0, KV=0.0, KX=0.0, KY=0.0)),
    ("yaw-rate gain 0 (model default)", 6.0, "liftoff", dict(YAW_RATE_GAIN=0.0)),
    ("sink 12", 12.0, "liftoff", {}),
    ("sink 15", 15.0, "liftoff", {}),
    ("sink 1", 1.0, "liftoff", {}),
    ("half vertical gains KP=0.04 KI=0.15", 2.0, "liftoff", dict(KP=0.04, KI=0.15)),
    ("half vertical gains KP=0.04 KI=0.15", 10.0, "liftoff", dict(KP=0.04, KI=0.15)),
    ("double vertical gains KP=0.16 KI=0.6", 6.0, "liftoff", dict(KP=0.16, KI=0.6)),
    ("short waits T_HOVER=2 T_STEADY=1.5", 6.0, "liftoff", dict(T_HOVER=2.0, T_STEADY=1.5)),
    ("slow lift-off CLIMB=1", 6.0, "liftoff", dict(CLIMB=1.0)),
    ("fast lift-off CLIMB=6", 6.0, "liftoff", dict(CLIMB=6.0)),
    ("collective down in 0.5 s", 10.0, "liftoff", dict(COL_DOWN=0.5)),
    ("collective down in 6 s", 10.0, "liftoff", dict(COL_DOWN=6.0)),
    ("no pitch/roll AFCS, repeat with the stricter upright test", 6.0, "liftoff", dict(PITCH_ROLL_AFCS=0.0)),
    ("wind from north 10 ft/s (tailwind)", 6.0, "liftoff", dict(WIND_N=-10.0)),
    ("wind from east 10 ft/s (from the right)", 6.0, "liftoff", dict(WIND_E=-10.0)),
    ("T_SPOOL=6", 6.0, "liftoff", dict(T_SPOOL=6.0)),
    ("T_SPOOL=11", 6.0, "liftoff", dict(T_SPOOL=11.0)),
    ("reinit start, sink 15", 15.0, "reinit", {}),
    ("reinit start, sink 1", 1.0, "reinit", {}),
]
sel = sys.argv[1:] and [int(x) for x in sys.argv[1].split(",")]
print(HEAD, "  vg_c  drift  t_total upright psi-range contact-before-descent")
for k, (name, s, start, over) in enumerate(cases):
    if sel and k not in sel:
        continue
    r = trial(480, s, start=start, what="fragility: " + name, **over)
    print(row(name, 480, s, r), "%5.2f %6.2f %7.2f %s [%.1f, %.1f] %s" % (
        r["ground_speed_at_contact_fps"] or 0, r["max_drift_ft"], r["sim_time_total"], r["upright_at_end"],
        r["psi_range_deg"][0], r["psi_range_deg"][1], r["contact_before_descent"]))
    sys.stdout.flush()
