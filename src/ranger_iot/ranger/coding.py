from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil

from ranger_iot.ranger.capsule import RekeyCapsule


@dataclass(frozen=True, slots=True)
class CodingParameters:
    """Ideal systematic MDS coding parameters for the simulator."""

    data_fragments: int
    total_fragments: int

    def __post_init__(self) -> None:
        if self.data_fragments < 1:
            raise ValueError("data_fragments must be at least 1")
        if self.total_fragments < self.data_fragments:
            raise ValueError("total_fragments must be >= data_fragments")

    @property
    def redundancy_fragments(self) -> int:
        return self.total_fragments - self.data_fragments

    def fragment_payload_bytes(self, payload_bytes: int) -> int:
        if payload_bytes < 1:
            raise ValueError("payload_bytes must be at least 1")
        return ceil(payload_bytes / self.data_fragments)


@dataclass(frozen=True, slots=True)
class CodedFragment:
    """One abstract erasure-coded fragment of a rekey capsule."""

    capsule_id: str
    group_id: int
    epoch: int
    fragment_index: int
    data_fragments: int
    total_fragments: int
    payload_bytes: int

    def __post_init__(self) -> None:
        if not self.capsule_id:
            raise ValueError("capsule_id must not be empty")
        if self.group_id < 0:
            raise ValueError("group_id must be non-negative")
        if self.epoch < 1:
            raise ValueError("epoch must be at least 1")
        if self.data_fragments < 1:
            raise ValueError("data_fragments must be at least 1")
        if self.total_fragments < self.data_fragments:
            raise ValueError("total_fragments must be >= data_fragments")
        if not 0 <= self.fragment_index < self.total_fragments:
            raise ValueError("fragment_index out of range")
        if self.payload_bytes < 1:
            raise ValueError("payload_bytes must be at least 1")


class StaticErasureCoder:
    """Create ideal k-of-n fragments without simulating codec CPU work.

    Any ``data_fragments`` distinct fragments are considered sufficient to
    recover the opaque capsule.  No real Reed-Solomon bytes are generated at
    this abstraction layer.
    """

    @staticmethod
    def encode(
        capsule: RekeyCapsule,
        parameters: CodingParameters,
    ) -> tuple[CodedFragment, ...]:
        fragment_bytes = parameters.fragment_payload_bytes(capsule.payload_bytes)
        return tuple(
            CodedFragment(
                capsule_id=capsule.capsule_id,
                group_id=capsule.group_id,
                epoch=capsule.epoch,
                fragment_index=index,
                data_fragments=parameters.data_fragments,
                total_fragments=parameters.total_fragments,
                payload_bytes=fragment_bytes,
            )
            for index in range(parameters.total_fragments)
        )


@dataclass(slots=True)
class FragmentAccumulator:
    """Track unique fragments for exactly one capsule and coding profile."""

    capsule_id: str
    group_id: int
    epoch: int
    parameters: CodingParameters
    _received_indexes: set[int] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.capsule_id:
            raise ValueError("capsule_id must not be empty")
        if self.group_id < 0:
            raise ValueError("group_id must be non-negative")
        if self.epoch < 1:
            raise ValueError("epoch must be at least 1")

    @property
    def unique_received(self) -> int:
        return len(self._received_indexes)

    @property
    def received_indexes(self) -> tuple[int, ...]:
        return tuple(sorted(self._received_indexes))

    @property
    def decodable(self) -> bool:
        return self.unique_received >= self.parameters.data_fragments

    @property
    def remaining_needed(self) -> int:
        return max(0, self.parameters.data_fragments - self.unique_received)

    def accept(self, fragment: CodedFragment) -> bool:
        """Accept one matching fragment.

        Returns ``True`` only when the fragment contributes a previously unseen
        index.  Metadata mismatches are rejected because fragments from another
        group, epoch, capsule, or coding profile must never be combined.
        """

        self._validate_fragment(fragment)
        before = len(self._received_indexes)
        self._received_indexes.add(fragment.fragment_index)
        return len(self._received_indexes) > before

    def _validate_fragment(self, fragment: CodedFragment) -> None:
        if fragment.capsule_id != self.capsule_id:
            raise ValueError("fragment capsule_id does not match accumulator")
        if fragment.group_id != self.group_id:
            raise ValueError("fragment group_id does not match accumulator")
        if fragment.epoch != self.epoch:
            raise ValueError("fragment epoch does not match accumulator")
        if fragment.data_fragments != self.parameters.data_fragments:
            raise ValueError("fragment data_fragments does not match accumulator")
        if fragment.total_fragments != self.parameters.total_fragments:
            raise ValueError("fragment total_fragments does not match accumulator")
