from ranger_iot.experiments.config import ExperimentConfig
from ranger_iot.experiments.runner import run_experiment


def test_ranger_adaptive_v2_no_loss_preserves_v1_behavior(tmp_path) -> None:
    config = ExperimentConfig(
        experiment_id="ranger-adaptive-v2-line-smoke",
        protocol="ranger-adaptive-v2",
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

    summary = run_experiment(config, tmp_path / "run").summary

    assert summary["completed"] is True
    assert summary["accepted_count"] == 3
    assert summary["initial_flood_injections"] == 3
    assert summary["adaptive_parity_injections"] == 0
    assert summary["adaptive_nacks"] == 0
    assert summary["adaptive_nack_forwarded"] == 0
    assert summary["adaptive_nack_suppressed"] == 0
    assert summary["radio_transmissions"] == 12
    assert summary["manager_radio_transmissions"] == 3
    assert summary["t100_us"] == 30
