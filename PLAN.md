# Plan (attempt 2)

Update this file at the end of every session: mark what is done, link the report, and name the next step.

## Stage 1: JSBSim baseline (`baseline/jsbsim`)

**Status:** next (`prompts/01-jsbsim-baseline.md`).

**Goal:** JSBSim compiled to WebAssembly from scratch, upstream physics, no patches.

**Done when:**
- The build is reproducible with pinned versions.
- Every bundled aircraft loads.
- Results match native JSBSim built from the same tag, step by step.
- External forces can be set from JavaScript and match native.
- An iPhone test page runs.
- The result is tagged `jsbsim-baseline-v1`.

## Stage 2: YASim baseline (`baseline/yasim`)

**Status:** not started.

**Goal:** FlightGear's YASim compiled to WebAssembly the same way, with only the minimum glue it needs to run
outside FlightGear (YASim depends on SimGear's property tree and XML parsing).

**Done when:** the same checks as stage 1, as far as they apply.
- The answer key is native YASim, the same code built natively.
- YASim is GPL-2. A combined build with JSBSim (LGPL-2.1) would be GPL. Record the licences in the report.
- The result is tagged `yasim-baseline-v1`.

## Stage 3: integration (`integrate/*`)

**Status:** not started.

**Goal:** to be decided after stages 1 and 2, from their tags. This is also where game-specific physics work
(wing-strip forces, ground model, integrator choice) happens, never on the baselines.
