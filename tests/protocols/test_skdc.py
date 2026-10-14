from ranger_iot.group import GroupState
from ranger_iot.protocols.skdc import SkdcParameters, SkdcProtocol
from ranger_iot.sim.core import SimulationEngine
from ranger_iot.sim.delay import ConstantDelay
from ranger_iot.sim.loss import NoLoss
from ranger_iot.sim.metrics import NetworkMetrics
from ranger_iot.sim.network import Network
from ranger_iot.sim.node import NodeRegistry
from ranger_iot.sim.packet import PacketFactory
from ranger_iot.sim.randomness import RandomStream
from ranger_iot.sim.routing import ShortestPathRouter
from ranger_iot.sim.topology import StaticTopology


def build_skdc_line():  # type: ignore[no-untyped-def]
    engine = SimulationEngine()
    nodes = NodeRegistry([0, 1, 2, 3, 4])
    topology = StaticTopology.from_edges(
        nodes=[0, 1, 2, 3, 4],
        edges=[(0, 1), (1, 2), (2, 3), (3, 4)],
    )
    metrics = NetworkMetrics()
    network = Network(
        engine=engine,
        topology=topology,
        nodes=nodes,
        loss_model=NoLoss(),
        delay_model=ConstantDelay(10),
        rng=RandomStream(1, "skdc"),
        observers=[metrics],
    )
    router = ShortestPathRouter(
        network=network,
        topology=topology,
        packet_factory=PacketFactory(),
    )
    group = GroupState(group_id=1, manager_id=0, member_ids={1, 2, 3, 4})
    protocol = SkdcProtocol(
        group=group,
        router=router,
        parameters=SkdcParameters(rekey_payload_bytes=64),
    )
    return engine, group, metrics, protocol


def test_skdc_revocation_excludes_member_and_converges() -> None:
    engine, group, metrics, protocol = build_skdc_line()

    session = protocol.start_rekey(revoked_nodes={3})
    assert session.targets == (1, 2, 4)

    engine.run()

    assert group.current_epoch == 1
    assert group.member_epoch(1) == 1
    assert group.member_epoch(2) == 1
    assert group.member_epoch(3) == 0
    assert group.member_epoch(4) == 1
    assert group.revoked_member_ids == (3,)

    summary = session.summary()
    assert summary.completed
    assert summary.t50_us == 20
    assert summary.t95_us == 40
    assert summary.t100_us == 40

    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 7
    assert snapshot.bytes_sent == 7 * 64


def test_skdc_supports_sequential_rekeys() -> None:
    engine, group, _, protocol = build_skdc_line()

    first = protocol.start_rekey(revoked_nodes={4})
    engine.run()
    assert first.completed

    second = protocol.start_rekey(revoked_nodes={3})
    engine.run()

    assert group.current_epoch == 2
    assert second.targets == (1, 2)
    assert second.completed
    assert group.member_epoch(1) == 2
    assert group.member_epoch(2) == 2
    assert group.member_epoch(3) == 1
    assert group.member_epoch(4) == 0


def test_skdc_parameter_and_session_validation() -> None:
    from pytest import raises

    with raises(ValueError, match="positive"):
        SkdcParameters(rekey_payload_bytes=0)

    _, _, _, protocol = build_skdc_line()
    with raises(KeyError, match="unknown rekey epoch"):
        protocol.session(99)


def test_skdc_can_rekey_without_revocation() -> None:
    engine, group, _, protocol = build_skdc_line()

    session = protocol.start_rekey(revoked_nodes=set())
    engine.run()

    assert session.targets == (1, 2, 3, 4)
    assert session.completed
    assert group.current_epoch == 1
    assert group.convergence_fraction() == 1.0
