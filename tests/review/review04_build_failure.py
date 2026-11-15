"""Fault injection: a failed incremental native build must not certify a stale .so.
Only a temporary WORK tree and fake cmake are used; repository binaries unchanged.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='review04-build-failure-') as tmp:
    t=Path(tmp);fake=t/'fakebin';fake.mkdir()
    cmake=fake/'cmake'
    cmake.write_text('#!/bin/sh\nif [ "$1" = --build ]; then echo "INJECTED compile failure (exit 42)" >&2; exit 42; fi\nexit 0\n')
    cmake.chmod(0o755)
    stale=t/'native-build-patched/tests/jsbsim'
    stale.parent.mkdir(parents=True)
    shutil.copytree(ROOT/'build/native/unpatched/jsbsim',stale)
    env=os.environ.copy();env.update(PATH=str(fake)+os.pathsep+env['PATH'],WORK=str(t),
        JSBSIM_REPO=str(ROOT/'build/src-native-unpatched'))
    p=subprocess.run([str(ROOT/'scripts/build-native.sh'),'patched'],cwd=ROOT,env=env,text=True,capture_output=True)
    print(p.stdout);print(p.stderr);print('Build script exit code:',p.returncode)
    out=t/'native/patched'
    if out.exists():
        info=json.loads((out/'native-info.json').read_text())
        print('Recorded set:',info['set'],'recorded patch count:',len(info['patches']))
        child=env.copy();child['PYTHONPATH']=str(out);child['JSBSIM_DEBUG']='0'
        q=subprocess.run([str(ROOT/'.venv/bin/python'),'-c',
            'import jsbsim; f=jsbsim.FGFDMExec("."); print("Actual midpoint property exists:", f.get_property_manager().hasNode("simulation/integrator/midpoint/steps"))'],
            env=child,cwd=t,text=True,capture_output=True)
        print(q.stdout)
        so=next((out/'jsbsim').glob('_jsbsim*.so'))
        original=next((ROOT/'build/native/unpatched/jsbsim').glob('_jsbsim*.so'))
        print('Copied binary is stale unpatched binary:',hashlib.sha256(so.read_bytes()).digest()==hashlib.sha256(original.read_bytes()).digest())
