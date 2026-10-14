from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ranger_iot.sim.topology_factory import TopologyName

ProtocolName = Literal[
    "skdc",
    "lkh-flood",
    "lkh-unicast",
    "ranger-static",
    "ranger-recovery",
    "ranger-adaptive",
    "ranger-adaptive-v2",
]


class ExperimentConfig(BaseModel):
    """Validated, serializable configuration for one deterministic rekey run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    experiment_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._-]+$")
    protocol: ProtocolName
    seed: int = Field(ge=0)
    group_id: int = Field(default=1, ge=0)
    manager_id: int = Field(default=0, ge=0)
    member_count: int = Field(ge=2)
    revoked_members: tuple[int, ...]
    topology: TopologyName = "line"
    packet_loss: float = Field(default=0.0, ge=0.0, le=1.0)
    link_delay_us: int = Field(default=10, ge=0)
    payload_bytes: int = Field(default=64, gt=0)
    ranger_data_fragments: int = Field(default=3, gt=0)
    ranger_total_fragments: int = Field(default=5, gt=0)
    ranger_capsule_overhead_bytes: int = Field(default=0, ge=0)
    ranger_recovery_rounds: int = Field(default=2, ge=0)
    ranger_recovery_request_bytes: int = Field(default=24, gt=0)
    ranger_adaptive_max_fragments: int = Field(default=5, gt=0)
    ranger_adaptive_nack_bytes: int = Field(default=16, gt=0)
    ranger_adaptive_recovery_rounds: int = Field(default=2, ge=0)
    max_events: int = Field(default=1_000_000, gt=0)

    @property
    def member_ids(self) -> tuple[int, ...]:
        return tuple(range(1, self.member_count + 1))

    @property
    def all_node_ids(self) -> tuple[int, ...]:
        return (self.manager_id, *self.member_ids)

    @model_validator(mode="after")
    def validate_membership(self) -> ExperimentConfig:
        if self.manager_id in self.member_ids:
            raise ValueError("manager_id must not overlap generated member identifiers")
        if not self.revoked_members:
            raise ValueError("revoked_members must contain at least one member")
        if len(set(self.revoked_members)) != len(self.revoked_members):
            raise ValueError("revoked_members must be unique")
        unknown = set(self.revoked_members) - set(self.member_ids)
        if unknown:
            raise ValueError(f"revoked member is outside the group: {min(unknown)}")
        if len(self.revoked_members) >= self.member_count:
            raise ValueError("a run must retain at least one authorized member")
        if self.protocol.startswith("lkh-") and self.member_count < 2:
            raise ValueError("LKH requires at least two members")
        if self.ranger_data_fragments > self.ranger_total_fragments:
            raise ValueError(
                "ranger_data_fragments must be less than or equal to ranger_total_fragments"
            )
        if self.ranger_adaptive_max_fragments < self.ranger_data_fragments:
            raise ValueError(
                "ranger_adaptive_max_fragments must be greater than or equal to "
                "ranger_data_fragments"
            )
        return self

    @classmethod
    def from_yaml(cls, path: Path) -> ExperimentConfig:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("experiment configuration must be a YAML mapping")
        return cls.model_validate(data)
