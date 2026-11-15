"""Test of REPORT-03 ledger 15: "the gear's spring-damper is too stiff for the integrator's stability limit".
(Diagnostic, not a gate. Native JSBSim, patched build: PYTHONPATH=build/native/patched.)

usage: python tests/gates/diag/gear_damper.py modes            the linear model's prediction for all five aircraft
       python tests/gates/diag/gear_damper.py sweep            predicted against measured critical damping (at rest)
       python tests/gates/diag/gear_damper.py landing          hard landings against the damping scale

The linear model (it does not use JSBSim's integrators or gear code, only the aircraft's numbers):
  - The aircraft stands on its gear. Small motions in heave z, pitch and roll about the centre of gravity.
  - Every contact point that carries weight at rest is a vertical spring k and damper c (the rebound damper
    where the file gives one, since it is the stiffer of the two).
  - The equations are stepped the way FGPropagate steps them: vertical velocity by AB2, height by AB3 of the
    velocity, body rates by the scheme under test (Euler, AB2, AB3, AB4), attitude by Buss 2, which for small
    angles is angle += dt*rate + dt^2/2*rate derivative.
  - The scheme is unstable when the largest eigenvalue of that step map is larger than 1 in magnitude.
What it leaves out: friction (so the wheels' grip on the ground does not hold the aircraft sideways), the tilt
of the gear legs, aerodynamics, and everything non-linear (lift-off, the clamp on the compression speed).
"""
import json
import math
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_native as R  # noqa: E402  (frozen gate runner: set-up helpers only)

native = R.native
G = R.G
G4 = json.loads((HERE.parent / "gates-04.json").read_text())
DATA = native.DATA
SCHEMES = {"Euler": (1, [1.0]), "AB2": (3, [1.5, -0.5]), "AB3": (4, [23 / 12, -16 / 12, 5 / 12]), "AB4": (5, [55 / 24, -59 / 24, 37 / 24, -9 / 24])}
# Known stability limits on the negative real axis (|lambda|*dt), textbook values, for the reader's orientation.
REAL_AXIS_LIMIT = {"Euler": 2.0, "AB2": 1.0, "AB3": 6 / 11, "AB4": 0.3}
FT = {"IN": 1 / 12.0, "FT": 1.0, "M": 3.280839895}


def contacts(model):
    root = ET.parse(DATA / f"aircraft/{model}/{model}.xml").getroot()
    out = []
    for c in root.find("ground_reactions").findall("contact"):
        loc = c.find("location")
        u = FT[loc.get("unit", "IN").upper()]

        def num(tag):
            el = c.find(tag)
            if el is None:
                return None
            unit = (el.get("unit") or "").upper()
            if unit not in ("LBS/FT", "LBS/FT/SEC", ""):
                raise RuntimeError(f"{model}: unit {unit} not handled")
            if el.get("type"):
                raise RuntimeError(f"{model}: damping type {el.get('type')} not handled (linear only)")
            return float(el.text)

        k, c1, c2 = num("spring_coeff"), num("damping_coeff"), num("damping_coeff_rebound")
        out.append(dict(name=c.get("name"), type=c.get("type"), x=float(loc.find("x").text) * u, y=float(loc.find("y").text) * u,
                        z=float(loc.find("z").text) * u, k=k, c=c1 or 0.0, c_rebound=c2 if c2 is not None else (c1 or 0.0),
                        function=c.find("strut_force") is not None))
    for c in out:
        if c["k"] is None:
            # c172x: the right main gear's force is given as a <strut_force> function that the file says is "exactly
            # equivalent to the definition of the left main gear". Use the mirrored point's numbers.
            twin = [d for d in out if d["k"] is not None and d["x"] == c["x"] and d["y"] == -c["y"] and d["z"] == c["z"]]
            if not (c["function"] and len(twin) == 1):
                raise RuntimeError(f"{model}: contact {c['name']} has no spring coefficient and no mirrored twin")
            c.update(k=twin[0]["k"], c=twin[0]["c"], c_rebound=twin[0]["c_rebound"])
    return out


def rest_state(model, root=None):
    """Mass, inertia, centre of gravity and which contact points carry weight, read from JSBSim standing at rest."""
    f = native.new_fdm(root, dt=1 / 1000)
    f.load_model(model)
    f.load_ic(G["aircraft"][model], True)
    f.run_ic()
    for _ in range(20000):
        f.run()
    n = int(f["gear/num-units"])
    pm = f.get_property_manager()
    wow = []
    for k in range(n):
        p = f"gear/unit[{k}]/WOW" if pm.hasNode(f"gear/unit[{k}]/WOW") else f"contact/unit[{k}]/WOW"
        wow.append(f[p] > 0.5)
    return dict(mass=f["inertia/mass-slugs"], ixx=f["inertia/ixx-slugs_ft2"], iyy=f["inertia/iyy-slugs_ft2"],
                cg=[f["inertia/cg-x-in"] / 12, f["inertia/cg-y-in"] / 12, f["inertia/cg-z-in"] / 12], wow=wow,
                theta_deg=f["attitude/theta-deg"], h_agl=f["position/h-agl-ft"])


