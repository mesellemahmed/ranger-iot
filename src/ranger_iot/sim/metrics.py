from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from ranger_iot.sim.packet import Packet


class DropReason(StrEnum):
    LOSS_MODEL = "loss_model"
    RECEIVER_INACTIVE = "receiver_inactive"


class NetworkObserver(Protocol):
    def on_transmit(self, *, at_us: int, sender: int, receiver: int, packet: Packet) -> None: ...

    def on_deliver(self, *, at_us: int, sender: int, receiver: int, packet: Packet) -> None: ...

    def on_drop(
        self,
        *,
        at_us: int,
        sender: int,
        receiver: int,
        packet: Packet,
        reason: DropReason,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class NetworkMetricsSnapshot:
    # Legacy/link-level accounting. ``transmissions`` counts one attempt per
    # receiver/link and is retained for backward compatibility.
    transmissions: int
    radio_transmissions: int
    deliveries: int
    drops: int
    bytes_sent: int
    radio_bytes_sent: int
    bytes_delivered: int
    drops_by_reason: dict[DropReason, int]
    transmissions_by_node: dict[int, int]
    radio_transmissions_by_node: dict[int, int]


class NetworkMetrics:
    """In-memory network counters used by tests and experiment collectors."""

    def __init__(self) -> None:
        self._transmissions = 0
        self._radio_transmissions = 0
        self._deliveries = 0
        self._drops = 0
        self._bytes_sent = 0
        self._radio_bytes_sent = 0
        self._bytes_delivered = 0
        self._drops_by_reason: Counter[DropReason] = Counter()
        self._transmissions_by_node: Counter[int] = Counter()
        self._radio_transmissions_by_node: Counter[int] = Counter()

    def on_transmit(self, *, at_us: int, sender: int, receiver: int, packet: Packet) -> None:
        """Count one receiver/link delivery attempt."""

        del at_us, receiver
        self._transmissions += 1
        self._bytes_sent += packet.payload_bytes
        self._transmissions_by_node[sender] += 1

    def on_radio_transmit(self, *, at_us: int, sender: int, packet: Packet) -> None:
        """Count one sender-side radio emission."""

        del at_us
        self._radio_transmissions += 1
        self._radio_bytes_sent += packet.payload_bytes
        self._radio_transmissions_by_node[sender] += 1

    def on_deliver(self, *, at_us: int, sender: int, receiver: int, packet: Packet) -> None:
        del at_us, sender, receiver
        self._deliveries += 1
        self._bytes_delivered += packet.payload_bytes

    def on_drop(
        self,
        *,
        at_us: int,
        sender: int,
        receiver: int,
        packet: Packet,
        reason: DropReason,
    ) -> None:
        del at_us, sender, receiver, packet
        self._drops += 1
        self._drops_by_reason[reason] += 1

    def snapshot(self) -> NetworkMetricsSnapshot:
        return NetworkMetricsSnapshot(
            transmissions=self._transmissions,
            radio_transmissions=self._radio_transmissions,
            deliveries=self._deliveries,
            drops=self._drops,
            bytes_sent=self._bytes_sent,
            radio_bytes_sent=self._radio_bytes_sent,
            bytes_delivered=self._bytes_delivered,
            drops_by_reason=dict(self._drops_by_reason),
            transmissions_by_node=dict(self._transmissions_by_node),
            radio_transmissions_by_node=dict(self._radio_transmissions_by_node),
        )
