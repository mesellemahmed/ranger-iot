from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ranger_iot.sim.packet import Packet
from ranger_iot.sim.randomness import RandomStream


class DelayModel(Protocol):
    def delay_us(
        self,
        *,
        sender: int,
        receiver: int,
        packet: Packet,
        rng: RandomStream,
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class ConstantDelay:
    value_us: int

    def __post_init__(self) -> None:
        if self.value_us < 0:
            raise ValueError("delay must be non-negative")

    def delay_us(
        self,
        *,
        sender: int,
        receiver: int,
        packet: Packet,
        rng: RandomStream,
    ) -> int:
        del sender, receiver, packet, rng
        return self.value_us
