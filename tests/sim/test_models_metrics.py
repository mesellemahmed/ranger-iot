import pytest

from ranger_iot.sim.delay import ConstantDelay
from ranger_iot.sim.loss import BernoulliLoss, NoLoss
from ranger_iot.sim.metrics import DropReason, NetworkMetrics
from ranger_iot.sim.packet import Packet
from ranger_iot.sim.randomness import RandomStream


def make_packet() -> Packet:
    return Packet(packet_id=0, source=0, kind="test", payload_bytes=25, created_at_us=0)


def test_loss_models_cover_boundaries() -> None:
    packet = make_packet()
    rng = RandomStream(1)

    assert not NoLoss().should_drop(sender=0, receiver=1, packet=packet, rng=rng)
    assert not BernoulliLoss(0.0).should_drop(sender=0, receiver=1, packet=packet, rng=rng)
    assert BernoulliLoss(1.0).should_drop(sender=0, receiver=1, packet=packet, rng=rng)

    first = BernoulliLoss(0.5).should_drop(
        sender=0, receiver=1, packet=packet, rng=RandomStream(99, "loss")
    )
    replay = BernoulliLoss(0.5).should_drop(
        sender=0, receiver=1, packet=packet, rng=RandomStream(99, "loss")
    )
    assert first == replay

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        BernoulliLoss(-0.1)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        BernoulliLoss(1.1)


def test_constant_delay_and_validation() -> None:
    packet = make_packet()
    delay = ConstantDelay(123)

    assert (
        delay.delay_us(
            sender=0,
            receiver=1,
            packet=packet,
            rng=RandomStream(1),
        )
        == 123
    )

    with pytest.raises(ValueError, match="non-negative"):
        ConstantDelay(-1)


def test_network_metrics_snapshot() -> None:
    packet = make_packet()
    metrics = NetworkMetrics()

    metrics.on_transmit(at_us=0, sender=0, receiver=1, packet=packet)
    metrics.on_deliver(at_us=5, sender=0, receiver=1, packet=packet)
    metrics.on_drop(
        at_us=6,
        sender=0,
        receiver=1,
        packet=packet,
        reason=DropReason.LOSS_MODEL,
    )

    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 1
    assert snapshot.deliveries == 1
    assert snapshot.drops == 1
    assert snapshot.bytes_sent == 25
    assert snapshot.bytes_delivered == 25
    assert snapshot.drops_by_reason == {DropReason.LOSS_MODEL: 1}
    assert snapshot.transmissions_by_node == {0: 1}
