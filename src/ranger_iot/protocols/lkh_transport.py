from __future__ import annotations

from dataclasses import dataclass, field

from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree, LkhKeyUpdate, LkhRekeyPlan
from ranger_iot.rekey import RekeySession
from ranger_iot.sim.routing import RoutedMessage, RoutedReceiver, ShortestPathRouter


@dataclass(frozen=True, slots=True)
class LkhTransportParameters:
    """Wire-size model for one routed LKH ciphertext copy."""

    ciphertext_payload_bytes: int = 64

    def __post_init__(self) -> None:
        if self.ciphertext_payload_bytes <= 0:
            raise ValueError("ciphertext_payload_bytes must be positive")


@dataclass(frozen=True, slots=True)
class LkhRekeyMessage:
    """One routed copy of a logical LKH key update."""

    group_id: int
    epoch: int
    update_index: int
    update: LkhKeyUpdate
    recipient: int


@dataclass(frozen=True, slots=True)
class LkhTransportStats:
    """Protocol-level transport counters for one LKH rekey epoch."""

    epoch: int
    logical_ciphertexts: int
    routed_copies: int


@dataclass(slots=True)
class _LkhEpochState:
    plan: LkhRekeyPlan
    session: RekeySession
    required_updates: dict[int, frozenset[int]]
    received_updates: dict[int, set[int]] = field(default_factory=dict)
    routed_copies: int = 0


class LkhUnicastProtocol:
    """LKH baseline transported as deterministic per-recipient unicasts.

    The key tree defines the logical ciphertexts. Each logical ciphertext is
    copied to every authorized recipient covered by its wrapping key and routed
    independently over the shortest-path transport. This intentionally isolates
    the LKH cryptographic plan from multicast/flooding optimizations.
    """

    MESSAGE_KIND = "lkh.rekey"

    def __init__(
        self,
        *,
        group: GroupState,
        tree: LkhKeyTree,
        router: ShortestPathRouter,
        parameters: LkhTransportParameters | None = None,
    ) -> None:
        if set(group.member_ids) != set(tree.member_ids):
            raise ValueError("group and LKH tree must contain the same members")
        if group.current_epoch != tree.root_key.version:
            raise ValueError("group epoch and LKH root-key version must match")

        self._group = group
        self._tree = tree
        self._router = router
        self._parameters = parameters or LkhTransportParameters()
        self._epochs: dict[int, _LkhEpochState] = {}

        for member_id in group.member_ids:
            self._router.register_receiver(member_id, self._make_member_receiver(member_id))

    @property
    def sessions(self) -> tuple[RekeySession, ...]:
        return tuple(self._epochs[epoch].session for epoch in sorted(self._epochs))

    def session(self, epoch: int) -> RekeySession:
        return self._require_epoch(epoch).session

    def plan(self, epoch: int) -> LkhRekeyPlan:
        return self._require_epoch(epoch).plan

    def transport_stats(self, epoch: int) -> LkhTransportStats:
        state = self._require_epoch(epoch)
        return LkhTransportStats(
            epoch=epoch,
            logical_ciphertexts=state.plan.logical_ciphertexts,
            routed_copies=state.routed_copies,
        )

    def start_rekey(self, *, revoked_nodes: set[int]) -> RekeySession:
        self._validate_group_revocations(revoked_nodes)
        plan = self._tree.rekey(revoked_nodes)

        for node_id in sorted(revoked_nodes):
            self._group.revoke(node_id)

        epoch = self._group.advance_epoch()
        if epoch != plan.root_key.version:
            raise RuntimeError("LKH root-key version diverged from group epoch")

        targets = self._group.authorized_member_ids
        session = RekeySession(epoch=epoch, started_at_us=self._router.now_us, targets=targets)
        required_updates = self._required_updates(plan=plan, targets=targets)
        state = _LkhEpochState(
            plan=plan,
            session=session,
            required_updates=required_updates,
            received_updates={member_id: set() for member_id in targets},
        )
        self._epochs[epoch] = state

        for update_index, update in enumerate(plan.updates):
            for member_id in update.recipients:
                if member_id not in required_updates:
                    raise RuntimeError("LKH plan includes a non-authorized recipient")
                message = LkhRekeyMessage(
                    group_id=self._group.group_id,
                    epoch=epoch,
                    update_index=update_index,
                    update=update,
                    recipient=member_id,
                )
                self._router.send(
                    origin=self._group.manager_id,
                    destination=member_id,
                    kind=self.MESSAGE_KIND,
                    payload_bytes=self._parameters.ciphertext_payload_bytes,
                    epoch=epoch,
                    payload=message,
                )
                state.routed_copies += 1

        return session

    def _make_member_receiver(self, member_id: int) -> RoutedReceiver:
        def receive(message: RoutedMessage, at_us: int) -> None:
            self._handle_rekey(member_id=member_id, routed=message, at_us=at_us)

        return receive

    def _handle_rekey(self, *, member_id: int, routed: RoutedMessage, at_us: int) -> None:
        if routed.kind != self.MESSAGE_KIND:
            return

        payload = routed.payload
        if not isinstance(payload, LkhRekeyMessage):
            raise TypeError("invalid LKH rekey payload")
        if payload.group_id != self._group.group_id:
            return
        if payload.recipient != member_id:
            return
        if routed.epoch != payload.epoch:
            raise ValueError("routed epoch does not match LKH payload epoch")
        if not self._group.is_authorized(member_id):
            return

        state = self._epochs.get(payload.epoch)
        if state is None:
            return
        if payload.update_index >= len(state.plan.updates):
            raise ValueError("LKH update index is out of range")
        expected_update = state.plan.updates[payload.update_index]
        if payload.update != expected_update:
            raise ValueError("LKH payload does not match the rekey plan")
        if member_id not in expected_update.recipients:
            return

        received = state.received_updates[member_id]
        received.add(payload.update_index)
        if not state.required_updates[member_id].issubset(received):
            return

        accepted = self._group.accept_epoch(member_id, payload.epoch)
        if accepted:
            state.session.record_acceptance(member_id, at_us)

    def _validate_group_revocations(self, revoked_nodes: set[int]) -> None:
        members = set(self._group.member_ids)
        unknown = revoked_nodes - members
        if unknown:
            raise KeyError(f"unknown group member: {min(unknown)}")

        already_revoked = {
            node_id for node_id in revoked_nodes if not self._group.is_authorized(node_id)
        }
        if already_revoked:
            raise ValueError(f"member already revoked: {min(already_revoked)}")

    @staticmethod
    def _required_updates(
        *,
        plan: LkhRekeyPlan,
        targets: tuple[int, ...],
    ) -> dict[int, frozenset[int]]:
        required: dict[int, set[int]] = {member_id: set() for member_id in targets}
        for update_index, update in enumerate(plan.updates):
            for member_id in update.recipients:
                if member_id in required:
                    required[member_id].add(update_index)

        missing = [member_id for member_id, indexes in required.items() if not indexes]
        if missing:
            raise RuntimeError(f"LKH plan does not cover authorized member: {missing[0]}")
        return {member_id: frozenset(indexes) for member_id, indexes in required.items()}

    def _require_epoch(self, epoch: int) -> _LkhEpochState:
        try:
            return self._epochs[epoch]
        except KeyError as exc:
            raise KeyError(f"unknown rekey epoch: {epoch}") from exc
