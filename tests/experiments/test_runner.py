import json
from pathlib import Path

import pytest

from ranger_iot.experiments.config import ExperimentConfig
from ranger_iot.experiments.runner import run_experiment


def make_config(protocol: str, *, packet_loss: float = 0.0) -> ExperimentConfig:
    return ExperimentConfig.model_validate(
        {
            "experiment_id": f"step4c-{protocol}",
            "protocol": protocol,
            "seed": 42,
            "member_count": 4,
            "revoked_members": [4],
            "packet_loss": packet_loss,
            "link_delay_us": 10,
            "payload_bytes": 64,
        }
    )


def test_skdc_run_writes_expected_artifacts(tmp_path: Path) -> None:
    result = run_experiment(make_config("skdc"), tmp_path / "skdc")

    assert result.summary["completed"] is True
    assert result.summary["logical_ciphertexts"] == 3
    assert result.summary["routed_copies"] == 3
    assert result.summary["physical_transmissions"] == 6
    assert result.summary["bytes_sent"] == 384
    assert result.summary["manager_transmissions"] == 3
    assert result.summary["t50_us"] == 20
    assert result.summary["t95_us"] == 30
    assert result.summary["t100_us"] == 30
    assert sorted(path.name for path in result.output_dir.iterdir()) == [
        "config.json",
        "events.csv",
        "nodes.csv",
        "summary.json",
    ]


def test_lkh_run_preserves_logical_and_physical_costs(tmp_path: Path) -> None:
    result = run_experiment(make_config("lkh-unicast"), tmp_path / "lkh")

    assert result.summary["completed"] is True
    assert result.summary["logical_ciphertexts"] == 3
    assert result.summary["routed_copies"] == 4
    assert result.summary["physical_transmissions"] == 9
    assert result.summary["bytes_sent"] == 576
    assert result.summary["manager_transmissions"] == 4
    assert result.summary["t50_us"] == 20
    assert result.summary["t95_us"] == 30
    assert result.summary["t100_us"] == 30


def test_lkh_flood_run_uses_one_source_injection_per_logical_ciphertext(
    tmp_path: Path,
) -> None:
    result = run_experiment(make_config("lkh-flood"), tmp_path / "lkh-flood")

    assert result.summary["completed"] is True
    assert result.summary["logical_ciphertexts"] == 3
    assert result.summary["routed_copies"] == 3
    assert result.summary["flood_injections"] == 3
    assert result.summary["physical_transmissions"] == 12
    assert result.summary["bytes_sent"] == 768
    assert result.summary["manager_transmissions"] == 3
    assert result.summary["t50_us"] == 20
    assert result.summary["t95_us"] == 30
    assert result.summary["t100_us"] == 30


def test_loss_can_leave_run_incomplete_without_hidden_retries(tmp_path: Path) -> None:
    result = run_experiment(make_config("skdc", packet_loss=1.0), tmp_path / "loss")

    assert result.summary["completed"] is False
    assert result.summary["accepted_count"] == 0
    assert result.summary["t100_us"] is None
    assert result.summary["drops"] == 3


def test_identical_runs_produce_identical_artifacts(tmp_path: Path) -> None:
    config = make_config("lkh-unicast", packet_loss=0.2)
    first = tmp_path / "first"
    second = tmp_path / "second"

    run_experiment(config, first)
    run_experiment(config, second)

    for name in ("config.json", "events.csv", "nodes.csv", "summary.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_output_directory_must_be_empty(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    (output / "sentinel.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="must be empty"):
        run_experiment(make_config("skdc"), output)


def test_summary_json_matches_returned_summary(tmp_path: Path) -> None:
    result = run_experiment(make_config("skdc"), tmp_path / "run")
    persisted = json.loads((result.output_dir / "summary.json").read_text(encoding="utf-8"))

    assert persisted == result.summary


def test_skdc_star_topology_uses_one_hop_per_authorized_member(tmp_path: Path) -> None:
    config = ExperimentConfig.model_validate(
        {
            "experiment_id": "step4e2-skdc-star",
            "protocol": "skdc",
            "seed": 42,
            "member_count": 4,
            "revoked_members": [4],
            "topology": "star",
            "packet_loss": 0.0,
            "link_delay_us": 10,
            "payload_bytes": 64,
        }
    )

    result = run_experiment(config, tmp_path / "skdc-star")

    assert result.summary["completed"] is True
    assert result.summary["physical_transmissions"] == 3
    assert result.summary["manager_transmissions"] == 3
    assert result.summary["t50_us"] == 10
    assert result.summary["t95_us"] == 10
    assert result.summary["t100_us"] == 10
