#!/usr/bin/env python3
"""Pure-python keccak-256 (no deps). Verified against the Transfer topic."""
RC = [0x0000000000000001,0x0000000000008082,0x800000000000808A,0x8000000080008000,
      0x000000000000808B,0x0000000080000001,0x8000000080008081,0x8000000000008009,
      0x000000000000008A,0x0000000000000088,0x0000000080008009,0x000000008000000A,
      0x000000008000808B,0x800000000000008B,0x8000000000008089,0x8000000000008003,
      0x8000000000008002,0x8000000000000080,0x000000000000800A,0x800000008000000A,
      0x8000000080008081,0x8000000000008080,0x0000000080000001,0x8000000080008008]
ROT = [[0,36,3,41,18],[1,44,10,45,2],[62,6,43,15,61],[28,55,25,21,56],[27,20,39,8,14]]
MASK = (1<<64)-1

def _rol(x, n):
    return ((x << n) | (x >> (64-n))) & MASK if n else x

def _permute(a):
    for rc in RC:
        c = [a[x]^a[x+5]^a[x+10]^a[x+15]^a[x+20] for x in range(5)]
        d = [c[(x-1)%5] ^ _rol(c[(x+1)%5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                a[x+5*y] ^= d[x]
        b = [0]*25
        for x in range(5):
            for y in range(5):
                b[y + 5*((2*x+3*y)%5)] = _rol(a[x+5*y], ROT[x][y])
        for x in range(5):
            for y in range(5):
                a[x+5*y] = b[x+5*y] ^ ((~b[(x+1)%5+5*y] & MASK) & b[(x+2)%5+5*y])
        a[0] ^= rc

def keccak256(data: bytes) -> bytes:
    rate = 136  # 1088-bit rate for 256-bit output
    a = [0]*25
    padded = bytearray(data)
    padded.append(0x01)
    while len(padded) % rate != rate-1:
        padded.append(0)
    padded.append(0x80)
    for off in range(0, len(padded), rate):
        block = padded[off:off+rate]
        for i in range(rate//8):
            a[i] ^= int.from_bytes(block[i*8:(i+1)*8], 'little')
        _permute(a)
    out = b''
    for i in range(4):
        out += a[i].to_bytes(8, 'little')
    return out[:32]

if __name__ == '__main__':
    t = keccak256(b"Transfer(address,address,uint256)").hex()
    exp = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    print("Transfer topic:", t)
    print("MATCH" if t == exp else "MISMATCH!")
    e = keccak256(b'').hex()
    print("empty:", e, "MATCH" if e == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470" else "MISMATCH!")
