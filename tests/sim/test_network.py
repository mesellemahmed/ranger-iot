import pytest

from ranger_iot.sim.core import ScheduledEvent, SimulationEngine
from ranger_iot.sim.delay import ConstantDelay
from ranger_iot.sim.loss import BernoulliLoss, NoLoss
from ranger_iot.sim.metrics import DropReason, NetworkMetrics
from ranger_iot.sim.network import Network
from ranger_iot.sim.node import NodeRegistry
from ranger_iot.sim.packet import PacketFactory
from ranger_iot.sim.randomness import RandomStream
from ranger_iot.sim.topology import StaticTopology


def build_network(
    *, loss_probability: float = 0.0
) -> tuple[
    SimulationEngine,
    NodeRegistry,
    NetworkMetrics,
    Network,
    PacketFactory,
]:
    engine = SimulationEngine()
    nodes = NodeRegistry([0, 1, 2])
    topology = StaticTopology.from_edges(nodes=[0, 1, 2], edges=[(0, 1), (0, 2)])
    metrics = NetworkMetrics()
    network = Network(
        engine=engine,
        topology=topology,
        nodes=nodes,
        loss_model=BernoulliLoss(loss_probability),
        delay_model=ConstantDelay(10),
        rng=RandomStream(123, "network"),
        observers=[metrics],
    )
    return engine, nodes, metrics, network, PacketFactory()


def test_unicast_delivery_and_metrics() -> None:
    engine, _, metrics, network, factory = build_network()
    received: list[tuple[int, int, int]] = []
    network.register_receiver(
        1,
        lambda packet, sender, at_us: received.append((packet.packet_id, sender, at_us)),
    )
    packet = factory.create(source=0, kind="hello", payload_bytes=40, created_at_us=0)

    assert network.send(sender=0, receiver=1, packet=packet)
    assert engine.pending_events == 1
    assert engine.run() == 1
    assert received == [(0, 0, 10)]

    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 1
    assert snapshot.deliveries == 1
    assert snapshot.drops == 0
    assert snapshot.bytes_sent == 40
    assert snapshot.bytes_delivered == 40


def test_broadcast_uses_deterministic_neighbor_order() -> None:
    engine, _, metrics, network, factory = build_network()
    observed: list[int] = []
    network.register_receiver(1, lambda packet, sender, at_us: observed.append(1))
    network.register_receiver(2, lambda packet, sender, at_us: observed.append(2))
    packet = factory.create(source=0, kind="broadcast", payload_bytes=8, created_at_us=0)

    assert network.broadcast(sender=0, packet=packet) == 2
    assert engine.run() == 2
    assert observed == [1, 2]
    assert metrics.snapshot().transmissions_by_node == {0: 2}


def test_loss_and_inactive_receiver_are_recorded() -> None:
    engine, nodes, metrics, network, factory = build_network(loss_probability=1.0)
    packet = factory.create(source=0, kind="x", payload_bytes=5, created_at_us=0)

    assert not network.send(sender=0, receiver=1, packet=packet)
    nodes.set_active(2, False)
    assert not network.send(sender=0, receiver=2, packet=packet)
    assert engine.pending_events == 0

    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 2
    assert snapshot.drops == 2
    assert snapshot.drops_by_reason == {
        DropReason.LOSS_MODEL: 1,
        DropReason.RECEIVER_INACTIVE: 1,
    }


def test_receiver_can_go_offline_after_transmission() -> None:
    engine, nodes, metrics, network, factory = build_network()
    packet = factory.create(source=0, kind="x", payload_bytes=5, created_at_us=0)

    assert network.send(sender=0, receiver=1, packet=packet)
    nodes.set_active(1, False)
    assert engine.run() == 1
    assert metrics.snapshot().drops_by_reason == {DropReason.RECEIVER_INACTIVE: 1}


def test_network_send_validation() -> None:
    _, nodes, _, network, factory = build_network()
    packet = factory.create(source=0, kind="x", payload_bytes=1, created_at_us=0)

    with pytest.raises(KeyError, match="unknown sender"):
        network.send(sender=9, receiver=1, packet=packet)
    with pytest.raises(KeyError, match="unknown receiver"):
        network.send(sender=0, receiver=9, packet=packet)

    nodes.set_active(0, False)
    with pytest.raises(RuntimeError, match="inactive"):
        network.send(sender=0, receiver=1, packet=packet)
    nodes.set_active(0, True)

    with pytest.raises(ValueError, match="must differ"):
        network.send(sender=0, receiver=0, packet=packet)

    wrong_source = factory.create(source=1, kind="x", payload_bytes=1, created_at_us=0)
    with pytest.raises(ValueError, match="source does not match"):
        network.send(sender=0, receiver=1, packet=wrong_source)

    with pytest.raises(ValueError, match="not directly connected"):
        network.send(sender=1, receiver=2, packet=wrong_source)


def test_receiver_registration_and_topology_validation() -> None:
    engine, _, _, network, _ = build_network()
    network.register_receiver(1, lambda packet, sender, at_us: None)

    with pytest.raises(ValueError, match="already registered"):
        network.register_receiver(1, lambda packet, sender, at_us: None)
    with pytest.raises(KeyError, match="unknown node"):
        network.register_receiver(9, lambda packet, sender, at_us: None)

    nodes = NodeRegistry([0, 1])
    topology = StaticTopology.from_edges(nodes=[0], edges=[])
    with pytest.raises(ValueError, match="same node identifiers"):
        Network(
            engine=SimulationEngine(),
            topology=topology,
            nodes=nodes,
            loss_model=NoLoss(),
            delay_model=ConstantDelay(0),
            rng=RandomStream(1),
        )

    assert engine.pending_events == 0


def test_invalid_delivery_payload_is_rejected() -> None:
    _, _, _, network, _ = build_network()
    bad_event = ScheduledEvent(at_us=0, sequence=0, kind=Network.DELIVERY_EVENT, payload="bad")

    with pytest.raises(TypeError, match="invalid network delivery payload"):
        network._handle_delivery(bad_event)
