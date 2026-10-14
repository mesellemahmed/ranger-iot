# RANGER Static Coding Core

STEP 5A introduces the reliability abstraction that will later be connected to
RANGER dissemination.  It deliberately does **not** implement network
transport, recovery, adaptation, or a concrete Reed-Solomon codec.

## Separation of responsibilities

The authorization layer (currently LKH) produces authenticated encrypted rekey
material.  RANGER wraps that opaque material in a `RekeyCapsule` and applies an
ideal systematic MDS erasure-code model.

For parameters `k` and `n`:

- `k` is the number of distinct fragments required for reconstruction;
- `n` is the total number of encoded fragments;
- `n - k` is the redundancy budget;
- any `k` distinct matching fragments are considered sufficient to reconstruct
  the capsule.

For example, `k=3, n=5` tolerates any two erasures at the coding abstraction
layer.

## What is modeled

The simulator models:

- deterministic fragment identifiers;
- fragment payload size as `ceil(capsule_bytes / k)`;
- unique-fragment accounting;
- k-of-n reconstruction readiness;
- strict isolation by capsule, group, epoch, and coding profile.

Fragments from different epochs, groups, capsules, or coding profiles must never
be combined.

## What is not modeled yet

STEP 5A does not claim a concrete Reed-Solomon implementation.  It does not
model finite-field operations, CPU cycles, encoding latency, decoding latency,
or codec memory.  Those costs belong to the later implementation/measurement
layer.

It also does not yet provide:

- distributed fragment dissemination;
- neighbor recovery or self-healing;
- adaptive redundancy;
- retransmission;
- Contiki-NG/Cooja integration.

Those features are introduced incrementally so that reliability gains can be
attributed to specific mechanisms.
