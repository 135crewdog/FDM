// Deterministic force schedule, shared with schedule.py (same arithmetic, only + - * /,
// so JS and Python produce bit-identical inputs).
export function tri(k: number, period: number, phase: number): number {
  // triangle wave in [-1, 1], integer step k
  const x = ((k + phase) % period) / period; // [0,1)
  return x < 0.5 ? 4 * x - 1 : 3 - 4 * x;
}
/** [locX, locY, locZ, dirX, dirY, dirZ, magnitude] for force i at step k. */
export function forceAt(i: number, k: number): number[] {
  return [
    43.2 + 20 * tri(k, 700, 37 * i),
    30 * tri(k, 900, 53 * i),
    59.4 + 10 * tri(k, 500, 11 * i),
    0.3 * tri(k, 400, 7 * i),
    0.2 * tri(k, 300, 13 * i),
    -1,
    40 + 30 * tri(k, 250, 29 * i),
  ];
}
export const SUFFIX = ["location-x-in", "location-y-in", "location-z-in", "x", "y", "z", "magnitude"];
