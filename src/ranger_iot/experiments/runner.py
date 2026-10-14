from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ranger_iot.experiments.artifacts import (
    canonical_config_json,
    config_sha256,
    write_csv,
    write_json,
)
from ranger_iot.experiments.config import ExperimentConfig
from ranger_iot.experiments.trace import NetworkTrace
from ranger_iot.group import GroupState
from ranger_iot.protocols.lkh import LkhKeyTree
from ranger_iot.protocols.lkh_flood import LkhFloodParameters, LkhFloodProtocol
from ranger_iot.protocols.lkh_transport import LkhTransportParameters, LkhUnicastProtocol
from ranger_iot.protocols.skdc import SkdcParameters, SkdcProtocol
from ranger_iot.ranger.adaptive_protocol import (
    RangerAdaptiveParameters,
    RangerAdaptiveProtocol,
)
from ranger_iot.ranger.adaptive_v2_protocol import RangerAdaptiveV2Protocol
from ranger_iot.ranger.coding import CodingParameters
from ranger_iot.ranger.recovery_protocol import (
    RangerRecoveryParameters,
    RangerRecoveryProtocol,
)
from ranger_iot.ranger.static_protocol import RangerStaticParameters, RangerStaticProtocol
from ranger_iot.rekey import RekeySession
from ranger_iot.sim.core import SimulationEngine
from ranger_iot.sim.delay import ConstantDelay
from ranger_iot.sim.flooding import FloodTransport
from ranger_iot.sim.loss import BernoulliLoss
from ranger_iot.sim.metrics import NetworkMetrics, NetworkMetricsSnapshot
from ranger_iot.sim.network import Network
from ranger_iot.sim.node import NodeRegistry
from ranger_iot.sim.packet import PacketFactory
from ranger_iot.sim.randomness import RandomStream
from ranger_iot.sim.routing import ShortestPathRouter
from ranger_iot.sim.topology import StaticTopology
from ranger_iot.sim.topology_factory import build_topology

EVENT_FIELDS = (
    "at_us",
    "event",
    "sender",
    "receiver",
    "packet_id",
    "packet_kind",
    "epoch",
    "payload_bytes",
    "drop_reason",
)
NODE_FIELDS = (
    "node_id",
    "role",
    "active",
    "authorized",
    "revoked",
    "current_epoch",
    "synchronized",
    "transmissions",
)


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    output_dir: Path
    summary: dict[str, object]