def matrices(model, scale=1.0, st=None):
    st = st or rest_state(model)
    M = np.diag([st["mass"], st["iyy"], st["ixx"]])
    K = np.zeros((3, 3))
    C = np.zeros((3, 3))
    used = []
    for c, w in zip(contacts(model), st["wow"]):
        if not w:
            continue
        xb = -(c["x"] - st["cg"][0])   # body x (forward) of the point, ft
        yb = c["y"] - st["cg"][1]      # body y (right)
        a = np.array([1.0, -xb, yb])   # downward movement of the point per unit (heave down, pitch up, roll right)
        K += c["k"] * np.outer(a, a)
        C += scale * max(c["c"], c["c_rebound"]) * np.outer(a, a)
        used.append(c["name"])
    return M, K, C, used


def step_matrix(M, K, C, dt, weights):
    """One step of FGPropagate's scheme on the linear model, as a matrix on the stacked state."""
    Minv = np.linalg.inv(M)
    nr = len(weights) - 1          # past rotational derivatives kept
    # state: q(3) = z, theta, phi; v(3) = w, qrate, prate; w(n-1), w(n-2); az(n-1); past angular accelerations (2 each)
    n = 6 + 2 + 1 + 2 * nr

    def step(s):
        q, v = s[0:3], s[3:6]
        w1, w2, az1 = s[6], s[7], s[8]
        past = s[9:].reshape(nr, 2) if nr else np.zeros((0, 2))
        a = Minv @ (-K @ q - C @ v)
        qn, vn = q.copy(), v.copy()
        qn[0] = q[0] + dt * (23 * v[0] - 16 * w1 + 5 * w2) / 12          # height: AB3 of the velocity
        qn[1:] = q[1:] + dt * v[1:] + 0.5 * dt * dt * a[1:]               # attitude: Buss 2, small angles
        vn[0] = v[0] + dt * (1.5 * a[0] - 0.5 * az1)                      # vertical velocity: AB2
        acc = weights[0] * a[1:]
        for j in range(nr):
            acc = acc + weights[j + 1] * past[j]
        vn[1:] = v[1:] + dt * acc                                         # body rates: the scheme under test
        newpast = np.vstack([a[1:], past[:-1]]) if nr else past
        return np.concatenate([qn, vn, [v[0], w1, a[0]], newpast.ravel()])

    A = np.zeros((n, n))
    for i in range(n):
        e = np.zeros(n)
        e[i] = 1.0
        A[:, i] = step(e)
    return A


def radius(M, K, C, hz, scheme):
    return float(np.max(np.abs(np.linalg.eigvals(step_matrix(M, K, C, 1.0 / hz, SCHEMES[scheme][1])))))


def stable_window(model, hz, scheme, st):
    """(smallest, largest) damping scale between which the linear model is stable, searched around the aircraft's
    own damping (scale 1) over 0.01 to 100. Too little damping is unstable too (an explicit scheme on a springy
    mode); the claim under test is about the upper end. Returns None if scale 1 itself is unstable and so is
    everything near it."""
    def stable(s):
        M, K, C, _ = matrices(model, s, st)
        return radius(M, K, C, hz, scheme) <= 1.0 + 1e-9
    grid = [10 ** (k / 40.0) for k in range(-80, 81)]
    ok = [stable(s) for s in grid]
    if not any(ok):
        return None
    i1 = min((i for i in range(len(grid)) if ok[i]), key=lambda i: abs(math.log(grid[i])))  # stable point nearest to 1
    lo = hi = i1
    while lo > 0 and ok[lo - 1]:
        lo -= 1
    while hi < len(grid) - 1 and ok[hi + 1]:
        hi += 1

    def edge(a, b):  # a stable, b unstable
        for _ in range(50):
            mid = math.sqrt(a * b)
            a, b = (mid, b) if stable(mid) else (a, mid)
        return a
    s_min = 0.0 if lo == 0 else edge(grid[lo], grid[lo - 1])
    s_max = math.inf if hi == len(grid) - 1 else edge(grid[hi], grid[hi + 1])
    return s_min, s_max


def critical_scale(model, hz, scheme, st):
    """Largest damping scale the linear model tolerates (None: no limit below 100, or no stable window)."""
    w = stable_window(model, hz, scheme, st)
    return None if w is None or math.isinf(w[1]) else w[1]


