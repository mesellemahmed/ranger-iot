# RANGER-STATIC coded dissemination

This stage connects the abstract coding core to the deterministic network model.
It is intentionally the smallest end-to-end RANGER prototype.

## Pipeline

```text
LKH rekey plan
      |
      v
opaque RekeyCapsule
      |
      v
ideal k-of-n MDS model
      |
      v
coded fragments
      |
      v
one deterministic flood per fragment
      |
      v
authorized member receives >= k distinct fragments
      |
      v
member accepts the new epoch
```

LKH remains responsible for authorization. The capsule is modeled as containing
all encrypted LKH update objects for one epoch. Reconstructing the capsule does
not by itself grant authorization: a revoked member may receive and relay every
fragment but cannot accept the new group epoch.

## Static size model

For `c` logical LKH ciphertexts of `B` modeled bytes each, the capsule payload is
currently:

```text
capsule_bytes = c * B + capsule_overhead_bytes
```

With ideal `k-of-n` coding, each fragment has:

```text
fragment_bytes = ceil(capsule_bytes / k)
```

The network therefore injects `n` fragment floods. This intentionally exposes
the bandwidth cost of redundancy.

## Scope boundary

This stage does **not** implement:

- a real Reed-Solomon codec;
- retries;
- neighbor recovery;
- self-healing after missed epochs;
- adaptive `k` or `n`;
- topology-aware forwarding suppression;
- CPU or memory cost of coding.

Those mechanisms are introduced only after this fixed-policy baseline is
validated.
