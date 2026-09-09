import json, time, os, sys
SCAN = 'xchain_scan.jsonl'
print(1)
cnt = 0
f = open(SCAN)
print(2)
for _ in f:
    cnt += 1
    if cnt % 5000 == 0:
        print('line', cnt)
print(3, cnt)