def modes():
    print("# Linear model of the aircraft standing on its gear (tests/gates/diag/gear_damper.py modes)")
    print()
    print("Fastest decay rate = the most negative real eigenvalue of the standing aircraft's heave, pitch and roll motion.")
    print("A scheme is unstable roughly when (fastest decay rate) x dt exceeds its limit: Euler 2.0, AB2 1.0, AB3 0.545, AB4 0.3.")
    print("The table uses the full step map (see the file header), not that rule of thumb.")
    print()
    print("| aircraft | points carrying weight | fastest decay rate, 1/s | its motion | x dt at 120 / 240 / 480 / 1000 Hz | predicted unstable at rest (body-rate scheme: step rates) | largest damping the scheme tolerates, as a multiple of the aircraft's own (120 / 240 / 480 / 1000 Hz) |")
    print("|---|---|---|---|---|---|---|")
    out = {}
    for model in G["aircraft"]:
        st = rest_state(model)
        M, K, C, used = matrices(model, 1.0, st)
        A = np.block([[np.zeros((3, 3)), np.eye(3)], [-np.linalg.inv(M) @ K, -np.linalg.inv(M) @ C]])
        lam, vec = np.linalg.eig(A)
        i = int(np.argmax(np.abs(lam)))
        shape = np.abs(vec[3:, i] * np.sqrt(np.diag(M)))
        which = ["heave", "pitch", "roll"][int(np.argmax(shape))]
        bad = []
        crit = []
        for name in SCHEMES:
            wins = [stable_window(model, hz, name, st) for hz in G["rates_hz"]]
            rates = [hz for hz, w in zip(G["rates_hz"], wins) if w is None or not (w[0] <= 1.0 <= w[1])]
            if rates:
                bad.append(f"{name}: {', '.join(str(r) for r in rates)} Hz")
            crit.append(f"{name} " + " / ".join("none" if w is None else ("no limit" if math.isinf(w[1]) else f"{w[1]:.2f}") for w in wins))
        out[model] = dict(lam=float(abs(lam[i])), unstable=bad)
        print(f"| {model} | {', '.join(used)} | {abs(lam[i]):.1f}{'' if abs(lam[i].imag) < 1e-9 else ' (oscillating)'} | {which} | " + " / ".join(f"{abs(lam[i]) / hz:.3f}" for hz in G["rates_hz"])
              + f" | {'; '.join(bad) or 'none'} | {'; '.join(crit)} |")
    return out


def scaled_root(model, scale):
    """A JSBSim data root whose copy of the aircraft has every ground-contact damper multiplied by `scale`."""
    root = Path(tempfile.mkdtemp(prefix="fdm-damper-"))
    for d in ("engine", "systems"):
        os.symlink(DATA / d, root / d)
    (root / "aircraft").mkdir()
    shutil.copytree(DATA / f"aircraft/{model}", root / f"aircraft/{model}")
    path = root / f"aircraft/{model}/{model}.xml"
    tree = ET.parse(path)
    for c in tree.getroot().find("ground_reactions").findall("contact"):
        for tag in ("damping_coeff", "damping_coeff_rebound"):
            el = c.find(tag)
            if el is not None:
                el.text = repr(float(el.text) * scale)
    tree.write(path)
    return root


def rest_rate(model, hz, scheme_id, scale, seconds=40.0, tail=5.0):
    """Largest body rate in the last `tail` seconds standing at rest, candidate 1 (friction-aware) with the scheme."""
    root = scaled_root(model, scale)
    try:
        f = native.new_fdm(root, dt=1.0 / hz)
        f.load_model(model)
        f.load_ic(G["aircraft"][model], True)
        f["simulation/integrator/rate/rotational"] = scheme_id
        f["simulation/integrator/position/rotational"] = 7
        f["simulation/integrator/friction-aware"] = 1
        f.run_ic()
        get = R.getters(f, G["body_rates"])
        steps, t0 = round(seconds * hz), round((seconds - tail) * hz)
        worst = 0.0
        for k in range(steps):
            f.run()
            v = [g() for g in get]
            if not all(math.isfinite(x) for x in v):
                return math.inf
            if k >= t0:
                worst = max(worst, max(abs(x) for x in v))
        return worst
    finally:
        shutil.rmtree(root, ignore_errors=True)


def measured_critical(model, hz, scheme_id, guess):
    """Bisect the damping scale between settled (< 1e-6 rad/s, G1's limit) and not settled."""
    lo, hi = guess / 2.5, guess * 2.5
    if rest_rate(model, hz, scheme_id, lo) >= 1e-6:
        return None, f"already unsettled at {lo:.3f}"
    if rest_rate(model, hz, scheme_id, hi) < 1e-6:
        return None, f"still settled at {hi:.3f}"
    for _ in range(9):
        mid = math.sqrt(lo * hi)
        if rest_rate(model, hz, scheme_id, mid) >= 1e-6:
            hi = mid
        else:
            lo = mid
    return math.sqrt(lo * hi), f"between {lo:.3f} and {hi:.3f}"


