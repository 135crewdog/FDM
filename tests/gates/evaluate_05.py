"""Session 05: the judge. Reads the per-step rows that sim05.py (native) and sim05.ts (WebAssembly) wrote and
measures every quantity the gates of GATES-05.md put a limit on. One implementation for both platforms.

Energy bookkeeping (all in the Earth-fixed frame, where the ground does not move):
  kinetic energy  K = m |v|^2 / 2 + w.Jw / 2      v = velocity of the centre of gravity over the ground (body
                                                   axes), w = body rates, J = inertia matrix
  power           P = F.v + M.w                    for the forces and moments of each source, as JSBSim reports
                                                   them: ground contact, aerodynamics, propulsion, external, and
                                                   weight (gravity). The centrifugal term of the rotating frame is
                                                   added; the Coriolis force does no work.
  closure         R(t) = K(t) - K(0) - integral of the total power    (0 if every joule is accounted for)
  ground work     Wg(t) = integral of the ground's power               (the ground can take energy and give back
                                                   what its springs stored, never more: Wg(t) <= 0)
Integrals use the trapezoidal rule over the step's two ends. Energies are divided by the aircraft's weight, so
they read in feet ("enough to lift the aircraft so many feet").
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
G5 = json.loads((HERE / "gates-05.json").read_text())
OMEGA_EARTH = 7.292115e-5  # rad/s (JSBSim's default planet)


class Run:
    def __init__(self, path):
        path = Path(path)
        self.meta = json.loads(path.with_suffix(".json").read_text())
        self.cols = {n: i for i, n in enumerate(self.meta["columns"])}
        a = np.fromfile(path, dtype="<f8")
        self.a = a[: (len(a) // len(self.cols)) * len(self.cols)].reshape(-1, len(self.cols))
        self.t = self.g("simulation/sim-time-sec")
        self.W = self.meta["weight_lbs"]
        self.m = self.meta["mass_slugs"]
        units = self.meta["units"]
        self.bogey = np.array(self.meta["bogey"], dtype=bool)
        self.wow = np.stack([self.g(u + "/WOW") for u in units], axis=1) > 0.5
        self.comp = np.stack([self.g(u + "/compression-ft") for u in units], axis=1)

    def g(self, name):
        return self.a[:, self.cols[name]]

    def vec(self, fmt, keys):
        return np.stack([self.g(fmt.format(k)) for k in keys], axis=1)

    def energy(self):
        """Per step: kinetic energy, and the cumulative work of each source; all divided by the weight (ft)."""
        v = self.vec("velocities/{}-fps", "uvw")
        w = self.vec("velocities/{}-rad_sec", "pqr")
        i = self.meta["inertia"]
        J = np.array([[i["ixx"], -i["ixy"], i["ixz"]], [-i["ixy"], i["iyy"], -i["iyz"]], [i["ixz"], -i["iyz"], i["izz"]]])
        K = 0.5 * self.m * (v * v).sum(axis=1) + 0.5 * np.einsum("ij,jk,ik->i", w, J, w)
        dt = np.diff(self.t)

        def work(src):
            p = (self.vec("forces/fb{}-" + src + "-lbs", "xyz") * v).sum(axis=1)
            if src != "weight":
                p = p + (self.vec("moments/{}-" + src + "-lbsft", "lmn") * w).sum(axis=1)
            return np.concatenate([[0.0], np.cumsum(0.5 * (p[1:] + p[:-1]) * dt)])

        out = {s: work(s) / self.W for s in ("total", "weight", "gear", "aero", "prop", "external")}
        x, ve = self.vec("position/ecef-{}-ft", "xyz"), self.vec("velocities/ecef-{}-fps", "xyz")
        pc = self.m * OMEGA_EARTH ** 2 * (x[:, 0] * ve[:, 0] + x[:, 1] * ve[:, 1])
        out["centrifugal"] = np.concatenate([[0.0], np.cumsum(0.5 * (pc[1:] + pc[:-1]) * dt)]) / self.W
        out["kinetic"] = K / self.W
        out["closure"] = out["kinetic"] - out["kinetic"][0] - out["total"] - out["weight"] - out["centrifugal"]
        return out


def wrap(d):
    return (d + np.pi) % (2.0 * np.pi) - np.pi


def samples(r):
    """Attitude, body rates and height at G5.sample_hz from the first row (the release), for comparisons with a
    reference run at another step rate: both are sampled at the same times."""
    every = round(1.0 / (r.meta["dt"] * G5["sample_hz"]))
    idx = np.arange(0, len(r.a), every)
    return np.column_stack([r.t[idx] - r.t[0], r.vec("attitude/{}-rad", ["phi", "theta", "psi"])[idx],
                            r.vec("velocities/{}-rad_sec", "pqr")[idx], r.g("position/h-agl-ft")[idx]])


def landing_metrics(path, keep_samples=False):
    """Everything G2d and G8 measure, for one landing run."""
    r = Run(path)
    meta, a = r.meta, r.a
    d = dict(kind="landing", model=meta["model"], case=meta["case"], hz=meta["hz"], error=meta.get("error"), rows=len(a), theta0_deg=meta["theta0_deg"])
    finite = bool(np.isfinite(a).all())
    d["finite"] = finite
    any_b = r.wow[:, r.bogey].any(axis=1)
    d["touched"] = bool(any_b.any())
    if not finite or not d["touched"]:
        return d
    k0 = int(np.argmax(any_b))
    kb = max(k0 - 1, 0)   # the last row in the air
    deg = lambda n: np.degrees(r.g(n))  # noqa: E731
    phi, theta = deg("attitude/phi-rad"), deg("attitude/theta-rad")
    psi = np.degrees(wrap(r.g("attitude/psi-rad") - r.g("attitude/psi-rad")[0]))   # heading change since the first row
    h = r.g("position/h-agl-ft")
    fg = np.sqrt((r.vec("forces/fb{}-gear-lbs", "xyz") ** 2).sum(axis=1)) / r.W
    e = r.energy()
    names = meta["units"]
    anyc = r.wow.any(axis=1)
    air_after = ~anyc[k0:]
    last = float(r.t[k0:][air_after].max() - r.t[k0]) if air_after.any() else 0.0
    d.update(t_touch=float(r.t[k0] - r.t[0]), t_end_after_touch=float(r.t[-1] - r.t[k0]),
             touch=dict(sink_fps=float(r.g("velocities/v-down-fps")[kb]), theta_deg=float(theta[kb]), phi_deg=float(phi[kb]),
                        u_fps=float(r.g("velocities/u-fps")[kb]), v_fps=float(r.g("velocities/v-fps")[kb]), w_fps=float(r.g("velocities/w-fps")[kb]),
                        vc_kts=float(r.g("velocities/vc-kts")[kb]), alpha_deg=float(deg("aero/alpha-rad")[kb]),
                        thrust_lbs=float(r.g("propulsion/engine/thrust-lbs")[kb]), first_units=[names[j] for j in range(len(names)) if r.wow[k0, j]]),
             h_agl_at_release=float(h[0]), min_h_agl_ft=float(h.min()), max_h_agl_after_touch_ft=float(h[k0:].max()),
             max_abs_phi_deg=float(np.abs(phi).max()), min_theta_deg=float(theta.min()), max_theta_deg=float(theta.max()),
             max_abs_psi_deg=float(np.abs(psi).max()), max_rate_rad_s=float(np.abs(r.vec("velocities/{}-rad_sec", "pqr")).max()),
             max_ground_force_weights=float(fg.max()),
             max_compression_ft=[float(r.comp[:, j].max()) for j in range(len(names))], bogey=[bool(b) for b in r.bogey],
             structure_contacts=[names[j] for j in np.where(~r.bogey)[0] if r.wow[:, j].any()],
             contact_episodes=int((np.diff(anyc.astype(int)) == 1).sum()) + int(anyc[0]),
             last_airborne_after_touch_s=last,
             end=dict(h_agl_ft=float(h[-1]), theta_deg=float(theta[-1]), phi_deg=float(phi[-1]), psi_deg=float(psi[-1]), vc_kts=float(r.g("velocities/vc-kts")[-1]),
                      all_wheels_down=bool(r.wow[-1, r.bogey].all()), any_contact=bool(anyc[-1]), v_down_fps=float(r.g("velocities/v-down-fps")[-1])),
             energy_ft=dict(kinetic_start=float(e["kinetic"][0]), kinetic_end=float(e["kinetic"][-1]),
                            closure_max_abs=float(np.abs(e["closure"]).max()), ground_work_max=float(e["gear"].max()), ground_work_end=float(e["gear"][-1]),
                            aero_work_end=float(e["aero"][-1]), prop_work_end=float(e["prop"][-1]), weight_work_end=float(e["weight"][-1])))
    if keep_samples:
        np.save(Path(path).with_suffix(".samples.npy"), samples(r))
    return d


def crash_metrics(path):
    """Everything G3d measures, for one crash run."""
    r = Run(path)
    meta, a = r.meta, r.a
    d = dict(kind="crash", model=meta["model"], scenario=meta["scenario"], run=meta["run"], hz=meta["hz"], error=meta.get("error"), rows=len(a))
    ok = np.isfinite(a).all(axis=1)
    n = int(ok.sum()) if ok.all() else int(np.argmin(ok))   # rows before the first non-finite one
    d["finite"] = bool(ok.all())
    if n < 2:
        return d
    r.a, r.t, r.wow, r.comp = a[:n], r.t[:n], r.wow[:n], r.comp[:n]
    fg = np.sqrt((r.vec("forces/fb{}-gear-lbs", "xyz") ** 2).sum(axis=1)) / r.W
    rates = np.abs(r.vec("velocities/{}-rad_sec", "pqr")).max(axis=1)
    e = r.energy()
    h = r.g("position/h-agl-ft")
    anyc = r.wow.any(axis=1)
    d.update(touched=bool(anyc.any()), first_contact_s=float(r.t[np.argmax(anyc)] - r.t[0]) if anyc.any() else None,
             max_rate_rad_s=float(rates.max()), max_ground_force_weights=float(fg.max()), t_max_ground_force=float(r.t[int(fg.argmax())] - r.t[0]),
             max_compression_ft=float(r.comp[:, r.bogey].max()) if r.bogey.any() else 0.0,
             ground_work_max_ft=float(e["gear"].max()), ground_work_end_ft=float(e["gear"][-1]), energy_closure_max_ft=float(np.abs(e["closure"]).max()),
             min_h_agl_ft=float(h.min()), max_h_agl_ft=float(h.max()), end_h_agl_ft=float(h[-1]),
             end_abs_phi_deg=float(abs(np.degrees(r.g("attitude/phi-rad")[-1]))), end_theta_deg=float(np.degrees(r.g("attitude/theta-rad")[-1])),
             end_speed_fps=float(np.sqrt((r.vec("velocities/{}-fps", "uvw")[-1] ** 2).sum())), end_any_contact=bool(anyc[-1]))
    return d


def probe_exact(case, t):
    """Exact answer of G7's probe: (p, phi) of a body of unit inertia under the moment -c*p - k*phi."""
    if case["kind"] == "damping":
        lam = case["rate_per_s"]
        return case["p0_rad_s"] * np.exp(-lam * t), case["phi0_rad"] + case["p0_rad_s"] * (1.0 - np.exp(-lam * t)) / lam
    w, z = case["omega_rad_s"], case["zeta"]
    wd = w * math.sqrt(1.0 - z * z)
    env = np.exp(-z * w * t)
    return (-case["phi0_rad"] * env * (w * w / wd) * np.sin(wd * t), case["phi0_rad"] * env * (np.cos(wd * t) + z * w / wd * np.sin(wd * t)))


