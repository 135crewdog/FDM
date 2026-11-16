"""AH-1S rotor-running landing fixture (session 05 exploration; not a gate, nothing here is frozen).

    cd /home/user/FDM && PYTHONPATH=build/native/patched .venv/bin/python tests/gates/explore05/ah1s_landing.py

trial(hz, target_sink_fps) spools the rotor up on the skids with the model's RPM governor, lifts off, hovers,
descends vertically at the target sink, and after the first contact lowers the collective and waits 10 s.
JSBSim's default integrators only (nothing under simulation/integrator/ is written). No trim routine. The
control law is plain arithmetic on properties read and written once per step, so it can be ported line by line.
Every call appends one line to results/05-fixture-trials-ah1s.jsonl.

Two ways to get into the hover (parameter `start`):
  "liftoff" (default)  nothing is preset: the helicopter flies up from the skids under the same control law.
  "reinit"             after the spool-up the flight state is put into the hover with a second run_ic()
                       (position, attitude, velocities, rates from ic/...; rotor, engine, governor and FCS
                       filter states are kept from the spool-up). Faster; says exactly what is preset below.
"""
import math
import sys

from ah1s_common import new_sim, Recorder, log_trial, contacts, HEAD, row

# ---- constants of the recipe -------------------------------------------------------------------------------
T_SPOOL = 8.0                    # s on the skids before anything but the governor is touched
GOV_T0, GOV_TC = 1.0, 5.0        # fcs/rpm-governor-active-norm: 0 until 1 s, linear to 1 at 6 s, then 1
ELE0, AIL0, RUD0 = -0.1558, 0.19095, 0.39    # pilot cyclic and pedal for the hover (ah1s_flight_test.xml)
PHI0, THETA0 = -0.049254, -0.006428          # AFCS attitude trims for the hover, rad (ah1s_flight_test.xml)
YAW_RATE_GAIN = 0.3              # ap/afcs/adj/yaw-rate-ctrl-gain (model default 0: heading swings +-2 deg)
KP, KI = 0.08, 0.3               # vertical-speed loop on fcs/collective-cmd-norm: per ft/s, per ft
COL_BASE_REINIT = 0.611          # collective preset used only with start="reinit"
KH, CLIMB = 0.5, 3.0             # height loop before the descent: vd_cmd = clip(KH*(h - h0), -CLIMB, CLIMB)
KU, KX = 0.03, 0.006             # position hold: theta trim = THETA0 + KU*u_h + KX*X   (rad per ft/s, rad per ft)
KV, KY = 0.03, 0.006             #                phi trim   = PHI0   - KV*v_h - KY*Y
TRIM_LIM = 0.12                  # rad, limit of the trim excursions
H_SKIDS = 7.6                    # ft: h-agl-ft with the skids about 1 ft above the ground (they touch near 6.6)
SINK_ACC = 4.0                   # ft/s^2: the commanded sink rises at this rate
T_STEADY = 3.0                   # s at the full commanded sink before the ground is reached (sets the hover height)
T_HOVER = 6.0                    # s in the hover before the descent starts
COL_DOWN = 2.0                   # s: after first contact collective, cyclic, pedal, pitch and roll AFCS go to 0
T_AFTER = 10.0                   # s simulated after the first contact
T_MAX = 90.0                     # s: give up


