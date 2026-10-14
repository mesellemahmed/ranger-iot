from dataclasses import dataclass, field

import pytest

from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree
from ranger_iot.ranger.adaptive_protocol import (
    AdaptiveRedundancyRequest,
    RangerAdaptiveParameters,
    RangerAdaptiveProtocol,
)
from ranger_iot.ranger.coding import CodingParameters
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
    adaptive_recovery_rounds: int = 2,
) -> tuple[SimulationEngine, GroupState, NetworkMetrics, RangerAdaptiveProtocol]:
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
        rng=RandomStream(73, "ranger-adaptive-test"),
        observers=(metrics,),
    )
    transport = FloodTransport(
        network=network,
        topology=topology,
        packet_factory=PacketFactory(),
    )
    group = GroupState(group_id=9, manager_id=0, member_ids={1, 2, 3, 4})
    protocol = RangerAdaptiveProtocol(
        group=group,
        tree=LkhKeyTree({1, 2, 3, 4}),
        transport=transport,
        parameters=RangerAdaptiveParameters(
            coding=CodingParameters(data_fragments=3, total_fragments=5),
            ciphertext_payload_bytes=64,
            recovery_request_bytes=24,
            adaptive_nack_bytes=16,
            adaptive_recovery_rounds=adaptive_recovery_rounds,
        ),
    )
    return engine, group, metrics, protocol


def test_no_loss_uses_only_data_fragments() -> None:
    engine, group, metrics, protocol = _build_protocol()

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()

    assert session.completed
    assert protocol.advance(session.epoch) == 0
    assert group.member_epoch(3) == 1
    assert group.member_epoch(4) == 0

    stats = protocol.transport_stats(session.epoch)
    assert stats.initial_flood_injections == 3
    assert stats.flood_injections == 3
    assert stats.adaptive_parity_injections == 0
    assert stats.adaptive_nacks == 0
    assert stats.unused_redundancy_fragments == 2
    assert metrics.snapshot().transmissions == 12


def test_explicit_nack_releases_only_one_parity_per_round() -> None:
    engine, _, _, protocol = _build_protocol(
        loss_model=_DropFirstLinkAttempt(sender=1, receiver=2),
        adaptive_recovery_rounds=0,
    )

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()
    assert session.accepted_count == 1
    assert protocol._manager_available_indexes(session.epoch) == (0, 1, 2)

    nack_count = protocol.advance(session.epoch)
    assert nack_count == 2
    engine.run()

    assert session.completed
    stats = protocol.transport_stats(session.epoch)
    assert stats.adaptive_nack_rounds == 1
    assert stats.adaptive_nacks == 2
    assert stats.adaptive_nack_hop_attempts == 5
    assert stats.adaptive_parity_injections == 1
    assert stats.flood_injections == 4
    assert stats.unused_redundancy_fragments == 1


def test_adaptive_request_and_parameter_validation() -> None:
    with pytest.raises(ValueError, match="capsule_id"):
        AdaptiveRedundancyRequest("", 1, 1, 1, 1, 0)
    with pytest.raises(ValueError, match="round_id"):
        AdaptiveRedundancyRequest("c", 1, 1, 1, 0, 0)
    with pytest.raises(ValueError, match="unique_received"):
        AdaptiveRedundancyRequest("c", 1, 1, 1, 1, -1)
    with pytest.raises(ValueError, match="adaptive_nack_bytes"):
        RangerAdaptiveParameters(adaptive_nack_bytes=0)
    with pytest.raises(ValueError, match="adaptive_recovery_rounds"):
        RangerAdaptiveParameters(adaptive_recovery_rounds=-1)
