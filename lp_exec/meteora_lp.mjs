// Meteora DLMM LP execution tool — add/exit/claim/status for the owner wallet.
// Single-sided SOL (quote) deposits, Spot strategy, bins [active-BINS_BELOW, active].
// Wallet: ../live_wallet.json (keypair_bytes). RPC: Helius key from ../helius_key.txt.
// State: ../lp_positions.json records every open position for the watcher/exiter.
//
// Usage: node meteora_lp.bundle.cjs <status|add|exit|claim> [poolAddr] [solAmount]
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { Connection, Keypair, PublicKey, LAMPORTS_PER_SOL, sendAndConfirmTransaction, ComputeBudgetProgram } from '@solana/web3.js';
import { DLMM, StrategyType } from './vendor/dlmm.patched.mjs';
import BN from 'bn.js';

// __dirname works in the esbuild CJS bundle
const HERE = __dirname;
const MON = path.resolve(HERE, '..');
const STATE_F = path.join(MON, 'lp_positions.json');
const BINS_BELOW = 30;               // ~30 bin-steps below active (scaled by binStep at runtime)
const MAX_BINS_PER_TX = 68;          // DLMM position width cap is 70; stay under

function loadWallet() {
  const d = JSON.parse(fs.readFileSync(path.join(MON, 'live_wallet.json')));
  return Keypair.fromSecretKey(Uint8Array.from(d.keypair_bytes));
}
function rpc() {
  const k = fs.readFileSync(path.join(MON, 'helius_key.txt'), 'utf8').trim();
  return new Connection(`https://mainnet.helius-rpc.com/?api-key=${k}`, 'confirmed');
}
function loadState() { try { return JSON.parse(fs.readFileSync(STATE_F)); } catch { return { positions: [] }; } }
function saveState(s) { fs.writeFileSync(STATE_F, JSON.stringify(s, null, 1)); }

const PRIORITY_UPL = parseInt(process.env.PRIORITY_UPL || '100000', 10); // ~0.00004 SOL at 400k CU
async function sendTx(conn, tx, extraSigners, wallet) {
  tx.feePayer = wallet.publicKey;
  tx.instructions.unshift(
    ComputeBudgetProgram.setComputeUnitLimit({ units: 400000 }),
    ComputeBudgetProgram.setComputeUnitPrice({ microLamports: PRIORITY_UPL }),
  );
  const { blockhash, lastValidBlockHeight } = await conn.getLatestBlockhash('confirmed');
  tx.recentBlockhash = blockhash;
  tx.sign(...extraSigners, wallet);
  const sig = await conn.sendRawTransaction(tx.serialize(), { skipPreflight: false, maxRetries: 3 });
  await conn.confirmTransaction({ signature: sig, blockhash, lastValidBlockHeight }, 'confirmed');
  return sig;
}

async function cmdStatus(conn, wallet) {
  const bal = await conn.getBalance(wallet.publicKey);
  console.log(`wallet ${wallet.publicKey.toBase58()}  balance ${(bal / LAMPORTS_PER_SOL).toFixed(6)} SOL`);
  const st = loadState();
  for (const p of st.positions.filter(x => x.status === 'open')) {
    const pool = await DLMM.create(conn, new PublicKey(p.pool));
    const ab = await pool.getActiveBin();
    const { userPositions } = await pool.getPositionsByUserAndLbPair(wallet.publicKey);
    const mine = userPositions.find(u => u.publicKey.toBase58() === p.position);
    if (!mine) { console.log(`${p.name}: position not found on-chain`); continue; }
    const d = mine.positionData;
    const inRange = ab.binId >= d.lowerBinId && ab.binId <= d.upperBinId;
    console.log(`${p.name}: bins ${d.lowerBinId}..${d.upperBinId} active=${ab.binId} inRange=${inRange} ` +
      `fees X=${d.feeX?.toString()} Y=${d.feeY?.toString()}`);
  }
}

async function cmdStatusJson(conn, wallet) {
  const st = loadState();
  const out = [];
  for (const p of st.positions.filter(x => x.status === 'open')) {
    try {
      const pool = await DLMM.create(conn, new PublicKey(p.pool));
      const ab = await pool.getActiveBin();
      const { userPositions } = await pool.getPositionsByUserAndLbPair(wallet.publicKey);
      const mine = userPositions.find(u => u.publicKey.toBase58() === p.position);
      if (!mine) { out.push({ position: p.position, pool: p.pool, name: p.name, error: 'not_onchain' }); continue; }
      const d = mine.positionData;
      out.push({
        position: p.position, pool: p.pool, name: p.name,
        activeBin: ab.binId, lowerBinId: d.lowerBinId, upperBinId: d.upperBinId,
        inRange: ab.binId >= d.lowerBinId && ab.binId <= d.upperBinId,
        feeX_lamports: d.feeX?.toString(), feeY_lamports: d.feeY?.toString(),
      });
    } catch (e) {
      out.push({ position: p.position, pool: p.pool, name: p.name, error: String(e.message || e) });
    }
  }
  console.log(JSON.stringify(out));
}

