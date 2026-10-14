# LKH-FLOOD baseline

`lkh-flood` separates the Logical Key Hierarchy authorization plan from a shared graph-level dissemination mechanism.

For each logical LKH ciphertext, the Group Manager injects exactly one flood message. A node forwards a message only after its first successful reception. The immediate ingress neighbor is excluded from forwarding, and later copies of the same flood message are suppressed by message identifier.

## Security / transport separation

A node may relay a flooded ciphertext without being an authorized recipient of the corresponding LKH update. This includes an active node that has been cryptographically revoked. Revocation prevents epoch acceptance; it does not make the device disappear from the network topology.

## Intentionally absent mechanisms

This baseline does not implement:

- retransmission;
- local recovery;
- erasure coding;
- adaptive redundancy;
- RANGER-specific forwarding decisions.

Loss can therefore leave an authorized subtree stale.

## Metric interpretation

The deterministic simulator counts `physical_transmissions` as per-link delivery attempts. A forwarding node with two graph neighbors can therefore contribute two transmissions for one dissemination step. This is a graph-level cost model, not yet an IEEE 802.15.4 broadcast-airtime model. Radio/MAC behavior is evaluated later in Contiki-NG/Cooja.

For this protocol, the generic `routed_copies` summary field is the number of source flood injections, not the number of relay forwarding attempts. The explicit `flood_injections` field records the same quantity without ambiguity.

For the Step 4D line smoke scenario `0-1-2-3-4`, revoking member 4 produces three logical LKH ciphertexts. Each one traverses four links, so the expected total is 12 per-link transmissions and three Group Manager transmissions.
