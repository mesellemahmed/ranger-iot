# RANGER multi-hop RPL core — STEP 6B.3

This experiment validates the RANGER epoch/revocation state machine over a
real Contiki-NG RPL-Lite multi-hop topology before adding coded dissemination.

- Node 1: RPL DAG root / Group Manager.
- Nodes 2–7: authorized members.
- Node 8: revoked member.
- Topology: deterministic 8-node line generated from JSON.
- Transport: `simple-udp` over the default Contiki-NG RPL-Lite + CSMA stack.

The farthest node (8) is outside direct radio range of the GM. A PASS therefore
requires successful multi-hop registration, GM-to-node update delivery, and
node-to-GM report delivery.

This is a functional transport/state validation, not yet a cryptographic
post-revocation proof.
