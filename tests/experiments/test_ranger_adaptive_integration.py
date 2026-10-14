import pytest

from ranger_iot.experiments.campaign import CampaignConfig, iter_experiment_configs
from ranger_iot.experiments.config import ExperimentConfig
from ranger_iot.experiments.runner import run_experiment


def test_ranger_adaptive_no_loss_avoids_upfront_parity(tmp_path) -> None:
    config = ExperimentConfig(
        experiment_id="ranger-adaptive-line-smoke",
        protocol="ranger-adaptive",
        seed=11,
        member_count=4,
        revoked_members=(4,),
        topology="line",
        packet_loss=0.0,
        link_delay_us=10,
        payload_bytes=64,
        ranger_data_fragments=3,
        ranger_adaptive_max_fragments=5,
        ranger_adaptive_recovery_rounds=2,
    )

    result = run_experiment(config, tmp_path / "run")
    summary = result.summary

    assert summary["completed"] is True
    assert summary["accepted_count"] == 3
    assert summary["initial_flood_injections"] == 3
    assert summary["flood_injections"] == 3
    assert summary["adaptive_parity_injections"] == 0
    assert summary["adaptive_nacks"] == 0
    assert summary["unused_redundancy_fragments"] == 2
    assert summary["physical_transmissions"] == 12
    assert summary["manager_transmissions"] == 3
    assert summary["t50_us"] == 20
    assert summary["t95_us"] == 30
    assert summary["t100_us"] == 30


def test_campaign_propagates_adaptive_parameters() -> None:
    campaign = CampaignConfig(
        campaign_id="adaptive-matrix",
        protocols=("ranger-adaptive",),
        topologies=("grid",),
        member_counts=(8,),
        packet_losses=(0.2,),
        seeds=(17,),
        ranger_adaptive_max_fragments=6,
        ranger_adaptive_nack_bytes=20,
        ranger_adaptive_recovery_rounds=3,
    )

    runs = iter_experiment_configs(campaign)

    assert campaign.run_count == 1
    _, experiment = runs[0]
    assert experiment.protocol == "ranger-adaptive"
    assert experiment.ranger_adaptive_max_fragments == 6
    assert experiment.ranger_adaptive_nack_bytes == 20
    assert experiment.ranger_adaptive_recovery_rounds == 3


@pytest.mark.parametrize("max_fragments", [1, 2])
def test_adaptive_max_fragments_must_cover_data_fragments(max_fragments: int) -> None:
    with pytest.raises(ValueError, match="ranger_adaptive_max_fragments"):
        ExperimentConfig(
            experiment_id="invalid-adaptive-profile",
            protocol="ranger-adaptive",
            seed=1,
            member_count=4,
            revoked_members=(4,),
            ranger_data_fragments=3,
            ranger_adaptive_max_fragments=max_fragments,
        )
