# RANGER adaptive incremental redundancy

STEP 5D replaces fixed upfront redundancy with explicit feedback-driven
incremental redundancy.

## Policy

For a configured ideal `k-of-n_max` code, RANGER-ADAPTIVE initially floods only
the first `k` fragments. A member that remains unable to decode emits an
explicit adaptive NACK. The NACK is forwarded hop-by-hop toward the Group
Manager over a deterministic BFS control tree and remains subject to the same
loss model and network accounting as data traffic.

For each adaptive NACK round, the Group Manager releases at most one additional
parity fragment. Local same-epoch neighbor recovery is then attempted before
the next redundancy-request round.

The protocol does **not** inspect the configured Bernoulli packet-loss
probability. This avoids an oracle policy in which the simulator tells the
protocol the true loss rate.

## Ablation

The STEP 5D smoke campaign keeps the same maximum coding ceiling for the three
RANGER variants:

- RANGER-STATIC: 3-of-5, all five fragments sent upfront.
- RANGER-RECOVERY: 3-of-5 upfront plus local recovery.
- RANGER-ADAPTIVE: 3-of-5 maximum, only three sent upfront; parity 4 and 5 are
  released only after explicit demand, with local recovery between rounds.

This isolates incremental redundancy without giving RANGER-ADAPTIVE a larger
maximum code budget.

## Metrics

RANGER-ADAPTIVE adds:

- `initial_flood_injections`
- `adaptive_parity_injections`
- `adaptive_nack_rounds`
- `adaptive_nacks`
- `adaptive_nack_hop_attempts`
- `adaptive_actions`
- `unused_redundancy_fragments`

These must be interpreted with convergence, bytes, physical transmissions,
manager load, recovery traffic, and T50/T95/T100.

## Scope

This remains a deterministic graph-level simulator. Flood transmissions are
counted per link, not as a true IEEE 802.15.4 one-to-many radio broadcast. That
link-layer abstraction must be addressed before publication-level Cooja or
hardware claims.