def probe_metrics(path):
    path = Path(path)
    meta = json.loads(path.with_suffix(".json").read_text())
    case = G5["G7"]["probe_cases"][meta["case"]]
    n = len(meta["columns"])
    a = np.fromfile(path, dtype="<f8")
    a = a[: (len(a) // n) * n].reshape(-1, n)
    d = dict(kind="probe", case=meta["case"], where=meta["where"], hz=meta["hz"], error=meta["error"], rows=len(a), finite=bool(np.isfinite(a).all()))
    expected = round(case["seconds"] * meta["hz"]) + 1
    d["complete"] = len(a) == expected
    if not d["finite"] or len(a) < 2:
        return d
    t = a[:, 0] - a[0, 0]
    pe, phie = probe_exact(case, t)
    if case["kind"] == "damping":
        x, xe, x0, tc = a[:, 1], pe, case["p0_rad_s"], 1.0 / case["rate_per_s"]
    else:
        x, xe, x0, tc = a[:, 4], phie, case["phi0_rad"], 1.0 / (case["zeta"] * case["omega_rad_s"])
    late = t >= G5["G7"]["limits"]["settled_after_time_constants"] * tc
    d.update(peak_over_initial=float(np.abs(x).max() / abs(x0)), max_error_over_initial=float(np.abs(x - xe).max() / abs(x0)),
             late_max_over_initial=float(np.abs(x[late]).max() / abs(x0)) if late.any() else None,
             other_axes_max=float(max(np.abs(a[:, [2, 3]]).max(), np.abs(wrap(a[:, [5, 6]])).max())))
    return d


def flight_table(path):
    path = Path(path)
    meta = json.loads(path.with_suffix(".json").read_text())
    n = len(meta["columns"])
    a = np.fromfile(path, dtype="<f8")
    return meta, a[: (len(a) // n) * n].reshape(-1, n)


def fast_metrics(path, ref_path):
    """G7, real aircraft: largest difference in attitude and body rates from the reference at the same times."""
    meta, a = flight_table(path)
    d = dict(kind="fast", model=meta["model"], hz=meta["hz"], error=meta["error"], rows=len(a), finite=bool(np.isfinite(a).all()))
    c = {n: i for i, n in enumerate(meta["columns"])}
    rmeta, ref = flight_table(ref_path)
    d["reference_ok"] = rmeta["error"] is None and bool(np.isfinite(ref).all())
    d["complete"] = len(a) == len(ref)
    if not d["finite"] or not d["reference_ok"] or len(a) < 2:
        return d
    n = min(len(a), len(ref))
    ia = [c[f"attitude/{x}-rad"] for x in ("phi", "theta", "psi")]
    ir = [c[f"velocities/{x}-rad_sec"] for x in "pqr"]
    d.update(max_attitude_error_deg=float(np.degrees(np.abs(wrap(a[:n, ia] - ref[:n, ia]))).max()), max_rate_error_rad_s=float(np.abs(a[:n, ir] - ref[:n, ir]).max()),
             alpha_range_deg=[float(np.degrees(a[:, c["aero/alpha-rad"]]).min()), float(np.degrees(a[:, c["aero/alpha-rad"]]).max())],
             max_rate_rad_s=float(np.abs(a[:, ir]).max()), vc_kts=[float(a[0, c["velocities/vc-kts"]]), float(a[-1, c["velocities/vc-kts"]])])
    return d


def release_metrics(path):
    """G8's synthetic case (reported only): error against the exact answer p = A sin(w t) / w."""
    path = Path(path)
    meta = json.loads(path.with_suffix(".json").read_text())
    n = len(meta["columns"])
    a = np.fromfile(path, dtype="<f8")
    a = a[: (len(a) // n) * n].reshape(-1, n)
    d = dict(kind="release", hz=meta["hz"], error=meta["error"], rows=len(a), finite=bool(np.isfinite(a).all()), contact_steps=meta.get("contact_steps"))
    if not d["finite"] or len(a) < 2:
        return d
    syn = G5["G8"]["synthetic_reported_only"]
    w = 2.0 * math.pi * syn["moment_hz"]
    t = a[:, 0]
    d.update(max_rate_error_rad_s=float(np.abs(a[:, 1] - syn["moment_amplitude"] * np.sin(w * t) / w).max()), final_rate_rad_s=float(a[-1, 1]),
             max_gear_moment_lbsft=meta.get("max_gear_moment"))
    return d


def measure(raw, keep=False):
    """Measure one raw run by its kind; delete the raw rows unless asked to keep them. Fast-flight tables are small
    and are kept: the judge compares them with the reference."""
    raw = Path(raw)
    kind = json.loads(raw.with_suffix(".json").read_text())["kind"]
    if kind == "fast_flight":
        return None
    m = {"landing": lambda: landing_metrics(raw, keep_samples=True), "crash": lambda: crash_metrics(raw),
         "probe": lambda: probe_metrics(raw), "release": lambda: release_metrics(raw)}[kind]()
    m["file"] = raw.stem
    if not keep:
        raw.unlink()
    return m


def measure_dir(d, prefix, tag):
    """For the WebAssembly runner, which only writes raw rows: measure every run whose file starts with prefix."""
    d = Path(d)
    with (d / f"metrics-{tag}.jsonl").open("w") as s:
        for meta in sorted(d.glob(prefix + "*.json")):
            raw = meta.with_suffix(".f64")
            if not raw.exists():
                if json.loads(meta.read_text()).get("kind") == "error":   # the runner recorded an exception
                    s.write(meta.read_text().strip() + "\n")
                continue
            try:
                m = measure(raw, keep=bool(os.environ.get("KEEP_RAW")))
            except Exception as e:  # noqa: BLE001
                m = dict(file=raw.stem, kind="error", error=f"{type(e).__name__}: {e}")
            if m is not None:
                s.write(json.dumps(m) + "\n")


# ---------------------------------------------------------------------------------------------------------
# The judge: limits of gates-05.json applied to the measurements. Every failed condition is named.

REPO = HERE.parents[1]
OUT = REPO / "out/gates05"
PLATFORMS = ("native", "wasm")
CONFIGS = json.loads((HERE / "configs.json").read_text())


def load_metrics(config, hz, platform):
    d = OUT / config / str(hz) / platform
    recs = {}
    for p in sorted(d.glob("metrics-*.jsonl")):
        for line in p.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                recs[r["file"]] = r
    return recs, d


def cases_for(model):
    return G5["G2d"].get("cases_by_aircraft", {}).get(model, G5["G2d"]["cases"])


def nominal_sink(model, case):
    s = G5["landing_cases"][case]["sink_fps"]
    return G5["aircraft"][model]["limit_sink_fps"] if s == "limit" else s


def judge_landing(model, case, m, ref):
    """G2d: the list of failed conditions of one landing (empty = good)."""
    L = G5["G2d"]["limits"]
    ac = G5["aircraft"][model]
    if m is None:
        return ["no measurement"]
    if m.get("kind") == "error" or m.get("error"):
        return [f"did not complete: {m.get('error')}"]
    if not m.get("finite"):
        return ["non-finite values"]
    if not m.get("touched"):
        return ["never touched the ground"]
    bad = []
    nom = nominal_sink(model, case)
    lo, hi = L["touch_sink_fraction_of_nominal"]
    if not lo * nom <= m["touch"]["sink_fps"] <= hi * nom:
        bad.append(f"not the landing described: touched at {m['touch']['sink_fps']:.2f} ft/s, nominal {nom:g}")
    if m["touch"]["u_fps"] < -1.0:
        bad.append("not the landing described: moving backward at the touchdown")
    if m["min_h_agl_ft"] < L["min_cg_height_fraction_of_rest"] * ac["cg_rest_h_agl_ft"]:
        bad.append(f"sank into the ground: centre of gravity {m['min_h_agl_ft']:.2f} ft above it (stands at {ac['cg_rest_h_agl_ft']:.2f})")
    if m["max_abs_phi_deg"] > L["max_abs_bank_deg"]:
        bad.append(f"bank {m['max_abs_phi_deg']:.1f} deg")
    if m["min_theta_deg"] < L["min_pitch_deg"] or m["max_theta_deg"] > m["theta0_deg"] + L["max_pitch_above_approach_deg"]:
        bad.append(f"pitch {m['min_theta_deg']:.1f} to {m['max_theta_deg']:.1f} deg")
    if m["max_abs_psi_deg"] > L["max_abs_heading_deg"]:
        bad.append(f"heading off by {m['max_abs_psi_deg']:.1f} deg")
    if m["structure_contacts"]:
        bad.append("airframe touched the ground: " + ", ".join(m["structure_contacts"]))
    comps = [c for c, b in zip(m["max_compression_ft"], m["bogey"]) if b]
    for j, (c, k) in enumerate(zip(comps, ac["bogey_spring_lbs_ft"])):
        travel = L["max_compression_weights_over_spring"] * ac["weight_lbs"] / k
        if c > travel:
            bad.append(f"wheel {j} compressed {c:.2f} ft (limit {travel:.2f})")
    if m["max_ground_force_weights"] > L["max_ground_force_weights"]:
        bad.append(f"ground force {m['max_ground_force_weights']:.1f} times the weight")
    e = m["energy_ft"]
    if e["closure_max_abs"] > L["max_energy_closure_ft"]:
        bad.append(f"energy not accounted for: {e['closure_max_abs']:.3f} ft")
    if e["ground_work_max"] > L["max_ground_work_ft"]:
        bad.append(f"the ground gave energy: {e['ground_work_max']:.3f} ft")
    settled = m["end"]["all_wheels_down"] and m["last_airborne_after_touch_s"] <= m["t_end_after_touch"] - L["settled_last_seconds"]
    if not settled:
        bad.append("not settled on its wheels at the end")
    if model in G5["G2d"]["converged_aircraft"]:
        if ref is None or ref.get("kind") == "error" or not ref.get("touched") or ref.get("error"):
            bad.append("no valid reference run")
        else:
            tol = L["max_relative_difference_from_reference"]
            for label, a, b in (("ground force", m["max_ground_force_weights"], ref["max_ground_force_weights"]),
                                ("compression", max(comps), max(c for c, bb in zip(ref["max_compression_ft"], ref["bogey"]) if bb))):
                if abs(a - b) > tol * abs(b):
                    bad.append(f"peak {label} {a:.3f} differs from the reference's {b:.3f} by more than {tol:.0%}")
    return bad


def judge_g8(model, case, m, d, ref, dref):
    L = G5["G8"]["limits"]
    if m is None:
        return ["no measurement"], {}
    if m.get("kind") == "error" or m.get("error") or not m.get("finite") or not m.get("touched"):
        return [f"did not complete: {m.get('error')}"], {}
    if ref is None or ref.get("kind") == "error" or ref.get("error") or not ref.get("touched"):
        return ["no valid reference run"], {}
    a, b = np.load(d / (m["file"] + ".samples.npy")), np.load(dref / (ref["file"] + ".samples.npy"))
    n = min(len(a), len(b))
    bad = []
    if abs(len(a) - len(b)) > 2:
        bad.append(f"ran {len(a)} samples, the reference {len(b)}")
    att = np.degrees(np.abs(wrap(a[:n, 1:4] - b[:n, 1:4])))
    rate = np.abs(a[:n, 4:7] - b[:n, 4:7])
    num = dict(max_attitude_error_deg=float(att.max()), end_attitude_error_deg=float(att[-1].max()), end_rate_error_rad_s=float(rate[-1].max()),
               max_rate_error_rad_s=float(rate.max()), contact_episodes=m["contact_episodes"], reference_contact_episodes=ref["contact_episodes"])
    if num["end_attitude_error_deg"] > L["max_end_attitude_error_deg"]:
        bad.append(f"attitude at the end off by {num['end_attitude_error_deg']:.3f} deg")
    if num["end_rate_error_rad_s"] > L["max_end_rate_error_rad_s"]:
        bad.append(f"body rates at the end off by {num['end_rate_error_rad_s']:.4f} rad/s")
    if num["max_attitude_error_deg"] > L["max_attitude_error_deg"]:
        bad.append(f"attitude off by up to {num['max_attitude_error_deg']:.3f} deg")
    need = L["min_contact_episodes"][case]
    if min(m["contact_episodes"], ref["contact_episodes"]) < need:
        bad.append(f"not the case described: {m['contact_episodes']} contact episodes (reference {ref['contact_episodes']}), at least {need} wanted")
    return bad, num


def judge_crash(m):
    L = G5["G3d"]["limits"]
    if m is None:
        return ["no measurement"]
    if m.get("kind") == "error" or m.get("error"):
        return [f"did not complete: {m.get('error')}"]
    if not m.get("finite"):
        return ["non-finite values"]
    bad = []
    if m["max_rate_rad_s"] > L["runaway_rate_rad_s"]:
        bad.append(f"runaway: body rate {m['max_rate_rad_s']:.3g} rad/s")
    if m["max_ground_force_weights"] > L["max_ground_force_weights"]:
        bad.append(f"ground force {m['max_ground_force_weights']:.4g} times the weight")
    if m["ground_work_max_ft"] > L["max_ground_work_ft"]:
        bad.append(f"the ground gave energy: {m['ground_work_max_ft']:.4g} ft")
    return bad


def judge_probe(m):
    L = G5["G7"]["limits"]
    if m is None:
        return ["no measurement"]
    if m.get("kind") == "error" or m.get("error") or not m.get("finite") or not m.get("complete"):
        return [f"did not complete: {m.get('error')}"]
    bad = []
    if m["peak_over_initial"] > L["max_peak_over_initial"]:
        bad.append(f"grew to {m['peak_over_initial']:.3g} times its start")
    if m["late_max_over_initial"] is None or m["late_max_over_initial"] > L["settled_fraction"]:
        bad.append(f"did not die away: still {m['late_max_over_initial']:.3g} of its start after {L['settled_after_time_constants']:g} time constants")
    if G5["G7"]["probe_cases"][m["case"]]["kind"] == "spring" and m["max_error_over_initial"] > L["max_spring_error_over_initial"]:
        bad.append(f"off by {m['max_error_over_initial']:.1%} of its start")
    return bad


def judge_fast(m):
    L = G5["G7"]["limits"]
    if m.get("error") or not m.get("finite") or not m.get("complete"):
        return [f"did not complete: {m.get('error')}"]
    if not m.get("reference_ok"):
        return ["no valid reference run"]
    bad = []
    if m["max_attitude_error_deg"] > L["max_flight_attitude_error_deg"]:
        bad.append(f"attitude off by {m['max_attitude_error_deg']:.3f} deg")
    if m["max_rate_error_rad_s"] > L["max_flight_rate_error_rad_s"]:
        bad.append(f"body rates off by {m['max_rate_error_rad_s']:.4f} rad/s")
    return bad


def judge(config):
    """All four gates, per step rate and platform. Returns a nested dict (also written as summary.json)."""
    cfg = CONFIGS[config]
    ref_hz = G5["reference"]["hz"]
    res = dict(config=config, properties=cfg["properties"], source=cfg["source"], rates={})
    for hz in cfg["rates_05"]:
        per = {}
        for pf in PLATFORMS:
            M, d = load_metrics(config, hz, pf)
            RG, dref = load_metrics(cfg["ref_ground"], ref_hz, pf)
            g = {}
            # G2d
            rows = []
            for model in G5["G2d"]["aircraft"]:
                for case in cases_for(model):
                    f = f"landing-{model}-{case}"
                    bad = judge_landing(model, case, M.get(f), RG.get(f))
                    rows.append(dict(model=model, case=case, bad=bad, m=M.get(f)))
            g["G2d"] = dict(passed=all(not r["bad"] for r in rows), rows=rows)
            # G8
            rows = []
            for model in G5["G8"]["aircraft"]:
                for case in G5["G8"]["cases"]:
                    f = f"g8-{model}-{case}"
                    bad, num = judge_g8(model, case, M.get(f), d, RG.get(f), dref)
                    rows.append(dict(model=model, case=case, bad=bad, num=num))
            g["G8"] = dict(passed=all(not r["bad"] for r in rows), rows=rows, synthetic=M.get("g8-release"))
            # G3d
            rows = []
            for model in G5["G3d"]["aircraft"]:
                for sc in G5["G3d"]["scenarios"]:
                    runs = [M.get(f"crash-{model}-{sc}-{k}") for k in range(len(G5["G3d"]["draws"]))]
                    bads = [judge_crash(m) for m in runs]
                    rows.append(dict(model=model, scenario=sc, failed_runs=sum(1 for b in bads if b), runs=len(runs),
                                     bad=sorted({x.split(":")[0].split(" ")[0] + " " + " ".join(x.split(" ")[1:3]) for b in bads for x in b}), first_bad=next((b for b in bads if b), []),
                                     max_force=max((m.get("max_ground_force_weights", float("nan")) for m in runs if m), default=float("nan")),
                                     max_ground_work=max((m.get("ground_work_max_ft", float("nan")) for m in runs if m), default=float("nan")),
                                     max_rate=max((m.get("max_rate_rad_s", float("nan")) for m in runs if m), default=float("nan")),
                                     min_h=min((m.get("min_h_agl_ft", float("nan")) for m in runs if m), default=float("nan")),
                                     max_h=max((m.get("max_h_agl_ft", float("nan")) for m in runs if m), default=float("nan"))))
            g["G3d"] = dict(passed=all(r["failed_runs"] == 0 for r in rows), rows=rows)
            # G7
            rows = []
            for c in G5["G7"]["probe_cases"]:
                for where in G5["G7"]["where"]:
                    m = M.get(f"probe-{c}-{where}")
                    rows.append(dict(what=f"{c}, {where}", bad=judge_probe(m), m=m))
            for model in G5["G7"]["fast_points"]:
                raw, rref = d / f"fast-{model}.f64", OUT / cfg["ref_flight"] / str(ref_hz) / pf / f"fast-{model}.f64"
                if raw.exists() and rref.exists():
                    m = fast_metrics(raw, rref)
                    bad = judge_fast(m)
                else:
                    m, bad = None, ["no measurement" if not raw.exists() else "no reference run"]
                rows.append(dict(what=f"{model} at its fastest", bad=bad, m=m))
            g["G7"] = dict(passed=all(not r["bad"] for r in rows), rows=rows)
            per[pf] = g
        res["rates"][str(hz)] = per
    return res


def fmt(x, spec=".3g"):
    return "n/a" if x is None or (isinstance(x, float) and x != x) else format(x, spec)


def report(res):
    out = []
    w = out.append
    cfg = CONFIGS[res["config"]]
    w(f"# Session 05 gates (GATES-05.md): {res['config']}")
    w(f"{cfg['role']}")
    w(f"Properties: {json.dumps(res['properties'])}. Source: {res['source']}. References: {cfg['ref_ground']} (ground), {cfg['ref_flight']} (flight), at {G5['reference']['hz']} Hz.")
    for hz in res["rates"]:
        for pf in PLATFORMS:
            ip = OUT / res["config"] / hz / pf / "info.json"
            if ip.exists():
                i = json.loads(ip.read_text())
                w(f"- {hz} Hz, {pf}: " + (i.get("build") or f"native JSBSim module sha256 {str(i.get('module_sha256'))[:16]} [{i.get('key')}]") +
                  ("" if i.get("build") else " patches: " + (", ".join(f"{p['file']} {p['sha256'][:12]}" for p in i.get("patches", [])) or "none")))
    w("")
    w("## Verdict per step rate (a gate passes only if it passes on both platforms)")
    w("| step rate | G2d Landing | G8 Repeated contact | G3d Crash containment | G7 Forced flight | all four |")
    w("|---|---|---|---|---|---|")
    for hz, per in res["rates"].items():
        cells, ok_all = [], True
        for gname in ("G2d", "G8", "G3d", "G7"):
            parts = []
            for pf in PLATFORMS:
                rows = per[pf][gname]["rows"]
                nbad = sum(1 for r in rows if (r.get("bad") or r.get("failed_runs")))
                parts.append(f"{len(rows) - nbad}/{len(rows)}")
            ok = all(per[pf][gname]["passed"] for pf in PLATFORMS)
            ok_all = ok_all and ok
            cells.append(("pass " if ok else "**FAIL** ") + " / ".join(parts))
        w(f"| {hz} Hz | " + " | ".join(cells) + f" | {'pass' if ok_all else '**FAIL**'} |")
    w("")
    w("Cells: cases good, native / WebAssembly.")
    for hz, per in res["rates"].items():
        w("")
        w(f"## {hz} Hz")
        w("")
        w("### G2d Landing")
        w("| aircraft | case | platform | touchdown: sink ft/s, pitch, bank deg, kt | lowest CG ft | largest bank deg | ground force / weight | largest compression ft | energy closure ft | ground work max ft | airborne again until s | verdict |")
        w("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for pf in PLATFORMS:
            for r in per[pf]["G2d"]["rows"]:
                m = r["m"]
                if m and m.get("touched") and m.get("finite"):
                    t, e = m["touch"], m["energy_ft"]
                    w(f"| {r['model']} | {r['case']} | {pf} | {t['sink_fps']:.2f}, {t['theta_deg']:.1f}, {t['phi_deg']:.1f}, {t['vc_kts']:.0f} | {m['min_h_agl_ft']:.2f} | {m['max_abs_phi_deg']:.1f} | "
                      f"{m['max_ground_force_weights']:.2f} | {max(m['max_compression_ft']):.2f} | {e['closure_max_abs']:.4f} | {e['ground_work_max']:.4f} | {m['last_airborne_after_touch_s']:.2f} | "
                      + ("good" if not r["bad"] else "**BAD**: " + "; ".join(r["bad"])) + " |")
                else:
                    w(f"| {r['model']} | {r['case']} | {pf} | | | | | | | | | **BAD**: " + "; ".join(r["bad"]) + " |")
        w("")
        w("### G8 Repeated contact (against the reference at the same times)")
        w("| aircraft | case | platform | contact episodes (reference) | attitude error: largest, at the end, deg | rate error at the end rad/s | largest rate error rad/s (not judged) | verdict |")
        w("|---|---|---|---|---|---|---|---|")
        for pf in PLATFORMS:
            for r in per[pf]["G8"]["rows"]:
                n = r["num"]
                if n:
                    w(f"| {r['model']} | {r['case']} | {pf} | {n['contact_episodes']} ({n['reference_contact_episodes']}) | {n['max_attitude_error_deg']:.4f}, {n['end_attitude_error_deg']:.4f} | "
                      f"{n['end_rate_error_rad_s']:.5f} | {n['max_rate_error_rad_s']:.4f} | " + ("good" if not r["bad"] else "**BAD**: " + "; ".join(r["bad"])) + " |")
                else:
                    w(f"| {r['model']} | {r['case']} | {pf} | | | | | **BAD**: " + "; ".join(r["bad"]) + " |")
        for pf in PLATFORMS:
            s = per[pf]["G8"]["synthetic"]
            if s:
                w(f"- Synthetic case of the review, {pf} (reported, not judged): largest body-rate error {fmt(s.get('max_rate_error_rad_s'))} rad/s, rate at the end {fmt(s.get('final_rate_rad_s'))} rad/s "
                  f"(exact: 0), {s.get('contact_steps')} contact steps, error: {s.get('error')}.")
        w("")
        w("### G3d Crash containment (5 runs per case)")
        w("| aircraft | case | platform | failed runs | largest ground force / weight | largest energy from the ground ft | largest body rate rad/s | height range of the CG ft | verdict |")
        w("|---|---|---|---|---|---|---|---|---|")
        for pf in PLATFORMS:
            for r in per[pf]["G3d"]["rows"]:
                w(f"| {r['model']} | {r['scenario']} | {pf} | {r['failed_runs']}/{r['runs']} | {fmt(r['max_force'], '.4g')} | {fmt(r['max_ground_work'], '.4g')} | {fmt(r['max_rate'], '.3g')} | "
                  f"{fmt(r['min_h'], '.4g')} to {fmt(r['max_h'], '.4g')} | " + ("contained" if not r["failed_runs"] else "**FAILS**: " + "; ".join(r["first_bad"])) + " |")
        w("")
        w("### G7 Forced flight")
        w("| what | platform | peak / start | error / start | left after 10 time constants | attitude error deg | rate error rad/s | verdict |")
        w("|---|---|---|---|---|---|---|---|")
        for pf in PLATFORMS:
            for r in per[pf]["G7"]["rows"]:
                m = r["m"] or {}
                w(f"| {r['what']} | {pf} | {fmt(m.get('peak_over_initial'))} | {fmt(m.get('max_error_over_initial'))} | {fmt(m.get('late_max_over_initial'))} | "
                  f"{fmt(m.get('max_attitude_error_deg'))} | {fmt(m.get('max_rate_error_rad_s'))} | " + ("good" if not r["bad"] else "**BAD**: " + "; ".join(r["bad"])) + " |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    if sys.argv[1] == "measure":
        measure_dir(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        res = judge(sys.argv[1])
        (OUT / sys.argv[1]).mkdir(parents=True, exist_ok=True)
        (OUT / sys.argv[1] / "summary.json").write_text(json.dumps(res, default=float))
        sys.stdout.write(report(res))
