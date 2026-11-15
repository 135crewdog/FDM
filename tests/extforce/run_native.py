"""Test 2 in native JSBSim (Python). Same modes as run_wasm.ts."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pylib"))
import native
from schedule import force_at, SUFFIX

PROPS = ["simulation/sim-time-sec", "position/h-sl-ft", "velocities/vtrue-kts",
         "aero/alpha-rad", "aero/beta-rad", "attitude/phi-rad", "attitude/theta-rad",
         "attitude/psi-rad", "velocities/p-rad_sec", "velocities/q-rad_sec", "velocities/r-rad_sec",
         "position/h-agl-ft", "gear/wow",
         "forces/fbx-external-lbs", "forces/fby-external-lbs", "forces/fbz-external-lbs",
         "moments/l-external-lbsft", "moments/m-external-lbsft", "moments/n-external-lbsft"]

def setup(script):
    fdm = native.new_fdm()
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
    # Same workload as run_wasm.ts bench: every repetition is a fresh load, the same warm-up and the same
    # timed steps with the same schedule. "No external forces" really has none (c172p_ext0).
    STEPS, WARMUP, REPS = 6000, 600, 5
    cases = [("c172p, no external forces", "scripts/ext_c172p_ext0.xml", False),
             ("c172p + 20 forces, not updated", "scripts/ext_c172p_ext20.xml", False),
             ("c172p + 20 forces, 7 props each set every step", "scripts/ext_c172p_ext20.xml", True)]
    print(f"workload per repetition: fresh load, {WARMUP} warm-up steps, then {STEPS} timed steps; {REPS} repetitions ({native.describe()})")
    for label, script, update in cases:
        names = [[f"external_reactions/f{i}/{s}" for s in SUFFIX] for i in range(20)]
        times = []
        for _ in range(REPS):
            fdm = setup(script)
            def step(k):
                if update:
                    for i in range(20):
                        v = force_at(i, k); v[6] *= 0.1
                        for j in range(7):
                            fdm[names[i][j]] = v[j]
                fdm.run()
            for k in range(WARMUP):
                step(k)
            t0 = time.perf_counter()
            for k in range(WARMUP, WARMUP + STEPS):
                step(k)
            times.append((time.perf_counter() - t0) * 1e6 / STEPS)
        times.sort()
        print(f"{label:50s} median {times[len(times) // 2]:.2f} us/step, min {times[0]:.2f}, max {times[-1]:.2f} (native, includes Python call overhead)")

if __name__ == "__main__":
    if sys.argv[1] == "parity":
        parity(os.path.abspath(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "")
    else:
        bench()
