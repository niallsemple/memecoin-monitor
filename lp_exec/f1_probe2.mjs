import { Connection, Keypair, PublicKey, TransactionInstruction, TransactionMessage, VersionedTransaction, SystemProgram } from '@solana/web3.js';
import { createHash } from 'crypto';
import fs from 'fs';
import path from 'path';

const MON = path.dirname(new URL(import.meta.url).pathname) + '/..';
const PROG = new PublicKey('LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo');
const key = fs.readFileSync(path.join(MON, 'helius_key.txt'), 'utf8').trim();
const conn = new Connection(`https://mainnet.helius-rpc.com/?api-key=${key}`, 'confirmed');
const wraw = JSON.parse(fs.readFileSync(path.join(MON, 'live_wallet.json')));
const wallet = Keypair.fromSecretKey(Uint8Array.from(wraw.keypair_bytes));
const ZERO32 = '11111111111111111111111111111111';

const empties = await conn.getProgramAccounts(PROG, {
  filters: [{ dataSize: 8120 }, { memcmp: { offset: 72, bytes: ZERO32 } }],
  dataSlice: { offset: 40, length: 32 }, encoding: 'base64',
});
console.log('empty positions chain-wide:', empties.length);
const foreign = empties.filter(a => {
  const raw = Array.isArray(a.account.data) ? a.account.data[0] : a.account.data;
  const buf = Buffer.isBuffer(raw) ? raw : Buffer.from(raw, 'base64');
  return new PublicKey(buf).toBase58() !== wallet.publicKey.toBase58();
});
console.log('foreign empties:', foreign.length, '≈ rent', (foreign.length * 0.0419).toFixed(1), 'SOL');
if (!foreign.length) process.exit(0);
const target = foreign[0].pubkey;
console.log('probe target:', target.toBase58());

const disc = createHash('sha256').update('global:close_position_if_empty').digest().subarray(0, 8);
const [eventAuth] = PublicKey.findProgramAddressSync([Buffer.from('__event_authority')], PROG);
const ix = new TransactionInstruction({
  programId: PROG,
  keys: [
    { pubkey: target, isSigner: false, isWritable: true },
    { pubkey: wallet.publicKey, isSigner: true, isWritable: false },
    { pubkey: wallet.publicKey, isSigner: false, isWritable: true },
    { pubkey: eventAuth, isSigner: false, isWritable: false },
    { pubkey: PROG, isSigner: false, isWritable: false },
  ],
  data: Buffer.from(disc),
});
const { blockhash } = await conn.getLatestBlockhash();
const msg = new TransactionMessage({ payerKey: wallet.publicKey, recentBlockhash: blockhash, instructions: [ix] }).compileToV0Message();
const vtx = new VersionedTransaction(msg);
vtx.sign([wallet]);
const sim = await conn.simulateTransaction(vtx);
console.log('simulation err:', JSON.stringify(sim.value.err));
console.log('logs tail:', (sim.value.logs || []).slice(-5).join(' | '));
