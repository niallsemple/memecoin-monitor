#!/usr/bin/env python3
"""Gated LP deploy driver — deploys ONLY when lp_watchlist.json qualifies the pool.

Owner rule: take action only when the data says. This script refuses to deploy
unless the target pool is in the deploy-grade watchlist written by
meteora_lp_ranker.py (age>=30d candles, IL<1%/d, vol_alive>=0.5, fa_disabled,
net>=2%/d). No override flag exists — if the data doesn't qualify, it exits.

Usage: python3 lp_deploy_watchlist.py <pool-name-or-address> [sol] [widthPct]
Default: XMR-SOL, 0.5 SOL, 0.56 width (wide arm, 2x the v1 narrow range).
"""
import json, os, subprocess, sys, time
from pathlib import Path

MON = Path(__file__).resolve().parent
WATCHLIST = MON / "lp_watchlist.json"
RANKER_REPORT = MON / "meteora_lp_ranker_report.json"
BUNDLE = MON / "lp_exec" / "meteora_lp.bundle.cjs"
HELIUS_KEY = (MON / "helius_key.txt").read_text().strip()
WALLET = json.loads((MON / "live_wallet.json").read_text())


def wallet_pubkey() -> str:
    try:
        from solders.keypair import Keypair  # type: ignore
        return str(Keypair.from_bytes(bytes(WALLET["keypair_bytes"])).pubkey())
    except Exception:
        # fall back to last known address file
        return "CQcKkSee9bdHZ1bejYFDUXVtodbfKHe2KSx6AaAnTW2K"


def sol_balance() -> float:
    import urllib.request
    req = urllib.request.Request(
        f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getBalance",
                         "params": [wallet_pubkey()]}).encode(),
        headers={"Content-Type": "application/json"})
    r = json.loads(urllib.request.urlopen(req, timeout=20).read())
    return r["result"]["value"] / 1e9


def size_arm(hit, bal, explicit=None):
    """Data-driven arm size. Explicit CLI size always wins (manual runs).
    Tier S (spicy, net>=2%/d): 0.5 SOL baseline, 1.0 SOL when net >= 20%/d.
    Tier A (safe majors, net 0.15-2%/d, IL~0): 1.0 SOL baseline — the tier-A
    model (tier_a_lp_model.py) showed rent economics only work with size;
    1.0 SOL on a 0.2%/d pool breaks even in ~1.4 days vs 2.9 days at 0.5.
    Hard cap 12% of free balance; hard reserve 0.15 SOL."""
    if explicit is not None:
        return explicit
    net = hit.get("net_daily_lp") or 0
    if hit.get("tier") == "A":
        arm = 1.0
    else:
        arm = 1.0 if net >= 0.20 else 0.5
    cap = max(0.0, (bal - 0.15) * 0.12)
    return round(max(0.0, min(arm, cap)), 3)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "XMR-SOL"
    sol_arg = float(sys.argv[2]) if len(sys.argv) > 2 else None
    width = float(sys.argv[3]) if len(sys.argv) > 3 else 0.56

    wl = json.loads(WATCHLIST.read_text())
    pools = wl.get("pools", [])
    print(f"watchlist generated {wl.get('generated_utc')} — {len(pools)} qualified")
    if target.upper() == "AUTO":
        if not pools:
            print("REFUSED: AUTO mode, 0 pools qualified. Data does not say go.")
            sys.exit(3)
        hit = pools[0]  # ranker writes deploy-grade list in net-yield order
        print(f"AUTO selected top-qualified pool: {hit.get('name')}")
    else:
        hit = next((p for p in pools
                    if target.lower() in (p.get("name", "") + p.get("address", "")).lower()), None)
    if not hit:
        names = [p.get("name") for p in pools]
        print(f"REFUSED: '{target}' not in qualified watchlist {names}. "
              f"Data does not say go. Run meteora_lp_ranker.py for a fresh scan.")
        sys.exit(3)

    # duplicate protection: never stack a second position on a pool we already hold
    pos_state = json.loads((MON / "lp_positions.json").read_text())
    if any(p.get("pool") == hit["address"] and p.get("status") == "open"
           for p in pos_state.get("positions", [])):
        print(f"REFUSED: already holding an open position on {hit.get('name')}.")
        sys.exit(4)

    # freshness gate: watchlist must be < 26h old
    gen = time.strptime(wl["generated_utc"], "%Y-%m-%d %H:%M")
    import calendar
    age_h = (time.time() - calendar.timegm(gen)) / 3600
    if age_h > 26:
        print(f"REFUSED: watchlist is {age_h:.1f}h old — rerun ranker first.")
        sys.exit(3)

    bal = sol_balance()
    sol = size_arm(hit, bal, sol_arg)
    need = sol + 0.10  # rent + tx fee reserve
    print(f"wallet {wallet_pubkey()} balance {bal:.4f} SOL; arm {sol} SOL"
          f"{' (CLI override)' if sol_arg is not None else ' (auto-sized)'}; need {need:.2f}")
    if sol <= 0 or bal < need:
        print("REFUSED: insufficient balance for the sized arm.")
        sys.exit(3)

    print(f"QUALIFIED: {hit.get('name')} [tier {hit.get('tier','S')}] net={hit.get('net_daily_lp', 0)*100:.2f}%/d "
          f"il={hit.get('il_daily_avg7', 0)*100:.3f}%/d days={hit.get('days')} — deploying "
          f"{sol} SOL at {width*100:.0f}% width (tag wide_arm_v2)")
    cmd = ["node", str(BUNDLE), "add", hit["address"], str(sol), str(width), "wide_arm_v2"]
    if os.environ.get("LP_DRY_RUN") == "1":
        print(f"DRY RUN — would execute: {' '.join(cmd)}")
        print("DRY RUN OK: all gates passed, sizing done, command assembled. No tx sent.")
        sys.exit(0)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    print(r.stdout.strip())
    if r.returncode != 0:
        print("DEPLOY FAILED:", r.stderr.strip()[:500])
        sys.exit(2)
    print("DEPLOYED. Guardian automation is already armed (no-op until a position is open); "
          "it will watch floor/blacklist/TVL, compound fees, and re-center if price runs above range.")


if __name__ == "__main__":
    main()
