from __future__ import annotations

from dataclasses import dataclass

from ranger_iot.group import GroupState
from ranger_iot.rekey import RekeySession
from ranger_iot.sim.routing import RoutedMessage, RoutedReceiver, ShortestPathRouter


@dataclass(frozen=True, slots=True)
class SkdcParameters:
    """Wire-size model for one pairwise-protected group-key update."""

    rekey_payload_bytes: int = 64

    def __post_init__(self) -> None:
        if self.rekey_payload_bytes <= 0:
            raise ValueError("rekey_payload_bytes must be positive")


@dataclass(frozen=True, slots=True)
class SkdcRekeyMessage:
    group_id: int
    epoch: int
    recipient: int


class SkdcProtocol:
    """Secure key distribution center baseline with pairwise rekey delivery."""

    MESSAGE_KIND = "skdc.rekey"

    def __init__(
        self,
        *,
        group: GroupState,
        router: ShortestPathRouter,
        parameters: SkdcParameters | None = None,
    ) -> None:
        self._group = group
        self._router = router
        self._parameters = parameters or SkdcParameters()
        self._sessions: dict[int, RekeySession] = {}

        for member_id in group.member_ids:
            self._router.register_receiver(member_id, self._make_member_receiver(member_id))

    @property
    def sessions(self) -> tuple[RekeySession, ...]:
        return tuple(self._sessions[epoch] for epoch in sorted(self._sessions))

    def session(self, epoch: int) -> RekeySession:
        try:
            return self._sessions[epoch]
        except KeyError as exc:
            raise KeyError(f"unknown rekey epoch: {epoch}") from exc

    def start_rekey(self, *, revoked_nodes: set[int]) -> RekeySession:
        for node_id in sorted(revoked_nodes):
            self._group.revoke(node_id)

        epoch = self._group.advance_epoch()
        targets = self._group.authorized_member_ids
        session = RekeySession(epoch=epoch, started_at_us=self._router.now_us, targets=targets)
        self._sessions[epoch] = session

        for member_id in targets:
            message = SkdcRekeyMessage(
                group_id=self._group.group_id,
                epoch=epoch,
                recipient=member_id,
            )
            self._router.send(
                origin=self._group.manager_id,
                destination=member_id,
                kind=self.MESSAGE_KIND,
                payload_bytes=self._parameters.rekey_payload_bytes,
                epoch=epoch,
                payload=message,
            )

        return session

    def _make_member_receiver(self, member_id: int) -> RoutedReceiver:
        def receive(message: RoutedMessage, at_us: int) -> None:
            self._handle_rekey(member_id=member_id, routed=message, at_us=at_us)

        return receive

    def _handle_rekey(self, *, member_id: int, routed: RoutedMessage, at_us: int) -> None:
        if routed.kind != self.MESSAGE_KIND:
            return
        payload = routed.payload
        if not isinstance(payload, SkdcRekeyMessage):
            raise TypeError("invalid SKDC rekey payload")
        if payload.group_id != self._group.group_id:
            return
        if payload.recipient != member_id:
            return
        if routed.epoch != payload.epoch:
            raise ValueError("routed epoch does not match SKDC payload epoch")
        if not self._group.is_authorized(member_id):
            return

        accepted = self._group.accept_epoch(member_id, payload.epoch)
        if not accepted:
            return

        session = self._sessions.get(payload.epoch)
        if session is not None:
            session.record_acceptance(member_id, at_us)
