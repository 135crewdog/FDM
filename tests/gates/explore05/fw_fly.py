"""Fixture exploration: fly one landing case with the draft fixture and print what really happened (the evaluator's
measurements). Every call is logged (triallog). JSBSim's default integrators unless a configuration is named.
usage: ... fw_fly.py <model> <case> [hz] [config]
"""
import json
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import sim05  # noqa: E402
import evaluate_05 as E  # noqa: E402
from triallog import log  # noqa: E402

REF = {"properties": {}, "source": "patched"}   # JSBSim's defaults: no integrator property is set
SCRATCH = Path("/tmp/claude-0/-home-user-FDM/0bbef996-2fa3-51f1-933b-53a1a733c414/scratchpad")


def fly(model, case, hz=480, config=None, quiet=False, keep=False):
    cfg = sim05.CONFIGS[config] if config else REF
    out = SCRATCH / f"fly-{model}-{case if isinstance(case, str) else 'x'}-{hz}-{config or 'default'}.f64"
    sim05.landing(model, case, hz, cfg, out)
    d = E.landing_metrics(out)
    d["config"] = config or "JSBSim defaults"
    log("flown landing fixture trial", **d)
    if not keep:
        out.unlink()
    if not quiet:
        print(json.dumps(d, indent=None, default=float))
    return d, out


def short(d):
    if not d.get("touched"):
        return f"{d['model']:6s} {str(d['case']):40s} {d['hz']:5d} NOT TOUCHED error={d['error']}"
    t, e = d["touch"], d.get("energy_ft", {})
    mc = max(d["max_compression_ft"])
    return (f"{d['model']:6s} {d['case'].get('sink_fps'):4} b{d['case'].get('bank_deg', 0):g} d{d['case'].get('drift_fps', 0):g} {d['hz']:5d}Hz err={d['error']} touch t={d['t_touch']:.2f}s sink={t['sink_fps']:.2f} "
            f"th={t['theta_deg']:.2f} phi={t['phi_deg']:.2f} vc={t['vc_kts']:.1f} v={t['v_fps']:.1f} first={[u.split('/')[1] for u in t['first_units']]} | "
            f"minh={d['min_h_agl_ft']:.2f} maxh={d['max_h_agl_after_touch_ft']:.2f} |phi|max={d['max_abs_phi_deg']:.1f} th=[{d['min_theta_deg']:.1f},{d['max_theta_deg']:.1f}] |psi|={d['max_abs_psi_deg']:.1f} "
            f"F/W={d['max_ground_force_weights']:.2f} comp={mc:.2f} struct={d['structure_contacts']} air_after={d['last_airborne_after_touch_s']:.2f}s "
            f"end: vc={d['end']['vc_kts']:.0f} down={d['end']['all_wheels_down']} | E: closure={e.get('closure_max_abs', float('nan')):.4f} Wg_max={e.get('ground_work_max', float('nan')):.5f} Wg_end={e.get('ground_work_end', float('nan')):.1f}")


if __name__ == "__main__":
    a = sys.argv[1:]
    d, _ = fly(a[0], a[1], int(a[2]) if len(a) > 2 else 480, a[3] if len(a) > 3 else None, quiet=True)
    print(short(d))
