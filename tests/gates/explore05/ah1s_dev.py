"""Development harness for the AH-1S landing fixture (session 05 exploration). Every call of run() logs one trial.

Sequence: (A) spool up on the skids with the model's RPM governor; (B) put the flight state into a hover at a
chosen height with a second run_ic() (engine, rotor and FCS states are kept); (C) hold vertical speed with the
collective, hold position with the AFCS attitude trims; (D) descend at the target sink; (E) on first contact
lower the collective and wait.
"""
import math
import sys
from ah1s_common import new_sim, ramp, Recorder, snap, log_trial, contacts

DEFAULT = dict(
    hz=480,
    t_spool=8.0,            # time on the ground before the re-initialisation
    gov_t0=1.0, gov_tc=5.0,  # governor ramp 0 -> 1
    h0=None,                # h-agl of the hover after re-initialisation (ft, CG height; skids touch near 6.6);
                            # None = 7.6 + sink^2/(2*sink_acc) + sink*t_steady
    t_steady=3.0,
    yaw_rate_gain=0.0,      # ap/afcs/adj/yaw-rate-ctrl-gain (model default 0)
    phi0=-0.049254, theta0=-0.006428,   # AFCS attitude trims (rad), from ah1s_flight_test.xml
    col0=0.55, ele0=-0.1558, ail0=0.19095, rud0=0.39,   # pilot controls preset at re-initialisation
    kp=0.04, ki=0.04,       # vertical-speed loop on fcs/collective-cmd-norm, per ft/s and per ft
    ku=0.01, kx=0.002,      # position hold through theta trim (rad per ft/s, rad per ft)
    kv=0.01, ky=0.002,      # position hold through phi trim
    trim_lim=0.12,
    t_hover=6.0,            # hover time before the descent starts
    sink=0.0,               # target sink (ft/s, positive down); 0 = hover only
    sink_acc=4.0,           # ft/s^2, ramp of the commanded sink
    t_after=10.0,           # time after first contact
    col_down_tc=2.0,        # collective to 0 after contact over this many seconds
    release="ramp",         # what the cyclic/AFCS do after contact
    t_max=60.0,
    start="reinit",         # "reinit": second run_ic() into the hover; "liftoff": fly up from the skids (no second run_ic)
    climb=3.0, kh=0.5,      # liftoff mode: vd_cmd = clip(kh*(h - h0), -climb, climb) until the descent starts
    verbose=1,
)


