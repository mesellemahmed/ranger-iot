import pytest

from ranger_iot.experiments.campaign import CampaignConfig, iter_experiment_configs
from ranger_iot.experiments.config import ExperimentConfig
from ranger_iot.experiments.runner import run_experiment


def test_ranger_static_run_reports_coding_metrics(tmp_path) -> None:
    config = ExperimentConfig(
        experiment_id="ranger-static-line-smoke",
        protocol="ranger-static",
        seed=11,
        member_count=4,
        revoked_members=(4,),
        topology="line",
        packet_loss=0.0,
        link_delay_us=10,
        payload_bytes=64,
        ranger_data_fragments=3,
        ranger_total_fragments=5,
        ranger_capsule_overhead_bytes=0,
    )

    result = run_experiment(config, tmp_path / "run")
    summary = result.summary

    assert summary["completed"] is True
    assert summary["accepted_count"] == 3
    assert summary["logical_ciphertexts"] == 3
    assert summary["capsule_payload_bytes"] == 192
    assert summary["data_fragments"] == 3
    assert summary["total_fragments"] == 5
    assert summary["fragment_payload_bytes"] == 64
    assert summary["flood_injections"] == 5
    assert summary["physical_transmissions"] == 20
    assert summary["manager_transmissions"] == 5
    assert summary["t50_us"] == 20
    assert summary["t95_us"] == 30
    assert summary["t100_us"] == 30


def test_campaign_propagates_ranger_static_profile() -> None:
    campaign = CampaignConfig(
        campaign_id="ranger-profile",
        protocols=("ranger-static",),
        topologies=("grid",),
        member_counts=(8,),
        packet_losses=(0.1,),
        seeds=(29,),
        ranger_data_fragments=4,
        ranger_total_fragments=7,
        ranger_capsule_overhead_bytes=12,
    )

    runs = iter_experiment_configs(campaign)

    assert len(runs) == 1
    _, experiment = runs[0]
    assert experiment.protocol == "ranger-static"
    assert experiment.ranger_data_fragments == 4
    assert experiment.ranger_total_fragments == 7
    assert experiment.ranger_capsule_overhead_bytes == 12


@pytest.mark.parametrize(
    ("data_fragments", "total_fragments"),
    [
        (4, 3),
        (6, 5),
    ],
)
def test_invalid_ranger_coding_profile_is_rejected(
    data_fragments: int,
    total_fragments: int,
) -> None:
    with pytest.raises(ValueError, match="ranger_data_fragments"):
        ExperimentConfig(
            experiment_id="invalid-ranger-profile",
            protocol="ranger-static",
            seed=1,
            member_count=4,
            revoked_members=(4,),
            ranger_data_fragments=data_fragments,
            ranger_total_fragments=total_fragments,
        )


def test_ranger_recovery_is_integrated_into_runner(tmp_path) -> None:
    config = ExperimentConfig(
        experiment_id="ranger-recovery-line-smoke",
        protocol="ranger-recovery",
        seed=11,
        member_count=4,
        revoked_members=(4,),
        topology="line",
        packet_loss=0.0,
        ranger_data_fragments=3,
        ranger_total_fragments=5,
        ranger_recovery_rounds=2,
        ranger_recovery_request_bytes=24,
    )

    summary = run_experiment(config, tmp_path / "recovery").summary

    assert summary["completed"] is True
    assert summary["recovery_rounds"] == 0
    assert summary["recovery_requests"] == 0
    assert summary["recovered_members"] == 0
