# RANGER same-epoch neighbor recovery

STEP 5C extends RANGER-STATIC with deterministic one-hop repair after the
initial coded flood has quiesced.

## Scope

This checkpoint implements **same-epoch local self-healing**. It does not claim
catch-up across multiple missed epochs. Multi-epoch recovery requires explicit
key-history and forward/backward-security rules and is intentionally kept out
of this abstraction.

## Recovery round

For each authorized member that still has fewer than `k` distinct coded
fragments after the initial dissemination:

1. the member sends one recovery request to every directly connected eligible
   neighbor;
2. an authorized neighbor returns fragment indexes it owns and the requester
   lacks, capped by the requester's remaining decoding deficit;
3. the Group Manager may answer only when it is itself a direct neighbor; its
   recovery fragment attempts are counted separately;
4. direct requests and responses are subject to the same network loss model as
   every other packet;
5. duplicate fragment indexes are ignored by the existing accumulator.

The runner executes at most `ranger_recovery_rounds` after the initial flood.
This allows repair to cascade: a node repaired in round 1 can help a farther
neighbor in round 2.

## Metrics

RANGER-RECOVERY adds:

- `recovery_rounds`
- `recovery_requests`
- `recovery_fragment_attempts`
- `peer_recovery_fragment_attempts`
- `manager_recovery_fragment_attempts`
- `recovered_members`

These metrics must be interpreted jointly with convergence, physical
transmissions, bytes, manager load, and T50/T95/T100.

## Smoke campaign

`step5c-ranger-recovery-suite-smoke.yaml` compares five protocols across four
deterministic topologies, sizes 4/8/16, loss 0%/10%/20%/30%, and seeds 11/29. The matrix
contains 480 runs and is an integration/behavioral smoke campaign, not a
statistically powered scientific evaluation.
