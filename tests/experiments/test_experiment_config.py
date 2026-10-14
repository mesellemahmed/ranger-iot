from pathlib import Path

import pytest
from pydantic import ValidationError

from ranger_iot.experiments.config import ExperimentConfig


def make_config(**overrides: object) -> ExperimentConfig:
    values: dict[str, object] = {
        "experiment_id": "smoke",
        "protocol": "skdc",
        "seed": 7,
        "member_count": 4,
        "revoked_members": (4,),
    }
    values.update(overrides)
    return ExperimentConfig.model_validate(values)


def test_config_generates_deterministic_member_identifiers() -> None:
    config = make_config(member_count=4)

    assert config.member_ids == (1, 2, 3, 4)
    assert config.all_node_ids == (0, 1, 2, 3, 4)


def test_config_validation_rejects_invalid_membership() -> None:
    with pytest.raises(ValidationError, match="at least one member"):
        make_config(revoked_members=())
    with pytest.raises(ValidationError, match="must be unique"):
        make_config(revoked_members=(2, 2))
    with pytest.raises(ValidationError, match="outside the group"):
        make_config(revoked_members=(9,))
    with pytest.raises(ValidationError, match="retain at least one"):
        make_config(member_count=2, revoked_members=(1, 2))


def test_config_loads_yaml_and_forbids_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "experiment.yaml"
    path.write_text(
        "\n".join(
            [
                "experiment_id: yaml-smoke",
                "protocol: lkh-unicast",
                "seed: 11",
                "member_count: 4",
                "revoked_members: [4]",
            ]
        ),
        encoding="utf-8",
    )

    config = ExperimentConfig.from_yaml(path)
    assert config.protocol == "lkh-unicast"

    path.write_text("- invalid\n- sequence\n", encoding="utf-8")
    with pytest.raises(ValueError, match="YAML mapping"):
        ExperimentConfig.from_yaml(path)


def test_config_accepts_lkh_flood_protocol() -> None:
    config = make_config(protocol="lkh-flood")
    assert config.protocol == "lkh-flood"


@pytest.mark.parametrize("topology", ["line", "star", "balanced-tree", "grid"])
def test_config_accepts_supported_topologies(topology: str) -> None:
    config = make_config(topology=topology)
    assert config.topology == topology


def test_config_rejects_unknown_topology() -> None:
    with pytest.raises(ValidationError):
        make_config(topology="ring")
