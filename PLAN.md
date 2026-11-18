# Plan (attempt 2)

Update this file at the end of every session: mark what is done, link the report, and name the next step.

## Done

- **Session 00 (research), 2026-11-18:** `RESEARCH.md` on `main`. User decisions recorded in `CLAUDE.md`.

## Stage 1: JSBSim baseline (`baseline/jsbsim`)

**Status:** next (`prompts/01-jsbsim-baseline.md`). Read `RESEARCH.md` first: research done 2026-11-18
(session 00), and prompt 01 was rewritten from it.

**Goal:** JSBSim compiled to WebAssembly from scratch, upstream physics, no patches, plus a thin host layer
(wrapper, C++ ground hook, fixed-step loop in a Worker and in Node).

**Done when** (full list in `prompts/01-jsbsim-baseline.md`):
- The build is reproducible with pinned versions (`-fwasm-exceptions` build plus `-fexceptions` fallback).
- Native JSBSim from the same commit, with the same wrapper C++, is the answer key.
- Every aircraft that loads natively loads in WebAssembly.
- The ground hook matches native on flat ground and a slope.
- Parity step by step on c1723, an f16 script and NASA check cases 01, 02 and one more.
- External forces can be set from TypeScript and match native.
- An iPhone test page runs (Worker and main thread); the user pastes results.
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
