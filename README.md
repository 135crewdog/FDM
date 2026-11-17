# FDM

Flight dynamics model for a flight-sim game that runs as a web app (PWA) on iPhone.

This is **attempt 2**. Everything from attempt 1 is kept on the branch
[`archive/attempt-1`](https://github.com/135crewdog/FDM/tree/archive/attempt-1) (commit `264ec44`).

## Branches

| Branch | Role |
|---|---|
| `main` | Docs, plan and prompts. Later, the integrated FDM. |
| `baseline/jsbsim` | JSBSim compiled to WebAssembly from scratch: upstream physics, no patches. |
| `baseline/yasim` | YASim compiled to WebAssembly the same way. |
| `integrate/*` | Later work combining the two FDMs. |
| `work/*` | Short-lived branches for one session. |
| `archive/attempt-1` | Attempt 1, read-only. |

Each working baseline gets a tag (`jsbsim-baseline-v1`, `yasim-baseline-v1`). Later work starts from that tag,
not from a moving branch.

## Attempt 1 in one paragraph

Sessions 01–05 (14–16 Nov 2026):
- **01:** evaluated the npm package `@0x62/jsbsim-wasm`. It was rejected: it was built without C++ exception
  support, so 22 of 60 aircraft failed to load.
- **02:** compiled JSBSim v1.3.3 ourselves (`-fwasm-exceptions`, all aircraft load, matches native JSBSim, about
  5–14 µs per step on iPhone).
- **03–05:** iterated on integrators and the ground model with patches, gates and three independent Codex reviews.
  The last review answered "no, as a game default to build on".

The restart keeps the lessons. It does not carry over the patches.
Start with `REPORT-02.md` and `REPORT-05.md` on the archive branch.

The GitHub Pages test page still shows attempt 1's last deployment until a new one replaces it.

See `PLAN.md` for the roadmap and `prompts/` for the next session.
