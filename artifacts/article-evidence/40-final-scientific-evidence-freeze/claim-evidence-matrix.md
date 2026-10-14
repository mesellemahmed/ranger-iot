# RANGER-IoT — Final Scientific Claim/Evidence Matrix

This document freezes the scientific interpretation of the evidence used
for the manuscript.

No manuscript statement may exceed the boundaries below without new
evidence and a new explicitly identified experiment/proof stage.

## C1 — Resilience benefit relative to static dissemination

### Permitted claim

Recovery-enabled and adaptive RANGER variants improve resilience relative
to static coded dissemination in multiple tested lossy contexts.

The strongest and most consistent comparative evidence is Recovery versus
Static.

### Evidence

- STEP 7A:
  30 paired seeds per target TX condition for the original Cooja scenario.
- STEP 7B1:
  2880 deterministic model runs.
- STEP 7B2:
  paired inference with Holm multiplicity control.
- STEP 7B3:
  480 confirmatory Cooja topology/layout runs.

### Boundary

Do NOT claim that one protocol universally dominates all contexts.

Adaptive-V2 versus Recovery is explicitly context dependent.


## C2 — External validity across topology, scale, and loss

### Permitted claim

The comparative behavior of RANGER depends materially on topology,
member count, and loss conditions; its benefits and trade-offs were
evaluated across multiple topological and scale regimes.

### Evidence

STEP 7B1:

- topologies:
  line, star, balanced-tree, grid;
- member counts:
  8, 16, 32, 64;
- packet-loss levels:
  0.0, 0.1, 0.2;
- 20 independent frozen seeds;
- 2880 total runs.

STEP 7B3:

- line;
- balanced-tree;
- grid;
- compact-onehop;
- fixed 8-mote Cooja implementation.

### Boundary

`compact-onehop` is not called an exact star.

Python `packet_loss` is not equated to Cooja `SUCCESS_RATIO_TX`.

The Cooja scale evidence is fixed at 8 motes.


## C3 — Byte-level Reed-Solomon realism

### Permitted claim

The canonical systematic GF(256) Reed-Solomon codec has been validated
at the byte level in Python and C, with bidirectional cross-language
decode equivalence and actual shard bytes validated on Cooja/RPL.

### Evidence

STEP 7C1:

- systematic GF(256);
- primitive polynomial 0x11D;
- primary profile 3-of-5;
- 2560 exact Python reconstructions.

STEP 7C2:

- 259 vectors;
- exact generator/shard parity;
- 2588 C-to-C subset decodes;
- 2588 Python-to-C subset decodes;
- 2588 C-to-Python subset decodes;
- -O0 / -O2 identical outputs.

STEP 7C3:

- actual RS shard bytes over isolated Cooja/RPL;
- C and Python reconstruction from actual received bytes;
- below-k rejection.

### Boundary

Reed-Solomon provides reconstruction/availability redundancy.

It does NOT provide secrecy, authentication, or Byzantine integrity.

CRC32 is only a reconstruction/corruption oracle.


## C4 — Comparative conclusions survive the real RS codec

### Permitted claim

For the seven frozen discriminant contexts used by the comparative bridge,
the idealized k-of-n reconstruction decision is exactly preserved by the
canonical byte-level Reed-Solomon implementation for the same received
fragment-index sets.

### Evidence

STEP 7D2-C-B:

- 7 frozen scenario cells;
- 3 protocols;
- 20 seeds per cell;
- 420 deterministic reruns;
- 16380 member-level decisions;
- exact idealized/protocol/RS decision parity;
- exact byte reconstruction for decodable sets;
- below-threshold rejection;
- exact historical deterministic replay;
- exact grouped completion/convergence reproduction.

### Boundary

This does NOT mean that all historical STEP7B simulations physically
transmitted serialized RS bytes.

Actual byte-level Cooja/RPL transmission is separately established by
STEP 7C3.


## C5 — Temporal security of the formal reference instance

### Permitted claim

The session-bound, multi-epoch four-member temporal-security reference
model satisfies all 17 specified Tamarin properties under the explicit
symbolic assumptions of the model.

### Evidence

STEP 7D2-B:

- 17/17 verified;
- 0 falsified;
- 0 timeout;
- 0 execution errors;
- intentional epoch-2 root disclosure mutation is detected as falsified;
- historical key-exposure boundary is explicitly demonstrated.

### Boundary

Do NOT claim:

- arbitrary-N formal proof;
- complete formal verification of all RANGER implementation code;
- network liveness under packet loss;
- formal equivalence between Python, C, Cooja, and Tamarin.


## C6 — Finite structural LKH generalization

### Permitted claim

The exact implemented LkhKeyTree was exhaustively checked over the
specified finite structural domain for survivor derivability, revoked
member exclusion, revoked-coalition exclusion, root freshness, and
historical-key retention.

### Evidence

STEP 7D2-C-A:

- group sizes:
  4, 5, 7, 8, 9, 16, 17, 32, 33, 64;
- all single revocations;
- all ordered two-epoch revocation pairs;
- all simultaneous two-member revocations;
- 10386 cases;
- 17180 rekey epochs;
- 0 failures.

### Boundary

This is finite exhaustive implementation-derived validation.

It is NOT an arbitrary-N theorem.


## C7 — Historical-key exposure boundary

### Permitted claim

A key held legitimately by an authorized member during an earlier epoch
cannot reasonably be required to remain confidential after that former
holder's retained historical state is later explicitly exposed.

The formal results distinguish this historical-exposure boundary from
confidentiality of newly generated post-revocation keys.

### Evidence

- preserved diagnostic counterexamples;
- mono-session causal audit;
- temporal-property reclassification;
- positive temporal contract;
- historical exposure witness;
- negative mutation control.

### Boundary

Do not describe the preserved historical exposure trace as a break of the
new epoch key unless the causal derivation actually establishes that fact.
