# RANGER Cooja Core — STEP 6B.1

## Purpose

This experiment validates the minimum functional semantics of RANGER
inside Contiki-NG/Cooja before introducing multi-hop routing, coding,
recovery, adaptive redundancy, or cryptographic key wrapping.

## Node roles

- Node 1: Group Manager
- Nodes 2, 3, 4: authorized members
- Node 5: revoked member

## Expected epoch-1 decision

- 2 -> ACCEPT
- 3 -> ACCEPT
- 4 -> ACCEPT
- 5 -> REJECT

The Group Manager must finally emit:

`RANGER_CORE_PASS epoch=1 accepted=3 rejected=1`

## Scope limitation

This step does NOT yet establish confidentiality or post-revocation
cryptographic security.

The epoch update is intentionally a functional control message.

Cryptographic protection will be introduced only after the protocol
state machine and Cooja communication path are validated.

## Topology

For STEP 6B.1 all five motes must be inside direct radio range.

Multi-hop RPL validation is STEP 6B.2.
