# FDM repository: notes for future sessions

This repo will hold the flight dynamics model for a flight-sim game that runs as a PWA on iPhone.
So far it holds only an **evaluation of JSBSim compiled to WebAssembly** via `@0x62/jsbsim-wasm`
(pinned 1.2.4-beta.4). Read `REPORT.md` first.

## JSBSim data
JSBSim v1.3.3's aircraft, engine, systems, scripts and check_cases/NASA_EOM_2015 folders are committed in
`jsbsim-data/` (private, non-commercial project; user's decision 2026-11-15). Refresh with `scripts/fetch-jsbsim-data.sh <tag>`.

## What was learned
- The package's JSBSim is master commit `1a2e114` (reports 1.2.5.dev1), not the v1.2.4 tag its version suggests.
- Its build compiles libJSBSim without `-fexceptions`, so JSBSim's own try/catch does not work. 22 aircraft,
  including c172x and f16, fail to load. Errors reach JavaScript as a bare number (a pointer);
  `src/wasm.ts: describeError` decodes the message from WASM memory.
- Where models load, WASM matches native JSBSim (pip 1.3.0) to rounding level. Runtime `<external_reactions>`
  forces set through properties are bit-identical to native.
- Each `setPropertyValue` by name costs about 0.9 µs (20 forces × 7 properties ≈ 125 µs/step). Use handles or
  bulk transfer in our own build.
- JSBSim's default rotational-rate integrator is first-order Euler. Set
  `simulation/integrator/rate/rotational = 5` (AB4) to match the NASA check case.
- iPhone (Safari 27.2): ~5 µs/step for a c172x-based model, ~60 µs with 20 forces set by name; timer resolution is 1 ms.
- Recommendation: compile JSBSim to WASM ourselves (see REPORT.md).

## How to run
```sh
npm ci
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
scripts/fetch-jsbsim-data.sh          # JSBSim data at the package's commit, plus NASA brick files from v1.3.2
scripts/run-tests.sh                  # tests 1-3; summaries to results/, raw CSVs to out/ (ignored)
node scripts/build-site.mjs           # test page into site/ (ignored); serve with: python3 -m http.server -d site
npx tsc                               # typecheck
```

## Layout
- `src/wasm.ts`: create the SDK in Node, copy data into MEMFS, decode C++ exceptions.
- `tests/parity/`: test 1 (WASM vs native, every step). `tests/extforce/`: test 2. `tests/nasa/`: test 3.
- `web/`: iPhone test page source. `scripts/build-site.mjs` assembles `site/`; `.github/workflows/pages.yml` deploys
  it from `main` to GitHub Pages.
