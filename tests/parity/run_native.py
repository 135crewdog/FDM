"""Run a JSBSim script in native JSBSim (Python package) and log every step.
usage: python tests/parity/run_native.py scripts/c1721.xml out/c1721.native.csv [rateRotationalIntegrator]"""
import os, sys, tempfile, time
import jsbsim

PROPS = ["simulation/sim-time-sec", "position/h-sl-ft", "velocities/vtrue-kts",
         "aero/alpha-rad", "aero/beta-rad", "attitude/phi-rad", "attitude/theta-rad",
         "attitude/psi-rad", "velocities/p-rad_sec", "velocities/q-rad_sec", "velocities/r-rad_sec",
         "position/h-agl-ft", "gear/wow"]
ROOT = os.path.abspath(os.environ.get("JSBSIM_DATA") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "jsbsim-data"))
PERTURB_H = float(os.environ.get("PERTURB_H", "0"))  # ft added to the initial altitude (sensitivity check)

def main(script, out, rate_int=None):
    out = os.path.abspath(out)
    os.chdir(tempfile.mkdtemp())  # scripts may write output files; keep them out of the repo
    fdm = jsbsim.FGFDMExec(ROOT)
    fdm.set_debug_level(0)
    fdm.load_script(script)
    if rate_int:
        fdm["simulation/integrator/rate/rotational"] = float(rate_int)
    if PERTURB_H:
        fdm["ic/h-sl-ft"] = fdm["ic/h-sl-ft"] + PERTURB_H
    fdm.run_ic()
    rows = [[fdm[p] for p in PROPS]]
    t0 = time.perf_counter()
    while fdm.run():
        rows.append([fdm[p] for p in PROPS])
    dt = time.perf_counter() - t0
    print(f"{script}: {len(rows)} rows, {dt * 1e6 / len(rows):.1f} us/step incl. logging (native {jsbsim.__version__})")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(",".join(PROPS) + "\n")
        for r in rows:
            f.write(",".join(repr(float(v)) for v in r) + "\n")

if __name__ == "__main__":
    main(*sys.argv[1:4])
