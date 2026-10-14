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


def _star_network() -> tuple[
    SimulationEngine,
    Network,
    NetworkMetrics,
    StaticTopology,
    PacketFactory,
]:
    engine = SimulationEngine()
    topology = StaticTopology.from_edges(
        nodes=(0, 1, 2, 3),
        edges=((0, 1), (0, 2), (0, 3)),
    )
    metrics = NetworkMetrics()
    network = Network(
        engine=engine,
        topology=topology,
        nodes=NodeRegistry((0, 1, 2, 3)),
        loss_model=NoLoss(),
        delay_model=ConstantDelay(10),
        rng=RandomStream(1, "radio-accounting"),
        observers=(metrics,),
    )
    return engine, network, metrics, topology, PacketFactory()


def test_unicast_counts_one_radio_and_one_link_attempt() -> None:
    engine, network, metrics, _, factory = _star_network()
    packet = factory.create(
        source=0,
        kind="unicast",
        payload_bytes=64,
        created_at_us=0,
    )
    assert network.send(sender=0, receiver=1, packet=packet)
    engine.run()
    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 1
    assert snapshot.radio_transmissions == 1
    assert snapshot.bytes_sent == 64
    assert snapshot.radio_bytes_sent == 64
    assert snapshot.deliveries == 1


def test_one_to_many_broadcast_separates_radio_from_link_attempts() -> None:
    engine, network, metrics, _, factory = _star_network()
    packet = factory.create(
        source=0,
        kind="broadcast",
        payload_bytes=64,
        created_at_us=0,
    )
    assert network.broadcast(sender=0, packet=packet) == 3
    engine.run()
    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 3
    assert snapshot.radio_transmissions == 1
    assert snapshot.bytes_sent == 192
    assert snapshot.radio_bytes_sent == 64
    assert snapshot.deliveries == 3
    assert snapshot.transmissions_by_node == {0: 3}
    assert snapshot.radio_transmissions_by_node == {0: 1}


def test_flood_origin_uses_one_radio_broadcast_on_star() -> None:
    engine, network, metrics, topology, factory = _star_network()
    transport = FloodTransport(
        network=network,
        topology=topology,
        packet_factory=factory,
    )
    transport.flood(origin=0, kind="test", payload_bytes=32)
    engine.run()
    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 3
    assert snapshot.radio_transmissions == 1
    assert snapshot.bytes_sent == 96
    assert snapshot.radio_bytes_sent == 32
