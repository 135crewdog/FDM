"""Diagnostic (not a gate): the 737 hard landing (G2) at 120 Hz with JSBSim's defaults, native side.
Writes the first 8 s, every step, to out/gates/diag/737-hard-120.native.json; the WebAssembly side is
divergence_737.mts; compare with divergence_737_compare.py.
usage: PYTHONPATH=build/native/unpatched python tests/gates/diag/divergence_737.py"""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "pylib"))
import native  # noqa: E402
G = json.loads((HERE.parent / "gates.json").read_text())
P = json.loads((HERE / "divergence_737_props.json").read_text())
f = native.new_fdm(dt=1 / 120)
f.load_model("737")
f.load_ic("reset00", True)
for p, v in G["scenarios"]["hard"]["ic"].items():
    f[p] = v
f["simulation/integrator/rate/rotational"] = 1
f.run_ic()
rows = [[f[p] for p in P]]
for k in range(120 * 8):
    f.run()
    rows.append([f[p] for p in P])
out = native.REPO / "out/gates/diag"
out.mkdir(parents=True, exist_ok=True)
(out / "737-hard-120.native.json").write_text(json.dumps(rows))
print("wrote", len(rows), "rows;", native.describe())
