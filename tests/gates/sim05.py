"""Session 05: the measuring procedures, NATIVE side. tests/gates/sim05.ts is the same thing for WebAssembly.

A procedure sets a simulation up from gates-05.json, steps it, and after EVERY step appends one row of
numbers to a raw file (float64, little endian). It judges nothing: tests/gates/evaluate_05.py reads the
rows of both platforms and applies the limits. So the two platforms share one judge.

Row layout (the same on both platforms): COMMON columns, then 4 columns per contact point
(WOW, compression-ft, compression-velocity-fps, AGL-ft), in the order of the aircraft file.
"""
import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pylib"))
import native  # noqa: E402

G5 = json.loads((HERE / "gates-05.json").read_text())
CONFIGS = json.loads((HERE / "configs.json").read_text())
COMMON = G5["columns"]
UNIT_COLS = G5["unit_columns"]
D2R = math.pi / 180.0


def apply_config(f, cfg):
    """Set the configuration's properties. Each must already exist (a missing patch must not pass silently)."""
    pm = f.get_property_manager()
    for p, v in cfg["properties"].items():
        if not pm.hasNode(p):
            raise RuntimeError(f"property {p} does not exist in this build (wrong source for this configuration?)")
        f[p] = v
        if f[p] != v:
            raise RuntimeError(f"property {p} did not take the value {v} (reads {f[p]})")


def check_config(f, cfg):
    """The candidate's settings must survive everything the fixture does before the measured part starts."""
    for p, v in cfg["properties"].items():
        if f[p] != v:
            raise RuntimeError(f"property {p} no longer has the value {v} (reads {f[p]})")


class Rows:
    """Per-step rows, written as raw float64. The header (column names, constants) goes into a .json next to it."""

    def __init__(self, f, path, extra_meta):
        pm = f.get_property_manager()
        n = int(f["gear/num-units"])
        self.units = []
        for k in range(n):
            base = f"gear/unit[{k}]" if pm.hasNode(f"gear/unit[{k}]/WOW") else f"contact/unit[{k}]"
            if not pm.hasNode(base + "/WOW"):
                raise RuntimeError(f"no WOW property for contact point {k}")
            self.units.append(base)
        self.names = list(COMMON) + [f"{u}/{c}" for u in self.units for c in UNIT_COLS]
        for p in self.names:
            if not pm.hasNode(p):
                raise RuntimeError(f"property {p} does not exist")
        self.get = [pm.get_node(p).get_double_value for p in self.names]
        self.pack = struct.Struct("<%dd" % len(self.names)).pack
        self.path = Path(path)
        self.s = self.path.open("wb")
        self.count = 0
        self.wow_idx = [len(COMMON) + 4 * k for k in range(n)]
        self.bogey = [u.startswith("gear/") for u in self.units]
        meta = dict(columns=self.names, units=self.units, bogey=self.bogey,
                    mass_slugs=f["inertia/mass-slugs"], weight_lbs=f["inertia/weight-lbs"],
                    inertia={k: f[f"inertia/{k}-slugs_ft2"] for k in ("ixx", "iyy", "izz", "ixy", "ixz", "iyz")},
                    cg_in=[f["inertia/cg-x-in"], f["inertia/cg-y-in"], f["inertia/cg-z-in"]],
                    unit_z_in=[f[u + "/z-position"] for u in self.units], dt=f.get_delta_t(), **extra_meta)
        self.meta = meta

    def row(self):
        v = [g() for g in self.get]
        self.s.write(self.pack(*v))
        self.count += 1
        return v

    def close(self, **more):
        self.s.close()
        self.meta.update(rows=self.count, **more)
        self.path.with_suffix(".json").write_text(json.dumps(self.meta))


def set_props(f, props):
    """Write properties. A property that does not exist, or that refuses the write (read-only), is an error:
    native JSBSim would ignore both silently."""
    pm = f.get_property_manager()
    for p, v in props.items():
        if not pm.hasNode(p):
            raise RuntimeError(f"property {p} does not exist")
        if not pm.get_node(p).set_double_value(v):
            raise RuntimeError(f"cannot write {p}: the property is read-only")


