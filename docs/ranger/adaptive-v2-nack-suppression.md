# RANGER Adaptive-V2 — branch-local NACK suppression

STEP 5F.2 responds to the publication-grade diagnostic of Adaptive-V1.

The development campaign showed that Adaptive-V1 preserves useful incremental
redundancy but can create a large number of hop-by-hop deficit-feedback
transmissions, especially on long line topologies. Adaptive-V2 changes only the
feedback forwarding rule; coding, maximum redundancy, local recovery, and the
loss-oblivious policy remain unchanged.

## Suppression rule

Every stale authorized member may still originate one deficit report in an
adaptive round.

At a control-tree relay, the first received deficit report for a given
`(epoch, round_id)` is forwarded to the parent. Later received reports for the
same round are suppressed at that relay.

A stale relay's own source report is not entered in the forwarding cache. This
means an edge can carry the relay's own report plus one aggregated descendant
report. The design intentionally keeps modest control-path redundancy under
loss instead of enforcing an unrealistically perfect one-report tree.

## Scientific isolation

Adaptive-V2 keeps the same:

- ideal 3-of-5 coding ceiling;
- three initial fragments;
- parity-release rule: at most one new parity fragment per NACK round;
- local same-epoch recovery;
- NACK payload size;
- recovery-round budget;
- receiver-specific loss model.

The only changed mechanism is branch-local duplicate NACK forwarding.

## Added counters

- `adaptive_nack_forwarded`: received deficit reports actually forwarded by
  intermediate relays;
- `adaptive_nack_suppressed`: received duplicate reports suppressed locally.

The existing `adaptive_nack_hop_attempts` remains the primary direct measure for
V1/V2 feedback-path cost.

## Evaluation discipline

Seeds 1–30 have already informed protocol development. STEP 5F.2 therefore uses
only a development comparison first. The confirmatory configuration using
seeds 101–130 is created now but must not be executed until Adaptive-V2 is
frozen after the development audit.
