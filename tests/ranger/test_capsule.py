import pytest

from ranger_iot.ranger.capsule import RekeyCapsule


def test_rekey_capsule_accepts_valid_metadata() -> None:
    capsule = RekeyCapsule(
        capsule_id="group-7-epoch-3",
        group_id=7,
        epoch=3,
        logical_ciphertexts=5,
        payload_bytes=321,
    )

    assert capsule.epoch == 3
    assert capsule.logical_ciphertexts == 5
    assert capsule.payload_bytes == 321


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("capsule_id", "", "capsule_id"),
        ("group_id", -1, "group_id"),
        ("epoch", 0, "epoch"),
        ("logical_ciphertexts", 0, "logical_ciphertexts"),
        ("payload_bytes", 0, "payload_bytes"),
    ],
)
def test_rekey_capsule_rejects_invalid_metadata(
    field: str,
    value: object,
    message: str,
) -> None:
    values: dict[str, object] = {
        "capsule_id": "capsule-1",
        "group_id": 1,
        "epoch": 1,
        "logical_ciphertexts": 1,
        "payload_bytes": 64,
    }
    values[field] = value

    with pytest.raises(ValueError, match=message):
        RekeyCapsule(**values)  # type: ignore[arg-type]
