# Platform Research: Moonshot (Moonit), LetsBonk.fun, Streamflow — 2026-09-03

Purpose: understand how each works and where they plug into the positive-ROI hunt. Research only; goal addition deferred until a positive-ROI system is proven.

## 1. Moonshot / Moonit (moonshot.fun)
- Built by **Dexscreener**. Bonding-curve launchpad, ~$2 launch cost, 1% curve trading fee.
- Graduation: creator sets custom liquidity threshold; liquidity auto-migrates to **Raydium or Meteora** (creator's choice); LP tokens permanently burned; 2 SOL bonding bonus to creator.
- Creator economics: creators keep **80% of trading fees** (platform 20%) — strongly incentivizes deployers vs pump.fun.
- Graduated tokens get free Dexscreener enhanced listing (~$299 value) + search visibility.
- **Warning for us:** an active volume-bot market exists for Moonshot (e.g. ChartUp — thousands of fake independent wallets, randomized timing/sizes, "looks organic"). Fake maker/holder counts are purchasable (50k makers for 1.25 SOL). This is exactly the fake-momentum pattern behind our rug closes — insider/bot-count fields from such tokens are polluted by design.
- Contracts audited by Ackee Blockchain.

## 2. LetsBonk.fun / bonk.fun
- Built by **BONK community + Raydium devs** (April 2025). Bonding curve, 1% swap fee.
- Graduation: liquidity moves to **Raydium AMM with immediate Jupiter routing** — tokens are Jupiter-indexed from graduation, meaning our existing pool-venue trading path (jupiter_quote_sell / pool_sell) works natively.
- Creator rewards: 0.1% of volume to creators (double pump.fun's 0.05%); fee revenue split: platform ops / BONKsolo validator staking / BONK buyback-and-burn; 1% of revenue buys back top launchpad pairs.
- Market share vs pump.fun swings violently (5%↔90% in weeks) because **top deployers are bots that migrate between platforms overnight**. Majority of tokens on both platforms are bot-launched (new token every few minutes from top accounts).
- Under ~2% of launched tokens graduate (pump.fun stat; bonk similar).

## 3. Streamflow (streamflow.finance)
- Not a launchpad — **token operations infrastructure**: locks, vesting, airdrops, staking. 40,000+ projects, $263M–1.4B TVL (sources vary), audited by FYEO + OPCODES, immutable contracts, no admin override.
- Lock types: fixed-date, time-period, **price-based unlocks**. SPL + LP tokens. ~37-second no-code setup, public proof links verifiable on Solscan/Explorer/RugCheck.
- BONK itself vested 20% of supply across 22 contributors, 3-year linear, via Streamflow.
- **Key angle for us:** a deployer who locks team/LP allocation on Streamflow produces **on-chain verifiable anti-rug proof**. Querying lock contracts for a given mint is a potential entry-gate signal — tokens with real Streamflow locks have structurally lower rug capacity. Caveat: serious memecoin deployers rarely lock; signal may be too rare to matter.

## Where this plugs into the ROI system
1. **New cohort sources:** LetsBonk and Moonshot tokens both graduate to Jupiter-routed venues (Raydium/Meteora) — our pool-venue path already handles them. Adding their new-launch feeds to the scanner increases trade flow → faster path to 60 closes and a bigger sample.
2. **Anti-rug gate candidate:** check Streamflow lock presence per mint at entry-time; log it as a position field, measure separation between rugs and greens (n=2 rugs so far, need more).
3. **Volume-bot awareness:** Moonshot's fake-maker market means maker/holder counts cannot be trusted as momentum evidence on that platform; treat as noise, not signal.
4. **Deployer-migration tracking:** the pump.fun↔bonk market-share swings are driven by top bot deployers — our existing blocklist/master-watch infra could track cross-platform deployer migration as a regime signal.

## Sources
- crypto.news bonding-curve guide (2026-06); stakepoint.app launchpad comparison (2026-01); tradetheday.com Moonshot review (2026-02); chartup.io Moonshot volume bot (2026-04); graphdex.io pump vs bonk war (2026-07); smithii.io comparison (2026-06); chaincatcher LetsBONK analysis (2025-04); rootdata / The Block launchpad share (2025-08); streamflow.finance docs/blog (2026-08).
