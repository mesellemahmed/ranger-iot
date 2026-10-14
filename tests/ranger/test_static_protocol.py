from dataclasses import dataclass

from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree
from ranger_iot.ranger.coding import CodingParameters
from ranger_iot.ranger.static_protocol import RangerStaticParameters, RangerStaticProtocol
from ranger_iot.sim.core import SimulationEngine
from ranger_iot.sim.delay import ConstantDelay
from ranger_iot.sim.flooding import FloodTransport
from ranger_iot.sim.loss import LossModel, NoLoss
from ranger_iot.sim.metrics import NetworkMetrics
from ranger_iot.sim.network import Network
from ranger_iot.sim.node import NodeRegistry
from ranger_iot.sim.packet import Packet, PacketFactory
from ranger_iot.sim.randomness import RandomStream
from ranger_iot.sim.topology import StaticTopology


@dataclass(frozen=True, slots=True)
class _DropPacketIds:
    packet_ids: frozenset[int]
    sender: int = 0
    receiver: int = 1

    def should_drop(
        self,
        *,
        sender: int,
        receiver: int,
        packet: Packet,
        rng: RandomStream,
    ) -> bool:
        del rng
        return (
            sender == self.sender
            and receiver == self.receiver
            and packet.packet_id in self.packet_ids
        )


def _build_protocol(
    *,
    loss_model: LossModel | None = None,
    revoked_member: int = 4,
    coding: CodingParameters | None = None,
) -> tuple[SimulationEngine, GroupState, NetworkMetrics, RangerStaticProtocol]:
    engine = SimulationEngine()
    node_ids = (0, 1, 2, 3, 4)
    nodes = NodeRegistry(node_ids)
    topology = StaticTopology.from_edges(
        nodes=node_ids,
        edges=((0, 1), (1, 2), (2, 3), (3, 4)),
    )
    metrics = NetworkMetrics()
    network = Network(
        engine=engine,
        topology=topology,
        nodes=nodes,
        loss_model=loss_model or NoLoss(),
        delay_model=ConstantDelay(10),
        rng=RandomStream(42, "ranger-static-test"),
        observers=(metrics,),
    )
    transport = FloodTransport(
        network=network,
        topology=topology,
        packet_factory=PacketFactory(),
    )
    group = GroupState(group_id=7, manager_id=0, member_ids={1, 2, 3, 4})
    tree = LkhKeyTree({1, 2, 3, 4})
    protocol = RangerStaticProtocol(
        group=group,
        tree=tree,
        transport=transport,
        parameters=RangerStaticParameters(
            coding=coding or CodingParameters(data_fragments=3, total_fragments=5),
            ciphertext_payload_bytes=64,
        ),
    )
    assert revoked_member in group.member_ids
    return engine, group, metrics, protocol


def test_static_ranger_completes_without_loss() -> None:
    engine, group, metrics, protocol = _build_protocol()

    session = protocol.start_rekey(revoked_nodes={4})
    processed = engine.run()
    stats = protocol.transport_stats(session.epoch)
    snapshot = metrics.snapshot()

    assert processed == 20
    assert session.completed
    assert session.accepted_at_us == {1: 10, 2: 20, 3: 30}
    assert group.member_epoch(1) == 1
    assert group.member_epoch(2) == 1
    assert group.member_epoch(3) == 1
    assert group.member_epoch(4) == 0
    assert not group.is_authorized(4)

    assert stats.logical_ciphertexts == 3
    assert stats.capsule_payload_bytes == 192
    assert stats.data_fragments == 3
    assert stats.total_fragments == 5
    assert stats.fragment_payload_bytes == 64
    assert stats.flood_injections == 5
    assert snapshot.transmissions == 20
    assert snapshot.bytes_sent == 1280
    assert snapshot.drops == 0


def test_static_ranger_tolerates_two_lost_origin_fragments_for_three_of_five() -> None:
    engine, group, metrics, protocol = _build_protocol(loss_model=_DropPacketIds(frozenset({0, 1})))

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()
    snapshot = metrics.snapshot()

    assert session.completed
    assert session.accepted_count == 3
    assert group.convergence_fraction() == 1.0
    assert snapshot.drops == 2
    assert snapshot.transmissions == 14


def test_static_ranger_fails_when_fewer_than_k_fragments_survive() -> None:
    engine, group, metrics, protocol = _build_protocol(
        loss_model=_DropPacketIds(frozenset({0, 1, 2}))
    )

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()
    snapshot = metrics.snapshot()

    assert not session.completed
    assert session.accepted_count == 0
    assert session.convergence_fraction == 0.0
    assert group.member_epoch(1) == 0
    assert group.member_epoch(2) == 0
    assert group.member_epoch(3) == 0
    assert snapshot.drops == 3


def test_revoked_member_can_relay_but_cannot_accept_epoch() -> None:
    engine, group, _, protocol = _build_protocol(
        revoked_member=2,
        coding=CodingParameters(data_fragments=2, total_fragments=3),
    )

    session = protocol.start_rekey(revoked_nodes={2})
    engine.run()

    assert session.completed
    assert session.targets == (1, 3, 4)
    assert group.member_epoch(1) == 1
    assert group.member_epoch(2) == 0
    assert group.member_epoch(3) == 1
    assert group.member_epoch(4) == 1
    assert not group.is_authorized(2)


def test_static_ranger_exposes_deterministic_capsule_and_fragments() -> None:
    _, _, _, protocol = _build_protocol()

    session = protocol.start_rekey(revoked_nodes={4})
    capsule = protocol.capsule(session.epoch)
    fragments = protocol.fragments(session.epoch)

    assert capsule.capsule_id == "group-7-epoch-1"
    assert capsule.group_id == 7
    assert capsule.epoch == 1
    assert capsule.logical_ciphertexts == 3
    assert capsule.payload_bytes == 192
    assert tuple(fragment.fragment_index for fragment in fragments) == (0, 1, 2, 3, 4)
    assert all(fragment.capsule_id == capsule.capsule_id for fragment in fragments)


def test_static_ranger_rejects_group_tree_mismatch() -> None:
    engine = SimulationEngine()
    nodes = NodeRegistry((0, 1, 2, 3, 4))
    topology = StaticTopology.from_edges(
        nodes=(0, 1, 2, 3, 4),
        edges=((0, 1), (1, 2), (2, 3), (3, 4)),
    )
    network = Network(
        engine=engine,
        topology=topology,
        nodes=nodes,
        loss_model=NoLoss(),
        delay_model=ConstantDelay(10),
        rng=RandomStream(42, "mismatch"),
    )
    transport = FloodTransport(
        network=network,
        topology=topology,
        packet_factory=PacketFactory(),
    )
    group = GroupState(group_id=7, manager_id=0, member_ids={1, 2, 3, 4})
    tree = LkhKeyTree({1, 2, 3})

    try:
        RangerStaticProtocol(group=group, tree=tree, transport=transport)
    except ValueError as exc:
        assert str(exc) == "group and LKH tree must contain the same members"
    else:
        raise AssertionError("expected group/tree mismatch to be rejected")
