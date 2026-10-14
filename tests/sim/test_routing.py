import pytest

from ranger_iot.sim.core import SimulationEngine
from ranger_iot.sim.delay import ConstantDelay
from ranger_iot.sim.loss import BernoulliLoss, NoLoss
from ranger_iot.sim.metrics import NetworkMetrics
from ranger_iot.sim.network import Network
from ranger_iot.sim.node import NodeRegistry
from ranger_iot.sim.packet import PacketFactory
from ranger_iot.sim.randomness import RandomStream
from ranger_iot.sim.routing import ShortestPathRouter, shortest_path
from ranger_iot.sim.topology import StaticTopology


def build_router(*, loss_probability: float = 0.0):  # type: ignore[no-untyped-def]
    engine = SimulationEngine()
    nodes = NodeRegistry([0, 1, 2, 3])
    topology = StaticTopology.from_edges(
        nodes=[0, 1, 2, 3],
        edges=[(0, 1), (1, 2), (2, 3), (0, 2)],
    )
    metrics = NetworkMetrics()
    network = Network(
        engine=engine,
        topology=topology,
        nodes=nodes,
        loss_model=NoLoss() if loss_probability == 0 else BernoulliLoss(loss_probability),
        delay_model=ConstantDelay(10),
        rng=RandomStream(7, "routing"),
        observers=[metrics],
    )
    router = ShortestPathRouter(
        network=network,
        topology=topology,
        packet_factory=PacketFactory(),
    )
    return engine, topology, metrics, router


def test_shortest_path_is_deterministic() -> None:
    _, topology, _, _ = build_router()

    assert shortest_path(topology, 0, 3) == (0, 2, 3)
    assert shortest_path(topology, 1, 1) == (1,)

    disconnected = StaticTopology.from_edges(nodes=[0, 1], edges=[])
    with pytest.raises(ValueError, match="no route"):
        shortest_path(disconnected, 0, 1)


def test_routed_unicast_delivers_over_multiple_hops() -> None:
    engine, _, metrics, router = build_router()
    received: list[tuple[int, int]] = []
    router.register_receiver(3, lambda message, at_us: received.append((message.message_id, at_us)))

    assert (
        router.send(
            origin=0,
            destination=3,
            kind="test",
            payload_bytes=32,
        )
        == 0
    )
    assert engine.run() == 2
    assert received == [(0, 20)]

    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 2
    assert snapshot.deliveries == 2
    assert snapshot.bytes_sent == 64


def test_routed_unicast_stops_on_loss() -> None:
    engine, _, metrics, router = build_router(loss_probability=1.0)
    received: list[int] = []
    router.register_receiver(3, lambda message, at_us: received.append(message.message_id))

    router.send(
        origin=0,
        destination=3,
        kind="test",
        payload_bytes=32,
    )

    assert engine.run() == 0
    assert received == []
    assert metrics.snapshot().drops == 1


def test_router_validation_and_receiver_registration() -> None:
    _, _, _, router = build_router()

    router.register_receiver(1, lambda message, at_us: None)
    with pytest.raises(ValueError, match="already registered"):
        router.register_receiver(1, lambda message, at_us: None)
    with pytest.raises(KeyError, match="unknown node"):
        router.register_receiver(9, lambda message, at_us: None)

    with pytest.raises(ValueError, match="must differ"):
        router.send(origin=0, destination=0, kind="test", payload_bytes=1)
    with pytest.raises(ValueError, match="must not be empty"):
        router.send(origin=0, destination=1, kind="", payload_bytes=1)
    with pytest.raises(ValueError, match="non-negative"):
        router.send(origin=0, destination=1, kind="test", payload_bytes=-1)


def test_shortest_path_rejects_unknown_nodes() -> None:
    _, topology, _, _ = build_router()

    with pytest.raises(KeyError, match="unknown source"):
        shortest_path(topology, 9, 1)
    with pytest.raises(KeyError, match="unknown destination"):
        shortest_path(topology, 0, 9)
