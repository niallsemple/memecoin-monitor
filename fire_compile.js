// fire_compile.js — compile+sign a v0 Kamino fire tx with official web3.js.
// stdin: {ixs:[{programId,accounts:[{pubkey,isWritable,isSigner}],data:[bytes]}],
//         walletPath, altPath}
// stdout: {tx_b64} or {error}
const fs = require("fs");
const { PublicKey, TransactionInstruction, TransactionMessage,
        VersionedTransaction, Connection, Keypair } =
      require("/Users/niallsemple/Documents/kimi/workspace/darwin-labs-ai/memecoin-monitor/node_modules/@solana/web3.js");
(async () => {
  const inp = JSON.parse(fs.readFileSync(0, "utf8"));
  const w = JSON.parse(fs.readFileSync(inp.walletPath, "utf8"));
  const kp = Keypair.fromSecretKey(Uint8Array.from(w.keypair_bytes));
  const ixs = inp.ixs.map(i => new TransactionInstruction({
    programId: new PublicKey(i.programId),
    keys: i.accounts.map(a => ({ pubkey: new PublicKey(a.pubkey),
                                 isWritable: a.isWritable, isSigner: a.isSigner })),
    data: Buffer.from(i.data) }));
  const altSt = JSON.parse(fs.readFileSync(inp.altPath, "utf8"));
  const key = fs.readFileSync(inp.heliusPath, "utf8").trim();
  const conn = new Connection("https://mainnet.helius-rpc.com/?api-key=" + key);
  const altAcc = (await conn.getAddressLookupTable(new PublicKey(altSt.address))).value;
  const bh = await conn.getLatestBlockhash("finalized");
  const msg = new TransactionMessage({ payerKey: kp.publicKey,
    recentBlockhash: bh.blockhash, instructions: ixs }).compileToV0Message([altAcc]);
  const tx = new VersionedTransaction(msg);
  tx.sign([kp]);
  console.log(JSON.stringify({ tx_b64: Buffer.from(tx.serialize()).toString("base64") }));
})().catch(e => { console.log(JSON.stringify({ error: e.message })); process.exit(0); });