async function cmdAdd(conn, wallet, poolAddr, solAmt, widthPct, tag) {
  const pool = await DLMM.create(conn, new PublicKey(poolAddr));
  await pool.refetchStates();
  const ab = await pool.getActiveBin();
  const binStep = pool.lbPair.binStep;
  // scale width: default ~28% below active regardless of binStep; wide arms pass widthPct=0.56
  const wp = (widthPct && widthPct > 0) ? widthPct : 0.28;
  const nBins = Math.min(Math.max(Math.round(wp / (binStep / 10000)), 5), MAX_BINS_PER_TX);
  const minBinId = ab.binId - nBins;
  const maxBinId = ab.binId;         // quote-only (SOL) sits at/below active
  const lamports = Math.round(solAmt * LAMPORTS_PER_SOL);
  const posKp = Keypair.generate();
  console.log(`pool ${poolAddr} binStep=${binStep} active=${ab.binId} range=[${minBinId},${maxBinId}] width=${(wp*100).toFixed(0)}% deposit=${solAmt} SOL (single-sided Y)`);
  const tx = await pool.initializePositionAndAddLiquidityByStrategy({
    positionPubKey: posKp.publicKey,
    totalXAmount: new BN(0),
    totalYAmount: new BN(lamports),
    strategy: { minBinId, maxBinId, strategyType: StrategyType.Spot },
    user: wallet.publicKey,
    slippage: 2,
  });
  const sig = await sendTx(conn, tx, [posKp], wallet);
  const st = loadState();
  st.positions.push({
    pool: poolAddr, position: posKp.publicKey.toBase58(),
    name: null, sol_in: solAmt, ts: Date.now() / 1000,
    entry_active_bin: ab.binId, minBinId, maxBinId, status: 'open', add_sig: sig,
    width_pct: wp, strategy_tag: tag || 'narrow_v1',
  });
  saveState(st);
  console.log(`ADDED position ${posKp.publicKey.toBase58()} sig=${sig}`);
}

// exact bin-count entry for HFNA pilot: Y-only at [ab - binsBelow, ab], no width floor
async function cmdAddUSDC(conn, wallet, poolAddr, usdcAmt, binsBelow, tag) {
  const pool = await DLMM.create(conn, new PublicKey(poolAddr));
  await pool.refetchStates();
  const ab = await pool.getActiveBin();
  const n = Math.min(Math.max(Math.round(binsBelow), 1), MAX_BINS_PER_TX);
  const minBinId = ab.binId - n;
  const maxBinId = ab.binId;
  const raw = Math.round(usdcAmt * 1e6);   // USDC 6dp, Y-side, wallet must hold USDC
  const posKp = Keypair.generate();
  console.log(`pool ${poolAddr} active=${ab.binId} range=[${minBinId},${maxBinId}] deposit=${usdcAmt} USDC (single-sided Y)`);
  const tx = await pool.initializePositionAndAddLiquidityByStrategy({
    positionPubKey: posKp.publicKey,
    totalXAmount: new BN(0),
    totalYAmount: new BN(raw),
    strategy: { minBinId, maxBinId, strategyType: StrategyType.Spot },
    user: wallet.publicKey,
    slippage: 2,
  });
  const sig = await sendTx(conn, tx, [posKp], wallet);
  const st = loadState();
  st.positions.push({
    pool: poolAddr, position: posKp.publicKey.toBase58(),
    name: null, sol_in: null, usdc_in: usdcAmt, ts: Date.now() / 1000,
    entry_active_bin: ab.binId, minBinId, maxBinId, status: 'open', add_sig: sig,
    width_pct: null, strategy_tag: tag || 'surf_probe_usdc',
  });
  saveState(st);
  console.log(`ADDED position ${posKp.publicKey.toBase58()} sig=${sig}`);
}

