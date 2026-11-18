# Research: JSBSim baseline (session FDM2 00, 2026-11-18)

**Session goal:** collect what we know about embedding JSBSim, so the baseline build (prompt 01) starts from
facts, not from attempt 1's habits.

**Done when:** this file exists with sources and labels; prompt 01 is rewritten with fixed done-criteria; the
user's decisions are in `CLAUDE.md`; `PLAN.md` and `prompts/README.md` point here; pushed to `main`.

**Labels.** **Verified:** upstream source or docs. **Supported:** our own attempt-1 tests (reports on branch
`archive/attempt-1`). **Reasoned:** inference; the test that would settle it is named.

## Corrections from session 01 (2026-11-18)

Found while doing the work; details in `REPORT.md` on `baseline/jsbsim`. The original lines below are left as
written.

- **PR #1504 is in v1.3.3.** It is commit `4e695159`, first shipped in v1.3.2. The line "merged after v1.3.3"
  in section 1 is wrong. **Verified** [upstream git history].
- **Upstream ships only NASA check case 02.** Cases 01 and 03 exist on `baseline/jsbsim` as test fixtures written
  from NASA's model files and checked against NASA's published results. **Verified** [upstream tree; NASA data].
- **`scripts/` holds 63 files, 58 of them scripts** (2 `.kml`, 3 helper `.xml`). **Verified** [the data].
- **An input acts in the step it is written for.** External force totals show a value written before `Run()` in
  that same step; the *motion* shows it one step later, as section 1 says. **Supported** [session 01 forces test].
- **`<latitude>` in an initial-condition file is geocentric** unless it says otherwise. At 30° that is 0.17° (about
  10 nm) away from the geodetic latitude. **Supported** [session 01, the misplaced slope grid].
- **Script `<property>` and `<event>` elements only work inside `<run>`.** **Verified** [`FGScript.cpp`].
- **A property that was never written has no type** (`external_reactions/<name>/magnitude` is one). It still
  reads 0 and can be written. **Supported** [session 01].
- **WebAssembly and native differ in the last digit from row 0** (start position by one or two units in the last
  place), and a gear spring turns that into about 1e-5 to 1e-4 lb. **Supported** [session 01].
- **The c310 autopilot and the mk82 bomb amplify a last-digit difference in native itself** (heading on the
  0 / 2π seam; a pitch-rate blow-up). **Supported** [session 01, native-only experiments].
- Not checked: whether `emcmake` would have given `-O2` for a Release build. The build sets `-O3` itself and
  checks every file's command line.

JSBSim references are to **v1.3.3** (tag commit `66f7faf`, released 2026-10-16) unless stated.

---

## 1. JSBSim requirements

### Run order
- `FGFDMExec::Run` runs: Propagate, Input, Inertial, Atmosphere, Winds, Systems, MassBalance, Auxiliary,
  Propulsion, Aerodynamics, GroundReactions, ExternalReactions, BuoyantForces, Aircraft, Accelerations, Output.
  **Verified** [`FGFDMExec.h`, `eModels`].
- Propagate integrates the accelerations from the *previous* step, so an input acts one step later.
  **Verified** [same].
- `Run()` returns false when `simulation/terminate` is set. **Verified** [`FGFDMExec.cpp`].
- *Baseline consequence:* parity tests must compare the same step index, and the host must check `Run()`'s
  return value. **Reasoned.**

### Time step (dt)
- Default dt is 1/120 s. `simulation/dt` is read-only; use `Setdt()`. **Verified** [`FGFDMExec`].
- Set dt before loading: filters bake dt in at load time. **Verified** [`FGFilter.cpp`].
- A script's `<run dt>` overrides the host's dt. **Verified** [`FGScript`].
- Flight-control channels can run slower with `execrate`. **Verified** [`FGFCSChannel`].
- *Baseline consequence:* the wrapper calls `Setdt` before load and re-checks dt after scripts, reset and
  initial conditions. **Reasoned.**

