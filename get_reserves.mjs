import { Connection, PublicKey } from '@solana/web3.js';
import DLMM from './lp_exec/vendor/dlmm.patched.mjs';
import fs from 'fs';
const key = fs.readFileSync('helius_key.txt','utf8').trim();
const conn = new Connection(`https://mainnet.helius-rpc.com/?api-key=${key}`);
const pool = await DLMM.create(conn, new PublicKey('nBXytBBfKLhj6teXarAv8rk6WNgUFBMyybUFRkuK7ad'));
console.log(JSON.stringify({
  reserveX: pool.lbPair.reserveX.toBase58(),
  reserveY: pool.lbPair.reserveY.toBase58(),
  tokenX: pool.lbPair.tokenXMint.toBase58(),
  tokenY: pool.lbPair.tokenYMint.toBase58(),
}));
