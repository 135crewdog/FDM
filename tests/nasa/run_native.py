"""NASA check case 02 in native JSBSim (Python) -> out/Atmos_02_native.csv"""
import json, math, os, tempfile
import jsbsim
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..", "jsbsim-data", "nasa-run")
cols = json.load(open(os.path.join(HERE, "columns.json")))
def conv(kind, v):
    return v * (180.0 / math.pi) if kind == "deg" else (math.fmod(v + 180.0, 360.0) - 180 if kind == "yaw" else v)
out = os.path.abspath("out/Atmos_02_native.csv")
os.chdir(tempfile.mkdtemp())
fdm = jsbsim.FGFDMExec(ROOT); fdm.set_debug_level(0)
fdm.load_script("scripts/Atmos_02.xml"); fdm.run_ic()
rows = [",".join(c[0] for c in cols)]
log = lambda: rows.append(",".join(repr(conv(k, fdm[p])) for _, p, k in cols))
log(); k = 0
while fdm.run():
    k += 1
    if k % 10 == 0:
        log()
open(out, "w").write("\n".join(rows) + "\n")
print(f"wrote {out} ({len(rows) - 1} rows)")
