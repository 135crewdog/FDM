"""Fixture exploration (JSBSim DEFAULT integrators only): touch-and-go and skipping. How many contact episodes are
there, and how far is a run at a gate step rate from the same run at 9600 Hz, at the same times after the release?
Logged. usage: ... g8_try.py [model ...]"""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
import sim05  # noqa: E402
import evaluate_05 as E  # noqa: E402
from triallog import log  # noqa: E402
S = Path("/tmp/claude-0/-home-user-FDM/0bbef996-2fa3-51f1-933b-53a1a733c414/scratchpad")
DEF = {"properties": {}}


def run(model, case, hz):
    out = S / f"g8-{hz}.f64"
    sim05.landing(model, case, hz, DEF, out)
    return E.Run(out)


def sampled(r, hz, n):
    """Rows at 40 Hz from the release."""
    idx = np.arange(0, len(r.a), hz // 40)[:n]
    return r, idx


def wrap(d):
    return (d + np.pi) % (2 * np.pi) - np.pi


for model in ([sys.argv[1]] if len(sys.argv) > 1 else ["c172x", "c310", "737", "f16"]):
    for case in (sys.argv[2:] or ("touch_and_go", "skip")):
        ref = run(model, case, 9600)
        anyc = ref.wow.any(axis=1)
        episodes = int((np.diff(anyc.astype(int)) == 1).sum())
        nref = (len(ref.a) - 1) // 240 + 1
        print(model, case, "reference: contact episodes", episodes, "airborne fraction after first touch", round(float(1 - anyc[np.argmax(anyc):].mean()), 3),
              "end h", round(float(ref.g('position/h-agl-ft')[-1]), 2), "max h", round(float(ref.g('position/h-agl-ft').max()), 2), "end vc", round(float(ref.g('velocities/vc-kts')[-1]), 1),
              "phi range", np.degrees(ref.g('attitude/phi-rad')).min().round(2), np.degrees(ref.g('attitude/phi-rad')).max().round(2),
              "theta range", np.degrees(ref.g('attitude/theta-rad')).min().round(2), np.degrees(ref.g('attitude/theta-rad')).max().round(2), "error", ref.meta["error"])
        for hz in (4800, 480, 960, 1200):
            r = run(model, case, hz)
            n = min((len(r.a) - 1) // (hz // 40) + 1, nref)
            ia, ib = np.arange(n) * (hz // 40), np.arange(n) * 240
            att = np.stack([r.g(f"attitude/{x}-rad") for x in ("phi", "theta", "psi")], axis=1)[ia]
            attr = np.stack([ref.g(f"attitude/{x}-rad") for x in ("phi", "theta", "psi")], axis=1)[ib]
            rat = r.vec("velocities/{}-rad_sec", "pqr")[ia]
            ratr = ref.vec("velocities/{}-rad_sec", "pqr")[ib]
            datt = np.degrees(np.abs(wrap(att - attr)))
            drat = np.abs(rat - ratr)
            ep = int((np.diff(r.wow.any(axis=1).astype(int)) == 1).sum())
            rec = dict(model=model, case=case, hz=hz, contact_episodes=ep, max_attitude_diff_deg=float(datt.max()), end_attitude_diff_deg=float(datt[-1].max()),
                       max_rate_diff_rad_s=float(drat.max()), end_rate_diff_rad_s=float(drat[-1].max()), rms_rate_diff=float(np.sqrt((drat ** 2).mean())),
                       end_h_diff_ft=float(abs(r.g("position/h-agl-ft")[ia[-1]] - ref.g("position/h-agl-ft")[ib[-1]])), error=r.meta["error"])
            log("touch-and-go / skip fixture at a gate rate against the same run at 9600 Hz, JSBSim defaults", **rec)
            print("   ", {k: (round(v, 5) if isinstance(v, float) else v) for k, v in rec.items() if k not in ("model", "case")})
