from __future__ import annotations

from dataclasses import dataclass, field

from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree
from ranger_iot.ranger.coding import CodedFragment
from ranger_iot.ranger.static_protocol import (
    RangerStaticParameters,
    RangerStaticProtocol,
    RangerStaticStats,
)
from ranger_iot.rekey import RekeySession
from ranger_iot.sim.flooding import FloodMessage, FloodReceiver, FloodTransport


@dataclass(frozen=True, slots=True)
class RecoveryRequest:
    """One same-epoch request for missing coded-fragment indexes."""

    capsule_id: str
    group_id: int
    epoch: int
    requester_id: int
    received_indexes: tuple[int, ...]
    needed_fragments: int

    def __post_init__(self) -> None:
        if not self.capsule_id:
            raise ValueError("capsule_id must not be empty")
        if self.group_id < 0:
            raise ValueError("group_id must be non-negative")
        if self.epoch < 1:
            raise ValueError("epoch must be at least 1")
        if self.requester_id < 0:
            raise ValueError("requester_id must be non-negative")
        if len(set(self.received_indexes)) != len(self.received_indexes):
            raise ValueError("received_indexes must be unique")
        if tuple(sorted(self.received_indexes)) != self.received_indexes:
            raise ValueError("received_indexes must be sorted")
        if self.needed_fragments < 1:
            raise ValueError("needed_fragments must be at least 1")


@dataclass(frozen=True, slots=True)
class RangerRecoveryParameters(RangerStaticParameters):
    """Static coding parameters plus local recovery control-message cost."""

    recovery_request_bytes: int = 24

    def __post_init__(self) -> None:
        RangerStaticParameters.__post_init__(self)
        if self.recovery_request_bytes <= 0:
            raise ValueError("recovery_request_bytes must be positive")


@dataclass(frozen=True, slots=True)
class RangerRecoveryStats(RangerStaticStats):
    """Protocol-level statistics including same-epoch local repair."""

    recovery_rounds: int
    recovery_requests: int
    recovery_fragment_attempts: int
    peer_recovery_fragment_attempts: int
    manager_recovery_fragment_attempts: int
    recovered_members: int


@dataclass(slots=True)
class _RecoveryCounters:
    rounds: int = 0
    requests: int = 0
    fragment_attempts: int = 0
    manager_fragment_attempts: int = 0
    recovered_members: set[int] = field(default_factory=set)