def start(model, hz, cfg, ic, preset, engines, throttle):
    """dt, model, start file, initial conditions, landing configuration, candidate properties, run_ic, engines."""
    ac = G5["aircraft"][model]
    f = native.new_fdm(dt=1.0 / hz)
    if not f.load_model(model):
        raise RuntimeError("load_model failed")
    if not f.load_ic(ac["ic_file"], True):
        raise RuntimeError("load_ic failed")
    set_props(f, ic)
    set_props(f, preset)
    apply_config(f, cfg)
    if not f.run_ic():
        raise RuntimeError("run_ic failed")
    if engines:
        f["propulsion/set-running"] = -1
    for p in ac["throttle_props"]:
        f[p] = throttle
    f["propulsion/fuel_freeze"] = 1
    return f


def wheel_ground_h(model, hz, ic):
    """The ic/h-agl-ft at which the lowest wheel (BOGEY) just touches the ground in the attitude of `ic`: measured in
    a separate, fresh simulation at 100 ft (JSBSim's own geometry; nothing is stepped)."""
    ac = G5["aircraft"][model]
    f = native.new_fdm(dt=1.0 / hz)
    if not (f.load_model(model) and f.load_ic(ac["ic_file"], True)):
        raise RuntimeError("load failed")
    set_props(f, dict(ic, **{"ic/h-agl-ft": 100.0}))
    set_props(f, ac["preset"])
    if not f.run_ic():
        raise RuntimeError("run_ic failed")
    pm = f.get_property_manager()
    agl = [f[f"gear/unit[{k}]/AGL-ft"] for k in range(int(f["gear/num-units"])) if pm.hasNode(f"gear/unit[{k}]/AGL-ft")]
    return 100.0 - min(agl)


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def approach_ic(model, sink, bank=0.0, drift=0.0, trim=None):
    """Initial conditions of a steady descent at `sink` ft/s, heading north, at the aircraft's approach speed."""
    ac = G5["aircraft"][model]
    ap = ac["approach"]
    tr = trim or ac["trim"][f"{sink:g}"]
    v = ap["vt_fps"]
    gamma = -math.asin(sink / v)
    theta0 = tr["alpha_deg"] + gamma / D2R
    ic = {}
    if drift:
        # A crosswind from the west: the air, and the aircraft in it, move east at `drift` ft/s. Set before the
        # velocities, through the two wind properties that can be written (ic/vw-east-fps is read-only).
        ic.update({"ic/vw-mag-fps": drift, "ic/vw-dir-deg": 90.0})
    ic.update({"ic/psi-true-deg": 0.0, "ic/phi-deg": bank, "ic/theta-deg": theta0,
               "ic/vn-fps": v * math.cos(gamma), "ic/ve-fps": drift, "ic/vd-fps": sink, "ic/h-agl-ft": 0.0})
    return ic, theta0, tr


I = {n: COMMON.index(p) for n, p in (("theta", "attitude/theta-rad"), ("phi", "attitude/phi-rad"), ("psi", "attitude/psi-rad"),
                                     ("p", "velocities/p-rad_sec"), ("q", "velocities/q-rad_sec"), ("r", "velocities/r-rad_sec"),
                                     ("t", "simulation/sim-time-sec"))}


def fly_controls(f, ac, tr, r, theta_target, phi_target, thr, brake):
    """Three proportional controllers, the same for every configuration and platform. `r` is the latest row.
    Signs (checked for these aircraft, tests/gates/explore05/fw_signs.py): a positive elevator command pitches
    down, a positive aileron command rolls right, a positive rudder command yaws left."""
    pc, lc = ac["pitch"], ac["lateral"]
    theta, phi, psi = r[I["theta"]] / D2R, r[I["phi"]] / D2R, r[I["psi"]] / D2R
    if psi > 180.0:
        psi -= 360.0
    f["fcs/elevator-cmd-norm"] = clamp(tr["elevator"] + pc["kp"] * (theta - theta_target) + pc["kq"] * r[I["q"]], -1.0, 1.0)
    f["fcs/aileron-cmd-norm"] = clamp(-(lc["kphi"] * (phi - phi_target) + lc["kp"] * r[I["p"]]), -1.0, 1.0)
    f["fcs/rudder-cmd-norm"] = clamp(lc["kpsi"] * psi + lc["kr"] * r[I["r"]], -1.0, 1.0)
    for p in ac["throttle_props"]:
        f[p] = thr
    for p in ac["brake_props"]:
        f[p] = brake


