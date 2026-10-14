from ranger_iot.experiments.artifacts import canonical_config_json, config_sha256
from ranger_iot.experiments.config import ExperimentConfig
from ranger_iot.experiments.trace import NetworkTrace
from ranger_iot.sim.metrics import DropReason
from ranger_iot.sim.packet import Packet


def test_trace_records_stable_rows() -> None:
    trace = NetworkTrace()
    packet = Packet(
        packet_id=3,
        source=1,
        kind="x",
        payload_bytes=64,
        created_at_us=0,
        epoch=1,
    )

    trace.on_transmit(at_us=0, sender=1, receiver=2, packet=packet)
    trace.on_deliver(at_us=10, sender=1, receiver=2, packet=packet)
    trace.on_drop(
        at_us=20,
        sender=1,
        receiver=2,
        packet=packet,
        reason=DropReason.LOSS_MODEL,
    )

    assert [row["event"] for row in trace.rows()] == ["transmit", "deliver", "drop"]
    assert trace.rows()[-1]["drop_reason"] == "loss_model"


def test_canonical_config_hash_is_stable() -> None:
    config = ExperimentConfig(
        experiment_id="hash",
        protocol="skdc",
        seed=1,
        member_count=4,
        revoked_members=(4,),
    )

    assert canonical_config_json(config).endswith("\n")
    assert config_sha256(config) == config_sha256(config)