class RangerRecoveryProtocol(RangerStaticProtocol):
    """RANGER-STATIC plus deterministic one-hop neighbor self-healing.

    Initial dissemination is identical to :class:`RangerStaticProtocol`. After
    the initial flood queue drains, stale authorized members may execute one or
    more recovery rounds. Each stale member asks all directly connected
    authorized neighbors for fragment indexes it is missing. The Group Manager
    may answer when it is itself a direct neighbor; this cost is tracked
    separately. Responses are direct one-hop transmissions and are still
    subject to the configured network loss model.

    Recovery is intentionally same-epoch only. Catch-up across multiple missed
    epochs requires a separate key-evolution/history model and is not silently
    approximated here.
    """

    RECOVERY_REQUEST_KIND = "ranger.recovery.request"
    RECOVERY_FRAGMENT_KIND = "ranger.recovery.fragment"

    def __init__(
        self,
        *,
        group: GroupState,
        tree: LkhKeyTree,
        transport: FloodTransport,
        parameters: RangerRecoveryParameters | None = None,
    ) -> None:
        recovery_parameters = parameters or RangerRecoveryParameters()
        super().__init__(
            group=group,
            tree=tree,
            transport=transport,
            parameters=recovery_parameters,
        )
        self._recovery_parameters = recovery_parameters
        self._recovery: dict[int, _RecoveryCounters] = {}
        self._transport.register_receiver(group.manager_id, self._make_manager_receiver())

    def start_rekey(self, *, revoked_nodes: set[int]) -> RekeySession:
        session = super().start_rekey(revoked_nodes=revoked_nodes)
        self._recovery[session.epoch] = _RecoveryCounters()
        return session

    def transport_stats(self, epoch: int) -> RangerRecoveryStats:
        static = super().transport_stats(epoch)
        counters = self._require_recovery(epoch)
        return RangerRecoveryStats(
            epoch=static.epoch,
            logical_ciphertexts=static.logical_ciphertexts,
            capsule_payload_bytes=static.capsule_payload_bytes,
            data_fragments=static.data_fragments,
            total_fragments=static.total_fragments,
            fragment_payload_bytes=static.fragment_payload_bytes,
            flood_injections=static.flood_injections,
            recovery_rounds=counters.rounds,
            recovery_requests=counters.requests,
            recovery_fragment_attempts=counters.fragment_attempts,
            peer_recovery_fragment_attempts=(
                counters.fragment_attempts - counters.manager_fragment_attempts
            ),
            manager_recovery_fragment_attempts=counters.manager_fragment_attempts,
            recovered_members=len(counters.recovered_members),
        )

    def start_recovery_round(self, epoch: int) -> int:
        """Issue one deterministic recovery request round for stale targets."""

        state = self._require_epoch(epoch)
        counters = self._require_recovery(epoch)
        request_count = 0

        for member_id in state.session.targets:
            if member_id in state.session.accepted_at_us:
                continue

            accumulator = state.accumulators[member_id]
            if accumulator.decodable:
                continue

            request = RecoveryRequest(
                capsule_id=state.capsule.capsule_id,
                group_id=state.capsule.group_id,
                epoch=epoch,
                requester_id=member_id,
                received_indexes=accumulator.received_indexes,
                needed_fragments=accumulator.remaining_needed,
            )
            for neighbor_id in self._eligible_recovery_neighbors(member_id):
                self._transport.send_neighbor(
                    origin=member_id,
                    destination=neighbor_id,
                    kind=self.RECOVERY_REQUEST_KIND,
                    payload_bytes=self._recovery_parameters.recovery_request_bytes,
                    epoch=epoch,
                    payload=request,
                )
                counters.requests += 1
                request_count += 1

        if request_count:
            counters.rounds += 1
        return request_count

    def _make_manager_receiver(self) -> FloodReceiver:
        def receive(message: FloodMessage, at_us: int) -> None:
            self._handle_transport_message(
                node_id=self._group.manager_id,
                message=message,
                at_us=at_us,
            )

        return receive

    def _handle_fragment(self, *, member_id: int, flooded: FloodMessage, at_us: int) -> None:
        self._handle_transport_message(node_id=member_id, message=flooded, at_us=at_us)

    def _handle_transport_message(
        self,
        *,
        node_id: int,
        message: FloodMessage,
        at_us: int,
    ) -> None:
        if message.kind == self.MESSAGE_KIND:
            if node_id == self._group.manager_id:
                return
            super()._handle_fragment(member_id=node_id, flooded=message, at_us=at_us)
            return

        if message.kind == self.RECOVERY_REQUEST_KIND:
            self._handle_recovery_request(node_id=node_id, message=message)
            return

        if message.kind == self.RECOVERY_FRAGMENT_KIND:
            if node_id == self._group.manager_id:
                return
            self._handle_recovery_fragment(member_id=node_id, message=message, at_us=at_us)

    def _handle_recovery_request(self, *, node_id: int, message: FloodMessage) -> None:
        request = message.payload
        if not isinstance(request, RecoveryRequest):
            raise TypeError("invalid RANGER recovery-request payload")
        if message.epoch != request.epoch:
            raise ValueError("recovery request epoch mismatch")
        if message.origin != request.requester_id:
            raise ValueError("recovery requester does not match message origin")
        if request.group_id != self._group.group_id:
            return
        if request.requester_id not in self._group.member_ids:
            return
        if not self._group.is_authorized(request.requester_id):
            return

        state = self._epochs.get(request.epoch)
        if state is None or request.capsule_id != state.capsule.capsule_id:
            return

        if node_id == self._group.manager_id:
            available_indexes = self._manager_available_indexes(request.epoch)
        else:
            if node_id not in state.accumulators or not self._group.is_authorized(node_id):
                return
            available_indexes = state.accumulators[node_id].received_indexes

        requester_indexes = set(request.received_indexes)
        candidate_indexes = tuple(
            index for index in available_indexes if index not in requester_indexes
        )[: request.needed_fragments]
        counters = self._require_recovery(request.epoch)

        for fragment_index in candidate_indexes:
            fragment = state.fragments[fragment_index]
            self._transport.send_neighbor(
                origin=node_id,
                destination=request.requester_id,
                kind=self.RECOVERY_FRAGMENT_KIND,
                payload_bytes=fragment.payload_bytes,
                epoch=request.epoch,
                payload=fragment,
            )
            counters.fragment_attempts += 1
            if node_id == self._group.manager_id:
                counters.manager_fragment_attempts += 1

    def _handle_recovery_fragment(
        self,
        *,
        member_id: int,
        message: FloodMessage,
        at_us: int,
    ) -> None:
        fragment = message.payload
        if not isinstance(fragment, CodedFragment):
            raise TypeError("invalid RANGER recovery-fragment payload")
        if message.epoch != fragment.epoch:
            raise ValueError("recovery fragment epoch mismatch")
        if self._accept_fragment(member_id=member_id, fragment=fragment, at_us=at_us):
            self._require_recovery(fragment.epoch).recovered_members.add(member_id)

    def _eligible_recovery_neighbors(self, member_id: int) -> tuple[int, ...]:
        neighbors: list[int] = []
        for neighbor_id in self._transport.neighbors(member_id):
            if neighbor_id == self._group.manager_id or (
                neighbor_id in self._group.member_ids and self._group.is_authorized(neighbor_id)
            ):
                neighbors.append(neighbor_id)
        return tuple(neighbors)

    def _manager_available_indexes(self, epoch: int) -> tuple[int, ...]:
        state = self._require_epoch(epoch)
        return tuple(range(len(state.fragments)))

    def _require_recovery(self, epoch: int) -> _RecoveryCounters:
        try:
            return self._recovery[epoch]
        except KeyError as exc:
            raise KeyError(f"unknown recovery epoch: {epoch}") from exc
