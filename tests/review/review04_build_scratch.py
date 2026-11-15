"""Build diagnostic native variants WITHOUT touching committed patches/binaries.

cap: BOGEY compression capped at 2 ft; projected-force divisions unchanged.
guard: same cap plus no BOGEY contact if LGearProj <= 0.1 (near-horizontal leg).
Neither is a proposed production fix or an acceptance-gate candidate.
Run .venv/bin/python tests/review/review04_build_scratch.py cap|guard
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
mode=sys.argv[1];assert mode in ['cap','guard']
source=ROOT/'build/review04-scratch-source'
build=ROOT/'build/review04-scratch-build'
if not source.exists():
    shutil.copytree(ROOT/'build/src-native-patched',source,ignore=shutil.ignore_patterns('.git'))
baseline=(ROOT/'build/src-native-patched/src/models/FGLGear.cpp').read_text()
old='compressLength = LGearProj > 0.0 ? height * normalZ / LGearProj : 0.0;'
assert baseline.count(old)==1
text=baseline.replace(old,'compressLength = LGearProj > 0.0 ? std::min(2.0, height * normalZ / LGearProj) : 0.0;')
if mode=='guard':
    assert text.count('if (isSolid) {')==1
    text=text.replace('if (isSolid) {','if (isSolid && LGearProj > 0.1) {')
(source/'src/models/FGLGear.cpp').write_text(text)
cmake=str(ROOT/'.venv/bin/cmake')
subprocess.run([cmake,'-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release',
    '-DBUILD_PYTHON_MODULE=ON','-DBUILD_DOCS=OFF','-DBUILD_SHARED_LIBS=OFF',
    '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',f'-DPython3_EXECUTABLE={ROOT}/.venv/bin/python',
    '-DPython3_FIND_VIRTUALENV=ONLY'],check=True)
subprocess.run([cmake,'--build',str(build),'--target','_jsbsim','--parallel','3'],check=True)
out=ROOT/f'build/native/review04-{mode}'
out.mkdir(parents=True,exist_ok=True)
shutil.copytree(build/'tests/jsbsim',out/'jsbsim',dirs_exist_ok=True)
so=next((out/'jsbsim').glob('_jsbsim*.so'))
info=dict(set=f'review04-{mode}',description='DIAGNOSTIC ONLY: '+mode,
    based_on=json.loads((ROOT/'build/native/patched/native-info.json').read_text()),
    gear_source_sha256=hashlib.sha256(text.encode()).hexdigest(),
    moduleSha256=hashlib.sha256(so.read_bytes()).hexdigest())
info['patches']=info['based_on']['patches']
(out/'native-info.json').write_text(json.dumps(info,indent=2))
print(json.dumps(info),flush=True)
