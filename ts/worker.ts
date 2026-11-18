// Browser Web Worker entry point: the game path. All the logic is in worker-handler.ts.
import { type Request, createHandler } from "./worker-handler.ts";

const scope = self as unknown as { postMessage(message: unknown, transfer?: ArrayBuffer[]): void; onmessage: ((e: MessageEvent) => void) | null };
const handle = createHandler((message, transfer) => scope.postMessage(message, transfer ?? []));
scope.onmessage = (e: MessageEvent) => {
  void handle(e.data as Request);
};
