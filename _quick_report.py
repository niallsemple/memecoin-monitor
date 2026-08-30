import json

state = json.load(open("xchain_outcomes.json"))
rows = sorted(state.values(), key=lambda s: s.get("entry_t", 0))

closed = [s["ret"] for s in rows if s["status"] == "closed"]
open_ = [s for s in rows if s["status"] == "open"]

print("\nCLOSED positions:")
for s in rows:
    if s["status"] == "closed":
        print(f"  {s.get('name','?')[:22]:22s} {s['chain']:6s} {s['exit_reason']:9s} {s['ret']*100:+6.0f}%")

if closed:
    wins = sum(1 for v in closed if v > 0)
    print(f"\nClosed stats: {sum(closed)/len(closed)*100:+.0f}% avg | {wins}/{len(closed)} wins ({wins/len(closed)*100:.0f}%)")

print(f"\nOPEN positions: {len(open_)}")
for s in open_:
    print(f"  {s.get('name','?')[:22]:22s} {s['chain']:6s} peak {s['peak']:.1f}x now {s.get('r_now',1):.1f}x")
