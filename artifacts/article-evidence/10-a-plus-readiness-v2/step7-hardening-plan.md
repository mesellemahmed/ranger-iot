# RANGER-IoT — STEP 7 A+ Hardening Plan

## 7A — Statistical hardening

Keep exact pairing across Static / Recovery / Adaptive-V2.

- TX=0.50: no new runs.
- TX=0.30: extend 10 -> 30 seeds.
- TX=0.20: extend 10 -> 30 seeds.
- Additional full-pairing budget: 120 runs.

## 7B — External-validity campaign

After 7A, add topology/scale sensitivity without changing protocol semantics.

## 7C — Coding realism

Audit/benchmark a real byte-level erasure codec if the implementation currently uses an idealized k-of-n/MDS abstraction.

## 7D — Formal security

Audit executable Tamarin/formal artifacts before any formal-security claim.

## Stop rule

No article drafting until 7A–7D are classified as PASS, bounded limitation, or explicitly out-of-scope.
