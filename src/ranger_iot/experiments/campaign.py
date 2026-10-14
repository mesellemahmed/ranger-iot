from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ranger_iot.experiments.config import ExperimentConfig
from ranger_iot.experiments.runner import run_experiment
from ranger_iot.sim.topology_factory import TopologyName

ProtocolName = Literal[
    "skdc",
    "lkh-unicast",
    "lkh-flood",
    "ranger-static",
    "ranger-recovery",
    "ranger-adaptive",
    "ranger-adaptive-v2",
]

AGGREGATE_FIELDS = (
    "run_id",
    "protocol",
    "topology",
    "member_count",
    "packet_loss",
    "seed",
    "completed",
    "convergence_fraction",
    "target_count",
    "accepted_count",
    "logical_ciphertexts",
    "routed_copies",
    "flood_injections",
    "capsule_payload_bytes",
    "data_fragments",
    "total_fragments",
    "fragment_payload_bytes",
    "recovery_rounds",
    "recovery_requests",
    "recovery_fragment_attempts",
    "peer_recovery_fragment_attempts",
    "manager_recovery_fragment_attempts",
    "recovered_members",
    "initial_flood_injections",
    "adaptive_parity_injections",
    "adaptive_nack_rounds",
    "adaptive_nacks",
    "adaptive_nack_hop_attempts",
    "adaptive_nack_forwarded",
    "adaptive_nack_suppressed",
    "adaptive_actions",
    "unused_redundancy_fragments",
    "physical_transmissions",
    "link_attempts",
    "radio_transmissions",
    "manager_transmissions",
    "manager_radio_transmissions",
    "bytes_sent",
    "link_bytes_attempted",
    "radio_bytes_sent",
    "drops",
    "t50_us",
    "t95_us",
    "t100_us",
)


