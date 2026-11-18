// The message handler that runs JSBSim off the main thread. It knows nothing about where it runs:
// ts/worker.ts wires it to a browser Worker, tests wire it to Node (directly and through worker_threads).
//
// Every request carries an id and gets exactly one reply with the same id:
//   { id, ok: true, ...result }   or   { id, ok: false, error: string, crash: boolean }
// Unasked messages from the worker have no id: { type: "event", event } and { type: "log", record }.
import { type BenchOptions, benchSteps } from "./bench.ts";
import { StepResult } from "./codes.ts";
import { Fdm, FdmCrash, type FdmEvent, type FdmFactory, type FdmModule, type GroundGrid, loadFdmModule } from "./core.ts";
import { readPack, writeFiles } from "./files.ts";
import { FixedStepLoop, type LoopOptions } from "./loop.ts";

export type Request =
  /** Load the WebAssembly module. moduleUrl: URL of fdm-weh.mjs / fdm-jseh.mjs. packs: [mount point, pack bytes]. */
  | { id: number; type: "init"; moduleUrl: string; wasmBinary?: ArrayBuffer | Uint8Array; packs?: [string, Uint8Array][]; forwardLogs?: boolean }
  /** Add files after init. */
  | { id: number; type: "files"; mountPoint: string; pack: Uint8Array }
  /** Create the instance, load, bind, RunIC, and start the loop (paused until the first tick). */
  | {
      id: number; type: "create"; dt?: number; root?: string; paths?: { aircraft: string; engine: string; systems: string };
      model?: string; script?: string; initfile?: string; ic?: string; ground?: GroundGrid;
      outputs: string[]; inputs?: string[]; loop?: LoopOptions;
    }
  /** One frame: now in seconds. inputs (optional) are held for every step of this frame. */
  | { id: number; type: "tick"; now: number; inputs?: Float64Array }
  | { id: number; type: "pause" }
  | { id: number; type: "resume" }
  | { id: number; type: "dispose" }
  | { id: number; type: "bench"; options: Omit<BenchOptions, "now"> }
  /** 20 create/load/step/destroy cycles; replies with heap bytes in use after each. */
  | { id: number; type: "cycles"; count: number; model: string; ic: string; steps: number }
  /** Tries to load an aircraft; replies loaded true, or loaded false with JSBSim's message. */
  | { id: number; type: "tryload"; model: string; paths?: { aircraft: string; engine: string; systems: string } };

export type Post = (message: Record<string, unknown>, transfer?: ArrayBuffer[]) => void;

