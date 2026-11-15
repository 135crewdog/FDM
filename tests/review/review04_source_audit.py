"""Audit patch-0002 solver text against independently downloaded PteroLabs source.
Usage: .venv/bin/python ... /path/to/upstream-FGPropagate.cpp
Removes counters and normalizes the equivalent split convergence test only.
"""
import difflib
import hashlib
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[2]
upstream=Path(sys.argv[1]).read_text()
patched=(ROOT/'build/src-native-patched/src/models/FGPropagate.cpp').read_text()
def block(s):
    a=s.index('// The implicit midpoint step needs the inertia')
    b=s.index('void FGPropagate::Integrate( FGColumnVector3&',a)
    return s[a:b]
u=block(upstream);p=block(patched)
p=re.sub(r',\s*FGPropagate::MidpointCounters& count\)',')',p)
p='\n'.join(line for line in p.splitlines() if not any(x in line for x in [
    'count.splitSteps','count.notConverged','count.newtonIterations','count.maxNewtonIterations',
    'count.roundingExits','midpoint.steps++','midpoint.eulerFallbacks++']))
p=p.replace('max(spin, pushedSpin), midpoint','max(spin, pushedSpin)')
p=re.sub(r'if \(size <= NewtonTolerance \* scale\)\s*break;\s*if \(iteration > 0 && size >= lastSize && size <= RoundingTolerance \* scale\) \{\s*break;\s*\}',
    'if (size <= NewtonTolerance * scale || (iteration > 0 && size >= lastSize && size <= RoundingTolerance * scale)) break;',p)
p=re.sub(r'else \{\s*VState.vPQRi \+= dt \* in.vPQRidot;\s*\}',
    'else VState.vPQRi += dt * in.vPQRidot;',p)
def normalize(s):
    return re.sub(r'\s+','',re.sub(r'//[^\n]*','',s))
a,b=normalize(u),normalize(p)
print('PteroLabs commit: 33384d9981614509c65698f5f8be8eb8d1950228')
print('Raw upstream file sha256:',hashlib.sha256(upstream.encode()).hexdigest())
print('Solver block identical after removing counters/equivalent convergence split:',a==b)
print('Normalized solver block sha256:',hashlib.sha256(a.encode()).hexdigest())
if a!=b:
    print('\n'.join(difflib.unified_diff(u.splitlines(),p.splitlines(),fromfile='upstream',tofile='normalized-project')))
    raise SystemExit(1)