async function cmdAddBins(conn, wallet, poolAddr, solAmt, binsBelow, tag) {
  const pool = await DLMM.create(conn, new PublicKey(poolAddr));
  await pool.refetchStates();
  const ab = await pool.getActiveBin();
  const n = Math.min(Math.max(Math.round(binsBelow), 1), MAX_BINS_PER_TX);
  const minBinId = ab.binId - n;
  const maxBinId = ab.binId;
  const lamports = Math.round(solAmt * LAMPORTS_PER_SOL);
  const posKp = Keypair.generate();
  console.log(`pool ${poolAddr} active=${ab.binId} range=[${minBinId},${maxBinId}] deposit=${solAmt} SOL (single-sided Y, exact-bins)`);
  const tx = await pool.initializePositionAndAddLiquidityByStrategy({
    positionPubKey: posKp.publicKey,
    totalXAmount: new BN(0),
    totalYAmount: new BN(lamports),
    strategy: { minBinId, maxBinId, strategyType: StrategyType.Spot },
    user: wallet.publicKey,
    slippage: 2,
  });
  const sig = await sendTx(conn, tx, [posKp], wallet);
  const st = loadState();
  st.positions.push({
    pool: poolAddr, position: posKp.publicKey.toBase58(),
    name: null, sol_in: solAmt, ts: Date.now() / 1000,
    entry_active_bin: ab.binId, minBinId, maxBinId, status: 'open', add_sig: sig,
    width_pct: null, strategy_tag: tag || 'hfna_live_v1',
  });
  saveState(st);
  console.log(`ADDED position ${posKp.publicKey.toBase58()} sig=${sig}`);
}

async function cmdExit(conn, wallet, poolAddr) {
  const pool = await DLMM.create(conn, new PublicKey(poolAddr));
  const { userPositions } = await pool.getPositionsByUserAndLbPair(wallet.publicKey);
  const st = loadState();
  for (const pos of userPositions) {
    const rec = st.positions.find(x => x.position === pos.publicKey.toBase58() && x.pool === poolAddr);
    if (!rec || rec.status !== 'open') continue;
    const binIds = pos.positionData.positionBinData.map(b => b.binId);
    if (!binIds.length) { console.log(`position ${rec.position}: no liquidity bins`); continue; }
    const txs = await pool.removeLiquidity({
      user: wallet.publicKey,
      position: pos.publicKey,
      fromBinId: Math.min(...binIds),
      toBinId: Math.max(...binIds),
      bps: new BN(10000),
      shouldClaimAndClose: true,
      skipUnwrapSOL: false,
    });
    const list = Array.isArray(txs) ? txs : [txs];
    const sigs = [];
    for (const tx of list) sigs.push(await sendTx(conn, tx, [], wallet));
    rec.status = 'exited'; rec.exit_sigs = sigs; rec.exit_ts = Date.now() / 1000;
    saveState(st);
    console.log(`EXITED ${rec.position} sigs=${sigs.join(',')}`);
  }
}

async function cmdClaim(conn, wallet, poolAddr) {
  const pool = await DLMM.create(conn, new PublicKey(poolAddr));
  const { userPositions } = await pool.getPositionsByUserAndLbPair(wallet.publicKey);
  const st = loadState();
  for (const pos of userPositions) {
    const rec = st.positions.find(x => x.position === pos.publicKey.toBase58() && x.pool === poolAddr);
    if (!rec || rec.status !== 'open') continue;
    // bypass claimSwapFee: its compute-unit estimator is broken in the bundle
    // ("Function.prototype.apply on undefined"). Use the raw method instead.
    const txs = await pool.createClaimSwapFeeMethod({ owner: wallet.publicKey, position: pos });
    const list = Array.isArray(txs) ? txs : [txs];
    for (const tx of list) {
      tx.instructions.unshift(ComputeBudgetProgram.setComputeUnitLimit({ units: 400000 }));
      const sig = await sendTx(conn, tx, [], wallet);
      console.log(`CLAIMED ${rec.position} sig=${sig}`);
    }
  }
}

