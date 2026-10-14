import pytest

from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree
from ranger_iot.ranger.adaptive_protocol import (
    AdaptiveRedundancyRequest,
    RangerAdaptiveParameters,
)
from ranger_iot.ranger.adaptive_v2_protocol import RangerAdaptiveV2Protocol
from ranger_iot.ranger.coding import CodingParameters
from ranger_iot.sim.core import SimulationEngine
from ranger_iot.sim.delay import ConstantDelay
from ranger_iot.sim.flooding import FloodMessage, FloodTransport
from ranger_iot.sim.loss import LossModel, NoLoss
from ranger_iot.sim.metrics import NetworkMetrics
from ranger_iot.sim.network import Network
from ranger_iot.sim.node import NodeRegistry
from ranger_iot.sim.packet import Packet, PacketFactory
from ranger_iot.sim.randomness import RandomStream
from ranger_iot.sim.topology import StaticTopology


class _DropFirstLinkAttempt:
    sender: int
    receiver: int
    dropped: bool

    def __init__(self, *, sender: int, receiver: int) -> None:
        self.sender = sender
        self.receiver = receiver
        self.dropped = False

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
    adaptive_recovery_rounds: int = 0,
) -> tuple[
    SimulationEngine,
    GroupState,
    NetworkMetrics,
    RangerAdaptiveV2Protocol,
]:
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
        rng=RandomStream(91, "ranger-adaptive-v2-test"),
        observers=(metrics,),
    )
    transport = FloodTransport(
        network=network,
        topology=topology,
        packet_factory=PacketFactory(),
    )
    group = GroupState(
        group_id=9,
        manager_id=0,
        member_ids={1, 2, 3, 4},
    )
    protocol = RangerAdaptiveV2Protocol(
        group=group,
        tree=LkhKeyTree({1, 2, 3, 4}),
        transport=transport,
        parameters=RangerAdaptiveParameters(
            coding=CodingParameters(
                data_fragments=3,
                total_fragments=5,
            ),
            ciphertext_payload_bytes=64,
            recovery_request_bytes=24,
            adaptive_nack_bytes=16,
            adaptive_recovery_rounds=adaptive_recovery_rounds,
        ),
    )
    return engine, group, metrics, protocol


def test_no_loss_matches_incremental_redundancy_without_feedback() -> None:
    engine, group, metrics, protocol = _build_protocol()

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()

    assert session.completed
    assert protocol.advance(session.epoch) == 0
    assert group.member_epoch(3) == 1
    assert group.member_epoch(4) == 0

    stats = protocol.transport_stats(session.epoch)
    assert stats.initial_flood_injections == 3
    assert stats.adaptive_parity_injections == 0
    assert stats.adaptive_nacks == 0
    assert stats.adaptive_nack_forwarded == 0
    assert stats.adaptive_nack_suppressed == 0
    assert stats.unused_redundancy_fragments == 2
    assert metrics.snapshot().radio_transmissions == 12


def test_branch_local_suppression_reduces_line_nack_hops() -> None:
    engine, _, _, protocol = _build_protocol(
        loss_model=_DropFirstLinkAttempt(sender=1, receiver=2),
    )

    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()
    assert session.accepted_count == 1

    source_reports = protocol.advance(session.epoch)
    assert source_reports == 2
    engine.run()

    assert session.completed
    stats = protocol.transport_stats(session.epoch)
    assert stats.adaptive_nacks == 2
    assert stats.adaptive_nack_hop_attempts == 4
    assert stats.adaptive_nack_forwarded == 2
    assert stats.adaptive_nack_suppressed == 1
    assert stats.adaptive_parity_injections == 1
    assert stats.flood_injections == 4


def test_v2_rejects_invalid_forwarded_feedback_and_unknown_epoch() -> None:
    engine, _, _, protocol = _build_protocol()
    session = protocol.start_rekey(revoked_nodes={4})
    engine.run()

    invalid = FloodMessage(
        message_id=999,
        origin=1,
        kind=protocol.ADAPTIVE_NACK_KIND,
        payload_bytes=16,
        created_at_us=engine.now_us,
        epoch=session.epoch,
        payload=object(),
    )
    with pytest.raises(TypeError, match="invalid RANGER adaptive-NACK"):
        protocol._handle_adaptive_nack(node_id=1, message=invalid)

    request = AdaptiveRedundancyRequest(
        capsule_id="capsule",
        group_id=9,
        epoch=session.epoch,
        requester_id=1,
        round_id=1,
        unique_received=2,
    )
    mismatch = FloodMessage(
        message_id=1000,
        origin=1,
        kind=protocol.ADAPTIVE_NACK_KIND,
        payload_bytes=16,
        created_at_us=engine.now_us,
        epoch=session.epoch + 1,
        payload=request,
    )
    with pytest.raises(ValueError, match="epoch mismatch"):
        protocol._handle_adaptive_nack(node_id=1, message=mismatch)

    with pytest.raises(KeyError, match="unknown adaptive-v2 epoch"):
        protocol._require_suppression(999)
