from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from math import ceil
from zlib import crc32

_PRIMITIVE_POLYNOMIAL = 0x11D
_FIELD_SIZE = 256
_FIELD_ORDER = 255

_GF_EXP = [0] * (_FIELD_ORDER * 2)
_GF_LOG = [0] * _FIELD_SIZE

_x = 1
for _i in range(_FIELD_ORDER):
    _GF_EXP[_i] = _x
    _GF_LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= _PRIMITIVE_POLYNOMIAL

for _i in range(_FIELD_ORDER, len(_GF_EXP)):
    _GF_EXP[_i] = _GF_EXP[_i - _FIELD_ORDER]


def _gf_mul(left: int, right: int) -> int:
    if left == 0 or right == 0:
        return 0
    return _GF_EXP[_GF_LOG[left] + _GF_LOG[right]]


def _gf_inv(value: int) -> int:
    if value == 0:
        raise ZeroDivisionError("zero has no multiplicative inverse in GF(256)")
    return _GF_EXP[_FIELD_ORDER - _GF_LOG[value]]


def _gf_pow(value: int, exponent: int) -> int:
    if exponent < 0:
        raise ValueError("exponent must be non-negative")
    if exponent == 0:
        return 1
    if value == 0:
        return 0
    return _GF_EXP[(_GF_LOG[value] * exponent) % _FIELD_ORDER]


def _matrix_multiply(
    left: Sequence[Sequence[int]],
    right: Sequence[Sequence[int]],
) -> list[list[int]]:
    if not left or not right:
        raise ValueError("matrices must not be empty")

    inner = len(right)

    if any(len(row) != inner for row in left):
        raise ValueError("matrix dimensions are incompatible")

    columns = len(right[0])

    if columns == 0 or any(len(row) != columns for row in right):
        raise ValueError("right matrix must be rectangular")

    result = [[0] * columns for _ in range(len(left))]

    for row_index, row in enumerate(left):
        for column_index in range(columns):
            value = 0

            for inner_index, coefficient in enumerate(row):
                value ^= _gf_mul(
                    coefficient,
                    right[inner_index][column_index],
                )

            result[row_index][column_index] = value

    return result


def _matrix_inverse(
    matrix: Sequence[Sequence[int]],
) -> list[list[int]]:
    size = len(matrix)

    if size == 0 or any(len(row) != size for row in matrix):
        raise ValueError("matrix must be non-empty and square")

    augmented = [
        list(row) + [(1 if row_index == column_index else 0) for column_index in range(size)]
        for row_index, row in enumerate(matrix)
    ]

    for column in range(size):
        pivot = next(
            (
                row
                for row in range(
                    column,
                    size,
                )
                if augmented[row][column] != 0
            ),
            None,
        )

        if pivot is None:
            raise ValueError("matrix is singular over GF(256)")

        (
            augmented[column],
            augmented[pivot],
        ) = (
            augmented[pivot],
            augmented[column],
        )

        inverse_pivot = _gf_inv(augmented[column][column])

        augmented[column] = [
            _gf_mul(
                value,
                inverse_pivot,
            )
            for value in augmented[column]
        ]

        for row in range(size):
            if row == column:
                continue

            factor = augmented[row][column]

            if factor == 0:
                continue

            augmented[row] = [
                left_value
                ^ _gf_mul(
                    factor,
                    pivot_value,
                )
                for (
                    left_value,
                    pivot_value,
                ) in zip(
                    augmented[row],
                    augmented[column],
                    strict=True,
                )
            ]

    return [row[size:] for row in augmented]


def _systematic_generator_matrix(
    data_shards: int,
    total_shards: int,
) -> tuple[
    tuple[int, ...],
    ...,
]:
    vandermonde = [
        [
            _gf_pow(
                row_index + 1,
                column_index,
            )
            for column_index in range(data_shards)
        ]
        for row_index in range(total_shards)
    ]

    systematic_transform = _matrix_inverse(vandermonde[:data_shards])

    generator = _matrix_multiply(
        vandermonde,
        systematic_transform,
    )

    return tuple(tuple(row) for row in generator)


@dataclass(
    frozen=True,
    slots=True,
)
class ReedSolomonParameters:
    data_shards: int
    total_shards: int

    def __post_init__(
        self,
    ) -> None:
        if self.data_shards < 1:
            raise ValueError("data_shards must be at least 1")

        if self.total_shards < self.data_shards:
            raise ValueError("total_shards must be >= data_shards")

        if self.total_shards > _FIELD_ORDER:
            raise ValueError("total_shards must be <= 255")

    @property
    def parity_shards(
        self,
    ) -> int:
        return self.total_shards - self.data_shards


