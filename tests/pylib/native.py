"""Shared set-up for native JSBSim runs (the answer key).

Which native JSBSim is used is decided by PYTHONPATH (see scripts/build-native.sh):
  (unset)                          pip's jsbsim==1.3.3
  PYTHONPATH=build/native/unpatched   v1.3.3 built here from source, no patches
  PYTHONPATH=build/native/patched     the same source plus wasm/patches/*.patch
Every runner prints describe() so a result always says which answer key produced it.

Rules enforced here:
- Output files (a script's <output> files, initfile dumps) go to a scratch directory, never into
  the JSBSim data root (they used to land in jsbsim-data/).
- dt is set before a model is loaded (flight-control filters cache dt at load).
"""
import hashlib
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("JSBSIM_DEBUG", "0")
import jsbsim  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("JSBSIM_DATA") or REPO / "jsbsim-data").resolve()
SCRATCH = tempfile.mkdtemp(prefix="fdm-native-out-")


def new_fdm(root=None, dt=None):
    """A fresh FGFDMExec on `root` (default: jsbsim-data). Give dt here, before loading a model."""
    fdm = jsbsim.FGFDMExec(str(root or DATA))
    fdm.set_debug_level(0)
    fdm.set_output_path(SCRATCH)  # absolute path: JSBSim would otherwise write into the data root
    if dt is not None:
        if not (dt > 0 and dt == dt and dt != float("inf")):
            raise ValueError(f"invalid dt {dt}")
        fdm.set_dt(dt)
    return fdm


def key_name():
    """pip, unpatched or patched (from native-info.json next to a source build)."""
    info = Path(jsbsim.__file__).resolve().parents[1] / "native-info.json"
    return json.loads(info.read_text())["set"] if info.exists() else "pip"


def key_info():
    pkg = Path(jsbsim.__file__).resolve().parent
    so = sorted(pkg.glob("_jsbsim*.so"))
    info = pkg.parent / "native-info.json"
    d = {"key": key_name(), "version": jsbsim.__version__,
         "module_sha256": hashlib.sha256(so[0].read_bytes()).hexdigest() if so else None, "patches": []}
    if info.exists():
        d["patches"] = json.loads(info.read_text())["patches"]
    return d


def describe():
    d = key_info()
    patches = ", ".join(f"{p['file']} {p['sha256'][:12]}" for p in d["patches"]) or "none"
    return f"native JSBSim {d['version']} [{d['key']}] module sha256 {str(d['module_sha256'])[:16]} patches: {patches}"
