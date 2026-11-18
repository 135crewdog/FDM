// Fixed-step loop ("Fix Your Timestep"): real time is fed in, physics advances in whole steps of dt.
// Pure logic with an injected clock value, so the same code runs in a Worker, on the main thread and in tests.
import { StepResult } from "./codes.ts";

/** What the loop drives: the Fdm class, or a stand-in in tests. */
export interface Steppable {
  readonly dt: number;
  /** Runs n steps; returns a StepResult code (0 = ok). */
  step(n: number): number;
  /** Outputs before and after the last step. */
  prev: Float64Array;
  curr: Float64Array;
}

export interface LoopOptions {
  /** A frame longer than this is cut to this length (seconds). Default 0.25. */
  maxFrameSeconds?: number;
  /** Most steps one advance() may run: the catch-up cap. Default 8 (4 frames' worth at 120 Hz on a 60 Hz display). */
  maxStepsPerAdvance?: number;
}

export class FixedStepLoop {
  readonly sim: Steppable;
  readonly maxFrameSeconds: number;
  readonly maxStepsPerAdvance: number;

  /** Real time not yet turned into steps; always less than dt after advance(). */
  accumulator = 0;
  paused = false;
  /** Steps run since the loop was created. */
  totalSteps = 0;
  /** Real time thrown away by the frame cut and the step cap: the sim ran slower than real time by this much. */
  droppedSeconds = 0;
  /** Result of the last step call; not OK means the sim ended or failed and the loop has stopped. */
  lastResult: number = StepResult.OK;

  private lastTime: number | null = null;

  constructor(sim: Steppable, options: LoopOptions = {}) {
    this.sim = sim;
    this.maxFrameSeconds = options.maxFrameSeconds ?? 0.25;
    this.maxStepsPerAdvance = options.maxStepsPerAdvance ?? 8;
  }

  /**
   * Call once per frame with the current time in seconds (any monotonic clock).
   * Returns the number of steps run.
   */
  advance(nowSeconds: number): number {
    if (this.paused || this.lastResult !== StepResult.OK) return 0;
    if (this.lastTime === null) {
      // First call, or first call after resume(): only start the clock. No time has passed for the sim.
      this.lastTime = nowSeconds;
      return 0;
    }
    let frame = nowSeconds - this.lastTime;
    this.lastTime = nowSeconds;
    if (!(frame > 0)) return 0;
    if (frame > this.maxFrameSeconds) {
      this.droppedSeconds += frame - this.maxFrameSeconds;
      frame = this.maxFrameSeconds;
    }
    const dt = this.sim.dt;
    this.accumulator += frame;
    // The tiny allowance keeps 60 frames of 1/60 s from giving 119 steps through rounding.
    const due = Math.floor(this.accumulator / dt + 1e-9);
    const steps = Math.min(due, this.maxStepsPerAdvance);
    if (due > steps) this.droppedSeconds += (due - steps) * dt;
    this.accumulator = Math.max(0, this.accumulator - due * dt);
    if (steps > 0) {
      this.lastResult = this.sim.step(steps);
      this.totalSteps += steps;
    }
    return steps;
  }

  /** The page was hidden: stop stepping. */
  pause(): void {
    this.paused = true;
  }

  /** The page is visible again: carry on from now. The hidden time is not caught up. */
  resume(): void {
    this.paused = false;
    this.lastTime = null;
  }

  /** How far the present is between prev (0) and curr (1): for drawing between two physics states. */
  get alpha(): number {
    const a = this.accumulator / this.sim.dt;
    return a < 0 ? 0 : a >= 1 ? 1 - Number.EPSILON : a;
  }
  get prev(): Float64Array {
    return this.sim.prev;
  }
  get curr(): Float64Array {
    return this.sim.curr;
  }
}