def clip(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def trial(hz, target_sink_fps, start="liftoff", log=True, what=None, verbose=0, **over):
    c = dict(T_SPOOL=T_SPOOL, ELE0=ELE0, AIL0=AIL0, RUD0=RUD0, PHI0=PHI0, THETA0=THETA0, YAW_RATE_GAIN=YAW_RATE_GAIN,
             KP=KP, KI=KI, COL_BASE_REINIT=COL_BASE_REINIT, KH=KH, CLIMB=CLIMB, KU=KU, KX=KX, KV=KV, KY=KY,
             TRIM_LIM=TRIM_LIM, H_SKIDS=H_SKIDS, SINK_ACC=SINK_ACC, T_STEADY=T_STEADY, T_HOVER=T_HOVER,
             COL_DOWN=COL_DOWN, T_AFTER=T_AFTER, PITCH_ROLL_AFCS=1.0, H0=None, WIND_N=0.0, WIND_E=0.0)
    for k in over:
        if k not in c:
            raise KeyError(k)
    c.update(over)
    dt = 1.0 / hz
    sink = float(target_sink_fps)
    h0 = c["H0"] if c["H0"] is not None else c["H_SKIDS"] + sink * sink / (2.0 * c["SINK_ACC"]) + sink * c["T_STEADY"]

    # new_sim: dt before load, load_model('ah1s'), load_ic('reset00'), tanks 0, aero/setup/downwash-enable 1,
    # aero/setup/Nr_limiter 0.05, fcs/adj/collective-profile 0, fcs/adj/center-sensitivity 1,
    # ap/afcs/psi-trim-rad 3.14159, run_ic()
    f = new_sim(hz)
    f["ap/afcs/adj/yaw-rate-ctrl-gain"] = c["YAW_RATE_GAIN"]
    if c["WIND_N"] != 0.0 or c["WIND_E"] != 0.0:     # robustness checks only; the recipe has no wind
        f["atmosphere/wind-north-fps"] = c["WIND_N"]
        f["atmosphere/wind-east-fps"] = c["WIND_E"]

    rec = Recorder()
    rec.airborne_seen = False
    phase = "spool"
    n_spool = int(round(c["T_SPOOL"] * hz))
    I = X = Y = 0.0                 # integrals: vertical-speed error (ft), displacement forward and right (ft)
    col = tht = pht = 0.0
    t_engage = t_arrive = t_descent = t_contact = None
    contact_before_descent = False
    psi_min, psi_max, drift_max = 360.0, 0.0, 0.0
    rpm_min, rpm_max = 1e9, 0.0
    i = 0
    while True:
        t = i * dt                                   # time since the start, exact multiples of dt
        # ---------------- controller: reads, then writes, then one step ----------------
        if phase == "spool":
            f["fcs/rpm-governor-active-norm"] = clip((t - GOV_T0) / GOV_TC, 0.0, 1.0)
            if i == n_spool:
                # engage: pilot cyclic and pedal, attitude trims, the three AFCS channels (steps, no ramps)
                f["fcs/elevator-cmd-norm"] = c["ELE0"]
                f["fcs/aileron-cmd-norm"] = c["AIL0"]
                f["fcs/rudder-cmd-norm"] = c["RUD0"]
                f["ap/afcs/manual/phi-trim-rad"] = c["PHI0"]
                f["ap/afcs/manual/theta-trim-rad"] = c["THETA0"]
                f["ap/afcs/yaw-channel-active-norm"] = 1.0
                f["ap/afcs/pitch-channel-active-norm"] = c["PITCH_ROLL_AFCS"]
                f["ap/afcs/roll-channel-active-norm"] = c["PITCH_ROLL_AFCS"]
                if start == "reinit":
                    # preset flight state: hover height, zero velocities and rates, hover attitude, heading south
                    f["ic/h-agl-ft"] = h0
                    f["ic/u-fps"] = 0.0
                    f["ic/v-fps"] = 0.0
                    f["ic/w-fps"] = 0.0
                    f["ic/p-rad_sec"] = 0.0
                    f["ic/q-rad_sec"] = 0.0
                    f["ic/r-rad_sec"] = 0.0
                    f["ic/phi-rad"] = c["PHI0"]
                    f["ic/theta-rad"] = c["THETA0"]
                    f["ic/psi-true-rad"] = math.pi
                    f["fcs/collective-cmd-norm"] = c["COL_BASE_REINIT"]
                    f.run_ic()                       # keeps rotor RPM, governor and FCS filter states
                t_engage = t
                phase = "hover"
        if phase in ("hover", "descent"):
            h = f["position/h-agl-ft"]
            vd = f["velocities/v-down-fps"]
            vn = f["velocities/v-north-fps"]
            ve = f["velocities/v-east-fps"]
            psi = f["attitude/psi-rad"]
            if t_arrive is None and abs(h - h0) < 0.5:
                t_arrive = t
            if phase == "hover" and t_arrive is not None and t >= t_arrive + c["T_HOVER"]:
                phase = "descent"
                t_descent = t
            if phase == "hover":
                vd_cmd = clip(c["KH"] * (h - h0), -c["CLIMB"], c["CLIMB"])
            else:
                vd_cmd = min(sink, (t - t_descent) * c["SINK_ACC"])
            e = vd - vd_cmd
            I += e * dt
            col = clip((c["COL_BASE_REINIT"] if start == "reinit" else 0.0) + c["KP"] * e + c["KI"] * I, 0.0, 1.0)
            uh = vn * math.cos(psi) + ve * math.sin(psi)       # ground velocity forward (ft/s)
            vh = -vn * math.sin(psi) + ve * math.cos(psi)      # ground velocity to the right (ft/s)
            X += uh * dt
            Y += vh * dt
            tht = c["THETA0"] + clip(c["KU"] * uh + c["KX"] * X, -c["TRIM_LIM"], c["TRIM_LIM"])
            pht = c["PHI0"] - clip(c["KV"] * vh + c["KY"] * Y, -c["TRIM_LIM"], c["TRIM_LIM"])
            f["fcs/collective-cmd-norm"] = col
            f["ap/afcs/manual/theta-trim-rad"] = tht
            f["ap/afcs/manual/phi-trim-rad"] = pht
            drift_max = max(drift_max, math.sqrt(X * X + Y * Y))
        elif phase == "ground":
            k = clip(1.0 - (t - t_contact) / c["COL_DOWN"], 0.0, 1.0)      # 1 -> 0 over COL_DOWN seconds
            f["fcs/collective-cmd-norm"] = col * k        # col, tht, pht: the last values of the descent
            f["fcs/elevator-cmd-norm"] = c["ELE0"] * k
            f["fcs/aileron-cmd-norm"] = c["AIL0"] * k
            f["fcs/rudder-cmd-norm"] = c["RUD0"] * k
            f["ap/afcs/pitch-channel-active-norm"] = c["PITCH_ROLL_AFCS"] * k
            f["ap/afcs/roll-channel-active-norm"] = c["PITCH_ROLL_AFCS"] * k
        f.run()
        i += 1
        # ---------------- measurement ----------------
        if phase == "descent":
            rec.airborne_seen = True        # arm the contact detection only in the descent
        touch = rec.step(f)
        if phase == "hover" and rec.t_contact is not None:
            # touched again between lift-off and the descent: not a touchdown of this fixture. Flag it (the
            # trial then counts as failed) and clear the record so the descent's first contact is measured.
            contact_before_descent = True
            rec.t_contact = None
            rec.rebounds = 0
            rec.max_roll = rec.max_pitch = rec.max_gear_fz = 0.0
            rec.tail_contact = False
        if phase == "hover" and t_arrive is not None and touch:
            contact_before_descent = True
        if phase == "descent" and rec.t_contact is not None:
            phase = "ground"
            t_contact = i * dt
        if phase != "spool":
            p = f["attitude/psi-deg"]
            psi_min, psi_max = min(psi_min, p), max(psi_max, p)
            r = f["propulsion/engine/rotor-rpm"]
            rpm_min, rpm_max = min(rpm_min, r), max(rpm_max, r)
        if verbose and (i % (hz // verbose) == 0):
            print("t=%6.2f %-7s h=%6.2f vd=%6.2f vg=%5.2f phi=%6.2f th=%6.2f psi=%6.1f rpm=%6.1f col=%.3f X=%5.1f Y=%5.1f fz=%7.0f wow=%s" % (
                i * dt, phase, f["position/h-agl-ft"], f["velocities/v-down-fps"], f["velocities/vg-fps"], f["attitude/phi-deg"],
                f["attitude/theta-deg"], f["attitude/psi-deg"], f["propulsion/engine/rotor-rpm"], f["fcs/collective-cmd-norm"],
                X, Y, f["forces/fbz-gear-lbs"], "".join("1" if x else "0" for x in contacts(f))))
        if not rec.finite:
            break
        if phase == "ground" and i * dt - t_contact >= c["T_AFTER"]:
            break
        if i * dt >= T_MAX:
            break
    res = rec.result(f)
    res.update(target_sink_fps=sink, hover_h_agl_ft=h0, t_engage=t_engage, t_arrive=t_arrive, t_descent_start=t_descent,
               contact_before_descent=contact_before_descent, psi_range_deg=[psi_min, psi_max],
               rpm_range_after_engage=[rpm_min, rpm_max], max_drift_ft=drift_max,
               sim_time_total=i * dt, last=dict(col=col, theta_trim=tht, phi_trim=pht, X=X, Y=Y),
               # "finite" is not "sane": also require the resting height and attitude, all four skids down,
               # no tail-bumper contact, never below the ground, and bounded roll/pitch after contact
               upright_at_end=bool(rec.finite and rec.t_contact is not None and not contact_before_descent
                                   and abs(f["attitude/phi-deg"]) < 5 and abs(f["attitude/theta-deg"]) < 5
                                   and all(contacts(f)[:4]) and not rec.tail_contact
                                   and abs(f["position/h-agl-ft"] - 6.29) < 0.3 and rec.min_h > 5.5
                                   and rec.max_roll < 15 and rec.max_pitch < 15
                                   and abs(f["velocities/v-down-fps"]) < 0.05 and f["velocities/vg-fps"] < 0.05))
    if log:
        log_trial(what or "ah1s_landing.trial", script="ah1s_landing.py", hz=hz, dt=dt, start=start,
                  overrides=over, constants=c, **res)
    return res


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "liftoff"
    rates = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [480]
    sinks = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [2, 4, 6, 8, 10]
    what = sys.argv[4] if len(sys.argv) > 4 else "ah1s_landing.py table run"
    print(HEAD, "  vg_c  drift  t_total upright")
    for hz in rates:
        for s in sinks:
            r = trial(hz, s, start=start, what=what)
            print(row(start, hz, s, r), "%5.2f %6.2f %7.2f %s" % (
                r["ground_speed_at_contact_fps"] or 0, r["max_drift_ft"], r["sim_time_total"], r["upright_at_end"]))
            sys.stdout.flush()
