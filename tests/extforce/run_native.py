"""Test 2 in native JSBSim (Python). Same modes as run_wasm.ts."""
import os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jsbsim
from schedule import force_at, SUFFIX

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "jsbsim-data")
PROPS = ["simulation/sim-time-sec", "position/h-sl-ft", "velocities/vtrue-kts",
         "aero/alpha-rad", "aero/beta-rad", "attitude/phi-rad", "attitude/theta-rad",
         "attitude/psi-rad", "velocities/p-rad_sec", "velocities/q-rad_sec", "velocities/r-rad_sec",
         "forces/fbx-external-lbs", "forces/fby-external-lbs", "forces/fbz-external-lbs",
         "moments/l-external-lbsft", "moments/m-external-lbsft", "moments/n-external-lbsft"]

def setup(script):
    fdm = jsbsim.FGFDMExec(ROOT)
    fdm.set_debug_level(0)
    fdm.load_script(script)
    fdm.run_ic()
    return fdm

def parity(out, variant):
    out = os.path.abspath(out)
    fdm = setup("scripts/ext_c172p_ext1.xml")
    names = [f"external_reactions/f0/{s}" for s in SUFFIX]
    rows = [[fdm[p] for p in PROPS]]
    for k in range(3600):
        v = force_at(0, k)
        if variant == "zero":
            v[6] = 0
        for j in range(7):
            fdm[names[j]] = v[j]
        fdm.run()
        rows.append([fdm[p] for p in PROPS])
    with open(out, "w") as f:
        f.write(",".join(PROPS) + "\n")
        for r in rows:
            f.write(",".join(repr(float(x)) for x in r) + "\n")

def bench():
    STEPS, REPS = 6000, 5
    cases = [("c172p, no external forces", "scripts/ext_c172p_ext1.xml", False),
             ("c172p + 20 forces, not updated", "scripts/ext_c172p_ext20.xml", False),
             ("c172p + 20 forces, 7 props each set every step", "scripts/ext_c172p_ext20.xml", True)]
    for label, script, update in cases:
        fdm = setup(script)
        names = [[f"external_reactions/f{i}/{s}" for s in SUFFIX] for i in range(20)]
        best, k = float("inf"), 0
        for _ in range(REPS):
            t0 = time.perf_counter()
            for _ in range(STEPS):
                if update:
                    for i in range(20):
                        v = force_at(i, k); v[6] *= 0.1
                        for j in range(7):
                            fdm[names[i][j]] = v[j]
                fdm.run(); k += 1
            best = min(best, (time.perf_counter() - t0) * 1e6 / STEPS)
        print(f"{label:50s} {best:.2f} us/step (best of {REPS} x {STEPS}, native, includes Python call overhead)")

if __name__ == "__main__":
    if sys.argv[1] == "parity":
        out = os.path.abspath(sys.argv[2])
        os.chdir(tempfile.mkdtemp())
        parity(out, sys.argv[3] if len(sys.argv) > 3 else "")
    else:
        os.chdir(tempfile.mkdtemp())
        bench()
