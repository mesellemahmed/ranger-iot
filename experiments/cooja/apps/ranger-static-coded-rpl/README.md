# RANGER Static Coded RPL — STEP 6C.1

This experiment validates fixed 3-of-5 coded reconstruction over the
multi-hop RPL topology already established in STEP 6B.3.

The coding semantics intentionally match the simulator abstraction:

- group ID: 1
- epoch: 1
- data fragments k: 3
- total fragments n: 5
- authorized nodes: 2..7
- revoked node: 8
- recovery: disabled
- adaptive redundancy: disabled
- radio loss: disabled

A node reconstructs the epoch only after receiving three distinct fragment
identifiers. Duplicate fragment identifiers do not increase the reconstruction
count.

This experiment does not implement Reed-Solomon byte arithmetic. It validates
the state machine and metadata-level k-of-n semantics over Contiki-NG/RPL.

The Python RANGER-STATIC simulator uses flooding. STEP 6C.1 deliberately keeps
the already validated RPL unicast transport so coding correctness can be
isolated before transport parity and controlled-loss experiments.
