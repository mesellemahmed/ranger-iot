from __future__ import annotations

from dataclasses import dataclass, field

from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree
from ranger_iot.ranger.adaptive_protocol import (
    AdaptiveRedundancyRequest,
    RangerAdaptiveParameters,
    RangerAdaptiveProtocol,
    RangerAdaptiveStats,
)
from ranger_iot.rekey import RekeySession
from ranger_iot.sim.flooding import FloodMessage, FloodTransport


@dataclass(frozen=True, slots=True)
class RangerAdaptiveV2Stats(RangerAdaptiveStats):
    """Adaptive-V2 counters for branch-local NACK suppression."""

    adaptive_nack_forwarded: int
    adaptive_nack_suppressed: int


@dataclass(slots=True)
class _SuppressionCounters:
    forwarded_node_rounds: set[tuple[int, int]] = field(default_factory=set)
    forwarded: int = 0
    suppressed: int = 0


class RangerAdaptiveV2Protocol(RangerAdaptiveProtocol):
    """RANGER Adaptive-V2 with branch-local duplicate NACK suppression.

    Stale members still originate explicit deficit reports. At intermediate
    control-tree relays, only the first received report for a given
    ``(epoch, round_id)`` is forwarded toward the Group Manager. Later reports
    received at the same relay in the same round are suppressed.

    A relay's own source report is deliberately not entered in the suppression
    cache. Consequently, a stale relay may send its own report and forward one
    descendant report. This preserves a modest amount of control-path
    redundancy under loss while changing long-chain feedback growth from
    repeated end-to-end forwarding toward branch-local aggregation.

    The protocol never reads the configured packet-loss probability.
    """

    MESSAGE_KIND = "ranger.adaptive-v2.fragment"
    ADAPTIVE_NACK_KIND = "ranger.adaptive-v2.nack"

    def __init__(
        self,
        *,
        group: GroupState,
        tree: LkhKeyTree,
        transport: FloodTransport,
        parameters: RangerAdaptiveParameters | None = None,
    ) -> None:
        self._suppression: dict[int, _SuppressionCounters] = {}
        super().__init__(
            group=group,
            tree=tree,
            transport=transport,
            parameters=parameters,
        )

    def start_rekey(self, *, revoked_nodes: set[int]) -> RekeySession:
        session = super().start_rekey(revoked_nodes=revoked_nodes)
        self._suppression[session.epoch] = _SuppressionCounters()
        return session

    def transport_stats(self, epoch: int) -> RangerAdaptiveV2Stats:
        base = super().transport_stats(epoch)
        suppression = self._require_suppression(epoch)
        return RangerAdaptiveV2Stats(
            epoch=base.epoch,
            logical_ciphertexts=base.logical_ciphertexts,
            capsule_payload_bytes=base.capsule_payload_bytes,
            data_fragments=base.data_fragments,
            total_fragments=base.total_fragments,
            fragment_payload_bytes=base.fragment_payload_bytes,
            flood_injections=base.flood_injections,
            recovery_rounds=base.recovery_rounds,
            recovery_requests=base.recovery_requests,
            recovery_fragment_attempts=base.recovery_fragment_attempts,
            peer_recovery_fragment_attempts=base.peer_recovery_fragment_attempts,
            manager_recovery_fragment_attempts=base.manager_recovery_fragment_attempts,
            recovered_members=base.recovered_members,
            initial_flood_injections=base.initial_flood_injections,
            adaptive_parity_injections=base.adaptive_parity_injections,
            adaptive_nack_rounds=base.adaptive_nack_rounds,
            adaptive_nacks=base.adaptive_nacks,
            adaptive_nack_hop_attempts=base.adaptive_nack_hop_attempts,
            adaptive_actions=base.adaptive_actions,
            unused_redundancy_fragments=base.unused_redundancy_fragments,
            adaptive_nack_forwarded=suppression.forwarded,
            adaptive_nack_suppressed=suppression.suppressed,
        )

    def _handle_adaptive_nack(
        self,
        *,
        node_id: int,
        message: FloodMessage,
    ) -> None:
        request = message.payload
        if not isinstance(request, AdaptiveRedundancyRequest):
            raise TypeError("invalid RANGER adaptive-NACK payload")
        if message.epoch != request.epoch:
            raise ValueError("adaptive NACK epoch mismatch")

        if node_id == self._group.manager_id:
            super()._handle_adaptive_nack(node_id=node_id, message=message)
            return

        suppression = self._require_suppression(request.epoch)
        key = (node_id, request.round_id)
        if key in suppression.forwarded_node_rounds:
            suppression.suppressed += 1
            return

        suppression.forwarded_node_rounds.add(key)
        suppression.forwarded += 1
        self._send_nack_hop(node_id=node_id, request=request)

    def _require_suppression(self, epoch: int) -> _SuppressionCounters:
        try:
            return self._suppression[epoch]
        except KeyError as exc:
            raise KeyError(f"unknown adaptive-v2 epoch: {epoch}") from exc
