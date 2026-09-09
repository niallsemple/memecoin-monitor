// Read pump.fun bonding curve state for a list of mints. Usage: node curve_state.cjs <mint> <ageH> ...
const { Connection, PublicKey } = require('@solana/web3.js');
const fs = require('fs');
const path = require('path');
const KEY = fs.readFileSync(path.join(__dirname, '..', 'helius_key.txt'), 'utf8').trim();
const PUMP = new PublicKey('6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P');
async function main() {
  const conn = new Connection(`https://mainnet.helius-rpc.com/?api-key=${KEY}`, 'confirmed');
  const args = process.argv.slice(2);
  console.log('age_h | vSOL | realSOL | complete | mint');
  for (let i = 0; i < args.length; i += 2) {
    const mint = args[i], ageH = parseFloat(args[i+1]);
    try {
      const [pda] = PublicKey.findProgramAddressSync(
        [Buffer.from('bonding-curve'), new PublicKey(mint).toBytes()], PUMP);
      const ai = await conn.getAccountInfo(pda);
      if (!ai) { console.log(`${ageH.toFixed(1)} | -- | -- | no-account | ${mint.slice(0,16)}`); continue; }
      const d = ai.data;
      const vs = Number(d.readBigUInt64LE(16)) / 1e9;   // virtualSolReserves (after 8b disc + 8b vToken)
      const rs = Number(d.readBigUInt64LE(32)) / 1e9;   // realSolReserves
      const complete = d[48] === 1;
      console.log(`${ageH.toFixed(1)} | ${vs.toFixed(3)} | ${rs.toFixed(3)} | ${complete} | ${mint.slice(0,16)}`);
    } catch (e) { console.log(`${ageH} | ERR ${e.message.slice(0,40)} | ${mint.slice(0,16)}`); }
  }
}
main();
