"""Session 05, for G7: how fast are the fastest aerodynamic moments of the test aircraft? (JSBSim defaults, native.)

For each aircraft and each speed from its approach speed to its fastest speed at sea level, in level flight:
  - the angle of attack is found so that the aircraft neither climbs nor sinks (Newton on wdot);
  - the body rates, the angle of attack and the sideslip angle are each moved a little, and the change of the
    angular accelerations is read from a freshly initialised state (nothing is stepped).
This gives the damping matrix D = d(pdot,qdot,rdot)/d(p,q,r) and the stiffness S = d(pdot,qdot,rdot)/d(alpha,beta).
Reported per point: the damping rates (1/s) on the diagonal of D, the largest |eigenvalue| of D, the pitch and yaw
stiffness as frequencies sqrt(-dqdot/dalpha), sqrt(drdot/dbeta) (rad/s), and the largest |eigenvalue| of the
rotational system [[D, S],[K, 0]] with alpha' = q, beta' = -r (the fast, short-period-like modes; the flight path
is held fixed, which makes them slightly faster than the real ones).
usage: PYTHONPATH=build/native/patched .venv/bin/python tests/gates/envelope05.py   -> results/05-envelope.txt
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pylib"))
import native  # noqa: E402

# knots calibrated at sea level: from the approach speed to the never-exceed or maximum-operating speed
SPEEDS = {"c172x": [55, 80, 110, 140, 160], "c310": [75, 110, 150, 190, 220], "737": [130, 180, 250, 300, 340],
          "f16": [150, 250, 400, 550, 700, 800]}
IC = {"c172x": "reset00", "c310": "reset00", "737": "reset00", "f16": "reset00"}
ACC = ["accelerations/pdot-rad_sec2", "accelerations/qdot-rad_sec2", "accelerations/rdot-rad_sec2"]


def state(model, kts, alpha, beta=0.0, pqr=(0.0, 0.0, 0.0), h=1000.0):
    f = native.new_fdm(dt=1.0 / 480)
    assert f.load_model(model) and f.load_ic(IC[model], True)
    for p, v in {"ic/h-sl-ft": h, "ic/terrain-elevation-ft": 0.0, "ic/vc-kts": kts, "ic/psi-true-deg": 0, "ic/phi-deg": 0, "ic/alpha-deg": alpha, "ic/beta-deg": beta,
                 "ic/gamma-deg": 0, "ic/p-rad_sec": pqr[0], "ic/q-rad_sec": pqr[1], "ic/r-rad_sec": pqr[2],
                 "gear/gear-cmd-norm": 0, "gear/gear-pos-norm": 0}.items():
        f[p] = v
    assert f.run_ic()
    return np.array([f[a] for a in ACC]), f["accelerations/wdot-ft_sec2"], f


def point(model, kts):
    a = 2.0
    for _ in range(20):
        _, w0, _ = state(model, kts, a)
        _, w1, _ = state(model, kts, a + 0.05)
        step = -w0 * 0.05 / (w1 - w0)
        a += max(-3.0, min(3.0, step))
        if abs(step) < 1e-7:
            break
    base, wdot, f = state(model, kts, a)
    dw, da = 0.01, 0.2
    D = np.column_stack([(state(model, kts, a, pqr=tuple(dw if i == j else 0.0 for i in range(3)))[0] - base) / dw for j in range(3)])
    S = np.column_stack([(state(model, kts, a + da)[0] - base) / math.radians(da), (state(model, kts, a, beta=da)[0] - base) / math.radians(da)])
    K = np.array([[0.0, 1.0, 0.0], [0.0, 0.0, -1.0]])
    A = np.block([[D, S], [K, np.zeros((2, 2))]])
    ev = np.linalg.eigvals(A)
    return dict(model=model, kts=kts, alpha_deg=a, wdot=wdot, mach=f["velocities/mach"], qbar_psf=f["aero/qbar-psf"],
                damping_per_s=[-D[0, 0], -D[1, 1], -D[2, 2]], damping_matrix_max_abs_eig=float(np.abs(np.linalg.eigvals(D)).max()),
                pitch_stiffness_rad_s=math.sqrt(max(0.0, -S[1, 0])), yaw_stiffness_rad_s=math.sqrt(max(0.0, S[2, 1])),
                dihedral_pdot_per_beta=S[0, 1], fastest_mode_abs=float(np.abs(ev).max()), fastest_mode_real=float(ev.real.min()),
                eigenvalues=[[float(e.real), float(e.imag)] for e in ev])


if __name__ == "__main__":
    recs = []
    print("# Fastest aerodynamic moments of the test aircraft (JSBSim defaults; see the header of tests/gates/envelope05.py)")
    print(f"# {native.describe()}")
    print("| aircraft | kt | Mach | alpha deg | roll, pitch, yaw damping 1/s | pitch, yaw stiffness rad/s | fastest mode |lambda| 1/s | most negative real part |")
    print("|---|---|---|---|---|---|---|---|")
    for model, speeds in SPEEDS.items():
        for kts in speeds:
            r = point(model, kts)
            recs.append(r)
            print(f"| {model} | {kts} | {r['mach']:.2f} | {r['alpha_deg']:.2f} | {r['damping_per_s'][0]:.2f}, {r['damping_per_s'][1]:.2f}, {r['damping_per_s'][2]:.2f} | "
                  f"{r['pitch_stiffness_rad_s']:.2f}, {r['yaw_stiffness_rad_s']:.2f} | {r['fastest_mode_abs']:.2f} | {r['fastest_mode_real']:.2f} |", flush=True)
    worst = max(recs, key=lambda r: r["fastest_mode_abs"])
    wd = max(recs, key=lambda r: max(r["damping_per_s"]))
    ws = max(recs, key=lambda r: max(r["pitch_stiffness_rad_s"], r["yaw_stiffness_rad_s"]))
    print()
    print(f"Largest damping rate: {max(wd['damping_per_s']):.2f} 1/s ({wd['model']} at {wd['kts']} kt). "
          f"Largest stiffness: {max(ws['pitch_stiffness_rad_s'], ws['yaw_stiffness_rad_s']):.2f} rad/s ({ws['model']} at {ws['kts']} kt). "
          f"Fastest mode: |lambda| = {worst['fastest_mode_abs']:.2f} 1/s ({worst['model']} at {worst['kts']} kt).")
    Path(HERE.parents[1] / "out").mkdir(exist_ok=True)
    (HERE.parents[1] / "out/05-envelope.json").write_text(json.dumps(recs, indent=1))
