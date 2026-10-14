from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RekeyCapsule:
    """Metadata for one authenticated encrypted rekey payload.

    The simulator intentionally treats the capsule payload as opaque.  LKH (or a
    later authorization mechanism) is responsible for producing the protected
    material; RANGER only models how that material is transported reliably.
    """

    capsule_id: str
    group_id: int
    epoch: int
    logical_ciphertexts: int
    payload_bytes: int

    def __post_init__(self) -> None:
        if not self.capsule_id:
            raise ValueError("capsule_id must not be empty")
        if self.group_id < 0:
            raise ValueError("group_id must be non-negative")
        if self.epoch < 1:
            raise ValueError("epoch must be at least 1")
        if self.logical_ciphertexts < 1:
            raise ValueError("logical_ciphertexts must be at least 1")
        if self.payload_bytes < 1:
            raise ValueError("payload_bytes must be at least 1")
