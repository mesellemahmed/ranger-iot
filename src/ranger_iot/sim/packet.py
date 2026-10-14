from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Packet:
    """Application-independent packet metadata used by the simulator."""

    packet_id: int
    source: int
    kind: str
    payload_bytes: int
    created_at_us: int
    epoch: int | None = None

    def __post_init__(self) -> None:
        if self.packet_id < 0:
            raise ValueError("packet_id must be non-negative")
        if self.source < 0:
            raise ValueError("source must be non-negative")
        if not self.kind:
            raise ValueError("packet kind must not be empty")
        if self.payload_bytes < 0:
            raise ValueError("payload_bytes must be non-negative")
        if self.created_at_us < 0:
            raise ValueError("created_at_us must be non-negative")
        if self.epoch is not None and self.epoch < 0:
            raise ValueError("epoch must be non-negative")


class PacketFactory:
    """Monotonic packet identifier allocator scoped to one simulation."""

    def __init__(self) -> None:
        self._next_packet_id = 0

    def create(
        self,
        *,
        source: int,
        kind: str,
        payload_bytes: int,
        created_at_us: int,
        epoch: int | None = None,
    ) -> Packet:
        packet = Packet(
            packet_id=self._next_packet_id,
            source=source,
            kind=kind,
            payload_bytes=payload_bytes,
            created_at_us=created_at_us,
            epoch=epoch,
        )
        self._next_packet_id += 1
        return packet
