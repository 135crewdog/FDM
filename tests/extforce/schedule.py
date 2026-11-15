"""Python copy of schedule.ts (same arithmetic)."""
def tri(k, period, phase):
    x = ((k + phase) % period) / period
    return 4 * x - 1 if x < 0.5 else 3 - 4 * x

def force_at(i, k):
    return [43.2 + 20 * tri(k, 700, 37 * i),
            30 * tri(k, 900, 53 * i),
            59.4 + 10 * tri(k, 500, 11 * i),
            0.3 * tri(k, 400, 7 * i),
            0.2 * tri(k, 300, 13 * i),
            -1,
            40 + 30 * tri(k, 250, 29 * i)]

SUFFIX = ["location-x-in", "location-y-in", "location-z-in", "x", "y", "z", "magnitude"]