def run(what, **kw):
    P = dict(DEFAULT)
    P.update(kw)
    hz = P["hz"]
    dt = 1.0 / hz
    if P["h0"] is None:
        P["h0"] = 7.6 + P["sink"] ** 2 / (2 * P["sink_acc"]) + P["sink"] * P["t_steady"]
    f = new_sim(hz)
    f["ap/afcs/adj/yaw-rate-ctrl-gain"] = P["yaw_rate_gain"]
    # ---- A: spool up on the ground
    n = int(round(P["t_spool"] * hz))
    for i in range(n):
        t = i * dt
        f["fcs/rpm-governor-active-norm"] = ramp(t, P["gov_t0"], P["gov_tc"], 0.0, 1.0)
        f.run()
    if P["verbose"]:
        print("after spool-up:", snap(f))
    rpm_spool = f["propulsion/engine/rotor-rpm"]
    # ---- B: re-initialise the flight state into a hover
    f["ic/h-agl-ft"] = P["h0"]
    f["ic/u-fps"] = 0.0
    f["ic/v-fps"] = 0.0
    f["ic/w-fps"] = 0.0
    f["ic/phi-rad"] = P["phi0"]
    f["ic/theta-rad"] = P["theta0"]
    f["ic/psi-true-rad"] = math.pi
    f["ic/p-rad_sec"] = 0.0
    f["ic/q-rad_sec"] = 0.0
    f["ic/r-rad_sec"] = 0.0
    f["fcs/collective-cmd-norm"] = P["col0"]
    f["fcs/elevator-cmd-norm"] = P["ele0"]
    f["fcs/aileron-cmd-norm"] = P["ail0"]
    f["fcs/rudder-cmd-norm"] = P["rud0"]
    f["ap/afcs/manual/phi-trim-rad"] = P["phi0"]
    f["ap/afcs/manual/theta-trim-rad"] = P["theta0"]
    f["ap/afcs/yaw-channel-active-norm"] = 1.0
    f["ap/afcs/pitch-channel-active-norm"] = 1.0
    f["ap/afcs/roll-channel-active-norm"] = 1.0
    if P["start"] == "reinit":
        f.run_ic()
    t_b = f["simulation/sim-time-sec"]
    t_arrive = None if P["start"] == "liftoff" else 0.0
    if P["verbose"]:
        print("after re-init: ", snap(f))
    rec = Recorder()
    I = 0.0
    X = 0.0
    Y = 0.0
    t_contact = None
    hold = None
    n = int(round(P["t_max"] * hz))
    psi_min, psi_max = 360.0, 0.0
    for i in range(n):
        t = i * dt
        vd = f["velocities/v-down-fps"]
        vn = f["velocities/v-north-fps"]
        ve = f["velocities/v-east-fps"]
        psi = f["attitude/psi-rad"]
        uh = vn * math.cos(psi) + ve * math.sin(psi)
        vh = -vn * math.sin(psi) + ve * math.cos(psi)
        f["fcs/rpm-governor-active-norm"] = 1.0
        if t_contact is None:
            if t_arrive is None and abs(f["position/h-agl-ft"] - P["h0"]) < 0.5:
                t_arrive = t
            if t_arrive is None or t < t_arrive + P["t_hover"]:
                vd_cmd = 0.0
                if P["start"] == "liftoff":
                    vd_cmd = min(P["climb"], max(-P["climb"], P["kh"] * (f["position/h-agl-ft"] - P["h0"])))
            else:
                vd_cmd = min(P["sink"], (t - t_arrive - P["t_hover"]) * P["sink_acc"])
            e = vd - vd_cmd
            I += e * dt
            col = (P["col0"] if P["start"] == "reinit" else 0.0) + P["kp"] * e + P["ki"] * I
            col = min(1.0, max(0.0, col))
            X += uh * dt
            Y += vh * dt
            tht = P["theta0"] + P["ku"] * uh + P["kx"] * X
            pht = P["phi0"] - P["kv"] * vh - P["ky"] * Y
            tht = min(P["theta0"] + P["trim_lim"], max(P["theta0"] - P["trim_lim"], tht))
            pht = min(P["phi0"] + P["trim_lim"], max(P["phi0"] - P["trim_lim"], pht))
            f["fcs/collective-cmd-norm"] = col
            f["ap/afcs/manual/theta-trim-rad"] = tht
            f["ap/afcs/manual/phi-trim-rad"] = pht
            hold = dict(col=col, tht=tht, pht=pht)
        else:
            tc = t - t_contact
            f["fcs/collective-cmd-norm"] = ramp(tc, 0.0, P["col_down_tc"], hold["col"], 0.0)
            if P["release"] == "ramp":
                k = ramp(tc, 0.0, P["col_down_tc"], 1.0, 0.0)
                f["fcs/elevator-cmd-norm"] = P["ele0"] * k
                f["fcs/aileron-cmd-norm"] = P["ail0"] * k
                f["fcs/rudder-cmd-norm"] = P["rud0"] * k
                f["ap/afcs/pitch-channel-active-norm"] = k
                f["ap/afcs/roll-channel-active-norm"] = k
        f.run()
        touch = rec.step(f)
        if P["start"] == "liftoff" and t_arrive is None:
            rec.t_contact = None     # still on or leaving the skids: not a touchdown
            rec.airborne_seen = False
            rec.rebounds = 0
        if t > 3.0:
            psi_min = min(psi_min, f["attitude/psi-deg"])
            psi_max = max(psi_max, f["attitude/psi-deg"])
        if touch and t_contact is None and rec.t_contact is not None:
            t_contact = t + dt
        if P["verbose"] and (i % (hz // P["verbose"]) == 0 or (t_contact is not None and t - t_contact < 1.0 and i % (hz // 16) == 0)):
            print(snap(f), "colcmd=%.3f tht=%.4f pht=%.4f X=%.1f Y=%.1f" % (
                f["fcs/collective-cmd-norm"], f["ap/afcs/manual/theta-trim-rad"], f["ap/afcs/manual/phi-trim-rad"], X, Y))
        if not rec.finite:
            break
        if t_contact is not None and t - t_contact >= P["t_after"]:
            break
    r = rec.result(f)
    r["t_first_contact_after_reinit"] = None if rec.t_contact is None else rec.t_contact - t_b
    r["rpm_after_spool"] = rpm_spool
    r["hover"] = hold
    r["t_arrive_at_hover_height"] = t_arrive
    r["psi_range_deg"] = [psi_min, psi_max]
    params = {k: v for k, v in P.items() if k != "verbose"}
    log_trial(what, script="ah1s_dev.py", dt=dt, params=params, **r)
    if P["verbose"]:
        print(r)
    return r, f


if __name__ == "__main__":
    kw = {}
    for a in sys.argv[2:]:
        k, v = a.split("=")
        try:
            kw[k] = int(v)
        except ValueError:
            try:
                kw[k] = float(v)
            except ValueError:
                kw[k] = v
    run(sys.argv[1], **kw)