def run_experiment(config: ExperimentConfig, output_dir: Path) -> ExperimentResult:
    """Execute one deterministic run and write stable machine-readable artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError(f"output directory must be empty: {output_dir}")

    engine = SimulationEngine()
    nodes = NodeRegistry(config.all_node_ids)
    topology = _build_topology(config)
    metrics = NetworkMetrics()
    trace = NetworkTrace()
    network = Network(
        engine=engine,
        topology=topology,
        nodes=nodes,
        loss_model=BernoulliLoss(config.packet_loss),
        delay_model=ConstantDelay(config.link_delay_us),
        rng=RandomStream(config.seed, "network/loss"),
        observers=(metrics, trace),
    )
    packet_factory = PacketFactory()
    group = GroupState(
        group_id=config.group_id,
        manager_id=config.manager_id,
        member_ids=set(config.member_ids),
    )

    session, protocol_fields, post_action, post_action_limit = _start_protocol(
        config=config,
        group=group,
        network=network,
        topology=topology,
        packet_factory=packet_factory,
    )
    processed_events = _drain_engine(
        engine=engine,
        processed_events=0,
        max_events=config.max_events,
    )

    if post_action is not None:
        for _ in range(post_action_limit):
            if session.completed:
                break
            if post_action() == 0:
                break
            processed_events = _drain_engine(
                engine=engine,
                processed_events=processed_events,
                max_events=config.max_events,
            )

    network_snapshot = metrics.snapshot()
    summary = _build_summary(
        config=config,
        group=group,
        session=session,
        network=network_snapshot,
        protocol_fields=protocol_fields(),
        processed_events=processed_events,
    )
    _write_artifacts(
        output_dir=output_dir,
        config=config,
        group=group,
        nodes=nodes,
        network=network_snapshot,
        trace=trace,
        summary=summary,
    )
    return ExperimentResult(output_dir=output_dir, summary=summary)


def _start_protocol(
    *,
    config: ExperimentConfig,
    group: GroupState,
    network: Network,
    topology: StaticTopology,
    packet_factory: PacketFactory,
) -> tuple[
    RekeySession,
    Callable[[], dict[str, object]],
    Callable[[], int] | None,
    int,
]:
    revoked = set(config.revoked_members)

    if config.protocol == "skdc":
        router = ShortestPathRouter(
            network=network,
            topology=topology,
            packet_factory=packet_factory,
        )
        skdc_protocol = SkdcProtocol(
            group=group,
            router=router,
            parameters=SkdcParameters(
                rekey_payload_bytes=config.payload_bytes,
            ),
        )
        session = skdc_protocol.start_rekey(
            revoked_nodes=revoked,
        )

        def skdc_fields() -> dict[str, object]:
            copies = len(session.targets)
            return {
                "logical_ciphertexts": copies,
                "routed_copies": copies,
            }

        return session, skdc_fields, None, 0

    tree = LkhKeyTree(set(config.member_ids))

    if config.protocol == "lkh-unicast":
        router = ShortestPathRouter(
            network=network,
            topology=topology,
            packet_factory=packet_factory,
        )
        lkh_protocol = LkhUnicastProtocol(
            group=group,
            tree=tree,
            router=router,
            parameters=LkhTransportParameters(
                ciphertext_payload_bytes=config.payload_bytes,
            ),
        )
        session = lkh_protocol.start_rekey(
            revoked_nodes=revoked,
        )

        def lkh_unicast_fields() -> dict[str, object]:
            stats = lkh_protocol.transport_stats(session.epoch)
            return {
                "logical_ciphertexts": stats.logical_ciphertexts,
                "routed_copies": stats.routed_copies,
            }

        return session, lkh_unicast_fields, None, 0

    if config.protocol == "lkh-flood":
        transport = FloodTransport(
            network=network,
            topology=topology,
            packet_factory=packet_factory,
        )
        flood_protocol = LkhFloodProtocol(
            group=group,
            tree=tree,
            transport=transport,
            parameters=LkhFloodParameters(
                ciphertext_payload_bytes=config.payload_bytes,
            ),
        )
        session = flood_protocol.start_rekey(
            revoked_nodes=revoked,
        )

        def lkh_flood_fields() -> dict[str, object]:
            stats = flood_protocol.transport_stats(session.epoch)
            return {
                "logical_ciphertexts": stats.logical_ciphertexts,
                "routed_copies": stats.flood_injections,
                "flood_injections": stats.flood_injections,
            }

        return session, lkh_flood_fields, None, 0

    if config.protocol == "ranger-static":
        transport = FloodTransport(
            network=network,
            topology=topology,
            packet_factory=packet_factory,
        )
        ranger_protocol = RangerStaticProtocol(
            group=group,
            tree=tree,
            transport=transport,
            parameters=RangerStaticParameters(
                coding=CodingParameters(
                    data_fragments=config.ranger_data_fragments,
                    total_fragments=config.ranger_total_fragments,
                ),
                ciphertext_payload_bytes=config.payload_bytes,
                capsule_overhead_bytes=config.ranger_capsule_overhead_bytes,
            ),
        )
        session = ranger_protocol.start_rekey(
            revoked_nodes=revoked,
        )

        def ranger_static_fields() -> dict[str, object]:
            stats = ranger_protocol.transport_stats(session.epoch)
            return {
                "logical_ciphertexts": stats.logical_ciphertexts,
                "routed_copies": stats.flood_injections,
                "flood_injections": stats.flood_injections,
                "capsule_payload_bytes": stats.capsule_payload_bytes,
                "data_fragments": stats.data_fragments,
                "total_fragments": stats.total_fragments,
                "fragment_payload_bytes": stats.fragment_payload_bytes,
            }

        return session, ranger_static_fields, None, 0

    if config.protocol == "ranger-recovery":
        transport = FloodTransport(
            network=network,
            topology=topology,
            packet_factory=packet_factory,
        )
        recovery_protocol = RangerRecoveryProtocol(
            group=group,
            tree=tree,
            transport=transport,
            parameters=RangerRecoveryParameters(
                coding=CodingParameters(
                    data_fragments=config.ranger_data_fragments,
                    total_fragments=config.ranger_total_fragments,
                ),
                ciphertext_payload_bytes=config.payload_bytes,
                capsule_overhead_bytes=config.ranger_capsule_overhead_bytes,
                recovery_request_bytes=config.ranger_recovery_request_bytes,
            ),
        )
        session = recovery_protocol.start_rekey(
            revoked_nodes=revoked,
        )

        def ranger_recovery_fields() -> dict[str, object]:
            stats = recovery_protocol.transport_stats(session.epoch)
            return {
                "logical_ciphertexts": stats.logical_ciphertexts,
                "routed_copies": stats.flood_injections,
                "flood_injections": stats.flood_injections,
                "capsule_payload_bytes": stats.capsule_payload_bytes,
                "data_fragments": stats.data_fragments,
                "total_fragments": stats.total_fragments,
                "fragment_payload_bytes": stats.fragment_payload_bytes,
                "recovery_rounds": stats.recovery_rounds,
                "recovery_requests": stats.recovery_requests,
                "recovery_fragment_attempts": stats.recovery_fragment_attempts,
                "peer_recovery_fragment_attempts": stats.peer_recovery_fragment_attempts,
                "manager_recovery_fragment_attempts": (stats.manager_recovery_fragment_attempts),
                "recovered_members": stats.recovered_members,
            }

        def recovery_round() -> int:
            return recovery_protocol.start_recovery_round(session.epoch)

        return (
            session,
            ranger_recovery_fields,
            recovery_round,
            config.ranger_recovery_rounds,
        )

    if config.protocol == "ranger-adaptive":
        transport = FloodTransport(
            network=network,
            topology=topology,
            packet_factory=packet_factory,
        )
        adaptive_protocol = RangerAdaptiveProtocol(
            group=group,
            tree=tree,
            transport=transport,
            parameters=RangerAdaptiveParameters(
                coding=CodingParameters(
                    data_fragments=config.ranger_data_fragments,
                    total_fragments=config.ranger_adaptive_max_fragments,
                ),
                ciphertext_payload_bytes=config.payload_bytes,
                capsule_overhead_bytes=config.ranger_capsule_overhead_bytes,
                recovery_request_bytes=config.ranger_recovery_request_bytes,
                adaptive_nack_bytes=config.ranger_adaptive_nack_bytes,
                adaptive_recovery_rounds=config.ranger_adaptive_recovery_rounds,
            ),
        )
        session = adaptive_protocol.start_rekey(revoked_nodes=revoked)

        def ranger_adaptive_fields() -> dict[str, object]:
            stats = adaptive_protocol.transport_stats(session.epoch)
            return {
                "logical_ciphertexts": stats.logical_ciphertexts,
                "routed_copies": stats.flood_injections,
                "flood_injections": stats.flood_injections,
                "capsule_payload_bytes": stats.capsule_payload_bytes,
                "data_fragments": stats.data_fragments,
                "total_fragments": stats.total_fragments,
                "fragment_payload_bytes": stats.fragment_payload_bytes,
                "recovery_rounds": stats.recovery_rounds,
                "recovery_requests": stats.recovery_requests,
                "recovery_fragment_attempts": stats.recovery_fragment_attempts,
                "peer_recovery_fragment_attempts": (stats.peer_recovery_fragment_attempts),
                "manager_recovery_fragment_attempts": (stats.manager_recovery_fragment_attempts),
                "recovered_members": stats.recovered_members,
                "initial_flood_injections": stats.initial_flood_injections,
                "adaptive_parity_injections": stats.adaptive_parity_injections,
                "adaptive_nack_rounds": stats.adaptive_nack_rounds,
                "adaptive_nacks": stats.adaptive_nacks,
                "adaptive_nack_hop_attempts": (stats.adaptive_nack_hop_attempts),
                "adaptive_actions": stats.adaptive_actions,
                "unused_redundancy_fragments": (stats.unused_redundancy_fragments),
            }

        def adaptive_action() -> int:
            return adaptive_protocol.advance(session.epoch)

        extra_fragments = max(
            0, config.ranger_adaptive_max_fragments - config.ranger_data_fragments
        )
        post_action_limit = extra_fragments + config.ranger_adaptive_recovery_rounds
        return session, ranger_adaptive_fields, adaptive_action, post_action_limit

    if config.protocol == "ranger-adaptive-v2":
        transport = FloodTransport(
            network=network,
            topology=topology,
            packet_factory=packet_factory,
        )
        adaptive_v2_protocol = RangerAdaptiveV2Protocol(
            group=group,
            tree=tree,
            transport=transport,
            parameters=RangerAdaptiveParameters(
                coding=CodingParameters(
                    data_fragments=config.ranger_data_fragments,
                    total_fragments=config.ranger_adaptive_max_fragments,
                ),
                ciphertext_payload_bytes=config.payload_bytes,
                capsule_overhead_bytes=config.ranger_capsule_overhead_bytes,
                recovery_request_bytes=config.ranger_recovery_request_bytes,
                adaptive_nack_bytes=config.ranger_adaptive_nack_bytes,
                adaptive_recovery_rounds=config.ranger_adaptive_recovery_rounds,
            ),
        )
        session = adaptive_v2_protocol.start_rekey(revoked_nodes=revoked)

        def ranger_adaptive_v2_fields() -> dict[str, object]:
            stats = adaptive_v2_protocol.transport_stats(session.epoch)
            return {
                "logical_ciphertexts": stats.logical_ciphertexts,
                "routed_copies": stats.flood_injections,
                "flood_injections": stats.flood_injections,
                "capsule_payload_bytes": stats.capsule_payload_bytes,
                "data_fragments": stats.data_fragments,
                "total_fragments": stats.total_fragments,
                "fragment_payload_bytes": stats.fragment_payload_bytes,
                "recovery_rounds": stats.recovery_rounds,
                "recovery_requests": stats.recovery_requests,
                "recovery_fragment_attempts": stats.recovery_fragment_attempts,
                "peer_recovery_fragment_attempts": stats.peer_recovery_fragment_attempts,
                "manager_recovery_fragment_attempts": stats.manager_recovery_fragment_attempts,
                "recovered_members": stats.recovered_members,
                "initial_flood_injections": stats.initial_flood_injections,
                "adaptive_parity_injections": stats.adaptive_parity_injections,
                "adaptive_nack_rounds": stats.adaptive_nack_rounds,
                "adaptive_nacks": stats.adaptive_nacks,
                "adaptive_nack_hop_attempts": stats.adaptive_nack_hop_attempts,
                "adaptive_nack_forwarded": stats.adaptive_nack_forwarded,
                "adaptive_nack_suppressed": stats.adaptive_nack_suppressed,
                "adaptive_actions": stats.adaptive_actions,
                "unused_redundancy_fragments": stats.unused_redundancy_fragments,
            }

        def adaptive_v2_action() -> int:
            return adaptive_v2_protocol.advance(session.epoch)

        extra_fragments = max(
            0,
            config.ranger_adaptive_max_fragments - config.ranger_data_fragments,
        )
        post_action_limit = extra_fragments + config.ranger_adaptive_recovery_rounds
        return (
            session,
            ranger_adaptive_v2_fields,
            adaptive_v2_action,
            post_action_limit,
        )

    raise ValueError(f"unsupported protocol: {config.protocol}")


def _drain_engine(
    *,
    engine: SimulationEngine,
    processed_events: int,
    max_events: int,
) -> int:
    remaining_events = max_events - processed_events
    if remaining_events <= 0:
        raise RuntimeError("max_events reached before the simulation queue was drained")

    processed_events += engine.run(max_events=remaining_events)
    if engine.pending_events:
        raise RuntimeError("max_events reached before the simulation queue was drained")
    return processed_events


def _build_topology(config: ExperimentConfig) -> StaticTopology:
    return build_topology(
        config.topology,
        nodes=config.all_node_ids,
        root_id=config.manager_id,
    )


def _build_summary(
    *,
    config: ExperimentConfig,
    group: GroupState,
    session: RekeySession,
    network: NetworkMetricsSnapshot,
    protocol_fields: dict[str, object],
    processed_events: int,
) -> dict[str, object]:
    rekey = session.summary()
    return {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "config_sha256": config_sha256(config),
        "protocol": config.protocol,
        "seed": config.seed,
        "group_id": config.group_id,
        "member_count": config.member_count,
        "revoked_members": list(config.revoked_members),
        "epoch": rekey.epoch,
        "target_count": rekey.target_count,
        "accepted_count": rekey.accepted_count,
        "completed": rekey.completed,
        "convergence_fraction": session.convergence_fraction,
        "t50_us": rekey.t50_us,
        "t95_us": rekey.t95_us,
        "t100_us": rekey.t100_us,
        "processed_events": processed_events,
        # Legacy names remain aliases for receiver/link accounting.
        "physical_transmissions": network.transmissions,
        "link_attempts": network.transmissions,
        "radio_transmissions": network.radio_transmissions,
        "deliveries": network.deliveries,
        "drops": network.drops,
        "bytes_sent": network.bytes_sent,
        "link_bytes_attempted": network.bytes_sent,
        "radio_bytes_sent": network.radio_bytes_sent,
        "bytes_delivered": network.bytes_delivered,
        "manager_transmissions": network.transmissions_by_node.get(config.manager_id, 0),
        "manager_radio_transmissions": network.radio_transmissions_by_node.get(
            config.manager_id, 0
        ),
        "final_group_epoch": group.current_epoch,
        **protocol_fields,
    }


def _write_artifacts(
    *,
    output_dir: Path,
    config: ExperimentConfig,
    group: GroupState,
    nodes: NodeRegistry,
    network: NetworkMetricsSnapshot,
    trace: NetworkTrace,
    summary: dict[str, object],
) -> None:
    (output_dir / "config.json").write_text(canonical_config_json(config), encoding="utf-8")
    write_json(output_dir / "summary.json", summary)
    write_csv(output_dir / "events.csv", EVENT_FIELDS, trace.rows())

    node_rows: list[dict[str, object]] = []
    for node_id in config.all_node_ids:
        is_manager = node_id == config.manager_id
        authorized = None if is_manager else group.is_authorized(node_id)
        revoked = None if is_manager else not authorized
        current_epoch = None if is_manager else group.member_epoch(node_id)
        synchronized = None if is_manager else current_epoch == group.current_epoch
        node_rows.append(
            {
                "node_id": node_id,
                "role": "manager" if is_manager else "member",
                "active": nodes.is_active(node_id),
                "authorized": "" if authorized is None else authorized,
                "revoked": "" if revoked is None else revoked,
                "current_epoch": "" if current_epoch is None else current_epoch,
                "synchronized": "" if synchronized is None else synchronized,
                "transmissions": network.transmissions_by_node.get(node_id, 0),
            }
        )
    write_csv(output_dir / "nodes.csv", NODE_FIELDS, node_rows)