### Initial conditions (`RunIC`)
- Suspends integration, initialises the state, runs twice, initialises derivatives, then starts engines the
  initial conditions mark as running. It does not reset time and does not trim. **Verified** [`FGFDMExec::RunIC`].
- A second `RunIC` does not cleanly reset the control systems: the f16's elevator moved. **Supported**
  [attempt 1, `REPORT-03..05`].
- *Baseline consequence:* reset = new instance; trim is the host's job. **Reasoned.**

### Integrators
- Defaults: rotational rate 1 (Euler), translational rate 3 (AB2), rotational position 1, translational
  position 4 (AB3). **Verified** [`FGPropagate.cpp:91-94`].
- Options: 0 none, 1 Euler, 2 trapezoidal, 3–5 AB2–AB4, 6–7 Buss1/2, 8 local linearisation, 9 AB5.
  `simulation/reset` and reloads restore the defaults. **Verified** [`FGPropagate.cpp`].
- Defaults are stable on the ground but inaccurate in the air; AB4 makes the gear chatter. **Supported**
  [attempt 1, `REPORT-02..05`, `REVIEW-codex-05`].
- The friction solver (`FGAccelerations::CalculateFrictionForces`) assumes an Euler step. An
  integrator-aware version (commit `53709ba8`, 2010) was lost in 2011 (`40279c20`). **Verified** [JSBSim git
  history]; its effect on our gear chatter is **Supported** [attempt 1].
- *Baseline consequence:* use upstream defaults; any change goes to `integrate/*`. **Reasoned.**

### Ground
- Hosts supply terrain through `FGGroundCallback::GetAGLevel(t, loc, contact&, normal&, v&, w&)`: height above
  ground (ft), plus contact point, normal and surface velocity, all ECEF. Install with
  `GetInertial()->SetGroundCallback()`. **Verified** [`FGGroundCallback.h`, `FGInertial`].
- `LoadModel` on a loaded instance re-allocates the models and brings back the default callback: re-install
  after every load. **Verified** [`FGFDMExec::LoadModel`].
- The default callback is a WGS84 ellipsoid at one terrain elevation. **Verified** [`FGDefaultGroundCallback`].
- Surface type (`FGSurface`: `ground/solid`, bumpiness, friction factors) is global, not per wheel.
  **Verified** [`FGSurface`].
- `FGLGear` is a spring-damper with Lagrange-multiplier friction. Its compression divides by the strut-tilt
  cosine without a limit. **Verified** [`FGLGear.cpp`]. This blew up in crashes. **Supported** [attempt 1].
- Aircraft without airframe contact points fall through the ground. **Verified** [JSBSim aircraft data].
- *Baseline consequence:* a C++ height-grid callback in the host layer, re-installed after each load, tested
  on flat ground and a slope against native. **Reasoned.**

### Properties
- Access by name parses the path on every call: about 1.8 µs on iPhone. A cached `SGPropertyNode*` is about 40×
  cheaper; a bulk array is cheapest. **Supported** [attempt 1, `REPORT-02`].
- Writes to read-only properties are ignored silently; invalid paths throw a `std::string`; ints truncate.
  **Verified** [`FGPropertyManager`, simgear props]; silent ignore also **Supported** [attempt 1].
- *Baseline consequence:* handles + bulk `Float64Array`, and validated writes. **Reasoned.**

