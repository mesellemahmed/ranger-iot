from ranger_iot.experiments.config import ExperimentConfig
from ranger_iot.experiments.runner import run_experiment


def test_skdc_star_radio_equals_link_attempts(tmp_path) -> None:
    config = ExperimentConfig(
        experiment_id="radio-skdc-star",
        protocol="skdc",
        seed=11,
        member_count=4,
        revoked_members=(4,),
        topology="star",
        packet_loss=0.0,
        payload_bytes=64,
    )
    summary = run_experiment(config, tmp_path / "skdc").summary
    assert summary["completed"] is True
    assert summary["link_attempts"] == 3
    assert summary["radio_transmissions"] == 3
    assert summary["manager_radio_transmissions"] == 3
    assert summary["link_bytes_attempted"] == 192
    assert summary["radio_bytes_sent"] == 192


def test_lkh_flood_star_uses_one_radio_per_flood(tmp_path) -> None:
    config = ExperimentConfig(
        experiment_id="radio-lkh-flood-star",
        protocol="lkh-flood",
        seed=11,
        member_count=4,
        revoked_members=(4,),
        topology="star",
        packet_loss=0.0,
        payload_bytes=64,
    )
    summary = run_experiment(config, tmp_path / "flood").summary
    assert summary["completed"] is True
    assert summary["logical_ciphertexts"] == 3
    assert summary["flood_injections"] == 3
    assert summary["link_attempts"] == 12
    assert summary["radio_transmissions"] == 3
    assert summary["manager_radio_transmissions"] == 3
    assert summary["link_bytes_attempted"] == 768
    assert summary["radio_bytes_sent"] == 192
