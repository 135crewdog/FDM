"""Expose missing finite/length checks using synthetic logs; original test untouched."""
from pathlib import Path
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='codex-comparator-') as d:
    a,b=Path(d)/'a.csv',Path(d)/'b.csv'
    a.write_text('simulation/sim-time-sec,velocities/q-rad_sec\n0,1\n1,2\n')
    b.write_text('simulation/sim-time-sec,velocities/q-rad_sec\n0,nan\n')
    p=subprocess.run([sys.executable,str(ROOT/'tests/parity/compare.py'),str(a),str(b)],
                     text=True,capture_output=True)
    print('Synthetic reference: 2 rows, finite rates 1 and 2.')
    print('Synthetic candidate: 1 row, rate NaN.')
    print(p.stdout)
    print('Comparator exit code:',p.returncode)