async function cmdBinsJson(conn, poolAddr) {
  // Read-only bin-level snapshot: active bin ± 10, liquidity per bin in Y terms.
  const pool = await DLMM.create(conn, new PublicKey(poolAddr));
  await pool.refetchStates();
  const ab = await pool.getActiveBin();
  const around = await pool.getBinsAroundActiveBin(10, 10);
  const xDec = pool.tokenX?.decimal ?? 9, yDec = pool.tokenY?.decimal ?? 9;
  const decScale = Math.pow(10, yDec - xDec);
  const bins = (around.bins || []).map(b => ({
    binId: b.binId,
    price: parseFloat(b.pricePerToken),
    // raw-Y units: yRaw + xRaw * pricePerToken * 10^(yDec-xDec)
    liqY: parseFloat(b.yAmount?.toString() || '0') +
          parseFloat(b.xAmount?.toString() || '0') * parseFloat(b.pricePerToken) * decScale,
  }));
  // Dynamic-fee leg (HFNA): volatility accumulator + fee params, raw strings.
  const vp = pool.lbPair.vParameters || {};
  const pr = pool.lbPair.parameters || pool.lbPair.staticParameters || {};
  console.log(JSON.stringify({
    pool: poolAddr, t: Date.now() / 1000, activeBin: ab.binId,
    binStep: pool.lbPair.binStep, bins, xDec, yDec,
    volAccum: (vp.volatilityAccumulator || vp.volatility_accumulator || '0').toString(),
    volRef: (vp.volatilityReference || vp.volatility_reference || '0').toString(),
    varFeeCtl: (pr.variableFeeControl || pr.variable_fee_control || '0').toString(),
    baseFactor: (pr.baseFactor || pr.base_factor || '0').toString(),
    baseFeeBps: (pool.lbPair.baseFeeRateFactor || '').toString(),
    collectFeeMode: (pool.lbPair.collectFeeMode ?? pool.lbPair.collect_fee_mode ?? -1).toString(),
    protocolShare: (pr.protocolShare ?? pr.protocol_share ?? '0').toString(),
    protFeeX: (pool.lbPair.protocolFee?.amountX || pool.lbPair.protocolFee?.x || '0').toString(),
    protFeeY: (pool.lbPair.protocolFee?.amountY || pool.lbPair.protocolFee?.y || '0').toString(),
  }));
}

async function cmdTaxCheck(conn, poolAddr) {
  // Detect Token-2022 transfer-fee (tax) tokens: a >~1% transfer tax destroys
  // the LP fee-capture margin (armed trade 6gQTdHry 09-12: 300bps tax).
  const pool = await DLMM.create(conn, new PublicKey(poolAddr));
  const mintX = pool.lbPair.tokenXMint;
  const info = await conn.getParsedAccountInfo(mintX);
  const parsed = info.value?.data?.parsed?.info || {};
  const exts = parsed.extensions || [];
  const tfc = exts.find(e => e.extension === 'transferFeeConfig');
  const bps = tfc ? (tfc.state?.newerTransferFee?.transferFeeBasisPoints ?? 0) : 0;
  console.log(JSON.stringify({
    pool: poolAddr, mintX: mintX.toBase58(), tokenProgram: info.value?.owner?.toBase58?.() || String(info.value?.owner),
    taxBps: bps, hasTransferFee: !!tfc, decimals: parsed.decimals ?? null,
  }));
}

async function main() {
  const [cmd, poolAddr, solAmt, widthPct, tag] = process.argv.slice(2);
  const wallet = loadWallet();
  const conn = rpc();
  try {
    if (cmd === 'status') await cmdStatus(conn, wallet);
    else if (cmd === 'statusjson') await cmdStatusJson(conn, wallet);
    else if (cmd === 'add') await cmdAdd(conn, wallet, poolAddr, parseFloat(solAmt), parseFloat(widthPct), tag);
    else if (cmd === 'addbins') await cmdAddBins(conn, wallet, poolAddr, parseFloat(solAmt), parseFloat(widthPct), tag);
    else if (cmd === 'addusdc') await cmdAddUSDC(conn, wallet, poolAddr, parseFloat(solAmt), parseFloat(widthPct), tag);
    else if (cmd === 'exit') await cmdExit(conn, wallet, poolAddr);
    else if (cmd === 'claim') await cmdClaim(conn, wallet, poolAddr);
    else if (cmd === 'binsjson') await cmdBinsJson(conn, poolAddr);
    else if (cmd === 'taxcheck') await cmdTaxCheck(conn, poolAddr);
    else if (cmd === 'balance') {
      const lam = await conn.getBalance(wallet.publicKey);
      console.log(JSON.stringify({ wallet: wallet.publicKey.toBase58(), lamports: lam, sol: lam / 1e9 }));
    }
    else { console.log('usage: status | add <pool> <sol> [widthPct] [tag] | addbins <pool> <sol> <binsBelow> [tag] | exit <pool> | claim <pool> | binsjson <pool> | balance'); process.exit(1); }
  } catch (e) {
    console.error('ERROR:', e.message || e);
    process.exit(2);
  }
}
main();
