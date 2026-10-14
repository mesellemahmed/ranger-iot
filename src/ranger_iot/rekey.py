from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RekeySummary:
    epoch: int
    target_count: int
    accepted_count: int
    t50_us: int | None
    t95_us: int | None
    t100_us: int | None
    completed: bool


@dataclass(slots=True)
class RekeySession:
    epoch: int
    started_at_us: int
    targets: tuple[int, ...]
    accepted_at_us: dict[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.epoch < 0:
            raise ValueError("epoch must be non-negative")
        if self.started_at_us < 0:
            raise ValueError("started_at_us must be non-negative")
        if len(set(self.targets)) != len(self.targets):
            raise ValueError("targets must be unique")
        if any(node_id < 0 for node_id in self.targets):
            raise ValueError("target identifiers must be non-negative")

    @property
    def accepted_count(self) -> int:
        return len(self.accepted_at_us)

    @property
    def completed(self) -> bool:
        return self.accepted_count == len(self.targets)

    @property
    def convergence_fraction(self) -> float:
        if not self.targets:
            return 1.0
        return self.accepted_count / len(self.targets)

    def record_acceptance(self, node_id: int, at_us: int) -> bool:
        if node_id not in self.targets:
            raise ValueError(f"node is not a target of epoch {self.epoch}: {node_id}")
        if at_us < self.started_at_us:
            raise ValueError("acceptance time cannot precede rekey start")
        if node_id in self.accepted_at_us:
            return False
        self.accepted_at_us[node_id] = at_us
        return True

    def time_to_fraction_us(self, fraction: float) -> int | None:
        if not 0.0 < fraction <= 1.0:
            raise ValueError("fraction must be in (0, 1]")
        if not self.targets:
            return 0

        required = math.ceil(fraction * len(self.targets))
        if self.accepted_count < required:
            return None

        accepted_times = sorted(self.accepted_at_us.values())
        return accepted_times[required - 1] - self.started_at_us

    def summary(self) -> RekeySummary:
        return RekeySummary(
            epoch=self.epoch,
            target_count=len(self.targets),
            accepted_count=self.accepted_count,
            t50_us=self.time_to_fraction_us(0.50),
            t95_us=self.time_to_fraction_us(0.95),
            t100_us=self.time_to_fraction_us(1.0),
            completed=self.completed,
        )
