"""Diagnostic: when do the native and WebAssembly 737 hard landings (120 Hz, defaults) part company?
Prints each step at which the largest relative difference has grown tenfold again."""
import json
from pathlib import Path
out = Path(__file__).resolve().parents[3] / "out/gates/diag"
a = json.loads((out / "737-hard-120.native.json").read_text())
b = json.loads((out / "737-hard-120.wasm.json").read_text())
prev = 0.0
print("time s   largest relative difference   native: h-agl ft, q rad/s    WebAssembly: h-agl ft, q rad/s")
for k, (x, y) in enumerate(zip(a, b)):
    if None in x or None in y:
        print(f"{k / 120:6.3f}   a value is NaN or infinite ({'native' if None in x else 'WebAssembly'})")
        break
    d = max(abs(u - v) / max(abs(u), 1e-3) for u, v in zip(x, y))
    if d > prev * 10 and d > 0:
        print(f"{k / 120:6.3f}   {d:10.2e}                    {x[0]:10.4f} {x[2]:10.4g}        {y[0]:10.4f} {y[2]:10.4g}")
        prev = d
