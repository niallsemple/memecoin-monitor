#!/usr/bin/env python3
"""deployer_local.py — at-birth deployer scorecard from OUR OWN birth feed.

curves.jsonl has recorded every pump.fun create (with deployer key) for
weeks. Repeat offenders we've seen before are flagged instantly, zero RPC.

Outcome labels come from live_positions.json (our own closes). Mints we
never traded are 'unknown' — conservative: only known rugs count against.
"""
import json, time
from pathlib import Path

MON = Path(__file__).parent
CURVES = MON / "curves.jsonl"
POSITIONS = MON / "live_positions.json"
RUG_REASONS = ("panic", "panic_writeoff", "rug")  # closes that mean rugged


def _load_creates():
    by_dep = {}
    try:
        with open(CURVES) as f:
            for line in f:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("txType") != "create":
                    continue
                dep = d.get("traderPublicKey")
                mint = d.get("mint")
                if dep and mint:
                    by_dep.setdefault(dep, []).append(mint)
    except FileNotFoundError:
        pass
    return by_dep


def deployer_of(mint):
    """Find the deployer of a mint from our own birth feed."""
    try:
        with open(CURVES) as f:
            for line in f:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("txType") == "create" and d.get("mint") == mint:
                    return d.get("traderPublicKey")
    except FileNotFoundError:
        pass
    return None


def score_mint(mint):
    """Shadow score for an incoming mint: deployer + prior history,
    excluding the mint itself."""
    dep = deployer_of(mint)
    if not dep:
        return {"deployer": None, "prior": 0, "prior_rugs": 0}
    r = lookup(dep)
    others = [m for m in r["prior_mints"] if m != mint]
    try:
        pos = json.loads(POSITIONS.read_text())
    except Exception:
        pos = {}
    rugs = 0
    for m in others:
        v = pos.get(m)
        if isinstance(v, dict) and not v.get("open"):
            rr = (v.get("exit_reason") or v.get("closed_reason") or "")
            if any(rr.startswith(x) for x in RUG_REASONS):
                rugs += 1
    return {"deployer": dep, "prior": len(others), "prior_rugs": rugs}


def lookup(deployer):
    """Return {'prior': n_other_mints, 'prior_rugs': k, 'prior_mints': [...]}."""
    if not deployer:
        return {"prior": 0, "prior_rugs": 0, "prior_mints": []}
    mints = _load_creates().get(deployer, [])
    try:
        pos = json.loads(POSITIONS.read_text())
    except Exception:
        pos = {}
    rugs = 0
    for m in mints:
        v = pos.get(m)
        if isinstance(v, dict) and not v.get("open"):
            r = (v.get("exit_reason") or v.get("closed_reason") or "")
            if any(r.startswith(x) for x in RUG_REASONS):
                rugs += 1
    return {"prior": len(mints), "prior_rugs": rugs, "prior_mints": mints}


if __name__ == "__main__":
    import sys
    for dep in sys.argv[1:]:
        r = lookup(dep)
        print(dep[:8], "prior launches:", r["prior"], "prior rugs:", r["prior_rugs"])
