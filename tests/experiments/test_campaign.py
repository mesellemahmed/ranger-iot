from pathlib import Path

import pytest
from pydantic import ValidationError

from ranger_iot.experiments.campaign import (
    CampaignConfig,
    campaign_sha256,
    iter_experiment_configs,
    run_campaign,
)


def _config() -> CampaignConfig:
    return CampaignConfig(
        campaign_id="campaign-test",
        protocols=("skdc", "lkh-unicast", "lkh-flood"),
        topologies=("line",),
        member_counts=(4, 8),
        packet_losses=(0.0, 0.1),
        seeds=(7, 11),
        revoked_count=1,
        link_delay_us=10,
        payload_bytes=64,
    )


def test_campaign_matrix_has_expected_size_and_order() -> None:
    config = _config()
    runs = iter_experiment_configs(config)

    assert config.run_count == 24
    assert len(runs) == 24
    assert runs[0][0] == "skdc__line__n0004__loss0000__seed000007"
    assert runs[-1][0] == "lkh_flood__line__n0008__loss0100__seed000011"


def test_campaign_revokes_last_member() -> None:
    config = _config()
    runs = iter_experiment_configs(config)

    by_size = {experiment.member_count: experiment for _, experiment in runs}
    assert by_size[4].revoked_members == (4,)
    assert by_size[8].revoked_members == (8,)


def test_campaign_rejects_invalid_matrix() -> None:
    with pytest.raises(ValidationError):
        CampaignConfig(
            campaign_id="bad",
            protocols=("skdc",),
            member_counts=(1,),
            packet_losses=(0.0,),
            seeds=(1,),
            revoked_count=1,
        )


def test_campaign_hash_is_deterministic() -> None:
    first = campaign_sha256(_config())
    second = campaign_sha256(_config())

    assert first == second
    assert len(first) == 64


def test_run_campaign_writes_expected_artifacts(tmp_path: Path) -> None:
    config = CampaignConfig(
        campaign_id="tiny-campaign",
        protocols=("skdc", "lkh-unicast", "lkh-flood"),
        topologies=("line",),
        member_counts=(4,),
        packet_losses=(0.0,),
        seeds=(3,),
        revoked_count=1,
    )

    output = tmp_path / "campaign"
    summary = run_campaign(config, output)

    assert summary["run_count"] == 3
    assert summary["completed_count"] == 3
    assert summary["incomplete_count"] == 0
    assert (output / "campaign.json").is_file()
    assert (output / "campaign_summary.json").is_file()
    assert (output / "aggregate.csv").is_file()

    run_dirs = sorted((output / "runs").iterdir())
    assert len(run_dirs) == 3
    for run_dir in run_dirs:
        assert (run_dir / "config.json").is_file()
        assert (run_dir / "summary.json").is_file()
        assert (run_dir / "events.csv").is_file()
        assert (run_dir / "nodes.csv").is_file()


def test_campaign_is_byte_reproducible(tmp_path: Path) -> None:
    config = CampaignConfig(
        campaign_id="repro-campaign",
        protocols=("skdc", "lkh-unicast", "lkh-flood"),
        member_counts=(4,),
        packet_losses=(0.0,),
        seeds=(17,),
    )
    first = tmp_path / "first"
    second = tmp_path / "second"

    run_campaign(config, first)
    run_campaign(config, second)

    first_files = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
    second_files = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
    assert first_files == second_files

    for relative_path in first_files:
        assert (first / relative_path).read_bytes() == (second / relative_path).read_bytes()


def test_campaign_refuses_non_empty_output(tmp_path: Path) -> None:
    output = tmp_path / "campaign"
    output.mkdir()
    (output / "existing.txt").write_text("do not overwrite", encoding="utf-8")

    with pytest.raises(ValueError, match="output directory must be empty"):
        run_campaign(_config(), output)


def test_campaign_expands_supported_topologies_deterministically() -> None:
    config = CampaignConfig(
        campaign_id="topology-matrix",
        protocols=("skdc",),
        topologies=("line", "star", "balanced-tree", "grid"),
        member_counts=(4,),
        packet_losses=(0.0,),
        seeds=(7,),
    )

    runs = iter_experiment_configs(config)

    assert config.run_count == 4
    assert [experiment.topology for _, experiment in runs] == [
        "line",
        "star",
        "balanced-tree",
        "grid",
    ]
    assert [run_id for run_id, _ in runs] == [
        "skdc__line__n0004__loss0000__seed000007",
        "skdc__star__n0004__loss0000__seed000007",
        "skdc__balanced-tree__n0004__loss0000__seed000007",
        "skdc__grid__n0004__loss0000__seed000007",
    ]


def test_campaign_propagates_recovery_parameters() -> None:
    config = CampaignConfig(
        campaign_id="recovery-matrix",
        protocols=("ranger-recovery",),
        topologies=("line",),
        member_counts=(4,),
        packet_losses=(0.1,),
        seeds=(5,),
        ranger_recovery_rounds=3,
        ranger_recovery_request_bytes=28,
    )

    runs = iter_experiment_configs(config)

    assert config.run_count == 1
    _, experiment = runs[0]
    assert experiment.protocol == "ranger-recovery"
    assert experiment.ranger_recovery_rounds == 3
    assert experiment.ranger_recovery_request_bytes == 28
