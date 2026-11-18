// Getting JSBSim's data files into the module's in-memory file system.
// The module never reads the host's disk or the network itself: the caller writes the files it needs.
import type { FdmModule } from "./core.ts";

/** A set of files: path relative to some root -> bytes. */
export type FileSet = Map<string, Uint8Array>;

/** Writes every file of the set under `mountPoint` (for example "/data"). */
export function writeFiles(module: FdmModule, mountPoint: string, files: FileSet): void {
  for (const [path, bytes] of files) module.writeFile(`${mountPoint}/${path}`, bytes);
}

// --- pack: many files in one download ------------------------------------------------------------------------
// Layout: 4 bytes little-endian = length of the index; the index as UTF-8 JSON [[path, offset, length], ...];
// then the file bytes.

export function buildPack(files: FileSet): Uint8Array {
  const index: [string, number, number][] = [];
  let offset = 0;
  for (const [path, bytes] of files) {
    index.push([path, offset, bytes.length]);
    offset += bytes.length;
  }
  const head = new TextEncoder().encode(JSON.stringify(index));
  const pack = new Uint8Array(4 + head.length + offset);
  new DataView(pack.buffer).setUint32(0, head.length, true);
  pack.set(head, 4);
  let at = 4 + head.length;
  for (const bytes of files.values()) {
    pack.set(bytes, at);
    at += bytes.length;
  }
  return pack;
}

export function readPack(pack: Uint8Array): FileSet {
  const headLength = new DataView(pack.buffer, pack.byteOffset, pack.byteLength).getUint32(0, true);
  const index = JSON.parse(new TextDecoder().decode(pack.subarray(4, 4 + headLength))) as [string, number, number][];
  const base = 4 + headLength;
  const files: FileSet = new Map();
  for (const [path, offset, length] of index) files.set(path, pack.subarray(base + offset, base + offset + length));
  return files;
}
