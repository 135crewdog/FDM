"""Copy JSBSim's NASA_EOM_2015 brick case into jsbsim-data/nasa-run/.
The only change: <emptywt unit="SLUG"> is rewritten in LBS, because the SLUG->LBS unit
conversion was added to JSBSim in v1.3.2 and the WASM package's JSBSim (1a2e114) and
pip jsbsim 1.3.0 do not have it. Conversion factor = the one v1.3.2 uses
(convert["SLUG"]["KG"] / convert["LBS"]["KG"] = 14.59390 / 0.45359237)."""
import os, re, shutil
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "jsbsim-data")
src = os.path.join(ROOT, "check_cases", "NASA_EOM_2015")
dst = os.path.join(ROOT, "nasa-run")
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(src, dst)
p = os.path.join(dst, "aircraft", "brick", "brick.xml")
x = open(p).read()
m = re.search(r'<emptywt unit="SLUG">\s*([0-9.eE+-]+)\s*</emptywt>', x)
lbs = float(m.group(1)) * (14.59390 / 0.45359237)
x = x.replace(m.group(0), f'<emptywt unit="LBS"> {lbs!r} </emptywt>')
open(p, "w").write(x)
print("brick emptywt:", m.group(1), "slug ->", lbs, "lbs")
