"""Test 1 (native side): load every aircraft folder in native JSBSim 1.3.3 -> out/loadmatrix.native.json"""
import json, os, sys, tempfile, time
import jsbsim
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "jsbsim-data"))
out = os.path.abspath("out/loadmatrix.native.json")
os.chdir(tempfile.mkdtemp())
names = sorted(d for d in os.listdir(os.path.join(ROOT, "aircraft")) if os.path.isdir(os.path.join(ROOT, "aircraft", d)))
res = []
for n in names:
    t0 = time.perf_counter()
    fdm = jsbsim.FGFDMExec(ROOT); fdm.set_debug_level(0)
    try:
        ok = bool(fdm.load_model(n)); msg = "" if ok else "load_model returned False"
    except Exception as e:
        ok, msg = False, f"{type(e).__name__}: {e}"
    res.append({"name": n, "ok": ok, "ms": (time.perf_counter() - t0) * 1e3, "msg": " ".join(msg.split())})
    del fdm
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(res, open(out, "w"), indent=1)
print(f"native {jsbsim.__version__}: {sum(r['ok'] for r in res)}/{len(res)} aircraft load")
