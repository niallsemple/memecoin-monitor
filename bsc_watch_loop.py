#!/usr/bin/env python3
"""
bsc_watch_loop.py — run evm_watcher.main(chain) every POLL seconds for WINDOW
minutes. Backwards-compatible name: default chain is bsc (the deployed BSC
automation calls `python3 bsc_watch_loop.py 19`).

Usage: python3 bsc_watch_loop.py [window_min] [chain]
"""
import time, traceback, sys
import evm_watcher
import fast_discover

WINDOW_MIN = 19
POLL_S = 5


def run(window_min=WINDOW_MIN, chains=('bsc',), poll_s=POLL_S):
    end = time.time() + window_min * 60
    cycles = errs = 0
    # fast discovery first: fresh pools enter xchain_scan.jsonl within
    # minutes of launch instead of waiting for the hourly scan
    try:
        fast_discover.main(list(chains))
    except Exception:
        traceback.print_exc()
    while time.time() < end:
        t0 = time.time()
        for chain in chains:
            try:
                evm_watcher.main(chain)
            except Exception:
                errs += 1
                traceback.print_exc()
        cycles += 1
        if cycles % 40 == 0:          # ~every 5 min: catch mid-window launches
            try:
                fast_discover.main(list(chains))
            except Exception:
                traceback.print_exc()
        dt = time.time() - t0
        time.sleep(max(0.5, poll_s - dt))
    print(f'loop done ({",".join(chains)}): {cycles} cycles, {errs} errors, {window_min} min')


if __name__ == '__main__':
    w = float(sys.argv[1]) if len(sys.argv) > 1 else WINDOW_MIN
    cs = tuple((sys.argv[2] if len(sys.argv) > 2 else 'bsc').split(','))
    run(w, cs)
