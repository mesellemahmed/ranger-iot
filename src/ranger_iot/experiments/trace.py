from __future__ import annotations

from dataclasses import asdict, dataclass

from ranger_iot.sim.metrics import DropReason
from ranger_iot.sim.packet import Packet


@dataclass(frozen=True, slots=True)
class NetworkTraceEvent:
    at_us: int
    event: str
    sender: int
    receiver: int
    packet_id: int
    packet_kind: str
    epoch: int | None
    payload_bytes: int
    drop_reason: str | None


class NetworkTrace:
    """Deterministic in-memory event trace implementing NetworkObserver."""

    def __init__(self) -> None:
        self._events: list[NetworkTraceEvent] = []

    @property
    def events(self) -> tuple[NetworkTraceEvent, ...]:
        return tuple(self._events)

    def rows(self) -> list[dict[str, object]]:
        return [asdict(event) for event in self._events]

    def on_transmit(self, *, at_us: int, sender: int, receiver: int, packet: Packet) -> None:
        self._append("transmit", at_us, sender, receiver, packet, None)

    def on_deliver(self, *, at_us: int, sender: int, receiver: int, packet: Packet) -> None:
        self._append("deliver", at_us, sender, receiver, packet, None)

    def on_drop(
        self,
        *,
        at_us: int,
        sender: int,
        receiver: int,
        packet: Packet,
        reason: DropReason,
    ) -> None:
        self._append("drop", at_us, sender, receiver, packet, reason.value)

    def _append(
        self,
        event: str,
        at_us: int,
        sender: int,
        receiver: int,
        packet: Packet,
        drop_reason: str | None,
    ) -> None:
        self._events.append(
            NetworkTraceEvent(
                at_us=at_us,
                event=event,
                sender=sender,
                receiver=receiver,
                packet_id=packet.packet_id,
                packet_kind=packet.kind,
                epoch=packet.epoch,
                payload_bytes=packet.payload_bytes,
                drop_reason=drop_reason,
            )
        )
