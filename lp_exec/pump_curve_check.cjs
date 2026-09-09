// pump.fun birth-curve ancestry check for a mint.
// Prints ONE json line: {"exists":bool,"complete":bool,"span_s":number|null}
// span_s = seconds between oldest and newest signature on the curve account
// (farm pattern: instant self-funded graduation -> span < ~120s).
// Usage: node pump_curve_check.cjs <mint>
const { Connection, PublicKey } = require('@solana/web3.js');
const fs = require('fs');
const path = require('path');
const KEY = fs.readFileSync(path.join(__dirname, '..', 'helius_key.txt'), 'utf8').trim();
const PUMP = new PublicKey('6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P');
async function main() {
  const mint = process.argv[2];
  const conn = new Connection(`https://mainnet.helius-rpc.com/?api-key=${KEY}`, 'confirmed');
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from('bonding-curve'), new PublicKey(mint).toBytes()], PUMP);
  const ai = await conn.getAccountInfo(pda);
  if (!ai || ai.data.length < 49) { console.log(JSON.stringify({ exists: false, complete: false, span_s: null })); return; }
  const complete = ai.data[48] === 1;
  let span = null;
  if (complete) {
    const sigs = await conn.getSignaturesForAddress(pda, { limit: 100 });
    const times = sigs.map(s => s.blockTime).filter(Boolean);
    if (times.length >= 2) span = Math.max(...times) - Math.min(...times);
    else if (times.length === 1) span = 0;
  }
  console.log(JSON.stringify({ exists: true, complete, span_s: span }));
}
main().catch(e => { console.log(JSON.stringify({ error: String(e.message || e) })); process.exit(2); });
