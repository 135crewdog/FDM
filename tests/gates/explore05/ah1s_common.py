"""AH-1S rotor-running landing fixture exploration (session 05): shared helpers.

Rules followed here: JSBSim default integrators only (nothing under simulation/integrator/ is written),
every simulation is created through tests/pylib/native.py, and every trial is appended to
results/05-fixture-trials-ah1s.jsonl through log_trial().
"""
import json
import math
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tests/pylib"))
import native  # noqa: E402

LOG = REPO / "results/05-fixture-trials-ah1s.jsonl"

WOW = ["gear/unit[0]/WOW", "gear/unit[1]/WOW", "gear/unit[2]/WOW", "gear/unit[3]/WOW", "contact/unit[4]/WOW"]


def log_trial(what, **fields):
    """Append one JSON line per simulation trial (complete and honest, failures included)."""
    rec = dict(when=time.strftime("%Y-%m-%dT%H:%M:%S"), aircraft="ah1s", what=what, **fields)
    with LOG.open("a") as s:
        s.write(json.dumps(rec) + "\n")
    return rec


def new_sim(hz):
    """Fresh ah1s on its skids (reset00), with the property presets of scripts/ah1s_flight_test.xml <run>."""
    f = native.new_fdm(dt=1.0 / hz)
    f.load_model("ah1s")
    f.load_ic("reset00", True)
    f["propulsion/tank[0]/contents-lbs"] = 0.0
    f["propulsion/tank[1]/contents-lbs"] = 0.0
    f["aero/setup/downwash-enable"] = 1.0
    f["aero/setup/Nr_limiter"] = 0.05
    f["fcs/adj/collective-profile"] = 0.0
    f["fcs/adj/center-sensitivity"] = 1.0
    f["ap/afcs/psi-trim-rad"] = 3.14159
    f.run_ic()
    return f


def ramp(t, t0, tc, v0, v1):
    """JSBSim FG_RAMP: linear from v0 at t0 to v1 at t0+tc, then v1."""
    if t <= t0:
        return v0
    if t >= t0 + tc:
        return v1
    return v0 + (v1 - v0) * (t - t0) / tc


def contacts(f):
    return [f[w] != 0.0 for w in WOW]