@dataclass(
    frozen=True,
    slots=True,
)
class ReedSolomonFragment:
    index: int
    data: bytes
    original_length: int
    shard_size: int
    data_shards: int
    total_shards: int
    payload_crc32: int

    def __post_init__(
        self,
    ) -> None:
        if not (0 <= self.index < self.total_shards):
            raise ValueError("fragment index out of range")

        if self.original_length < 1:
            raise ValueError("original_length must be at least 1")

        if self.shard_size < 1:
            raise ValueError("shard_size must be at least 1")

        if len(self.data) != self.shard_size:
            raise ValueError("fragment data length does not match shard_size")

        ReedSolomonParameters(
            data_shards=self.data_shards,
            total_shards=self.total_shards,
        )

        if self.original_length > self.shard_size * self.data_shards:
            raise ValueError("original_length exceeds data-shard capacity")

        if not (0 <= self.payload_crc32 <= 0xFFFFFFFF):
            raise ValueError("payload_crc32 out of range")


class ReedSolomonCodec:
    """Systematic MDS erasure coding over GF(256).

    This implementation performs actual
    byte-level coding. Any ``data_shards``
    distinct valid fragments reconstruct the
    original payload exactly.

    CRC32 is used only as a corruption oracle
    after reconstruction. It is not a
    cryptographic authentication mechanism.
    """

    def __init__(
        self,
        parameters: ReedSolomonParameters,
    ) -> None:
        self.parameters = parameters

        self._generator = _systematic_generator_matrix(
            parameters.data_shards,
            parameters.total_shards,
        )

    @property
    def generator_matrix(
        self,
    ) -> tuple[
        tuple[int, ...],
        ...,
    ]:
        return self._generator

    def encode(
        self,
        payload: bytes,
    ) -> tuple[
        ReedSolomonFragment,
        ...,
    ]:
        if not isinstance(
            payload,
            bytes,
        ):
            raise TypeError("payload must be bytes")

        if not payload:
            raise ValueError("payload must not be empty")

        shard_size = ceil(len(payload) / self.parameters.data_shards)

        padded_length = shard_size * self.parameters.data_shards

        padded = payload + bytes(padded_length - len(payload))

        data_vectors = [
            padded[index * shard_size : (index + 1) * shard_size]
            for index in range(self.parameters.data_shards)
        ]

        checksum = crc32(payload) & 0xFFFFFFFF

        fragments: list[ReedSolomonFragment] = []

        for (
            fragment_index,
            row,
        ) in enumerate(self._generator):
            encoded = bytearray(shard_size)

            for byte_index in range(shard_size):
                value = 0

                for (
                    shard_index,
                    coefficient,
                ) in enumerate(row):
                    value ^= _gf_mul(
                        coefficient,
                        data_vectors[shard_index][byte_index],
                    )

                encoded[byte_index] = value

            fragments.append(
                ReedSolomonFragment(
                    index=fragment_index,
                    data=bytes(encoded),
                    original_length=len(payload),
                    shard_size=shard_size,
                    data_shards=self.parameters.data_shards,
                    total_shards=self.parameters.total_shards,
                    payload_crc32=checksum,
                )
            )

        return tuple(fragments)

    def decode(
        self,
        fragments: Iterable[ReedSolomonFragment],
    ) -> bytes:
        by_index: dict[
            int,
            ReedSolomonFragment,
        ] = {}

        reference_metadata: (
            tuple[
                int,
                int,
                int,
            ]
            | None
        ) = None

        for fragment in fragments:
            self._validate_fragment_metadata(fragment)

            metadata = (
                fragment.original_length,
                fragment.shard_size,
                fragment.payload_crc32,
            )

            if reference_metadata is None:
                reference_metadata = metadata

            elif metadata != reference_metadata:
                raise ValueError("fragment metadata mismatch")

            previous = by_index.get(fragment.index)

            if previous is not None:
                if previous != fragment:
                    raise ValueError("conflicting duplicate fragment index")

                continue

            by_index[fragment.index] = fragment

        if len(by_index) < self.parameters.data_shards:
            raise ValueError("insufficient distinct fragments")

        selected = [by_index[index] for index in sorted(by_index)[: self.parameters.data_shards]]

        reference = selected[0]

        selected_matrix = [self._generator[fragment.index] for fragment in selected]

        inverse = _matrix_inverse(selected_matrix)

        recovered_data = [
            bytearray(reference.shard_size) for _ in range(self.parameters.data_shards)
        ]

        for (
            output_shard_index,
            row,
        ) in enumerate(inverse):
            for byte_index in range(reference.shard_size):
                value = 0

                for (
                    selected_index,
                    coefficient,
                ) in enumerate(row):
                    value ^= _gf_mul(
                        coefficient,
                        selected[selected_index].data[byte_index],
                    )

                recovered_data[output_shard_index][byte_index] = value

        payload = b"".join(bytes(shard) for shard in recovered_data)[: reference.original_length]

        if (crc32(payload) & 0xFFFFFFFF) != reference.payload_crc32:
            raise ValueError("reconstructed payload CRC mismatch")

        return payload

    def _validate_fragment_metadata(
        self,
        fragment: ReedSolomonFragment,
    ) -> None:
        if fragment.data_shards != self.parameters.data_shards:
            raise ValueError("fragment data_shards mismatch")

        if fragment.total_shards != self.parameters.total_shards:
            raise ValueError("fragment total_shards mismatch")

        if not (0 <= fragment.index < self.parameters.total_shards):
            raise ValueError("fragment index out of range")