def settle(f, model, hz, tr):
    """Let the engines and the control actuators reach the state of this flight condition before the measured
    part starts: fly settle_s seconds with the controls fixed at their trim values, and every settle_segment_s
    seconds put the aircraft back on its initial conditions (run_ic again: JSBSim resets position, velocity,
    attitude and rates, and keeps the engine and control-system states). It ends exactly on the initial
    conditions."""
    ap = G5["aircraft"][model]["approach"]
    ac = G5["aircraft"][model]
    f["fcs/elevator-cmd-norm"] = tr["elevator"]
    f["fcs/aileron-cmd-norm"] = 0.0
    f["fcs/rudder-cmd-norm"] = 0.0
    for p in ac["throttle_props"]:
        f[p] = tr["throttle"]
    for _ in range(round(ap["settle_s"] / ap["settle_segment_s"])):
        for _ in range(round(ap["settle_segment_s"] * hz)):
            f.run()
        if not f.run_ic():
            raise RuntimeError("run_ic (settle) failed")


def landing(model, case, hz, cfg, out_path, trim=None, height=None):
    """An approach that suits the aircraft, flown to touchdown and roll-out (G2d), or to a touch-and-go (G8).

    1. Steady descent at the case's sink rate, at the aircraft's approach speed, in landing configuration, engines
       running. The engines and controls are settled first (see settle); rows are written from the release on.
    2. From the release: pitch, roll and yaw are held by three proportional controllers. The start height puts
       the lowest wheel on the ground free_s seconds later.
    3. From the first wheel contact: idle, nose lowered at a fixed rate, wings level, brakes after a delay
       (or, for a touch-and-go: full power and the approach attitude)."""
    ac = G5["aircraft"][model]
    ap = ac["approach"]
    c = dict(G5["landing_cases"][case]) if isinstance(case, str) else dict(case)
    if c["sink_fps"] == "limit":
        c["sink_fps"] = ac["limit_sink_fps"]
    sink, bank, drift = c["sink_fps"], c.get("bank_deg", 0.0), c.get("drift_fps", 0.0)
    ic, theta0, tr = approach_ic(model, sink, bank, drift, trim)
    ic["ic/h-agl-ft"] = height if height is not None else wheel_ground_h(model, hz, ic) + sink * ap["free_s"]
    f = start(model, hz, cfg, ic, ac["preset"], ac["engines"], tr["throttle"])
    settle(f, model, hz, tr)
    check_config(f, cfg)
    pc = ac["pitch"]
    rows = Rows(f, out_path, dict(kind="landing", model=model, case=c, hz=hz, theta0_deg=theta0, ic=ic, trim=tr))
    r = rows.row()  # the state at the release
    t0 = r[I["t"]]
    t_touch = None
    # An undulating runway (G8's skipping case): the terrain height follows the distance run north, set before
    # every step. JSBSim's contact code only sees the height, as it would with a terrain callback of a game.
    wave = c.get("wave")
    terrain0, north, i_vn = f["position/terrain-elevation-asl-ft"], 0.0, COMMON.index("velocities/v-north-fps")
    mode = c.get("mode", "full_stop")
    after = c.get("seconds_after_touch", G5["G2d"]["seconds_after_touch"])
    error = None
    while True:
        t = r[I["t"]] - t0
        touched = any(r[k] > 0.5 for k, b in zip(rows.wow_idx, rows.bogey) if b)
        if touched and t_touch is None:
            t_touch = t
        if t_touch is None:
            target, phi_target, thr, brake = theta0, bank, tr["throttle"], 0.0
            if t > G5["G2d"]["max_seconds_to_touch"]:
                error = "no touchdown"
                break
        elif mode == "full_stop":
            target = max(pc["ground_theta_deg"], theta0 - pc["derotate_deg_s"] * (t - t_touch))
            phi_target, thr, brake = 0.0, 0.0, (ac["brake"] if t - t_touch >= ac["brake_delay_s"] else 0.0)
            if t - t_touch >= after:
                break
        elif mode == "touch_and_go":  # full power at the touchdown, the approach attitude plus a little, wings level
            target, phi_target, thr, brake = theta0 + c.get("go_pitch_up_deg", 0.0), 0.0, 1.0, 0.0
            if t - t_touch >= after:
                break
        else:  # skip: nothing changes at the touchdown (approach power and attitude), so the aircraft skips along
            target, phi_target, thr, brake = theta0, 0.0, tr["throttle"], 0.0
            if t - t_touch >= after:
                break
        fly_controls(f, ac, tr, r, target, phi_target, thr, brake)
        if wave:
            north += r[i_vn] / hz
            f["position/terrain-elevation-asl-ft"] = terrain0 + 0.5 * wave["amplitude_ft"] * (1.0 - math.cos(2.0 * math.pi * north / wave["length_ft"]))
        try:
            f.run()
        except Exception as e:  # noqa: BLE001  an exception ends the run; the evaluator counts it as a failure
            error = f"exception: {e}"
            break
        r = rows.row()
        if not all(map(math.isfinite, r)):
            error = "non-finite"
            break
    rows.close(error=error, t_touch=t_touch, t_release=t0)
    return rows.meta