class Recorder:
    """Per-step measurement of the values the trial log needs."""

    def __init__(self):
        self.t_contact = None
        self.sink_at_contact = None
        self.rpm_at_contact = None
        self.u_at_contact = None
        self.v_at_contact = None
        self.phi_at_contact = None
        self.theta_at_contact = None
        self.which_first = None
        self.max_roll = 0.0
        self.max_pitch = 0.0
        self.min_h = float("inf")
        self.max_h = -float("inf")
        self.finite = True
        self.max_gear_fz = 0.0
        self.tail_contact = False
        self.airborne_seen = False
        self.prev_vd = 0.0
        self.rebounds = 0
        self._was_touch = False

    def step(self, f):
        t = f["simulation/sim-time-sec"]
        h = f["position/h-agl-ft"]
        phi = f["attitude/phi-deg"]
        th = f["attitude/theta-deg"]
        vd = f["velocities/v-down-fps"]
        c = contacts(f)
        touch = any(c)
        for x in (h, phi, th, vd, f["velocities/p-rad_sec"], f["velocities/q-rad_sec"], f["velocities/r-rad_sec"],
                  f["velocities/u-fps"], f["velocities/v-fps"], f["propulsion/engine/rotor-rpm"]):
            if not math.isfinite(x):
                self.finite = False
        if not touch:
            self.airborne_seen = True
            if self._was_touch and self.t_contact is not None:
                self.rebounds += 1
        if touch and self.airborne_seen and self.t_contact is None:
            self.t_contact = t
            # v-down of the step before contact (the last airborne value) and of this step
            self.sink_at_contact = self.prev_vd
            self.sink_first_contact_step = vd
            self.rpm_at_contact = f["propulsion/engine/rotor-rpm"]
            self.vg_at_contact = f["velocities/vg-fps"]
            self.u_at_contact = f["velocities/u-fps"]
            self.v_at_contact = f["velocities/v-fps"]
            self.phi_at_contact = phi
            self.theta_at_contact = th
            self.which_first = [i for i, x in enumerate(c) if x]
        if self.t_contact is not None:
            self.max_roll = max(self.max_roll, abs(phi))
            self.max_pitch = max(self.max_pitch, abs(th))
            self.max_gear_fz = max(self.max_gear_fz, abs(f["forces/fbz-gear-lbs"]))
            if c[4]:
                self.tail_contact = True
        self.min_h = min(self.min_h, h)
        self.max_h = max(self.max_h, h)
        self.prev_vd = vd
        self._was_touch = touch
        return touch

    def result(self, f):
        return dict(
            touched_down=self.t_contact is not None,
            t_first_contact=self.t_contact,
            sink_at_contact_fps=self.sink_at_contact,
            sink_first_contact_step_fps=getattr(self, "sink_first_contact_step", None),
            first_contact_points=self.which_first,
            ground_speed_at_contact_fps=getattr(self, "vg_at_contact", None),
            u_at_contact_fps=self.u_at_contact, v_at_contact_fps=self.v_at_contact,
            phi_at_contact_deg=self.phi_at_contact, theta_at_contact_deg=self.theta_at_contact,
            rotor_rpm_at_contact=self.rpm_at_contact,
            max_abs_roll_deg_after_contact=self.max_roll, max_abs_pitch_deg_after_contact=self.max_pitch,
            max_abs_gear_fz_lbs=self.max_gear_fz, tail_bumper_touched=self.tail_contact,
            rebounds=self.rebounds,
            min_h_agl_ft=self.min_h, max_h_agl_ft=self.max_h, finite=self.finite,
            t_end=f["simulation/sim-time-sec"],
            end=dict(h=f["position/h-agl-ft"], phi=f["attitude/phi-deg"], theta=f["attitude/theta-deg"],
                     psi=f["attitude/psi-deg"], rpm=f["propulsion/engine/rotor-rpm"],
                     u=f["velocities/u-fps"], v=f["velocities/v-fps"], vd=f["velocities/v-down-fps"],
                     contacts=contacts(f), dist_m=f["position/distance-from-start-mag-mt"]),
        )


def snap(f):
    return ("t=%6.2f h=%7.2f vd=%6.2f u=%6.2f v=%6.2f phi=%6.2f th=%6.2f psi=%6.1f rpm=%6.1f col=%.3f thr=%.3f fz=%8.0f wow=%s"
            % (f["simulation/sim-time-sec"], f["position/h-agl-ft"], f["velocities/v-down-fps"], f["velocities/u-fps"],
               f["velocities/v-fps"], f["attitude/phi-deg"], f["attitude/theta-deg"], f["attitude/psi-deg"],
               f["propulsion/engine/rotor-rpm"], f["propulsion/engine/collective-ctrl-rad"], f["fcs/throttle-pos-norm"],
               f["forces/fbz-gear-lbs"], "".join("1" if x else "0" for x in contacts(f))))


HEAD = "%-58s %4s %5s %6s %7s %5s %5s %6s %6s %6s %6s %7s %-7s %3s %4s %3s" % (
    "case", "hz", "sink", "t_c", "vd_c", "roll", "pitch", "u_c", "v_c", "rpm_c", "min_h", "maxFz", "first", "reb", "tail", "fin")


def row(case, hz, sink, r):
    def n(x, d=0.0):
        return d if x is None else x
    return "%-58s %4d %5.1f %6.2f %7.3f %5.2f %5.2f %6.2f %6.2f %6.1f %6.2f %7.0f %-7s %3d %4s %3s" % (
        case, hz, sink, n(r["t_first_contact"], -1), n(r["sink_at_contact_fps"], -99), r["max_abs_roll_deg_after_contact"],
        r["max_abs_pitch_deg_after_contact"], n(r["u_at_contact_fps"]), n(r["v_at_contact_fps"]), n(r["rotor_rpm_at_contact"]),
        r["min_h_agl_ft"], r["max_abs_gear_fz_lbs"], "".join(str(i) for i in (r["first_contact_points"] or [])), r["rebounds"],
        "yes" if r["tail_bumper_touched"] else "no", "ok" if r["finite"] else "NO")
