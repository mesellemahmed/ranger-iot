from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree
from ranger_iot.ranger.coding import CodedFragment
from ranger_iot.ranger.recovery_protocol import (
    RangerRecoveryParameters,
    RangerRecoveryProtocol,
    RangerRecoveryStats,
)
from ranger_iot.rekey import RekeySession
from ranger_iot.sim.flooding import FloodMessage, FloodTransport


@dataclass(frozen=True, slots=True)
class AdaptiveRedundancyRequest:
    """One explicit demand signal for another coded parity fragment."""

    capsule_id: str
    group_id: int
    epoch: int
    requester_id: int
    round_id: int
    unique_received: int

    def __post_init__(self) -> None:
        if not self.capsule_id:
            raise ValueError("capsule_id must not be empty")
        if self.group_id < 0:
            raise ValueError("group_id must be non-negative")
        if self.epoch < 1:
            raise ValueError("epoch must be at least 1")
        if self.requester_id < 0:
            raise ValueError("requester_id must be non-negative")
        if self.round_id < 1:
            raise ValueError("round_id must be at least 1")
        if self.unique_received < 0:
            raise ValueError("unique_received must be non-negative")


@dataclass(frozen=True, slots=True)
class RangerAdaptiveParameters(RangerRecoveryParameters):
    """Incremental-redundancy controls for feedback-driven RANGER."""

    adaptive_nack_bytes: int = 16
    adaptive_recovery_rounds: int = 2

    def __post_init__(self) -> None:
        RangerRecoveryParameters.__post_init__(self)
        if self.adaptive_nack_bytes <= 0:
            raise ValueError("adaptive_nack_bytes must be positive")
        if self.adaptive_recovery_rounds < 0:
            raise ValueError("adaptive_recovery_rounds must be non-negative")


@dataclass(frozen=True, slots=True)
class RangerAdaptiveStats(RangerRecoveryStats):
    """Protocol counters for incremental redundancy and explicit feedback."""

    initial_flood_injections: int
    adaptive_parity_injections: int
    adaptive_nack_rounds: int
    adaptive_nacks: int
    adaptive_nack_hop_attempts: int
    adaptive_actions: int
    unused_redundancy_fragments: int


@dataclass(slots=True)
class _AdaptiveCounters:
    next_fragment_index: int
    next_phase: str = "nack"
    nack_rounds: int = 0
    nacks: int = 0
    nack_hop_attempts: int = 0
    parity_injections: int = 0
    actions: int = 0
    released_round_ids: set[int] = field(default_factory=set)