def trim_residual(model, sink, hz, alpha, elevator, throttle):
    """For make_fixtures05.py: settle the engines at this flight condition, put the aircraft back on its initial
    conditions and return what is left over there: the force along and across the body (in units of weight) and
    the pitching moment (divided by weight, so in ft)."""
    ac = G5["aircraft"][model]
    tr = dict(alpha_deg=alpha, elevator=elevator, throttle=throttle)
    ic, theta0, _ = approach_ic(model, sink, trim=tr)
    # At the height of the release, so that the ground effect of the aircraft's own model is in the trim.
    ic["ic/h-agl-ft"] = wheel_ground_h(model, hz, ic) + sink * ac["approach"]["free_s"]
    f = start(model, hz, {"properties": {}}, ic, ac["preset"], ac["engines"], throttle)
    settle(f, model, hz, tr)
    w = f["inertia/weight-lbs"]
    return ((f["forces/fbx-total-lbs"] + f["forces/fbx-weight-lbs"]) / w, (f["forces/fbz-total-lbs"] + f["forces/fbz-weight-lbs"]) / w,
            f["moments/m-total-lbsft"] / w, f)


# ---------------------------------------------------------------------------------------------------------
# G2d, helicopter: a rotor-running vertical landing of the ah1s (recipe developed in
# tests/gates/explore05/ah1s_landing.py, its "reinit" start; every constant is in gates-05.json, "heli").

