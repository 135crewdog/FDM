"""Sweep of the vertical-speed loop gains (and the AFCS yaw-rate gain), 480 Hz. Each run is logged by ah1s_dev.run()."""
import sys
from ah1s_dev import run

cases = [dict(kp=0.04, ki=0.04), dict(kp=0.06, ki=0.12), dict(kp=0.08, ki=0.16), dict(kp=0.08, ki=0.3),
         dict(kp=0.06, ki=0.12, yaw_rate_gain=0.3), dict(kp=0.06, ki=0.12, yaw_rate_gain=-0.3)]
print("%-45s %5s %7s %7s %6s %6s %6s %6s %7s %s" % ("case", "sink", "t_c", "vd_c", "roll", "pitch", "u_c", "v_c", "rpm", "psi range / first / rebounds / tail"))
for c in cases:
    for sink in (4.0, 10.0):
        r, f = run("sweep1: gains of the vertical-speed loop / yaw-rate gain, descent and touchdown", col0=0.611, sink=sink, verbose=0, **c)
        print("%-45s %5.1f %7.2f %7.3f %6.2f %6.2f %6.2f %6.2f %7.1f %s %s %d %s fin=%s endh=%.2f" % (
            c, sink, r["t_first_contact"] or -1, r["sink_at_contact_fps"] or -99, r["max_abs_roll_deg_after_contact"],
            r["max_abs_pitch_deg_after_contact"], r["u_at_contact_fps"] or 0, r["v_at_contact_fps"] or 0,
            r["rotor_rpm_at_contact"] or 0, ["%.1f" % x for x in r["psi_range_deg"]], r["first_contact_points"], r["rebounds"],
            r["tail_bumper_touched"], r["finite"], r["end"]["h"]))
        sys.stdout.flush()