### Lifecycle and threading
- Loading a second aircraft into the same `FGFDMExec` is a use-after-free in `SGPropertyNode::untie`.
  **Verified** [issue #1506, open].
- Globals (`debug_lvl`, the logger) and no locks. **Verified** [source]. Treat JSBSim as single-threaded and
  use one new instance per load. **Reasoned.**

### Random numbers
- `std::default_random_engine` and `std::` distributions differ between libc++ (Emscripten) and libstdc++
  (Linux), so turbulence will not match native. **Verified** [C++ standard leaves these
  implementation-defined; `FGWinds`]. Run parity with turbulence off. **Reasoned.**

### Upstream WebAssembly work
- PR #1504 (Emscripten fixes) merged after v1.3.3. **Verified** [GitHub].
- PR #1507 (official WebAssembly + TypeScript package, from 0x62/jsbsim-wasm) is open and depends on #1506; it
  found stripped catch blocks and unlinked IDBFS. **Verified** [GitHub].
- Attempt 1 built v1.3.3 unpatched with Emscripten 6.0.13. **Supported** [attempt 1, `REPORT-02`].

### Exceptions and logging
- Exceptions must be on for all code, including expat. **Verified** [source uses try/catch while loading];
  without them 22 aircraft failed to load. **Supported** [attempt 1, `REPORT-01`].
- A throw part-way through a step does not roll back; the clock has already advanced. **Verified**
  [`FGFDMExec::Run`]. After an error, discard the instance. **Reasoned.**
- Logging goes through `FGLogger` / `SetLogger`. **Verified** [`FGLog.h`].
- No official embedding guide; FlightGear's `JSBSim.cxx` and the Python module are the references.
  **Verified** [upstream docs].

---

## 2. What other sims do

All rows **Verified** from each project's source or docs, except where a lesson is marked **Reasoned**.

| Project | Rate | Threading | Terrain | Data exchange | Lessons |
|---|---|---|---|---|---|
| FlightGear (`JSBSim.cxx`) | 120 Hz (`/sim/model-hz`) | Main loop; accumulator in `SGSubsystemGroup`, **no catch-up cap** | Ground cache pre-filled each frame within gear radius + 2·dt·V | `copy_to_JSBsim` → `Run` loop → crash check → `copy_from_JSBsim` | AGL < −100 ft is a crash; ground trim needs gear |
| Official Unreal plugin (`UnrealEngine/`) | `Setdt(1/120)`; steps = 120·DeltaTime, remainder carried | Game thread; no cap, no interpolation | Line traces in `UEGroundCallback`, signed distance; ellipse parameters must be set or contact is invalid | `Commands` / `AircraftState` structs | Model loads once; heading −90° fix; flat-planet +180° hack |
| ArduPilot | One step per autopilot frame | Separate process, lockstep over sockets | JSBSim default | Sockets | Lockstep suits SITL, not games (**Reasoned**) |
| PX4 bridge | One `Run` per loop | Linked library | JSBSim default | Sim-time sensor stamps | Stamp with sim time, not wall time |
| gym-jsbsim | 60 Hz, as fast as possible | Python | JSBSim default | Python properties | Resets the same instance (we will not: #1506) |
| Flight Dynamics Lab | 1/240 s | Worker; rendering never steps physics | — | postMessage | Capped catch-up: sim slows down instead |
| WebFlight | 120 Hz | Worker; core also runs headless in Node | — | postMessage; no SharedArrayBuffer on GitHub Pages | `external_reactions` for tow forces |
| Aeronaut | 120 Hz | — | None fed in: flew through hills | — | f16 needed exceptions enabled |
| opengeo-sim (`docs/flight-view.md`) | — | — | 33×33 height grid via `position/terrain-elevation-asl-ft` (`terrain-elevation-ft` does nothing) | Properties | Rate-limit ground-height changes (a step spikes the gear); a stale grid gave a phantom runway; measure geoid/ellipsoid offsets; 1 s settle with brakes on before showing a ground start; alpha meaningless below 40 kt; cap time acceleration near the ground |
| 0x62/jsbsim-wasm | — | — | — | `Float64Array` property batch ≈ 25× faster than per-name calls; the view is invalidated by the next call | Copy out of the view before the next call |

**Not found:** any public iPhone timing for JSBSim in WebAssembly other than ours. **Reasoned** [search, 2026-11; absence cannot be verified].

---

## 3. Textbook and industry practice

### Real-time integration
- Real-time sims use fixed-step explicit methods; AB2 is the most common: one derivative evaluation per step,
  weak on fast modes, start-up error after a reset. Keep λ·h well below about 1. Run stiff subsystems (gear,
  actuators) at a multiple of the main rate. Never use a variable step in real time. **Verified** [NASA NTRS
  19900013748; Stevens, Lewis & Johnson, *Aircraft Control and Simulation*; Allerton, *Principles of Flight
  Simulation*; Zipfel, *Modeling and Simulation of Aerospace Vehicle Dynamics*].

### Validation
- NASA TM-2015-218675 check cases (nescacademy.nasa.gov/flightsim/2015); JSBSim took part. **Verified**.
- QTG style (14 CFR Part 60, AC 120-40B, ICAO 9625): scripted manoeuvres, tolerances set in advance,
  automated re-runs. **Verified**. This matches CLAUDE.md rule 3. **Reasoned.**
- DAVE-ML / AIAA S-119 for model data and check cases. **Verified**.

### Game loop
- Fiedler, "Fix Your Timestep": fixed dt with an accumulator; cap the frame time and the steps per frame;
  interpolate the render state (slerp for attitude); sample input once per frame and hold it; reset the
  accumulator after the page was hidden. **Verified** [gafferongames.com].

---

## 4. iPhone and WebAssembly facts

- **Exceptions.** `-fwasm-exceptions` (legacy encoding) works from Safari 15.2; exnref needs 18.4.
  **Verified** [WebKit release notes].
- **Safari 26.0 crashed at startup with `-fwasm-exceptions` + `-O3`** (WebKit bug 299629, fixed in a later
  26.x). **Verified** [WebKit bugzilla]. The user's Safari 27.2 ran attempt 1's build. **Supported**. Keep an
  `-fexceptions` fallback build. **Reasoned.**
- `-fwasm-exceptions` ≈ 2× faster than `-fexceptions` on iPhone, bit-identical. **Supported** [attempt 1].
- **Threads.** GitHub Pages cannot send COOP/COEP headers, so no SharedArrayBuffer; coi-serviceworker causes
  reload loops. Use `postMessage`. **Verified** [GitHub Pages docs; WebFlight].
- **Memory.** iOS is unreliable above about 300 MB, and a failed memory growth can kill the tab. Use a fixed,
  modest memory size and test on the device. **Verified** [WebKit/Emscripten issue reports]; the safe size for
  us is **Reasoned** until the iPhone page's create/destroy test.
- **Timers.** `performance.now` has 1 ms resolution on iPhone: time batches. **Supported** [attempt 1].
  `requestAnimationFrame` runs at 60 Hz in Low Power Mode. **Verified** [WebKit].
- **Background.** Timers and Workers pause in the background: pause the sim and do not catch up afterwards.
  **Verified** [WebKit]; the policy is **Reasoned.**
- **Build flags.** `-O3`; measure `-flto`; never `-ffast-math`. **Reasoned** [fast-math breaks parity].
  WebAssembly matches native to rounding level, not bit for bit (different libm). **Supported** [attempt 1].
- **Bindings.** Plain C exports, or a few bindings plus a heap struct, are cheaper than embind everywhere.
  **Supported** [attempt 1 property timings; 0x62/jsbsim-wasm].
- **Serving.** Serve `.wasm` as `application/wasm`. Cache files by content hash in the service worker; prompt
  for reload rather than calling `skipWaiting` mid-flight. **Verified** [MDN, web.dev].

---

## 5. Open questions

1. **Pin:** v1.3.3, or a later commit with #1504? The build session decides and records why. Settled by: does
   v1.3.3 build cleanly with the pinned Emscripten?
2. **Test page deploy branch.** Not decided by the user. Default in prompt 01: deploy from `main` (no settings
   change). Revisit if that gets in the way.
3. **Memory size.** What fixed size survives 20 create/destroy cycles on the iPhone? Settled by criterion 9.
4. **`-flto`:** worth it? Settled by timing both builds on the iPhone page.
5. **Integrator-aware friction** (lost 2010 code) and the strut-tilt divide: physics changes, so
   `integrate/*`, not the baseline.
6. **AB2 start-up error after reset:** does it matter for the game? Settled by a reset test on `integrate/*`.
7. **Ground grid size and update rate** (opengeo-sim used 33×33 with rate limits): baseline uses a fixed test
   grid; the game's values are an integration question.