def heli_landing(case, hz, cfg, out_path):
    """1. On the skids: the model's RPM governor spools the rotor up (spool_s seconds).
    2. The flight state is put into a hover at h0 with a second run_ic (rotor, governor and control-system states
       are kept), the model's own attitude-hold channels are switched on, and a vertical-speed loop on the
       collective plus a slow position hold on the attitude trims fly the hover for hover_s seconds.
    3. Descent: the commanded sink rises to the case's value and is held to the ground. Rows are written from the
       start of the descent.
    4. From the first contact: collective, cyclic and pedal go to zero in collective_down_s; seconds_after more."""
    H = G5["heli"]
    ac = G5["aircraft"]["ah1s"]
    c = dict(G5["landing_cases"][case]) if isinstance(case, str) else dict(case)
    if c["sink_fps"] == "limit":
        c["sink_fps"] = ac["limit_sink_fps"]
    sink = c["sink_fps"]
    dt = 1.0 / hz
    h0 = H["h_skids_ft"] + sink * sink / (2.0 * H["sink_acc_fps2"]) + sink * H["steady_s"]
    f = native.new_fdm(dt=dt)
    if not (f.load_model("ah1s") and f.load_ic(ac["ic_file"], True)):
        raise RuntimeError("load failed")
    set_props(f, H["preset"])
    apply_config(f, cfg)
    if not f.run_ic():
        raise RuntimeError("run_ic failed")
    set_props(f, H["after_ic"])
    n_spool = round(H["spool_s"] * hz)
    for i in range(n_spool):
        f["fcs/rpm-governor-active-norm"] = clamp((i * dt - H["governor_t0_s"]) / H["governor_ramp_s"], 0.0, 1.0)
        f.run()
    f["fcs/rpm-governor-active-norm"] = 1.0
    set_props(f, H["engage"])
    set_props(f, {"ic/h-agl-ft": h0, "ic/u-fps": 0.0, "ic/v-fps": 0.0, "ic/w-fps": 0.0, "ic/p-rad_sec": 0.0, "ic/q-rad_sec": 0.0, "ic/r-rad_sec": 0.0,
                  "ic/phi-rad": H["phi_trim_rad"], "ic/theta-rad": H["theta_trim_rad"], "ic/psi-true-rad": math.pi,
                  "fcs/collective-cmd-norm": H["collective_base"]})
    if not f.run_ic():
        raise RuntimeError("second run_ic failed")
    check_config(f, cfg)
    pm = f.get_property_manager()
    gh, gvd, gvn, gve, gpsi = (pm.get_node(p).get_double_value for p in
                               ("position/h-agl-ft", "velocities/v-down-fps", "velocities/v-north-fps", "velocities/v-east-fps", "attitude/psi-rad"))
    integ = x = y = col = tht = pht = 0.0
    rows = None
    t_touch = error = None
    n_hover, n_max = round(H["hover_s"] * hz), round(H["max_s"] * hz)
    k_desc = k_touch = None
    i = 0
    while True:
        if k_touch is None:
            if k_desc is None and i >= n_hover:
                k_desc = i
                rows = Rows(f, out_path, dict(kind="landing", model="ah1s", case=c, hz=hz, theta0_deg=H["theta_trim_rad"] / D2R, hover_h_agl_ft=h0))
                rows.row()
            vd = gvd()
            vd_cmd = clamp(H["kh"] * (gh() - h0), -H["climb_fps"], H["climb_fps"]) if k_desc is None else min(sink, (i - k_desc) * dt * H["sink_acc_fps2"])
            e = vd - vd_cmd
            integ += e * dt
            col = clamp(H["collective_base"] + H["kp"] * e + H["ki"] * integ, 0.0, 1.0)
            vn, ve, psi = gvn(), gve(), gpsi()
            uh = vn * math.cos(psi) + ve * math.sin(psi)
            vh = -vn * math.sin(psi) + ve * math.cos(psi)
            x += uh * dt
            y += vh * dt
            tht = H["theta_trim_rad"] + clamp(H["ku"] * uh + H["kx"] * x, -H["trim_limit_rad"], H["trim_limit_rad"])
            pht = H["phi_trim_rad"] - clamp(H["kv"] * vh + H["ky"] * y, -H["trim_limit_rad"], H["trim_limit_rad"])
            f["fcs/collective-cmd-norm"] = col
            f["ap/afcs/manual/theta-trim-rad"] = tht
            f["ap/afcs/manual/phi-trim-rad"] = pht
        else:
            k = clamp(1.0 - (i - k_touch) * dt / H["collective_down_s"], 0.0, 1.0)
            f["fcs/collective-cmd-norm"] = col * k
            f["fcs/elevator-cmd-norm"] = H["engage"]["fcs/elevator-cmd-norm"] * k
            f["fcs/aileron-cmd-norm"] = H["engage"]["fcs/aileron-cmd-norm"] * k
            f["fcs/rudder-cmd-norm"] = H["engage"]["fcs/rudder-cmd-norm"] * k
            f["ap/afcs/pitch-channel-active-norm"] = k
            f["ap/afcs/roll-channel-active-norm"] = k
            if (i - k_touch) * dt >= H["seconds_after_touch"]:
                break
        try:
            f.run()
        except Exception as ex:  # noqa: BLE001
            error = f"exception: {ex}"
            break
        i += 1
        if rows is not None:
            r = rows.row()
            if not all(map(math.isfinite, r)):
                error = "non-finite"
                break
            if k_touch is None and any(r[k] > 0.5 for k in rows.wow_idx):
                k_touch = i
                t_touch = (i - k_desc) * dt
        elif any(pm.get_node(u + "/WOW").get_double_value() > 0.5 for u in H["wow_props"]):
            error = "touched the ground before the descent"
            rows = Rows(f, out_path, dict(kind="landing", model="ah1s", case=c, hz=hz, theta0_deg=H["theta_trim_rad"] / D2R, hover_h_agl_ft=h0))
            rows.row()
            break
        if i >= n_max:
            error = "no touchdown"
            break
    if rows is None:
        rows = Rows(f, out_path, dict(kind="landing", model="ah1s", case=c, hz=hz, theta0_deg=H["theta_trim_rad"] / D2R, hover_h_agl_ft=h0))
        rows.row()
    rows.close(error=error, t_touch=t_touch)
    return rows.meta


