import pytest

from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree
from ranger_iot.protocols.lkh_flood import LkhFloodParameters, LkhFloodProtocol
from ranger_iot.sim.core import SimulationEngine
from ranger_iot.sim.delay import ConstantDelay
from ranger_iot.sim.flooding import FloodTransport
from ranger_iot.sim.loss import BernoulliLoss, NoLoss
from ranger_iot.sim.metrics import NetworkMetrics
from ranger_iot.sim.network import Network
from ranger_iot.sim.node import NodeRegistry
from ranger_iot.sim.packet import PacketFactory
from ranger_iot.sim.randomness import RandomStream
from ranger_iot.sim.topology import StaticTopology


def build_lkh_flood_line(*, loss_probability: float = 0.0):  # type: ignore[no-untyped-def]
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
        rng=RandomStream(13, "lkh-flood"),
        observers=[metrics],
    )
    transport = FloodTransport(
        network=network,
        topology=topology,
        packet_factory=PacketFactory(),
    )
    group = GroupState(group_id=1, manager_id=0, member_ids={1, 2, 3, 4})
    tree = LkhKeyTree({1, 2, 3, 4})
    protocol = LkhFloodProtocol(
        group=group,
        tree=tree,
        transport=transport,
        parameters=LkhFloodParameters(ciphertext_payload_bytes=64),
    )
    return engine, group, metrics, protocol


def test_lkh_flood_revocation_converges_with_one_injection_per_ciphertext() -> None:
    engine, group, metrics, protocol = build_lkh_flood_line()

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()

    assert session.targets == (1, 2, 3)
    assert session.completed
    assert group.member_epoch(1) == 1
    assert group.member_epoch(2) == 1
    assert group.member_epoch(3) == 1
    assert group.member_epoch(4) == 0

    stats = protocol.transport_stats(1)
    assert stats.logical_ciphertexts == 3
    assert stats.flood_injections == 3

    summary = session.summary()
    assert summary.t50_us == 20
    assert summary.t95_us == 30
    assert summary.t100_us == 30

    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 12
    assert snapshot.bytes_sent == 12 * 64
    assert snapshot.transmissions_by_node[0] == 3


def test_revoked_member_remains_available_as_a_relay() -> None:
    engine, group, _, protocol = build_lkh_flood_line()

    session = protocol.start_rekey(revoked_nodes={2})
    engine.run()

    assert session.completed
    assert not group.is_authorized(2)
    assert group.member_epoch(2) == 0
    assert group.member_epoch(3) == 1
    assert group.member_epoch(4) == 1


def test_lkh_flood_loss_can_leave_session_incomplete_without_recovery() -> None:
    engine, group, metrics, protocol = build_lkh_flood_line(loss_probability=1.0)

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()

    assert not session.completed
    assert session.accepted_count == 0
    assert group.convergence_fraction() == 0.0
    snapshot = metrics.snapshot()
    assert snapshot.transmissions == 3
    assert snapshot.drops == 3


def test_lkh_flood_validation() -> None:
    with pytest.raises(ValueError, match="positive"):
        LkhFloodParameters(ciphertext_payload_bytes=0)

    _, _, _, protocol = build_lkh_flood_line()
    with pytest.raises(KeyError, match="unknown rekey epoch"):
        protocol.session(99)
    with pytest.raises(KeyError, match="unknown group member"):
        protocol.start_rekey(revoked_nodes={9})
