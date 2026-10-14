import pytest

from ranger_iot.sim.core import SimulationEngine
from ranger_iot.sim.delay import ConstantDelay
from ranger_iot.sim.flooding import FloodTransport
from ranger_iot.sim.loss import NoLoss
from ranger_iot.sim.metrics import NetworkMetrics
from ranger_iot.sim.network import Network
from ranger_iot.sim.node import NodeRegistry
from ranger_iot.sim.packet import PacketFactory
from ranger_iot.sim.randomness import RandomStream
from ranger_iot.sim.topology import StaticTopology


def build_transport(
    *,
    nodes: list[int],
    edges: list[tuple[int, int]],
) -> tuple[SimulationEngine, NetworkMetrics, FloodTransport]:
    engine = SimulationEngine()
    registry = NodeRegistry(nodes)
    topology = StaticTopology.from_edges(nodes=nodes, edges=edges)
    metrics = NetworkMetrics()
    network = Network(
        engine=engine,
        topology=topology,
        nodes=registry,
        loss_model=NoLoss(),
        delay_model=ConstantDelay(10),
        rng=RandomStream(7, "flood"),
        observers=[metrics],
    )
    transport = FloodTransport(
        network=network,
        topology=topology,
        packet_factory=PacketFactory(),
    )
    return engine, metrics, transport


def test_line_flood_forwards_once_per_hop() -> None:
    engine, metrics, transport = build_transport(
        nodes=[0, 1, 2, 3],
        edges=[(0, 1), (1, 2), (2, 3)],
    )
    received: list[tuple[int, int]] = []
    transport.register_receiver(
        3,
        lambda message, at_us: received.append((message.message_id, at_us)),
    )

    assert transport.flood(origin=0, kind="test", payload_bytes=10, epoch=1) == 0
    assert engine.run() == 3
    assert received == [(0, 30)]

    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 3
    assert snapshot.bytes_sent == 30
    assert snapshot.transmissions_by_node == {0: 1, 1: 1, 2: 1}


def test_cycle_duplicate_is_delivered_once_and_does_not_loop() -> None:
    engine, metrics, transport = build_transport(
        nodes=[0, 1, 2, 3],
        edges=[(0, 1), (0, 2), (1, 3), (2, 3)],
    )
    received: list[int] = []
    transport.register_receiver(3, lambda message, at_us: received.append(at_us))

    transport.flood(origin=0, kind="test", payload_bytes=5)
    processed = engine.run(max_events=100)

    assert engine.pending_events == 0
    assert processed == 5
    assert received == [20]
    assert metrics.snapshot().transmissions == 5


def test_flood_transport_validation() -> None:
    _, _, transport = build_transport(nodes=[0, 1], edges=[(0, 1)])

    with pytest.raises(KeyError, match="unknown node"):
        transport.register_receiver(9, lambda message, at_us: None)

    transport.register_receiver(1, lambda message, at_us: None)
    with pytest.raises(ValueError, match="already registered"):
        transport.register_receiver(1, lambda message, at_us: None)

    with pytest.raises(KeyError, match="unknown origin"):
        transport.flood(origin=9, kind="x", payload_bytes=1)
    with pytest.raises(ValueError, match="must not be empty"):
        transport.flood(origin=0, kind="", payload_bytes=1)
    with pytest.raises(ValueError, match="non-negative"):
        transport.flood(origin=0, kind="x", payload_bytes=-1)


def test_direct_neighbor_message_is_not_forwarded() -> None:
    engine, metrics, transport = build_transport(
        nodes=[0, 1, 2],
        edges=[(0, 1), (1, 2)],
    )
    received_at_1: list[tuple[str, int]] = []
    received_at_2: list[str] = []
    transport.register_receiver(
        1,
        lambda message, at_us: received_at_1.append((message.kind, at_us)),
    )
    transport.register_receiver(2, lambda message, at_us: received_at_2.append(message.kind))

    message_id = transport.send_neighbor(
        origin=0,
        destination=1,
        kind="control",
        payload_bytes=7,
        epoch=1,
    )

    assert message_id == 0
    assert engine.run() == 1
    assert received_at_1 == [("control", 10)]
    assert received_at_2 == []
    assert metrics.snapshot().transmissions == 1


def test_direct_neighbor_validation_and_neighbor_view() -> None:
    _, _, transport = build_transport(
        nodes=[0, 1, 2],
        edges=[(0, 1), (1, 2)],
    )

    assert transport.neighbors(1) == (0, 2)
    with pytest.raises(KeyError, match="unknown node"):
        transport.neighbors(9)
    with pytest.raises(ValueError, match="direct neighbors"):
        transport.send_neighbor(
            origin=0,
            destination=2,
            kind="control",
            payload_bytes=1,
        )


def test_direct_neighbor_rejects_invalid_messages() -> None:
    _, _, transport = build_transport(nodes=[0, 1], edges=[(0, 1)])

    with pytest.raises(KeyError, match="unknown origin"):
        transport.send_neighbor(origin=9, destination=1, kind="x", payload_bytes=1)
    with pytest.raises(KeyError, match="unknown destination"):
        transport.send_neighbor(origin=0, destination=9, kind="x", payload_bytes=1)
    with pytest.raises(ValueError, match="must not be empty"):
        transport.send_neighbor(origin=0, destination=1, kind="", payload_bytes=1)
    with pytest.raises(ValueError, match="non-negative"):
        transport.send_neighbor(origin=0, destination=1, kind="x", payload_bytes=-1)