# ---------------------------------------------------------------------------------------------------------
# G3d: crash cases. The set-up of the frozen ground tests (aircraft's start file, the scenario's initial
# conditions, a tiny perturbation, engines not started); what is new is that every step is recorded.

def crash(model, scenario, run, hz, cfg, out_path):
    g3 = G5["G3d"]
    sc = g3["scenarios"][scenario]
    f = native.new_fdm(dt=1.0 / hz)
    if not (f.load_model(model) and f.load_ic(g3["aircraft"][model], True)):
        raise RuntimeError("load failed")
    ic = dict(sc["ic"])
    for p, d in zip(g3["perturbed_properties"], g3["draws"][run]):
        ic[p] = ic[p] + d
    set_props(f, ic)
    apply_config(f, cfg)
    if not f.run_ic():
        raise RuntimeError("run_ic failed")
    rows = Rows(f, out_path, dict(kind="crash", model=model, scenario=scenario, run=run, hz=hz, ic=ic))
    rows.row()
    error = None
    for _ in range(round(sc["seconds"] * hz)):
        try:
            f.run()
        except Exception as e:  # noqa: BLE001
            error = f"exception: {e}"
            break
        if not all(map(math.isfinite, rows.row())):
            error = "non-finite"
            break
    rows.close(error=error)
    return rows.meta


# ---------------------------------------------------------------------------------------------------------
# G7: forced flight. (a) a body with unit inertia and a moment law whose exact answer is known, computed inside
# JSBSim ("core") or written from outside before every step ("external", the way a game supplies forces);
# (b) the real aircraft at the fastest point of their envelope, flown with small control doublets.

PROBE_XML = """<fdm_config name="probe" version="2.0" release="BETA">
 <planet><rotation_rate>0</rotation_rate></planet>
 <metrics><wingarea unit="FT2">1</wingarea><wingspan unit="FT">1</wingspan><chord unit="FT">1</chord></metrics>
 <mass_balance><ixx unit="SLUG*FT2">1</ixx><iyy unit="SLUG*FT2">1</iyy><izz unit="SLUG*FT2">1</izz>
  <emptywt unit="LBS">32.174049</emptywt></mass_balance>
 <ground_reactions/>
 <external_reactions><moment name="roll" frame="BODY"><direction><x>1</x><y>0</y><z>0</z></direction></moment></external_reactions>
 <aerodynamics>%s</aerodynamics>
</fdm_config>
"""
PROBE_CORE = """<axis name="ROLL"><function name="moment-law"><sum>
   <product><value>%r</value><property>velocities/p-rad_sec</property></product>
   <product><value>%r</value><property>attitude/phi-rad</property></product></sum></function></axis>"""
PROBE_COLS = ["simulation/sim-time-sec", "velocities/p-rad_sec", "velocities/q-rad_sec", "velocities/r-rad_sec",
              "attitude/phi-rad", "attitude/theta-rad", "attitude/psi-rad", "moments/l-total-lbsft"]


def probe_law(case):
    """Moment = -c*p - k*phi on a body of unit inertia: c = damping rate (1/s) for a pure damper, or
    c = 2*zeta*omega and k = omega^2 for a damped spring."""
    if case["kind"] == "damping":
        return case["rate_per_s"], 0.0
    return 2.0 * case["zeta"] * case["omega_rad_s"], case["omega_rad_s"] ** 2