export function createHandler(post: Post): (request: Request) => Promise<void> {
  let module: FdmModule | undefined;
  let fdm: Fdm | undefined;
  let loop: FixedStepLoop | undefined;
  let inputsView: Float64Array | undefined;

  const need = (): FdmModule => {
    if (!module) throw new Error("not initialised: send init first");
    return module;
  };
  const onEvent = (event: FdmEvent): void => post({ type: "event", event });

  async function run(req: Request): Promise<Record<string, unknown> | [Record<string, unknown>, ArrayBuffer[]]> {
    switch (req.type) {
      case "init": {
        const factory = (await import(/* @vite-ignore */ req.moduleUrl)).default as FdmFactory;
        module = await loadFdmModule(factory, {
          wasmBinary: req.wasmBinary,
          onLog: req.forwardLogs ? (record) => post({ type: "log", record }) : undefined,
        });
        for (const [mountPoint, pack] of req.packs ?? []) writeFiles(module, mountPoint, readPack(pack));
        return { version: module.version(), memoryBytes: module.memoryBytes() };
      }
      case "files": {
        writeFiles(need(), req.mountPoint, readPack(req.pack));
        return {};
      }
      case "create": {
        const m = need();
        if (fdm) fdm.dispose();
        fdm = Fdm.create(m, { dt: req.dt, root: req.root, paths: req.paths, ground: req.ground, onEvent });
        if (req.script) fdm.loadScript(req.script, req.initfile ?? "");
        else fdm.loadModel(req.model!);
        if (req.ic) fdm.loadIC(req.ic);
        fdm.bindOutputs(req.outputs);
        inputsView = fdm.bindInputs(req.inputs ?? []);
        fdm.runIC();
        loop = new FixedStepLoop(fdm, req.loop);
        return { dt: fdm.dt, outputs: fdm.outputNames, simTime: fdm.simTime, curr: Float64Array.from(fdm.curr) };
      }
      case "tick": {
        if (!fdm || !loop) throw new Error("no instance: send create first");
        if (req.inputs && inputsView) inputsView.set(req.inputs);
        const steps = loop.advance(req.now);
        // Copies: the views point into WebAssembly memory, which never leaves the worker.
        const prev = Float64Array.from(loop.prev);
        const curr = Float64Array.from(loop.curr);
        return [
          { steps, alpha: loop.alpha, simTime: fdm.simTime, result: loop.lastResult, ended: loop.lastResult !== StepResult.OK,
            totalSteps: loop.totalSteps, droppedSeconds: loop.droppedSeconds, prev, curr },
          [prev.buffer, curr.buffer],
        ];
      }
      case "pause":
        if (loop) loop.pause();
        return {};
      case "resume":
        if (loop) loop.resume();
        return {};
      case "dispose":
        if (fdm) fdm.dispose();
        fdm = undefined;
        loop = undefined;
        return {};
      case "bench":
        return { result: benchSteps(need(), req.options) };
      case "cycles": {
        const m = need();
        const heap: number[] = [];
        for (let i = 0; i < req.count; i++) {
          const f = Fdm.create(m);
          try {
            f.loadModel(req.model);
            f.loadIC(req.ic);
            f.runIC();
            if (f.step(req.steps) !== StepResult.OK) throw new Error("cycle step failed");
          } finally {
            f.dispose();
          }
          heap.push(m.heapInUse());
        }
        return { heap, heapTop: m.heapTop(), memoryBytes: m.memoryBytes() };
      }
      case "tryload": {
        const f = Fdm.create(need(), { paths: req.paths });
        try {
          f.loadModel(req.model);
          return { loaded: true };
        } catch (e) {
          if (e instanceof FdmCrash) throw e;
          return { loaded: false, errorName: (e as Error).name, isError: e instanceof Error, message: (e as Error).message };
        } finally {
          f.dispose();
        }
      }
    }
  }

  return async (req: Request): Promise<void> => {
    try {
      const out = await run(req);
      if (Array.isArray(out)) post({ id: req.id, ok: true, ...out[0] }, out[1]);
      else post({ id: req.id, ok: true, ...out });
    } catch (e) {
      const crash = e instanceof FdmCrash;
      if (crash) post({ type: "event", event: { type: "crash", reason: "trap", message: (e as Error).message, simTime: NaN, step: -1 } });
      post({ id: req.id, ok: false, error: e instanceof Error ? e.message : String(e), crash });
    }
  };
}

/** Client side: turns postMessage traffic into promises. Works with a browser Worker or a Node Worker. */
export class WorkerClient {
  onEvent: ((event: FdmEvent) => void) | undefined;
  onLog: ((record: unknown) => void) | undefined;
  private nextId = 1;
  private pending = new Map<number, { resolve: (v: any) => void; reject: (e: Error) => void }>();
  private send: (message: unknown, transfer?: ArrayBuffer[]) => void;

  constructor(send: (message: unknown, transfer?: ArrayBuffer[]) => void) {
    this.send = send;
  }

  /** Feed every message that arrives from the worker into this. */
  receive(message: any): void {
    if (message && message.type === "event") {
      if (this.onEvent) this.onEvent(message.event);
      return;
    }
    if (message && message.type === "log") {
      if (this.onLog) this.onLog(message.record);
      return;
    }
    const p = this.pending.get(message.id);
    if (!p) return;
    this.pending.delete(message.id);
    if (message.ok) p.resolve(message);
    else p.reject(new Error(message.error));
  }

  /** Fails every request still waiting (the worker died). */
  failAll(reason: string): void {
    for (const p of this.pending.values()) p.reject(new Error(reason));
    this.pending.clear();
  }

  request<T = any>(body: Record<string, unknown>, transfer?: ArrayBuffer[]): Promise<T> {
    const id = this.nextId++;
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.send({ ...body, id }, transfer);
    });
  }
}