def sweep(cases=None):
    print("# Predicted against measured: how much gear damping each body-rate scheme tolerates at rest")
    print()
    print(f"Native JSBSim: {native.describe()}")
    print("Measured: every ground-contact damper of the aircraft is multiplied by a scale; 40 s standing at rest with candidate 1")
    print("(friction-aware) and Buss 2; 'settled' means all body rates below 1e-6 rad/s in the last 5 s (G1's limit). The scale")
    print("is bisected. Predicted: the linear model in this file, which shares no code with JSBSim.")
    print()
    print("| aircraft | step rate | body-rate scheme | predicted critical scale | measured critical scale | measured / predicted |")
    print("|---|---|---|---|---|---|")
    cases = cases or [("c310", 120, "AB4"), ("c310", 120, "AB3"), ("c310", 120, "AB2"), ("c310", 120, "Euler"),
                      ("c310", 240, "AB4"), ("c310", 240, "AB3"), ("c310", 480, "AB4"),
                      ("c172x", 120, "AB4"), ("f16", 120, "AB4"), ("ah1s", 120, "AB4"), ("737", 120, "AB4")]
    states = {}
    for model, hz, scheme in cases:
        st = states.setdefault(model, rest_state(model))
        pred = critical_scale(model, hz, scheme, st)
        if pred is None:
            print(f"| {model} | {hz} Hz | {scheme} | stable at any scale | not measured | - |")
            continue
        meas, note = measured_critical(model, hz, SCHEMES[scheme][0], pred)
        print(f"| {model} | {hz} Hz | {scheme} | {pred:.3f} | {'-' if meas is None else f'{meas:.3f}'} ({note}) | {'-' if meas is None else f'{meas / pred:.2f}'} |", flush=True)


def landing_ok(model, hz, props, scale, run, root):
    """One G2c forward hard landing (same set-up and checks as run_native_04.repeat_trial) on a scaled-damper aircraft."""
    sc = json.loads((HERE.parent / "gates-04b.json").read_text())["G2c"]["scenario_definition"]
    ic = dict(sc["ic"])
    for p, d in zip(G4["repeats"]["perturbed_properties"], G4["repeats"]["draws"][run]):
        ic[p] = ic[p] + d
    f = native.new_fdm(root, dt=1.0 / hz)
    f.load_model(model)
    f.load_ic(G["aircraft"][model], True)
    for p, v in ic.items():
        f[p] = v
    for p, v in props.items():
        f[p] = v
    f.run_ic()
    get = R.getters(f, G["state"])
    ir = [G["state"].index(p) for p in G["body_rates"]]
    for _ in range(round(sc["seconds"] * hz)):
        f.run()
        v = [g() for g in get]
        if not math.isfinite(sum(v)) or max(abs(v[j]) for j in ir) > G["runaway_rate_rad_s"]:
            return False
    return True


def landing():
    runs = 11
    scales = [0.125, 0.25, 0.5, 1.0, 2.0, 4.0]
    configs = {"Euler rates, no friction patch (the floor)": {"simulation/integrator/rate/rotational": 1, "simulation/integrator/position/rotational": 7},
               "AB3 rates, friction-aware (candidate 1)": {"simulation/integrator/rate/rotational": 4, "simulation/integrator/position/rotational": 7, "simulation/integrator/friction-aware": 1}}
    print("# Hard landings against the gear damping scale")
    print()
    print(f"Native JSBSim: {native.describe()}")
    print(f"G2c's forward hard landing, runs 0 to {runs - 1} of gates-04.json, on copies of the aircraft whose ground-contact dampers are")
    print("multiplied by a scale. Each cell: runs that stay finite and without runaway, of %d." % runs)
    print("If stiff dampers were the cause of the failures, softer dampers (scale < 1) would cure them and stiffer ones")
    print("would make them worse, and the scale that fails would move in proportion to the step rate.")
    for label, props in configs.items():
        print()
        print(f"## {label}")
        print()
        print("| aircraft | step rate | " + " | ".join(f"x{s:g}" for s in scales) + " |")
        print("|---|---|" + "---|" * len(scales))
        for model in ("737", "ah1s", "c310"):
            for hz in (120, 240, 480, 1000):
                cells = []
                for s in scales:
                    root = scaled_root(model, s)
                    try:
                        cells.append(str(sum(landing_ok(model, hz, props, s, r, root) for r in range(runs))))
                    finally:
                        shutil.rmtree(root, ignore_errors=True)
                print(f"| {model} | {hz} Hz | " + " | ".join(cells) + " |", flush=True)


if __name__ == "__main__":
    {"modes": modes, "sweep": sweep, "landing": landing}[sys.argv[1]]()
