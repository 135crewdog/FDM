// Node worker_threads entry point: the same handler as the browser Worker (ts/worker.ts).
import { parentPort } from "node:worker_threads";

import { type Request, createHandler } from "../../ts/worker-handler.ts";

const port = parentPort!;
const handle = createHandler((message, transfer) => port.postMessage(message, transfer ?? []));
port.on("message", (request: Request) => {
  void handle(request);
});
