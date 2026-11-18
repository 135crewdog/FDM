# FDM: notes for every session

Flight dynamics model for an iPhone PWA flight sim. **Attempt 2.** Read `README.md` (branches) and `PLAN.md`
(where we are) first. **Read `RESEARCH.md` before any baseline work.** Attempt 1 is on branch `archive/attempt-1`: reference only.

## Rules that keep us out of the loop
1. **One goal per session.** Take the goal and its done-criteria from the session's prompt and write them at the
   top of the session report before doing any work.
   - When the criteria are met, stop.
   - If you are blocked, report it with evidence and stop.
   - Anything outside the goal goes into the next prompt, not into this session.
2. **Baselines are upstream physics only.** `baseline/jsbsim` and `baseline/yasim` get no physics patches and no
   integrator tuning. They take only build and binding fixes, each with a test. Physics changes belong on
   `integrate/*` branches, starting from a baseline tag.
3. **Write pass/fail criteria before the results.** Never change a criterion after seeing a result. If a
   criterion was wrong, say so, keep the result and add a new criterion.
4. **Label evidence** in every report:
   - **Verified:** checked against an answer we did not produce (native build, NASA data, upstream source, the
     user's device).
   - **Supported:** our own test shows it.
   - **Reasoned:** not tested; say which test would settle it.
5. **Attempt 1 is reference only.** Read it for lessons; do not copy its patches or default settings.
6. **Finish every session the same way.** Update `PLAN.md`, write the next prompt in `prompts/`, add it to the
   table in `prompts/README.md`, and push.

## Lessons carried over from attempt 1 (Verified there)
- JSBSim must be compiled with exceptions enabled for **all** of its code (`-fwasm-exceptions` or `-fexceptions`
  in the global C/C++ flags before `add_subdirectory`). JSBSim uses try/catch while loading; without exceptions,
  22 aircraft fail to load.
- `-fwasm-exceptions` was about 2× faster than `-fexceptions` on iPhone, with bit-identical results. It needs
  Safari 15.2 or later.
- On iPhone, `performance.now()` has 1 ms resolution: time batches of steps, not single steps.
- Setting a property by name costs about 1 µs per call through embind. For many per-step values, use handles or
  a bulk array.
- Native JSBSim silently ignores writes to read-only properties. Read back every value a test depends on.
- **Safari 26.0 caveat:** a `-fwasm-exceptions` + `-O3` build crashed at startup on Safari 26.0 (WebKit bug
  299629, fixed in a later 26.x; Verified upstream). The user's Safari 27.2 ran attempt 1's build. Always ship an
  `-fexceptions` fallback build too.

## Lessons from attempt 2, session 01 (Supported there unless marked)
- **Write parity lines relative to noise, not as fixed tiny numbers.** WebAssembly and native differ in the last
  digit from the first row. A gear spring, a heading on the 0 / 2π seam, an autopilot or a numerical blow-up
  amplifies that, in native against native too. The useful line is: no more than 3 times what native differs from
  itself after a one-last-digit nudge. Keep position limits fixed.
- **Read back that a scenario is what its name says** (on the slope, on the ground, engine running). A JSBSim
  initial-condition latitude is geocentric; a grid laid out in geodetic latitude ended up 10 nm away.
- When a frozen line fails: keep it, find the cause, try to reproduce it in native alone, report, stop.
- JSBSim script `<property>` and `<event>` elements must be inside `<run>` (Verified upstream).
- A never-written JSBSim property has no type but is a valid value; only a node with children is a folder.
- Node 22 runs TypeScript files directly if they use only erasable syntax (no enums, no parameter properties).
- The git proxy accepted pushes to `baseline/jsbsim` and to `main`. Pages published `main` about 30 s after the
  push.

## Decisions (user, 2026-11-18)
- JSBSim runs in a **Web Worker**. Also time it on the main thread.
- The JSBSim baseline includes a **C++ ground hook** (`FGGroundCallback` reading a height grid). It is host
  layer, not a physics change.
- **Commit** JSBSim's data files under `jsbsim-data/` at the pinned JSBSim commit. The build session (prompt 01)
  commits them. `jsbsim-data/` is no longer in `.gitignore`.

## Git
- Push only to the branch the session's prompt names. The GitHub Pages environment allows `main` by default;
  deploying a page from another branch needs the user to allow it.
- The cloud sessions' git proxy has refused tag pushes and branch deletions (HTTP 403). If a tag cannot be pushed, record its intended name
  and commit in `PLAN.md` and ask the user to create it on GitHub (Releases → new tag on that commit).