def forced_probe(case_name, where, hz, cfg, out_path, root):
    """One synthetic forced-flight run. `root` is a scratch JSBSim root that this function writes the probe into."""
    case = G5["G7"]["probe_cases"][case_name]
    c, k = probe_law(case)
    d = Path(root) / "aircraft/probe"
    d.mkdir(parents=True, exist_ok=True)
    (d / "probe.xml").write_text(PROBE_XML % (PROBE_CORE % (-c, -k) if where == "core" else ""))
    f = native.new_fdm(root, dt=1.0 / hz)
    if not f.load_model("probe"):
        raise RuntimeError("load_model failed")
    set_props(f, {"ic/h-sl-ft": 100000.0, "ic/p-rad_sec": case["p0_rad_s"], "ic/phi-rad": case["phi0_rad"]})
    apply_config(f, cfg)
    if not f.run_ic():
        raise RuntimeError("run_ic failed")
    pm = f.get_property_manager()
    get = [pm.get_node(p).get_double_value for p in PROBE_COLS]
    pack = struct.Struct("<%dd" % len(PROBE_COLS)).pack
    error = None
    n = 0
    with open(out_path, "wb") as s:
        r = [g() for g in get]
        s.write(pack(*r))
        for _ in range(round(case["seconds"] * hz)):
            if where == "external":
                # What a game does: read the state the last step left, compute the moment, write it, step.
                f["external_reactions/roll/magnitude-lbsft"] = -c * r[1] - k * r[4]
            try:
                f.run()
            except Exception as e:  # noqa: BLE001
                error = f"exception: {e}"
                break
            r = [g() for g in get]
            s.write(pack(*r))
            n += 1
            if not all(map(math.isfinite, r)) or abs(r[1]) > 1e6:
                error = "non-finite or runaway"
                break
    Path(out_path).with_suffix(".json").write_text(json.dumps(dict(kind="probe", case=case_name, where=where, hz=hz, columns=PROBE_COLS,
                                                                    c=c, k=k, error=error, rows=n + 1, dt=1.0 / hz)))


def fast_ic(model, tr=None):
    g7 = G5["G7"]
    pt = tr or g7["fast_points"][model]
    return {"ic/h-sl-ft": g7["altitude_ft"], "ic/terrain-elevation-ft": 0.0, "ic/vc-kts": pt["kts"], "ic/psi-true-deg": 0.0, "ic/phi-deg": 0.0,
            "ic/alpha-deg": pt["alpha_deg"], "ic/beta-deg": 0.0, "ic/gamma-deg": 0.0, "ic/theta-deg": pt["alpha_deg"]}, pt


