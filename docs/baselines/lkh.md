# LKH baseline model

The RANGER-IoT simulator models Logical Key Hierarchy (LKH) as a balanced binary key tree.
The implementation in `ranger_iot.protocols.lkh` is deliberately separated from network
transport so that the cryptographic control-plane cost can be validated independently before
introducing dissemination strategies.

## State model

Each member owns an individual leaf key and the Key Encryption Keys (KEKs) on the path from
its leaf to the root. Node `1` is the group key. The simulator stores symbolic key versions
rather than secret key bytes because this stage measures rekey structure, not cryptographic
primitive execution time.

For a leave or revocation event, every non-empty internal node on a revoked member's path to
the root is replaced. Replacement keys are planned bottom-up. A new parent key is wrapped
under each surviving child key. If the child key was itself replaced during the same rekey,
the new child-key version is used as the wrapper.

This construction preserves the standard LKH exclusion property at the model level: a
revoked member is excluded from every recipient cover used to distribute future key versions.

## Metrics exposed by the plan

`LkhRekeyPlan.logical_ciphertexts` counts the number of logical encrypted key-update objects.
It is not a radio-transmission count. Physical dissemination is intentionally deferred to the
next implementation stage, where the same LKH plan will be transported over the deterministic
lossy multi-hop network.

Keeping these two costs separate prevents a methodological error: improvements in multicast
or flooding must not be misreported as improvements in the LKH cryptographic key-update
structure itself.

## Scope

This baseline currently supports:

- deterministic balanced-tree construction;
- arbitrary non-negative member identifiers;
- single and batch revocation;
- periodic group-key refresh with no revocation;
- sequential rekeys with monotonic key versions;
- non-power-of-two group sizes through unused padded leaves.

Dynamic joins are intentionally out of scope for this stage and will be added only when the
leave/revocation path and transport baselines are frozen.
