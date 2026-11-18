// Mirrors host/fdm_codes.h. Plain objects (no TypeScript enums) so Node can run this file as it is.

export const State = { NEW: 0, LOADED: 1, RUNNING: 2, ENDED: 3, DEAD: 4 } as const;

export const StepResult = {
  OK: 0,
  SCRIPT_END: 1,
  TERMINATE: 2,
  NONFINITE: 3,
  ERROR: -1,
  NOT_RUNNING: -2,
  BAD_INPUT: -3,
} as const;

export const SetStatus = {
  OK: 0,
  READ_ONLY: 1,
  NAN: 2,
  NOT_INTEGER: 3,
  REJECTED: 4,
  READBACK_DIFFERS: 5,
  BAD_HANDLE: 6,
} as const;

export const SET_STATUS_NAME = ["ok", "read-only", "nan", "not-integer", "rejected", "readback-differs", "bad-handle"];

export const Counter = {
  DT_RESTORED: 0,
  INTEGRATORS_RESTORED: 1,
  DT_CHANGED: 2,
  INTEGRATORS_CHANGED: 3,
  TIME_STALLED: 4,
  GROUND_CALLS: 5,
  TERRAIN_ELEV_IGNORED: 6,
  STEPS: 7,
} as const;

export const COUNTER_NAME = [
  "dt-restored",
  "integrators-restored",
  "dt-changed",
  "integrators-changed",
  "time-stalled",
  "ground-calls",
  "terrain-elevation-ignored",
  "steps",
];

export const PropFlag = { READ: 1, WRITE: 2, INTEGER: 4 } as const;

// JSBSim::LogLevel
export const LOG_LEVEL_NAME = ["BULK", "DEBUG", "INFO", "WARN", "ERROR", "FATAL", "STDOUT"];
