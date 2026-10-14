from dataclasses import dataclass, field

import pytest

from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree
from ranger_iot.ranger.coding import CodingParameters
from ranger_iot.ranger.recovery_protocol import (
    RangerRecoveryParameters,
    RangerRecoveryProtocol,
    RecoveryRequest,
)
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


@dataclass(slots=True)
class _DropFirstLinkAttempt:
    sender: int
    receiver: int
    dropped: bool = field(default=False, init=False)

    def should_drop(
        self,
        *,
        sender: int,
        receiver: int,
        packet: Packet,
        rng: RandomStream,
    ) -> bool:
        del packet, rng
        if self.dropped or sender != self.sender or receiver != self.receiver:
            return False
        self.dropped = True
        return True


def _build_protocol(
    *,
    loss_model: LossModel | None = None,
) -> tuple[SimulationEngine, GroupState, NetworkMetrics, RangerRecoveryProtocol]:
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
        rng=RandomStream(42, "ranger-recovery-test"),
        observers=(metrics,),
    )
    transport = FloodTransport(
        network=network,
        topology=topology,
        packet_factory=PacketFactory(),
    )
    group = GroupState(group_id=7, manager_id=0, member_ids={1, 2, 3, 4})
    protocol = RangerRecoveryProtocol(
        group=group,
        tree=LkhKeyTree({1, 2, 3, 4}),
        transport=transport,
        parameters=RangerRecoveryParameters(
            coding=CodingParameters(data_fragments=3, total_fragments=3),
            ciphertext_payload_bytes=64,
            recovery_request_bytes=24,
        ),
    )
    return engine, group, metrics, protocol


def test_recovery_is_idle_when_initial_dissemination_completes() -> None:
    engine, _, _, protocol = _build_protocol()

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()

    assert session.completed
    assert protocol.start_recovery_round(session.epoch) == 0
    stats = protocol.transport_stats(session.epoch)
    assert stats.recovery_rounds == 0
    assert stats.recovery_requests == 0
    assert stats.recovered_members == 0


def test_two_recovery_rounds_cascade_missing_fragment_along_line() -> None:
    engine, group, metrics, protocol = _build_protocol(
        loss_model=_DropFirstLinkAttempt(sender=1, receiver=2)
    )

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()

    assert session.accepted_count == 1
    assert group.member_epoch(1) == 1
    assert group.member_epoch(2) == 0
    assert group.member_epoch(3) == 0

    assert protocol.start_recovery_round(session.epoch) == 3
    engine.run()
    assert session.accepted_count == 2
    assert group.member_epoch(2) == 1
    assert group.member_epoch(3) == 0

    assert protocol.start_recovery_round(session.epoch) == 1
    engine.run()

    assert session.completed
    assert group.member_epoch(3) == 1
    assert group.member_epoch(4) == 0
    stats = protocol.transport_stats(session.epoch)
    assert stats.recovery_rounds == 2
    assert stats.recovery_requests == 4
    assert stats.recovery_fragment_attempts == 2
    assert stats.peer_recovery_fragment_attempts == 2
    assert stats.manager_recovery_fragment_attempts == 0
    assert stats.recovered_members == 2
    assert metrics.snapshot().drops == 1


def test_direct_manager_neighbor_can_supply_missing_fragment() -> None:
    engine, group, _, protocol = _build_protocol(
        loss_model=_DropFirstLinkAttempt(sender=0, receiver=1)
    )

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()
    assert session.accepted_count == 0

    assert protocol.start_recovery_round(session.epoch) == 5
    engine.run()

    assert group.member_epoch(1) == 1
    stats = protocol.transport_stats(session.epoch)
    assert stats.manager_recovery_fragment_attempts == 1
    assert stats.recovered_members >= 1


def test_recovery_request_and_parameters_validation() -> None:
    with pytest.raises(ValueError, match="capsule_id"):
        RecoveryRequest("", 1, 1, 1, (), 1)
    with pytest.raises(ValueError, match="group_id"):
        RecoveryRequest("c", -1, 1, 1, (), 1)
    with pytest.raises(ValueError, match="epoch"):
        RecoveryRequest("c", 1, 0, 1, (), 1)
    with pytest.raises(ValueError, match="requester_id"):
        RecoveryRequest("c", 1, 1, -1, (), 1)
    with pytest.raises(ValueError, match="unique"):
        RecoveryRequest("c", 1, 1, 1, (0, 0), 1)
    with pytest.raises(ValueError, match="sorted"):
        RecoveryRequest("c", 1, 1, 1, (2, 1), 1)
    with pytest.raises(ValueError, match="needed_fragments"):
        RecoveryRequest("c", 1, 1, 1, (), 0)
    with pytest.raises(ValueError, match="recovery_request_bytes"):
        RangerRecoveryParameters(recovery_request_bytes=0)
