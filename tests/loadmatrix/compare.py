"""Test 1 report: load matrix, ours vs native. Pass = everything that loads natively loads in ours."""
import json, sys
nat = {r["name"]: r for r in json.load(open("out/loadmatrix.native.json"))}
variants = [v for v in sys.argv[1:]] or ["jsbsim"]
ok_all = True
for v in variants:
    ours = {r["name"]: r for r in json.load(open(f"out/loadmatrix.{v}.json"))}
    print(f"\n## {v} vs native ({len(nat)} aircraft folders)\n")
    print(f"{'aircraft':18s} {'native':7s} {'ours':5s}  message (ours, else native)")
    for n in sorted(nat):
        a, b = nat[n], ours.get(n, {"ok": False, "msg": "missing"})
        flag = "" if a["ok"] == b["ok"] else ("   <-- FAIL: loads natively only" if a["ok"] else "   <-- loads only in ours")
        msg = (b["msg"] or a["msg"])[:150]
        print(f"{n:18s} {'ok' if a['ok'] else 'FAIL':7s} {'ok' if b['ok'] else 'FAIL':5s}  {msg}{flag}")
    lost = [n for n in nat if nat[n]["ok"] and not ours.get(n, {}).get("ok")]
    gained = [n for n in nat if not nat[n]["ok"] and ours.get(n, {}).get("ok")]
    print(f"\nnative loads {sum(r['ok'] for r in nat.values())}, ours loads {sum(r['ok'] for r in ours.values())}")
    print(f"load natively but not in ours: {lost or 'none'}")
    print(f"load in ours but not natively: {gained or 'none'}")
    print("RESULT:", "PASS" if not lost else "FAIL")
    ok_all &= not lost
sys.exit(0 if ok_all else 1)
