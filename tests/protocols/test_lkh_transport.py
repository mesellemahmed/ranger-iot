import pytest

from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree
from ranger_iot.protocols.lkh_transport import LkhTransportParameters, LkhUnicastProtocol
from ranger_iot.sim.core import SimulationEngine
from ranger_iot.sim.delay import ConstantDelay
from ranger_iot.sim.loss import BernoulliLoss, NoLoss
from ranger_iot.sim.metrics import NetworkMetrics
from ranger_iot.sim.network import Network
from ranger_iot.sim.node import NodeRegistry
from ranger_iot.sim.packet import PacketFactory
from ranger_iot.sim.randomness import RandomStream
from ranger_iot.sim.routing import ShortestPathRouter
from ranger_iot.sim.topology import StaticTopology


def build_lkh_line(*, loss_probability: float = 0.0):  # type: ignore[no-untyped-def]
    engine = SimulationEngine()
    nodes = NodeRegistry([0, 1, 2, 3, 4])
    topology = StaticTopology.from_edges(
        nodes=[0, 1, 2, 3, 4],
        edges=[(0, 1), (1, 2), (2, 3), (3, 4)],
    )
    metrics = NetworkMetrics()
    loss_model = NoLoss() if loss_probability == 0.0 else BernoulliLoss(loss_probability)
    network = Network(
        engine=engine,
        topology=topology,
        nodes=nodes,
        loss_model=loss_model,
        delay_model=ConstantDelay(10),
        rng=RandomStream(11, "lkh-transport"),
        observers=[metrics],
    )
    router = ShortestPathRouter(
        network=network,
        topology=topology,
        packet_factory=PacketFactory(),
    )
    group = GroupState(group_id=1, manager_id=0, member_ids={1, 2, 3, 4})
    tree = LkhKeyTree({1, 2, 3, 4})
    protocol = LkhUnicastProtocol(
        group=group,
        tree=tree,
        router=router,
        parameters=LkhTransportParameters(ciphertext_payload_bytes=64),
    )
    return engine, group, metrics, protocol


def test_lkh_unicast_revocation_converges_and_preserves_logical_cost() -> None:
    engine, group, metrics, protocol = build_lkh_line()

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()

    assert session.targets == (1, 2, 3)
    assert session.completed
    assert group.member_epoch(1) == 1
    assert group.member_epoch(2) == 1
    assert group.member_epoch(3) == 1
    assert group.member_epoch(4) == 0
    assert group.revoked_member_ids == (4,)

    plan = protocol.plan(1)
    stats = protocol.transport_stats(1)
    assert plan.logical_ciphertexts == 3
    assert stats.logical_ciphertexts == 3
    assert stats.routed_copies == 4

    summary = session.summary()
    assert summary.t50_us == 20
    assert summary.t95_us == 30
    assert summary.t100_us == 30

    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 9
    assert snapshot.bytes_sent == 9 * 64
    assert snapshot.transmissions_by_node[0] == 4


def test_lkh_member_accepts_only_after_all_required_updates_arrive() -> None:
    engine, group, _, protocol = build_lkh_line()

    session = protocol.start_rekey(revoked_nodes={4})

    assert engine.run(until_us=20) > 0
    assert group.member_epoch(1) == 1
    assert group.member_epoch(2) == 1
    assert group.member_epoch(3) == 0
    assert not session.completed

    engine.run()
    assert group.member_epoch(3) == 1
    assert session.completed


def test_lkh_loss_can_leave_session_incomplete_without_recovery() -> None:
    engine, group, metrics, protocol = build_lkh_line(loss_probability=1.0)

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()

    assert not session.completed
    assert session.accepted_count == 0
    assert group.convergence_fraction() == 0.0
    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 4
    assert snapshot.drops == 4


def test_lkh_supports_periodic_and_sequential_rekeys() -> None:
    engine, group, _, protocol = build_lkh_line()

    periodic = protocol.start_rekey(revoked_nodes=set())
    engine.run()
    assert periodic.completed
    assert protocol.plan(1).logical_ciphertexts == 2

    revoked = protocol.start_rekey(revoked_nodes={4})
    engine.run()

    assert revoked.completed
    assert group.current_epoch == 2
    assert group.member_epoch(4) == 1
    assert group.member_epoch(1) == 2
    assert group.member_epoch(2) == 2
    assert group.member_epoch(3) == 2


def test_lkh_transport_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        LkhTransportParameters(ciphertext_payload_bytes=0)

    engine = SimulationEngine()
    nodes = NodeRegistry([0, 1, 2, 3])
    topology = StaticTopology.from_edges(nodes=[0, 1, 2, 3], edges=[(0, 1), (1, 2), (2, 3)])
    network = Network(
        engine=engine,
        topology=topology,
        nodes=nodes,
        loss_model=NoLoss(),
        delay_model=ConstantDelay(1),
        rng=RandomStream(1),
    )
    router = ShortestPathRouter(network=network, topology=topology, packet_factory=PacketFactory())
    group = GroupState(group_id=1, manager_id=0, member_ids={1, 2, 3})

    with pytest.raises(ValueError, match="same members"):
        LkhUnicastProtocol(group=group, tree=LkhKeyTree({1, 2}), router=router)

    _, _, _, protocol = build_lkh_line()
    with pytest.raises(KeyError, match="unknown rekey epoch"):
        protocol.session(99)
    with pytest.raises(KeyError, match="unknown group member"):
        protocol.start_rekey(revoked_nodes={9})
