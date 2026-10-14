# SKDC baseline

The SKDC implementation is the linear-cost baseline used by the RANGER-IoT experiments.
It models a trusted group manager that shares an independent secure pairwise channel with
each authorized group member. On every rekey, the manager generates a new group epoch and
sends one pairwise-protected rekey message to every non-revoked member.

## Experimental contract

- The group manager is node `0` by convention in experiment configurations, but the
  implementation does not hard-code that identifier.
- Rekey authorization is represented by `GroupState`; revoked members remain network nodes
  and may still forward traffic, but they cannot accept future group epochs.
- The pairwise cryptographic channel is abstracted as a protected payload of configurable
  size. The simulator does not claim AES, HKDF, or signature execution cost at this stage.
- Unicast delivery uses deterministic shortest paths over the experiment topology. Each hop
  is charged as an independent link-layer transmission, so manager load and network load are
  measured separately.
- The initial SKDC baseline has no retransmission or recovery mechanism. Loss therefore
  directly reduces convergence. Reliability mechanisms are added only as explicit variants
  to avoid hiding baseline costs.
- `T50`, `T95`, and `T100` are measured from rekey initiation to the corresponding fraction
  of authorized members accepting the new epoch.

## Complexity expectation

For `N` authorized members, the manager creates `N` pairwise rekey messages. The manager-side
message count is therefore `O(N)`. Multi-hop network cost additionally depends on the sum of
shortest-path lengths from the manager to all authorized members.

This baseline is intentionally simple and must remain frozen once validated. Future LKH and
RANGER implementations will reuse the same network, routing, timing, and metric primitives.