class CampaignConfig(BaseModel):
    """Validated Cartesian-product configuration for deterministic baseline runs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    campaign_id: str = Field(min_length=1)
    protocols: tuple[ProtocolName, ...]
    topologies: tuple[TopologyName, ...] = ("line",)
    member_counts: tuple[int, ...]
    packet_losses: tuple[float, ...]
    seeds: tuple[int, ...]
    revoked_count: int = Field(default=1, ge=1)
    group_id: int = 1
    manager_id: int = 0
    link_delay_us: int = Field(default=10, gt=0)
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

    @model_validator(mode="after")
    def validate_matrix(self) -> CampaignConfig:
        if not self.protocols:
            raise ValueError("protocols must not be empty")
        if not self.topologies:
            raise ValueError("topologies must not be empty")
        if not self.member_counts:
            raise ValueError("member_counts must not be empty")
        if not self.packet_losses:
            raise ValueError("packet_losses must not be empty")
        if not self.seeds:
            raise ValueError("seeds must not be empty")

        if len(set(self.protocols)) != len(self.protocols):
            raise ValueError("protocols must be unique")
        if len(set(self.topologies)) != len(self.topologies):
            raise ValueError("topologies must be unique")
        if len(set(self.member_counts)) != len(self.member_counts):
            raise ValueError("member_counts must be unique")
        if len(set(self.packet_losses)) != len(self.packet_losses):
            raise ValueError("packet_losses must be unique")
        if len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be unique")

        if any(member_count <= self.revoked_count for member_count in self.member_counts):
            raise ValueError("every member_count must be greater than revoked_count")
        if any(loss < 0.0 or loss > 1.0 for loss in self.packet_losses):
            raise ValueError("packet_losses must be in [0.0, 1.0]")
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
    def from_yaml(cls, path: Path) -> CampaignConfig:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("campaign YAML root must be a mapping")
        return cls.model_validate(data)

    @property
    def run_count(self) -> int:
        return (
            len(self.protocols)
            * len(self.topologies)
            * len(self.member_counts)
            * len(self.packet_losses)
            * len(self.seeds)
        )


def canonical_campaign_json(config: CampaignConfig) -> str:
    payload = config.model_dump(mode="json")
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def campaign_sha256(config: CampaignConfig) -> str:
    return hashlib.sha256(canonical_campaign_json(config).encode("utf-8")).hexdigest()


def _loss_tag(packet_loss: float) -> str:
    return f"{round(packet_loss * 1000):04d}"


def _run_id(
    *,
    protocol: str,
    topology: str,
    member_count: int,
    packet_loss: float,
    seed: int,
) -> str:
    protocol_tag = protocol.replace("-", "_")
    return (
        f"{protocol_tag}__{topology}__n{member_count:04d}"
        f"__loss{_loss_tag(packet_loss)}__seed{seed:06d}"
    )


def _revoked_members(member_count: int, revoked_count: int) -> tuple[int, ...]:
    first = member_count - revoked_count + 1
    return tuple(range(first, member_count + 1))


def iter_experiment_configs(config: CampaignConfig) -> tuple[tuple[str, ExperimentConfig], ...]:
    runs: list[tuple[str, ExperimentConfig]] = []
    for protocol in config.protocols:
        for topology in config.topologies:
            for member_count in config.member_counts:
                for packet_loss in config.packet_losses:
                    for seed in config.seeds:
                        run_id = _run_id(
                            protocol=protocol,
                            topology=topology,
                            member_count=member_count,
                            packet_loss=packet_loss,
                            seed=seed,
                        )
                        experiment = ExperimentConfig(
                            schema_version=1,
                            experiment_id=f"{config.campaign_id}__{run_id}",
                            protocol=protocol,
                            seed=seed,
                            group_id=config.group_id,
                            manager_id=config.manager_id,
                            member_count=member_count,
                            revoked_members=_revoked_members(member_count, config.revoked_count),
                            topology=topology,
                            packet_loss=packet_loss,
                            link_delay_us=config.link_delay_us,
                            payload_bytes=config.payload_bytes,
                            ranger_data_fragments=config.ranger_data_fragments,
                            ranger_total_fragments=config.ranger_total_fragments,
                            ranger_capsule_overhead_bytes=config.ranger_capsule_overhead_bytes,
                            ranger_recovery_rounds=config.ranger_recovery_rounds,
                            ranger_recovery_request_bytes=config.ranger_recovery_request_bytes,
                            ranger_adaptive_max_fragments=(config.ranger_adaptive_max_fragments),
                            ranger_adaptive_nack_bytes=config.ranger_adaptive_nack_bytes,
                            ranger_adaptive_recovery_rounds=(
                                config.ranger_adaptive_recovery_rounds
                            ),
                            max_events=config.max_events,
                        )
                        runs.append((run_id, experiment))
    return tuple(runs)


def _aggregate_row(
    run_id: str,
    config: ExperimentConfig,
    summary: dict[str, object],
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "protocol": config.protocol,
        "topology": config.topology,
        "member_count": config.member_count,
        "packet_loss": config.packet_loss,
        "seed": config.seed,
        "completed": summary["completed"],
        "convergence_fraction": summary["convergence_fraction"],
        "target_count": summary["target_count"],
        "accepted_count": summary["accepted_count"],
        "logical_ciphertexts": summary.get("logical_ciphertexts", ""),
        "routed_copies": summary.get("routed_copies", ""),
        "flood_injections": summary.get("flood_injections", ""),
        "capsule_payload_bytes": summary.get("capsule_payload_bytes", ""),
        "data_fragments": summary.get("data_fragments", ""),
        "total_fragments": summary.get("total_fragments", ""),
        "fragment_payload_bytes": summary.get("fragment_payload_bytes", ""),
        "recovery_rounds": summary.get("recovery_rounds", ""),
        "recovery_requests": summary.get("recovery_requests", ""),
        "recovery_fragment_attempts": summary.get("recovery_fragment_attempts", ""),
        "peer_recovery_fragment_attempts": summary.get("peer_recovery_fragment_attempts", ""),
        "manager_recovery_fragment_attempts": summary.get("manager_recovery_fragment_attempts", ""),
        "recovered_members": summary.get("recovered_members", ""),
        "initial_flood_injections": summary.get("initial_flood_injections", ""),
        "adaptive_parity_injections": summary.get("adaptive_parity_injections", ""),
        "adaptive_nack_rounds": summary.get("adaptive_nack_rounds", ""),
        "adaptive_nacks": summary.get("adaptive_nacks", ""),
        "adaptive_nack_hop_attempts": summary.get("adaptive_nack_hop_attempts", ""),
        "adaptive_nack_forwarded": summary.get("adaptive_nack_forwarded", ""),
        "adaptive_nack_suppressed": summary.get("adaptive_nack_suppressed", ""),
        "adaptive_actions": summary.get("adaptive_actions", ""),
        "unused_redundancy_fragments": summary.get("unused_redundancy_fragments", ""),
        "physical_transmissions": summary["physical_transmissions"],
        "link_attempts": summary["link_attempts"],
        "radio_transmissions": summary["radio_transmissions"],
        "manager_transmissions": summary["manager_transmissions"],
        "manager_radio_transmissions": summary["manager_radio_transmissions"],
        "bytes_sent": summary["bytes_sent"],
        "link_bytes_attempted": summary["link_bytes_attempted"],
        "radio_bytes_sent": summary["radio_bytes_sent"],
        "drops": summary["drops"],
        "t50_us": summary["t50_us"],
        "t95_us": summary["t95_us"],
        "t100_us": summary["t100_us"],
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AGGREGATE_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_campaign(config: CampaignConfig, output_dir: Path) -> dict[str, object]:
    """Execute the campaign matrix in deterministic order and aggregate summaries."""

    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError(f"output directory must be empty: {output_dir}")

    runs_dir = output_dir / "runs"
    runs_dir.mkdir()
    (output_dir / "campaign.json").write_text(canonical_campaign_json(config), encoding="utf-8")

    rows: list[dict[str, object]] = []
    completed_count = 0
    for run_id, experiment in iter_experiment_configs(config):
        result = run_experiment(experiment, runs_dir / run_id)
        rows.append(_aggregate_row(run_id, experiment, result.summary))
        if result.summary["completed"] is True:
            completed_count += 1

    _write_csv(output_dir / "aggregate.csv", rows)
    summary: dict[str, object] = {
        "schema_version": 1,
        "campaign_id": config.campaign_id,
        "campaign_sha256": campaign_sha256(config),
        "run_count": len(rows),
        "completed_count": completed_count,
        "incomplete_count": len(rows) - completed_count,
        "protocols": list(config.protocols),
        "topologies": list(config.topologies),
        "member_counts": list(config.member_counts),
        "packet_losses": list(config.packet_losses),
        "seeds": list(config.seeds),
        "ranger_static": {
            "data_fragments": config.ranger_data_fragments,
            "total_fragments": config.ranger_total_fragments,
            "capsule_overhead_bytes": config.ranger_capsule_overhead_bytes,
        },
        "ranger_recovery": {
            "rounds": config.ranger_recovery_rounds,
            "request_bytes": config.ranger_recovery_request_bytes,
        },
        "ranger_adaptive": {
            "max_fragments": config.ranger_adaptive_max_fragments,
            "nack_bytes": config.ranger_adaptive_nack_bytes,
            "recovery_rounds": config.ranger_adaptive_recovery_rounds,
        },
    }
    _write_json(output_dir / "campaign_summary.json", summary)
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a deterministic RANGER baseline campaign")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    config = CampaignConfig.from_yaml(args.config)
    summary = run_campaign(config, args.output)
    print(f"campaign_id={summary['campaign_id']}")
    print(f"run_count={summary['run_count']}")
    print(f"completed_count={summary['completed_count']}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
