"""Run the report's switch diagnostic on the actual recommended configuration.
Its original VARIANTS list tests only configurations with friction-aware on.
No original test is changed.
"""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/gates/diag'))
import contact_switch as C
for model,scenario,hz in [('c172x','bounce',480),('c172x','bounce',1000),
    ('c172x','hard_forward',480),('c172x','hard_forward',1000),
    ('f16','hard_forward',480),('c310','hard_forward',480),('737','hard_forward',480),('ah1s','bounce',480)]:
    for config in ['c3-ab4','c3-ab4-fa']:
        print('RESULT '+json.dumps(dict(config=config,model=model,scenario=scenario,hz=hz,
            **C.run(config,model,scenario,hz))),flush=True)