def fast_flight(model, hz, cfg, out_path):
    """A real aircraft at the fastest point of its envelope (G7's table): level, gear and flaps up, full throttle,
    trimmed in pitch, held by the same three controllers as the landings, with small doublets added to elevator,
    aileron and rudder. Sampled at G7.sample_hz."""
    g7 = G5["G7"]
    ac = G5["aircraft"][model]
    ic, pt = fast_ic(model)
    f = start(model, hz, cfg, ic, g7["preset"][model], ac["engines"], pt["throttle"])
    settle(f, model, hz, pt)
    check_config(f, cfg)
    pm = f.get_property_manager()
    cols = g7["flight_columns"]
    get = [pm.get_node(p).get_double_value for p in cols]
    getc = [pm.get_node(p).get_double_value for p in COMMON]
    pack = struct.Struct("<%dd" % len(cols)).pack
    every = hz // g7["sample_hz"]
    assert every * g7["sample_hz"] == hz
    seg = round(g7["segment_s"] * hz)
    assert abs(seg - g7["segment_s"] * hz) < 1e-9
    error = None
    n = 0
    with open(out_path, "wb") as s:
        s.write(pack(*[g() for g in get]))
        n += 1
        for k in range(round(g7["seconds"] * hz)):
            fly_controls(f, ac, pt, [g() for g in getc], pt["alpha_deg"], 0.0, pt["throttle"], 0.0)
            for prop, mult in g7["doublets"]:
                f[prop] = clamp(f[prop] + ((k // (seg * mult)) % 3 - 1) * g7["doublet_amplitude"], -1.0, 1.0)
            try:
                f.run()
            except Exception as e:  # noqa: BLE001
                error = f"exception: {e}"
                break
            if (k + 1) % every == 0:
                r = [g() for g in get]
                s.write(pack(*r))
                n += 1
                if not all(map(math.isfinite, r)):
                    error = "non-finite"
                    break
    Path(out_path).with_suffix(".json").write_text(json.dumps(dict(kind="fast_flight", model=model, hz=hz, columns=cols, error=error, rows=n)))


def fast_trim_residual(model, hz, kts, alpha, elevator, throttle):
    """For make_fixtures05.py: the vertical force (in weights) and pitching moment (divided by weight) left over at a
    fast, level flight point after the engines have settled."""
    g7 = G5["G7"]
    ac = G5["aircraft"][model]
    tr = dict(kts=kts, alpha_deg=alpha, elevator=elevator, throttle=throttle)
    ic, _ = fast_ic(model, tr)
    f = start(model, hz, {"properties": {}}, ic, g7["preset"][model], ac["engines"], throttle)
    settle(f, model, hz, tr)
    w = f["inertia/weight-lbs"]
    return (f["forces/fbz-total-lbs"] + f["forces/fbz-weight-lbs"]) / w, f["moments/m-total-lbsft"] / w, f


# ---------------------------------------------------------------------------------------------------------
# G8, synthetic case (reported only): the review's repeated-contact test (tests/review/review04_release.py),
# unchanged in substance: unit inertia, roll moment A*cos(2*pi*f*t), a wheel with a negligible spring that is
# made to touch for contact_for_s every contact_every_s by moving the terrain. Exact answer: p = A*sin(wt)/w.

RELEASE_XML = """<fdm_config name="relprobe" version="2.0" release="BETA">
<planet><rotation_rate>0</rotation_rate></planet>
<metrics><wingarea unit="FT2">1</wingarea><wingspan unit="FT">1</wingspan><chord unit="FT">1</chord></metrics>
<mass_balance><ixx unit="SLUG*FT2">1</ixx><iyy unit="SLUG*FT2">1</iyy>
<izz unit="SLUG*FT2">1</izz><emptywt unit="LBS">32.174049</emptywt></mass_balance>
<ground_reactions><contact type="BOGEY" name="flag-probe"><location unit="IN"><x>0</x><y>0</y><z>-12</z></location>
<static_friction>0</static_friction><dynamic_friction>0</dynamic_friction><rolling_friction>0</rolling_friction>
<spring_coeff unit="LBS/FT">0.000001</spring_coeff><damping_coeff unit="LBS/FT/SEC">0</damping_coeff>
<max_steer unit="DEG">0</max_steer><brake_group>NONE</brake_group></contact></ground_reactions>
<aerodynamics><axis name="ROLL"><function name="sinusoidal-moment"><product><value>%r</value>
<cos><product><value>%r</value><property>simulation/sim-time-sec</property></product></cos>
</product></function></axis></aerodynamics></fdm_config>
"""


def release_probe(hz, cfg, out_path, root):
    syn = G5["G8"]["synthetic_reported_only"]
    d = Path(root) / "aircraft/relprobe"
    d.mkdir(parents=True, exist_ok=True)
    (d / "relprobe.xml").write_text(RELEASE_XML % (syn["moment_amplitude"], 2.0 * math.pi * syn["moment_hz"]))
    f = native.new_fdm(root, dt=1.0 / hz)
    if not f.load_model("relprobe"):
        raise RuntimeError("load_model failed")
    f["ic/h-sl-ft"] = 100000.0
    apply_config(f, cfg)
    if not f.run_ic():
        raise RuntimeError("run_ic failed")
    pm = f.get_property_manager()
    cols = ["simulation/sim-time-sec", "velocities/pi-rad_sec", "attitude/phi-rad", "gear/unit/WOW", "moments/l-gear-lbsft"]
    get = [pm.get_node(p).get_double_value for p in cols]
    pack = struct.Struct("<%dd" % len(cols)).pack
    every, length = round(syn["contact_every_s"] * hz), round(syn["contact_for_s"] * hz)
    error = None
    contact_steps = 0
    max_moment = 0.0
    with open(out_path, "wb") as s:
        s.write(pack(*[g() for g in get]))
        for k in range(round(syn["seconds"] * hz)):
            if k % every < length:
                f["position/terrain-elevation-asl-ft"] = f["position/h-sl-ft"] - math.cos(f["attitude/phi-rad"]) + 0.001
            else:
                f["position/terrain-elevation-asl-ft"] = f["position/h-sl-ft"] - 1000.0
            try:
                f.run()
            except Exception as e:  # noqa: BLE001
                error = f"exception: {e}"
                break
            r = [g() for g in get]
            s.write(pack(*r))
            contact_steps += r[3] > 0.5
            max_moment = max(max_moment, abs(r[4]))
    Path(out_path).with_suffix(".json").write_text(json.dumps(dict(kind="release", hz=hz, columns=cols, error=error, contact_steps=int(contact_steps), max_gear_moment=max_moment)))
