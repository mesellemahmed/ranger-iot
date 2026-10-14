from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ranger_iot.sim.packet import Packet
from ranger_iot.sim.randomness import RandomStream


class LossModel(Protocol):
    def should_drop(
        self,
        *,
        sender: int,
        receiver: int,
        packet: Packet,
        rng: RandomStream,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class NoLoss:
    def should_drop(
        self,
        *,
        sender: int,
        receiver: int,
        packet: Packet,
        rng: RandomStream,
    ) -> bool:
        del sender, receiver, packet, rng
        return False


@dataclass(frozen=True, slots=True)
class BernoulliLoss:
    probability: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError("loss probability must be in [0, 1]")

    def should_drop(
        self,
        *,
        sender: int,
        receiver: int,
        packet: Packet,
        rng: RandomStream,
    ) -> bool:
        del sender, receiver, packet
        if self.probability == 0.0:
            return False
        if self.probability == 1.0:
            return True
        return rng.random() < self.probability
