# CODE AUDIT — "what does the machine allow?" (memo #36)

Scope: legitimate permissionless asymmetries only. Explicitly excluded: auth bypass,
signature forgery, access-control defeat, fund draining. Source: Meteora DLMM IDL
(76 instructions, fetched from MeteoraAg/dlmm-sdk main, 2026-09-11).

## Q1 (the LP-skim question): minimum time for fee entitlement

From the instruction surface + known DLMM accounting:
- Fees accrue **per bin** via fee-growth accumulators; a swap crossing/landing in a bin
  credits that bin's liquidity at execution instant.
- `add_liquidity*` and `remove_liquidity*` are both single-transaction instructions with
  **no slot lock, no cooldown, no minimum holding period** in the IDL.
- `claim_fee2` needs position owner signature; accounting updates via
  `update_fees_and_reward2` (owner-signed, 3 accounts).

**Answer: fee entitlement is instant — liquidity present at the swap's execution slot earns
the fee; there is no protocol-level time lock.** JIT liquidity (add → swap crosses → remove)
is *programmatically* legal on Meteora DLMM. The blocker is not the program, it's
information: with the Jito public mempool gone, we cannot see victim swaps pre-execution.
Atomic [add → our own swap → remove] earns nothing (we'd pay our own fee).

=> LP skimming remains a *prediction* problem (fee-density windows), not a code exploit.
   This confirms memo #35's framing and closes memo #36's central experiment: NO shortcut
   to sub-second fee capture without orderflow visibility. BAM Maker Priority is the only
   theoretical lane (requires maker enrollment; not available to us now).

## Q2: permissionless instruction surface — what has no owner gate

| Instruction | Signers | Note |
|---|---|---|
| `go_to_a_bin` | **none** | moves active bin during limit-order fills; anyone can poke |
| `set_pair_status_permissionless` | any signer | can flip pair status (pre-activation pools) |
| `close_position_if_empty` | `sender` (IDL does not show owner constraint) | rent_receiver writable, NOT signer |
| `close_bin_array` | rent_receiver + signer | both sign |
| `close_limit_order_if_empty` | owner | gated |
| `withdraw_ineligible_reward` | funder | gated |
| `initialize_bin_array` / `*_bitmap_extension` | funder pays rent | first-touch pays; later users reuse free |

## Finding F1: rent-recovery asymmetry (TESTABLE)

`close_position_if_empty(position, sender, rent_receiver)` — the IDL shows `sender` as the
only signer and does NOT encode an owner constraint (constraints live in program code; the
IDL account list is suggestive but not proof). If the deployed program lets a non-owner
close *empty* positions and route rent to an arbitrary `rent_receiver`, then every abandoned
empty DLMM position on Solana is ~0.057 SOL of recoverable rent — a permissionless sweeper
lane. Surf pilot alone closed 17 positions; thousands of bots leave empties behind.

**Falsification test (cheap):** gPA for DLMM position accounts with zero liquidity, attempt
one close with our wallet as sender + rent_receiver. If the program rejects non-owner, lane
dies in one tx (~0.00001 SOL cost). If it succeeds, quantify the population.

## Finding F2: bin-array rent first-touch asymmetry (confirmed by docs, low value)

First position touching an uninitialized bin array pays its rent (~0.07 SOL/array); later
users reuse it free. This is a COST asymmetry against us (our surf entries often paid it),
not an extractable one. Already visible in entry_cost ≈ deposit + 0.054.

## Finding F3: `set_pair_status_permissionless`

Anyone can toggle pair status on permissionless pools. Mostly relevant to pre-activation
pairs (launch sniping protection). Watch item, not a lane.

## Verdict for the research programme

- The JIT-fee shortcut: **dead end** (info-blocked, not code-blocked). Skip.
- Rent sweeper (F1): **test next** — one cheap on-chain falsification tx decides.
- The durable edge remains where the data already points: aged-pool wide-band LP
  (KNOTS live), fee-density window prediction (skim_lab PASS), and cross-DEX arb
  (arb_scanner). Code audit continues on Raydium CLMM + Orca next pass.

## F1 RESULT — FALSIFIED (2026-09-11, one simulation, zero cost)

Population measured: **100,047 empty DLMM positions chain-wide ≈ 4,192 SOL locked rent**
(filter: dataSize 8120 + liquidity_shares[0..32]==0, Helius gPA).

Probe: non-owner `close_position_if_empty` with rent to our wallet, simulated on a live
foreign empty position (JEKNUXAy…Wmnma). Program rejected: AnchorError 2003 ConstraintRaw
on `position` — the deployed program enforces position.owner == sender even though the IDL
doesn't show it. **Lane dead. IDL account lists are not authority proofs — simulate first.**

Lesson banked for the code-audit programme: instruction *surface* enumeration finds
candidates; only simulation/on-chain probe settles authority. Cost per falsification: ~0 SOL.

## Raydium CLMM audit — tick-array rent asymmetry (2026-09-12, source read, no tx)

Source: raydium-io/raydium-clmm @ master (programs/amm/src/instructions/). No published IDL in repo.

Findings:
1. **First-touch pays tick-array rent.** `open_position` calls `TickArrayState::get_or_create_tick_array(payer=position opener)`. `increase_liquidity_v2` never creates arrays; `swap_v2` only checks `data_len == TickArrayState::LEN` and skips uninitialized arrays. So the first LP to open a position spanning a fresh tick array pays ~0.0745 SOL rent per array (~60 ticks/array). Everyone who LPs that range afterwards free-rides.
2. **Rent is permanently locked.** No `close_tick_array` instruction exists anywhere in the program. `close_position` refunds only the position state account to `nft_owner`. Tick-array rent can never be recovered — by anyone. No sweeper edge here (consistent with the F1 DLMM falsification).
3. **Cost-model consequence for us:** on Raydium CLMM, prefer ranges whose tick arrays already exist (established pools) — entering a fresh range on a 0.1–0.8 SOL position with multi-array span could cost 0.07–0.22 SOL in unrecoverable rent, dwarfing fee income. Meteora DLMM has the same first-touch pattern (bin arrays), so the rule generalizes: *never be the first LP into a range*.

Verdict: no extractable edge, one durable cost rule banked. Orca Whirlpools next pass.
