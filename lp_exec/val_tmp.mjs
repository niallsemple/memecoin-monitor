import { Connection, PublicKey } from '@solana/web3.js';
import { DLMM } from '/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor/lp_exec/vendor/dlmm.patched.mjs';
import fs from 'fs';
async function main(){
const k = fs.readFileSync('/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor/helius_key.txt','utf8').trim();
const conn = new Connection(`https://mainnet.helius-rpc.com/?api-key=${k}`, 'confirmed');
const pools = {
  'XMR-SOL': 'D5ozarJBkGKRw7ceuftyS31cqrjooTnKyvDhNeME79bE',
  'KNOTS-SOL': 'nBXytBBfKLhj6teXarAv8rk6WNgUFBMyybUFRkuK7ad',
  'Pumpcat-SOL': 'EqsbD725iSoa23kWnQBjiYT9bcWSH8YJ6WCPYwXYoVNR',
};
const wallet = JSON.parse(fs.readFileSync('/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor/live_wallet.json'));
const owner = new PublicKey(wallet.address);
for (const [name, pa] of Object.entries(pools)) {
  const pool = await DLMM.create(conn, new PublicKey(pa));
  const { userPositions } = await pool.getPositionsByUserAndLbPair(owner);
  for (const pos of userPositions) {
    const d = pos.positionData;
    const x = d.totalXAmount ? d.totalXAmount.toString() : '?';
    const y = d.totalYAmount ? d.totalYAmount.toString() : '?';
    console.log(name, pos.publicKey.toBase58().slice(0,8), 'X=', x, 'Y=', y,
      'feeX=', d.feeX?.toString(), 'feeY=', d.feeY?.toString());
  }
}
}
main().catch(e=>{console.error('ERR', e.message)});
