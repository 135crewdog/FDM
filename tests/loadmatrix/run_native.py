"""Test 1 (native side): load every aircraft folder in native JSBSim 1.3.3 -> out/loadmatrix.native.json"""
import json, os, re, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pylib"))
import native
ROOT = str(native.DATA)
out = os.path.abspath(os.environ.get("LOADMATRIX_OUT", "out/loadmatrix.native.json"))
names = sorted(d for d in os.listdir(os.path.join(ROOT, "aircraft")) if os.path.isdir(os.path.join(ROOT, "aircraft", d)) and not re.match(r"c172p_ext\d+$", d))  # skip test-generated copies
res = []
for n in names:
    t0 = time.perf_counter()
    fdm = native.new_fdm()
    try:
        ok = bool(fdm.load_model(n)); msg = "" if ok else "load_model returned False"
    except Exception as e:
        ok, msg = False, f"{type(e).__name__}: {e}"
    res.append({"name": n, "ok": ok, "ms": (time.perf_counter() - t0) * 1e3, "msg": " ".join(msg.split())})
    del fdm
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(res, open(out, "w"), indent=1)
print(f"{native.describe()}: {sum(r['ok'] for r in res)}/{len(res)} aircraft load")
