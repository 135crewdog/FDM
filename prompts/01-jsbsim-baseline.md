# FDM2 01 Work: JSBSim baseline

---

Name this chat "FDM2 01 Work: JSBSim baseline" (if you cannot, ask me to in your first line).

Read `CLAUDE.md`, `README.md`, `PLAN.md` and **`RESEARCH.md`** on `main` first, and follow their rules.
`RESEARCH.md` holds the facts this work depends on (run order, dt, ground callback, lifecycle, iPhone limits),
each with its source.

**Goal:** an upstream-physics JSBSim WebAssembly core plus a thin host layer, on a new branch `baseline/jsbsim`
created from `main`. The host layer (wrapper, ground hook, loop) is not a physics change. Do not reuse attempt 1's
build files; you may read them (branch `archive/attempt-1`) for lessons.

**Decided already (2026-11-18; do not ask again):**
- JSBSim runs in a Web Worker. Also time it on the main thread.
- The baseline includes a C++ ground hook.
- Commit JSBSim's data files under `jsbsim-data/` at the pinned commit (no longer git-ignored).
- The iPhone test page deploys from `main`: when the branch is done, copy only the built test page to `main`.
  No Pages settings change is needed.
- `build/` is git-ignored: commit the built binaries in another folder (for example `dist-wasm/`, after checking
  `.gitignore`).

## Done means
Write this list at the top of `REPORT.md` before any work. Never change it after seeing a result (CLAUDE.md
rule 3).

1. **Pin and build.**
   - Pin a JSBSim commit: v1.3.3, or a later one that includes PR #1504. Record the reason. Pin Emscripten.
   - Exceptions on for all code (including expat): a `-fwasm-exceptions` build plus an `-fexceptions` fallback
     build (Safari 26.0 bug, see `RESEARCH.md`).
   - `-O3`, no fast-math, fixed memory size.
   - The build stops on any error. Commit the binaries and a build-info file (versions, flags, hashes).
   - Commit the JSBSim data at that commit under `jsbsim-data/`.
2. **Answer key.** Native JSBSim built from the same commit, with the same wrapper C++.
3. **Wrapper (C++ + TypeScript).**
   - One new instance per load (issue #1506).
   - `Setdt` before load. dt and integrator settings are checked and enforced after scripts, reset and initial
     conditions.
   - Cached property handles plus a bulk in/out `Float64Array`.
   - Validated writes: read-only, NaN, int.
   - Errors become a JavaScript `Error` with JSBSim's message.
   - JSBSim's logger is routed to JavaScript.
   - Crash and terminate are reported as events.
4. **Ground hook.** A C++ `FGGroundCallback` reading a height grid we supply (height, normal, contact point),
   re-installed after each load. Tested on flat ground and on a slope, against native running the same C++.
5. **Loop.**
   - Fixed-step accumulator, 1/120 s by default, with a catch-up cap.
   - Pause when the page is hidden; no catch-up afterwards.
   - Expose the previous and current state for interpolation.
   - The same core runs in a Worker (the game path) and in headless Node (tests).
6. **Load test.** Every aircraft that loads natively also loads in WebAssembly (table of results).
7. **Parity.** Step-by-step against native on:
   - c1723 (c172x);
   - one f16 script;
   - NASA check cases 01, 02 and one more that applies.

   Turbulence off. Thresholds written down before the run.
8. **External forces.** Set from TypeScript every step and compared with native. Measure the cost of 20 forces
   through the bulk path.
9. **iPhone page.**
   - User agent.
   - Batched timing at 1/120, 1/240, 1/480 and 1/1000 s, in the Worker and on the main thread.
   - With and without 20 forces.
   - A broken aircraft caught and shown.
   - One instance created and destroyed 20 times (memory check).
   - I paste the results back.
10. **Finish.** Tag `jsbsim-baseline-v1`, or record the commit in `PLAN.md` if the tag push is refused. Write
    `prompts/02-yasim-baseline.md`, update `PLAN.md` and `prompts/README.md`, push.

**Out of scope:** integrator tuning, physics patches, wing-strip forces, real terrain data, rendering.

If something fails, report it with evidence and stop. Keep messages to me short and plain; I read them on my
phone.
