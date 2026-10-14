from dataclasses import replace

import pytest

from ranger_iot.ranger.capsule import RekeyCapsule
from ranger_iot.ranger.coding import (
    CodedFragment,
    CodingParameters,
    FragmentAccumulator,
    StaticErasureCoder,
)


def _capsule() -> RekeyCapsule:
    return RekeyCapsule(
        capsule_id="g1-e8",
        group_id=1,
        epoch=8,
        logical_ciphertexts=3,
        payload_bytes=301,
    )


def _fragments() -> tuple[CodedFragment, ...]:
    return StaticErasureCoder.encode(_capsule(), CodingParameters(3, 5))


def test_coding_parameters_report_redundancy_and_fragment_size() -> None:
    parameters = CodingParameters(data_fragments=3, total_fragments=5)

    assert parameters.redundancy_fragments == 2
    assert parameters.fragment_payload_bytes(301) == 101
    assert parameters.fragment_payload_bytes(300) == 100


@pytest.mark.parametrize(
    ("data_fragments", "total_fragments"),
    [(0, 1), (3, 2)],
)
def test_coding_parameters_reject_invalid_values(
    data_fragments: int,
    total_fragments: int,
) -> None:
    with pytest.raises(ValueError):
        CodingParameters(data_fragments, total_fragments)


def test_coding_parameters_reject_zero_payload() -> None:
    with pytest.raises(ValueError, match="payload_bytes"):
        CodingParameters(3, 5).fragment_payload_bytes(0)


def test_static_coder_emits_deterministic_k_of_n_metadata() -> None:
    fragments = _fragments()

    assert len(fragments) == 5
    assert tuple(fragment.fragment_index for fragment in fragments) == (0, 1, 2, 3, 4)
    assert {fragment.payload_bytes for fragment in fragments} == {101}
    assert {fragment.data_fragments for fragment in fragments} == {3}
    assert {fragment.total_fragments for fragment in fragments} == {5}
    assert {fragment.epoch for fragment in fragments} == {8}


def test_accumulator_decodes_any_three_distinct_fragments() -> None:
    fragments = _fragments()
    accumulator = FragmentAccumulator("g1-e8", 1, 8, CodingParameters(3, 5))

    assert accumulator.accept(fragments[0])
    assert accumulator.accept(fragments[3])
    assert not accumulator.decodable
    assert accumulator.remaining_needed == 1

    assert accumulator.accept(fragments[4])
    assert accumulator.decodable
    assert accumulator.unique_received == 3
    assert accumulator.remaining_needed == 0


def test_accumulator_does_not_count_duplicate_fragment_twice() -> None:
    fragments = _fragments()
    accumulator = FragmentAccumulator("g1-e8", 1, 8, CodingParameters(3, 5))

    assert accumulator.accept(fragments[0])
    assert not accumulator.accept(fragments[0])
    assert accumulator.accept(fragments[1])

    assert accumulator.unique_received == 2
    assert not accumulator.decodable


@pytest.mark.parametrize(
    "fragment",
    [
        replace(_fragments()[0], capsule_id="other"),
        replace(_fragments()[0], group_id=2),
        replace(_fragments()[0], epoch=9),
        replace(_fragments()[0], data_fragments=2),
        replace(_fragments()[0], total_fragments=6),
    ],
)
def test_accumulator_rejects_mismatched_fragment(fragment: CodedFragment) -> None:
    accumulator = FragmentAccumulator("g1-e8", 1, 8, CodingParameters(3, 5))

    with pytest.raises(ValueError):
        accumulator.accept(fragment)


@pytest.mark.parametrize(
    "changes",
    [
        {"capsule_id": ""},
        {"group_id": -1},
        {"epoch": 0},
        {"fragment_index": -1},
        {"fragment_index": 5},
        {"data_fragments": 0},
        {"data_fragments": 4, "total_fragments": 3},
        {"payload_bytes": 0},
    ],
)
def test_coded_fragment_rejects_invalid_metadata(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "capsule_id": "g1-e8",
        "group_id": 1,
        "epoch": 8,
        "fragment_index": 0,
        "data_fragments": 3,
        "total_fragments": 5,
        "payload_bytes": 101,
    }
    values.update(changes)

    with pytest.raises(ValueError):
        CodedFragment(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("capsule_id", "group_id", "epoch"),
    [("", 1, 8), ("g1-e8", -1, 8), ("g1-e8", 1, 0)],
)
def test_accumulator_rejects_invalid_identity(
    capsule_id: str,
    group_id: int,
    epoch: int,
) -> None:
    with pytest.raises(ValueError):
        FragmentAccumulator(capsule_id, group_id, epoch, CodingParameters(3, 5))
