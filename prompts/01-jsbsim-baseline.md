# FDM2 01 Work: JSBSim baseline

---

Name this chat "FDM2 01 Work: JSBSim baseline" (if you cannot, ask me to in your first line).

Read `CLAUDE.md`, `README.md` and `PLAN.md` on `main` first, and follow their rules.

**Goal:** compile JSBSim to WebAssembly from scratch, as a clean baseline on a new branch `baseline/jsbsim`
created from `main`. Use upstream physics with no patches and no integrator changes. Do not reuse attempt 1's
build files. You may read them (branch `archive/attempt-1`) for lessons.

**Ask me first, in one short message:**
1. Should JSBSim's data files (aircraft, engine, systems) be committed, or fetched by a script into a
   git-ignored folder? The repository is public.
2. Should the iPhone test page deploy from `baseline/jsbsim`? I would need to allow that branch in the
   repository's `github-pages` environment. The alternative is to deploy it from `main`.

**Done means.** Write this list at the top of `REPORT.md` before starting:
1. The latest JSBSim release tag is chosen and recorded. The Emscripten version is pinned. The build script stops
   on any error. The built `.mjs`/`.wasm` files and a build-info file (versions, hashes) are committed.
2. Exceptions are enabled for all of JSBSim. Every aircraft in that tag's `aircraft/` folder that loads in
   native JSBSim also loads in WebAssembly (table of results).
3. A small TypeScript wrapper: load, run, run_ic, get/set property; errors reach JavaScript as `Error` with
   JSBSim's message.
4. Step-by-step parity with native JSBSim built from the same tag on 3 scripts: a c172x takeoff, an f16, and
   NASA check case 02. Report the largest differences and explain anything above 1e-6 relative.
5. External forces (`<external_reactions>`) set from JavaScript every step match native; record the cost of 20
   forces per step.
6. A plain iPhone test page: user agent, average time per step over batches at 1/120, 1/480 and 1/1000 s, with
   and without 20 forces, and a deliberately broken aircraft caught and shown. I will paste the results.
7. Tag `jsbsim-baseline-v1`, or record the commit in `PLAN.md` if the tag cannot be pushed. Update `PLAN.md`,
   write `prompts/02-yasim-baseline.md`, update `prompts/README.md`, and push.

Do not tune integrators or change physics in this session. If something fails, report it with evidence and stop.
Keep messages to me short and plain; I read them on my phone.