class RangerAdaptiveProtocol(RangerRecoveryProtocol):
    """RANGER with feedback-driven incremental redundancy.

    The capsule is encoded as an ideal ``k-of-n_max`` code, but only the first
    ``k`` fragments are initially released. Stale authorized members send an
    adaptive NACK toward the Group Manager over a deterministic BFS control
    tree. The Group Manager releases at most one new parity fragment for that
    NACK round. Local same-epoch recovery is then allowed before another
    redundancy-request round.

    The configured Bernoulli packet-loss probability is never consulted by this
    protocol. Redundancy is therefore demand-driven rather than oracle-driven.
    """

    MESSAGE_KIND = "ranger.adaptive.fragment"
    ADAPTIVE_NACK_KIND = "ranger.adaptive.nack"

    def __init__(
        self,
        *,
        group: GroupState,
        tree: LkhKeyTree,
        transport: FloodTransport,
        parameters: RangerAdaptiveParameters | None = None,
    ) -> None:
        adaptive_parameters = parameters or RangerAdaptiveParameters()
        self._adaptive_parameters = adaptive_parameters
        self._adaptive: dict[int, _AdaptiveCounters] = {}
        super().__init__(
            group=group,
            tree=tree,
            transport=transport,
            parameters=adaptive_parameters,
        )
        self._control_parent = self._build_control_tree()

    def start_rekey(self, *, revoked_nodes: set[int]) -> RekeySession:
        session = super().start_rekey(revoked_nodes=revoked_nodes)
        initial = self._adaptive_parameters.coding.data_fragments
        self._adaptive[session.epoch] = _AdaptiveCounters(next_fragment_index=initial)
        return session

    def transport_stats(self, epoch: int) -> RangerAdaptiveStats:
        recovery = super().transport_stats(epoch)
        state = self._require_epoch(epoch)
        counters = self._require_adaptive(epoch)
        initial = self._adaptive_parameters.coding.data_fragments
        return RangerAdaptiveStats(
            epoch=recovery.epoch,
            logical_ciphertexts=recovery.logical_ciphertexts,
            capsule_payload_bytes=recovery.capsule_payload_bytes,
            data_fragments=recovery.data_fragments,
            total_fragments=recovery.total_fragments,
            fragment_payload_bytes=recovery.fragment_payload_bytes,
            flood_injections=recovery.flood_injections,
            recovery_rounds=recovery.recovery_rounds,
            recovery_requests=recovery.recovery_requests,
            recovery_fragment_attempts=recovery.recovery_fragment_attempts,
            peer_recovery_fragment_attempts=recovery.peer_recovery_fragment_attempts,
            manager_recovery_fragment_attempts=recovery.manager_recovery_fragment_attempts,
            recovered_members=recovery.recovered_members,
            initial_flood_injections=initial,
            adaptive_parity_injections=counters.parity_injections,
            adaptive_nack_rounds=counters.nack_rounds,
            adaptive_nacks=counters.nacks,
            adaptive_nack_hop_attempts=counters.nack_hop_attempts,
            adaptive_actions=counters.actions,
            unused_redundancy_fragments=len(state.fragments) - state.flood_injections,
        )

    def advance(self, epoch: int) -> int:
        """Start the next useful adaptive action, or return zero when quiescent."""

        state = self._require_epoch(epoch)
        if state.session.completed:
            return 0

        counters = self._require_adaptive(epoch)
        for _ in range(2):
            if counters.next_phase == "nack":
                counters.next_phase = "recovery"
                count = self.start_redundancy_request_round(epoch)
                if count:
                    counters.actions += 1
                    return count
                continue

            counters.next_phase = "nack"
            recovery = self._require_recovery(epoch)
            if recovery.rounds >= self._adaptive_parameters.adaptive_recovery_rounds:
                continue
            count = self.start_recovery_round(epoch)
            if count:
                counters.actions += 1
                return count

        return 0

    def start_redundancy_request_round(self, epoch: int) -> int:
        """Let stale members request one additional globally flooded parity."""

        state = self._require_epoch(epoch)
        counters = self._require_adaptive(epoch)
        if counters.next_fragment_index >= len(state.fragments):
            return 0

        stale_members = tuple(
            member_id
            for member_id in state.session.targets
            if member_id not in state.session.accepted_at_us
            and not state.accumulators[member_id].decodable
        )
        if not stale_members:
            return 0

        round_id = counters.nack_rounds + 1
        for member_id in stale_members:
            accumulator = state.accumulators[member_id]
            request = AdaptiveRedundancyRequest(
                capsule_id=state.capsule.capsule_id,
                group_id=state.capsule.group_id,
                epoch=epoch,
                requester_id=member_id,
                round_id=round_id,
                unique_received=accumulator.unique_received,
            )
            self._send_nack_hop(node_id=member_id, request=request)
            counters.nacks += 1

        counters.nack_rounds += 1
        return len(stale_members)

    def _initial_fragments(self, fragments: tuple[CodedFragment, ...]) -> tuple[CodedFragment, ...]:
        return fragments[: self._adaptive_parameters.coding.data_fragments]

    def _handle_transport_message(
        self,
        *,
        node_id: int,
        message: FloodMessage,
        at_us: int,
    ) -> None:
        if message.kind == self.ADAPTIVE_NACK_KIND:
            self._handle_adaptive_nack(node_id=node_id, message=message)
            return
        super()._handle_transport_message(node_id=node_id, message=message, at_us=at_us)

    def _handle_adaptive_nack(self, *, node_id: int, message: FloodMessage) -> None:
        request = message.payload
        if not isinstance(request, AdaptiveRedundancyRequest):
            raise TypeError("invalid RANGER adaptive-NACK payload")
        if message.epoch != request.epoch:
            raise ValueError("adaptive NACK epoch mismatch")
        if node_id != self._group.manager_id:
            self._send_nack_hop(node_id=node_id, request=request)
            return
        if request.group_id != self._group.group_id:
            return
        if request.requester_id not in self._group.member_ids:
            return
        if not self._group.is_authorized(request.requester_id):
            return

        state = self._epochs.get(request.epoch)
        if state is None or request.capsule_id != state.capsule.capsule_id:
            return

        counters = self._require_adaptive(request.epoch)
        if request.round_id in counters.released_round_ids:
            return
        if counters.next_fragment_index >= len(state.fragments):
            return

        fragment = state.fragments[counters.next_fragment_index]
        counters.next_fragment_index += 1
        counters.released_round_ids.add(request.round_id)
        counters.parity_injections += 1
        self._flood_fragment(state, fragment)

    def _send_nack_hop(
        self,
        *,
        node_id: int,
        request: AdaptiveRedundancyRequest,
    ) -> None:
        parent = self._control_parent.get(node_id)
        if parent is None:
            raise RuntimeError(f"node has no control-tree path to manager: {node_id}")
        if parent == node_id:
            raise RuntimeError("manager cannot forward an adaptive NACK to itself")
        self._transport.send_neighbor(
            origin=node_id,
            destination=parent,
            kind=self.ADAPTIVE_NACK_KIND,
            payload_bytes=self._adaptive_parameters.adaptive_nack_bytes,
            epoch=request.epoch,
            payload=request,
        )
        self._require_adaptive(request.epoch).nack_hop_attempts += 1

    def _build_control_tree(self) -> dict[int, int]:
        manager_id = self._group.manager_id
        parents = {manager_id: manager_id}
        queue: deque[int] = deque([manager_id])

        while queue:
            current = queue.popleft()
            for neighbor in self._transport.neighbors(current):
                if neighbor in parents:
                    continue
                parents[neighbor] = current
                queue.append(neighbor)

        return parents

    def _manager_available_indexes(self, epoch: int) -> tuple[int, ...]:
        state = self._require_epoch(epoch)
        return tuple(range(state.flood_injections))

    def _require_adaptive(self, epoch: int) -> _AdaptiveCounters:
        try:
            return self._adaptive[epoch]
        except KeyError as exc:
            raise KeyError(f"unknown adaptive epoch: {epoch}") from exc
