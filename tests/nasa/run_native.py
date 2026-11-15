"""NASA check case 02 in native JSBSim (Python), v1.3.3 files unchanged -> out/Atmos_02_native[_rateintN].csv
usage: run_native.py [rateRotationalIntegrator]"""
import json, math, os, sys, tempfile
import jsbsim
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..", "jsbsim-data", "check_cases", "NASA_EOM_2015")
cols = json.load(open(os.path.join(HERE, "columns.json")))
def conv(kind, v):
    return v * (180.0 / math.pi) if kind == "deg" else (math.fmod(v + 180.0, 360.0) - 180 if kind == "yaw" else v)
rate_int = sys.argv[1] if len(sys.argv) > 1 else None
out = os.path.abspath(f"out/Atmos_02_native_rateint{rate_int}.csv" if rate_int else "out/Atmos_02_native.csv")
os.chdir(tempfile.mkdtemp())
fdm = jsbsim.FGFDMExec(ROOT); fdm.set_debug_level(0)
fdm.load_script("scripts/Atmos_02.xml")
if rate_int:
    fdm["simulation/integrator/rate/rotational"] = float(rate_int)
fdm.run_ic()
rows = [",".join(c[0] for c in cols)]
log = lambda: rows.append(",".join(repr(conv(k, fdm[p])) for _, p, k in cols))
log(); k = 0
while fdm.run():
    k += 1
    if k % 10 == 0:
        log()
open(out, "w").write("\n".join(rows) + "\n")
print(f"wrote {out} ({len(rows) - 1} rows)")
