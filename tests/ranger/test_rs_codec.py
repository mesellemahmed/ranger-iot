from __future__ import annotations

from dataclasses import replace
from itertools import combinations

import pytest

from ranger_iot.ranger.rs_codec import (
    ReedSolomonCodec,
    ReedSolomonFragment,
    ReedSolomonParameters,
)

PARAMETERS = ReedSolomonParameters(
    data_shards=3,
    total_shards=5,
)


def make_payload(
    length: int,
) -> bytes:
    return bytes((length * 29 + index * 17) % 256 for index in range(length))


@pytest.mark.parametrize(
    "length",
    [
        1,
        2,
        3,
        4,
        5,
        7,
        15,
        16,
        17,
        31,
        32,
        33,
        64,
        127,
        128,
        129,
        255,
    ],
)
def test_any_three_of_five_reconstruct_exact_payload(
    length: int,
) -> None:
    codec = ReedSolomonCodec(PARAMETERS)

    payload = make_payload(length)

    fragments = codec.encode(payload)

    assert len(fragments) == 5

    assert [fragment.index for fragment in fragments] == [
        0,
        1,
        2,
        3,
        4,
    ]

    for subset in combinations(
        fragments,
        3,
    ):
        assert codec.decode(subset) == payload


def test_systematic_generator_starts_with_identity() -> None:
    codec = ReedSolomonCodec(PARAMETERS)

    assert codec.generator_matrix[:3] == (
        (1, 0, 0),
        (0, 1, 0),
        (0, 0, 1),
    )


def test_systematic_fragments_contain_padded_payload_shards() -> None:
    codec = ReedSolomonCodec(PARAMETERS)

    fragments = codec.encode(b"abcdefghijklmnop")

    assert fragments[0].data == b"abcdef"

    assert fragments[1].data == b"ghijkl"

    assert fragments[2].data == b"mnop\x00\x00"


def test_generic_two_of_three_profile() -> None:
    codec = ReedSolomonCodec(
        ReedSolomonParameters(
            data_shards=2,
            total_shards=3,
        )
    )

    payload = b"generic-profile"

    fragments = codec.encode(payload)

    for subset in combinations(
        fragments,
        2,
    ):
        assert codec.decode(subset) == payload


def test_generic_four_of_six_profile() -> None:
    codec = ReedSolomonCodec(
        ReedSolomonParameters(
            data_shards=4,
            total_shards=6,
        )
    )

    payload = make_payload(73)

    fragments = codec.encode(payload)

    for subset in combinations(
        fragments,
        4,
    ):
        assert codec.decode(subset) == payload


def test_insufficient_distinct_fragments_are_rejected() -> None:
    codec = ReedSolomonCodec(PARAMETERS)

    fragments = codec.encode(b"payload")

    with pytest.raises(
        ValueError,
        match="insufficient distinct fragments",
    ):
        codec.decode(fragments[:2])


def test_identical_duplicate_fragment_does_not_increase_rank() -> None:
    codec = ReedSolomonCodec(PARAMETERS)

    fragments = codec.encode(b"payload")

    with pytest.raises(
        ValueError,
        match="insufficient distinct fragments",
    ):
        codec.decode(
            (
                fragments[0],
                fragments[0],
                fragments[1],
            )
        )


def test_conflicting_duplicate_fragment_is_rejected() -> None:
    codec = ReedSolomonCodec(PARAMETERS)

    fragments = codec.encode(b"payload")

    conflicting = replace(
        fragments[0],
        data=(bytes([fragments[0].data[0] ^ 1]) + fragments[0].data[1:]),
    )

    with pytest.raises(
        ValueError,
        match=("conflicting duplicate fragment index"),
    ):
        codec.decode(
            (
                fragments[0],
                conflicting,
                fragments[1],
                fragments[2],
            )
        )


def test_corrupted_fragment_is_detected_by_payload_crc() -> None:
    codec = ReedSolomonCodec(PARAMETERS)

    fragments = codec.encode(b"0123456789abcdef")

    corrupted = replace(
        fragments[0],
        data=(bytes([fragments[0].data[0] ^ 1]) + fragments[0].data[1:]),
    )

    with pytest.raises(
        ValueError,
        match=("reconstructed payload CRC mismatch"),
    ):
        codec.decode(
            (
                corrupted,
                fragments[1],
                fragments[2],
            )
        )


def test_fragment_metadata_mismatch_is_rejected() -> None:
    codec = ReedSolomonCodec(PARAMETERS)

    fragments = codec.encode(b"0123456789abcdef")

    mismatch = replace(
        fragments[1],
        original_length=(fragments[1].original_length - 1),
    )

    with pytest.raises(
        ValueError,
        match="fragment metadata mismatch",
    ):
        codec.decode(
            (
                fragments[0],
                mismatch,
                fragments[2],
            )
        )


@pytest.mark.parametrize(
    (
        "data_shards",
        "total_shards",
        "message",
    ),
    [
        (
            0,
            5,
            "data_shards must be at least 1",
        ),
        (
            4,
            3,
            ("total_shards must be >= data_shards"),
        ),
        (
            1,
            256,
            "total_shards must be <= 255",
        ),
    ],
)
def test_invalid_parameters_are_rejected(
    data_shards: int,
    total_shards: int,
    message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=message,
    ):
        ReedSolomonParameters(
            data_shards=data_shards,
            total_shards=total_shards,
        )


def test_encode_requires_non_empty_bytes() -> None:
    codec = ReedSolomonCodec(PARAMETERS)

    with pytest.raises(
        ValueError,
        match="payload must not be empty",
    ):
        codec.encode(b"")

    with pytest.raises(
        TypeError,
        match="payload must be bytes",
    ):
        codec.encode(bytearray(b"x"))  # type: ignore[arg-type]


def test_fragment_profile_mismatch_is_rejected() -> None:
    codec = ReedSolomonCodec(PARAMETERS)

    fragments = codec.encode(b"payload")

    wrong_k = replace(
        fragments[0],
        data_shards=4,
    )

    with pytest.raises(
        ValueError,
        match=("fragment data_shards mismatch"),
    ):
        codec.decode(
            (
                wrong_k,
                fragments[1],
                fragments[2],
            )
        )

    wrong_n = replace(
        fragments[0],
        total_shards=6,
    )

    with pytest.raises(
        ValueError,
        match=("fragment total_shards mismatch"),
    ):
        codec.decode(
            (
                wrong_n,
                fragments[1],
                fragments[2],
            )
        )


def test_fragment_constructor_validates_crc() -> None:
    with pytest.raises(
        ValueError,
        match="payload_crc32 out of range",
    ):
        ReedSolomonFragment(
            index=0,
            data=b"x",
            original_length=1,
            shard_size=1,
            data_shards=1,
            total_shards=1,
            payload_crc32=-1,
        )
