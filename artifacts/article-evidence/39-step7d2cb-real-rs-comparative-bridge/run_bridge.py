from __future__ import annotations

import csv
import dataclasses
import hashlib
import importlib
import inspect
import itertools
import json
import math
import shutil

from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from ranger_iot.experiments.campaign import (
    CampaignConfig,
    iter_experiment_configs,
)

from ranger_iot.experiments.runner import run_experiment

from ranger_iot.ranger.static_protocol import RangerStaticProtocol
from ranger_iot.ranger.recovery_protocol import RangerRecoveryProtocol
from ranger_iot.ranger.adaptive_protocol import RangerAdaptiveProtocol
from ranger_iot.ranger.adaptive_v2_protocol import RangerAdaptiveV2Protocol


AGG = Path(
    "experiments/results/step7b1/"
    "model-external-validity-20261003T134431/"
    "aggregate.csv"
)

CONFIG = Path(
    "artifacts/article-evidence/"
    "16-step7b1-model-external-validity/"
    "step7b1-config.yaml"
)

OUT = Path(
    "artifacts/article-evidence/"
    "39-step7d2cb-real-rs-comparative-bridge"
)

TMP = Path(
    "/tmp/ranger-step7d2cb-runs"
)


PROTOCOLS = (
    "ranger-static",
    "ranger-recovery",
    "ranger-adaptive-v2",
)


# ==================================================================
# Utilities
# ==================================================================

def as_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def as_optional_float(value: Any) -> float | None:
    if value in {"", None}:
        return None

    return float(value)


def same_number(
    left: Any,
    right: Any,
    *,
    tolerance: float = 1e-9,
) -> bool:
    if left in {"", None} and right in {"", None}:
        return True

    if left in {"", None} or right in {"", None}:
        return False

    return math.isclose(
        float(left),
        float(right),
        rel_tol=tolerance,
        abs_tol=tolerance,
    )


def write_json(
    path: Path,
    payload: Any,
) -> None:
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


# ==================================================================
# Load frozen historical STEP7B data
# ==================================================================

with AGG.open(
    encoding="utf-8",
    newline="",
) as handle:
    historical_rows = list(
        csv.DictReader(handle)
    )


if len(historical_rows) != 2880:
    raise RuntimeError(
        f"Expected 2880 historical rows, got {len(historical_rows)}"
    )


historical_by_run = {
    row["run_id"]: row
    for row in historical_rows
}


if len(historical_by_run) != 2880:
    raise RuntimeError(
        "Historical run_id values are not unique"
    )


# ==================================================================
# Build grouped historical matrix
# ==================================================================

grouped_samples: dict[
    tuple[str, int, float, str],
    list[dict[str, str]],
] = defaultdict(list)


for row in historical_rows:
    key = (
        row["topology"],
        int(row["member_count"]),
        float(row["packet_loss"]),
        row["protocol"],
    )

    grouped_samples[key].append(row)


cells: dict[
    tuple[str, int, float],
    dict[str, dict[str, float]],
] = defaultdict(dict)


for (
    topology,
    member_count,
    packet_loss,
    protocol,
), rows in grouped_samples.items():

    cells[
        (
            topology,
            member_count,
            packet_loss,
        )
    ][protocol] = {
        "completion":
            sum(
                as_bool(row["completed"])
                for row in rows
            )
            / len(rows),

        "convergence":
            sum(
                float(
                    row["convergence_fraction"]
                )
                for row in rows
            )
            / len(rows),
    }


complete_cells = {
    key: value
    for key, value in cells.items()
    if set(value) == set(PROTOCOLS)
}


if len(complete_cells) != 48:
    raise RuntimeError(
        f"Expected 48 complete scenario cells, got {len(complete_cells)}"
    )


# ==================================================================
# Pre-register discriminant scenarios using ONLY historical data
#
# No real-RS result has been observed yet.
# ==================================================================

selected: list[dict[str, Any]] = []
used: set[tuple[str, int, float]] = set()


def rank_candidates(
    score: Callable[
        [tuple[str, int, float], dict[str, dict[str, float]]],
        tuple,
    ],
    predicate: Callable[
        [tuple[str, int, float], dict[str, dict[str, float]]],
        bool,
    ],
) -> list[
    tuple[
        tuple[str, int, float],
        dict[str, dict[str, float]],
    ]
]:
    items = [
        (cell, metrics)
        for cell, metrics
        in complete_cells.items()
        if predicate(cell, metrics)
    ]

    return sorted(
        items,
        key=lambda item:
            score(
                item[0],
                item[1],
            ),
        reverse=True,
    )


def choose(
    label: str,
    ranked,
) -> None:
    for cell, metrics in ranked:
        if cell in used:
            continue

        used.add(cell)

        topology, n, loss = cell

        selected.append(
            {
                "label":
                    label,

                "topology":
                    topology,

                "member_count":
                    n,

                "packet_loss":
                    loss,

                "historical":
                    metrics,
            }
        )

        return

    raise RuntimeError(
        f"No unique scenario available for {label}"
    )


stress = lambda cell, metrics: (
    math.isclose(
        cell[2],
        0.2,
    )
)


choose(
    "recovery_vs_static_max_convergence_gain",
    rank_candidates(
        lambda cell, m: (
            m["ranger-recovery"]["convergence"]
            -
            m["ranger-static"]["convergence"],
            cell[1],
        ),
        stress,
    ),
)


choose(
    "adaptive_vs_static_max_convergence_gain",
    rank_candidates(
        lambda cell, m: (
            m["ranger-adaptive-v2"]["convergence"]
            -
            m["ranger-static"]["convergence"],
            cell[1],
        ),
        stress,
    ),
)


choose(
    "recovery_over_adaptive_context",
    rank_candidates(
        lambda cell, m: (
            m["ranger-recovery"]["convergence"]
            -
            m["ranger-adaptive-v2"]["convergence"],
            cell[1],
        ),
        stress,
    ),
)


choose(
    "adaptive_over_recovery_context",
    rank_candidates(
        lambda cell, m: (
            m["ranger-adaptive-v2"]["convergence"]
            -
            m["ranger-recovery"]["convergence"],
            cell[1],
        ),
        stress,
    ),
)


choose(
    "robust_high_loss_control",
    rank_candidates(
        lambda cell, m: (
            min(
                value["completion"]
                for value
                in m.values()
            ),
            min(
                value["convergence"]
                for value
                in m.values()
            ),
            cell[1],
        ),
        stress,
    ),
)


choose(
    "harsh_high_loss_control",
    rank_candidates(
        lambda cell, m: (
            -
            max(
                value["convergence"]
                for value
                in m.values()
            ),
            cell[1],
        ),
        lambda cell, metrics: (
            stress(cell, metrics)
            and
            cell[1] >= 16
        ),
    ),
)


choose(
    "no_loss_high_scale_control",
    rank_candidates(
        lambda cell, m: (
            cell[1],
            min(
                value["completion"]
                for value
                in m.values()
            ),
        ),
        lambda cell, metrics: (
            math.isclose(
                cell[2],
                0.0,
            )
            and
            cell[0] == "grid"
        ),
    ),
)


if len(selected) != 7:
    raise RuntimeError(
        f"Expected 7 selected cells, got {len(selected)}"
    )


write_json(
    OUT / "bridge-selection.json",
    {
        "schema_version":
            1,

        "selection_source":
            "frozen STEP7B1 idealized dataset",

        "selection_timing":
            "before real-RS bridge execution",

        "selection_policy":
            (
                "algorithmic discriminant-context selection "
                "from the frozen historical matrix"
            ),

        "selected_cells":
            selected,

        "real_rs_results_used_for_selection":
            False,
    },
)


print(
    "BRIDGE_SCENARIOS_FROZEN=PASS"
)

for item in selected:
    print(
        f"  {item['label']:44s} "
        f"{item['topology']:14s} "
        f"N={item['member_count']:2d} "
        f"loss={item['packet_loss']:.2f}"
    )


# ==================================================================
# Canonical RS API resolver
# ==================================================================

rs_module = importlib.import_module(
    "ranger_iot.ranger.rs_codec"
)


Params = getattr(
    rs_module,
    "ReedSolomonParameters",
)


params = Params(
    data_shards=3,
    total_shards=5,
)


def invoke(
    function,
    pattern: tuple[str, ...],
    *,
    payload: bytes | None = None,
    fragments=None,
):
    args = []

    for token in pattern:
        if token == "payload":
            args.append(payload)

        elif token == "params":
            args.append(params)

        elif token == "fragments":
            args.append(fragments)

        else:
            raise RuntimeError(
                f"Unknown invocation token {token}"
            )

    return function(*args)


def fragment_bytes(fragment) -> bytes:
    if dataclasses.is_dataclass(fragment):
        for field in dataclasses.fields(fragment):
            value = getattr(
                fragment,
                field.name,
            )

            if isinstance(
                value,
                bytes,
            ):
                return value

    if hasattr(fragment, "__dict__"):
        for value in vars(fragment).values():
            if isinstance(
                value,
                bytes,
            ):
                return value

    for name in (
        "data",
        "shard",
        "payload",
        "bytes",
    ):
        value = getattr(
            fragment,
            name,
            None,
        )

        if isinstance(
            value,
            bytes,
        ):
            return value

    raise RuntimeError(
        "Unable to identify byte payload "
        "inside ReedSolomonFragment"
    )


def resolve_codec():
    payload = (
        b"RANGER-IOT-RS-BRIDGE-"
        + bytes(range(61))
    )


    candidates = []


    for name, cls in inspect.getmembers(
        rs_module,
        inspect.isclass,
    ):
        if (
            cls.__module__
            != rs_module.__name__
        ):
            continue

        if not (
            callable(
                getattr(
                    cls,
                    "encode",
                    None,
                )
            )
            and
            callable(
                getattr(
                    cls,
                    "decode",
                    None,
                )
            )
        ):
            continue


        targets = []


        targets.append(
            (
                f"{name}:class",
                cls,
            )
        )


        try:
            instance = cls(params)

        except Exception:
            pass

        else:
            targets.append(
                (
                    f"{name}:instance(params)",
                    instance,
                )
            )


        try:
            instance = cls()

        except Exception:
            pass

        else:
            targets.append(
                (
                    f"{name}:instance()",
                    instance,
                )
            )


        candidates.extend(
            targets
        )


    encode_patterns = [
        ("payload", "params"),
        ("params", "payload"),
        ("payload",),
    ]


    decode_patterns = [
        ("fragments", "params"),
        ("params", "fragments"),
        ("fragments",),
    ]


    errors = []


    for target_name, target in candidates:

        encode = getattr(
            target,
            "encode",
        )

        decode = getattr(
            target,
            "decode",
        )


        for encode_pattern in encode_patterns:

            try:
                fragments = tuple(
                    invoke(
                        encode,
                        encode_pattern,
                        payload=payload,
                    )
                )

            except Exception as exc:
                errors.append(
                    (
                        target_name,
                        "encode",
                        encode_pattern,
                        type(exc).__name__,
                    )
                )

                continue


            if len(fragments) != 5:
                continue


            indices = [
                int(
                    getattr(
                        fragment,
                        "index",
                    )
                )
                for fragment
                in fragments
            ]


            if sorted(indices) != list(
                range(5)
            ):
                continue


            for decode_pattern in decode_patterns:

                try:
                    reconstructed = invoke(
                        decode,
                        decode_pattern,
                        fragments=fragments[:3],
                    )

                except Exception as exc:
                    errors.append(
                        (
                            target_name,
                            "decode",
                            decode_pattern,
                            type(exc).__name__,
                        )
                    )

                    continue


                if reconstructed != payload:
                    continue


                # Validate all 3-of-5 subsets before accepting adapter.
                subset_ok = True

                for subset in itertools.combinations(
                    fragments,
                    3,
                ):
                    try:
                        value = invoke(
                            decode,
                            decode_pattern,
                            fragments=subset,
                        )

                    except Exception:
                        subset_ok = False
                        break


                    if value != payload:
                        subset_ok = False
                        break


                if not subset_ok:
                    continue


                return {
                    "target_name":
                        target_name,

                    "target":
                        target,

                    "encode_pattern":
                        encode_pattern,

                    "decode_pattern":
                        decode_pattern,

                    "encode":
                        encode,

                    "decode":
                        decode,
                }


    raise RuntimeError(
        "Unable to resolve canonical RS codec API; "
        f"attempts={errors!r}"
    )


adapter = resolve_codec()


write_json(
    OUT / "rs-api-resolution.json",
    {
        "schema_version":
            1,

        "target":
            adapter[
                "target_name"
            ],

        "encode_pattern":
            list(
                adapter[
                    "encode_pattern"
                ]
            ),

        "decode_pattern":
            list(
                adapter[
                    "decode_pattern"
                ]
            ),

        "all_3_of_5_subsets_validated":
            True,
    },
)


print(
    "CANONICAL_RS_API_RESOLUTION=PASS"
)


def rs_encode(
    payload: bytes,
):
    return tuple(
        invoke(
            adapter["encode"],
            adapter[
                "encode_pattern"
            ],
            payload=payload,
        )
    )


def rs_decode(
    fragments,
):
    return invoke(
        adapter["decode"],
        adapter[
            "decode_pattern"
        ],
        fragments=fragments,
    )


# ==================================================================
# Capture protocol object without modifying source
# ==================================================================

CAPTURED: dict[
    int,
    object,
] = {}


def install_capture(
    cls,
) -> None:
    original = cls.start_rekey

    if getattr(
        original,
        "_ranger_bridge_capture",
        False,
    ):
        return


    def wrapped(
        self,
        *args,
        **kwargs,
    ):
        session = original(
            self,
            *args,
            **kwargs,
        )

        CAPTURED[
            id(self)
        ] = self

        return session


    wrapped._ranger_bridge_capture = True

    cls.start_rekey = wrapped


for cls in (
    RangerStaticProtocol,
    RangerRecoveryProtocol,
    RangerAdaptiveProtocol,
    RangerAdaptiveV2Protocol,
):
    install_capture(cls)


# ==================================================================
# Exact selected run set from frozen STEP7B configuration
# ==================================================================

campaign = CampaignConfig.from_yaml(
    CONFIG
)


all_runs = dict(
    iter_experiment_configs(
        campaign
    )
)


selected_keys = {
    (
        item["topology"],
        int(
            item[
                "member_count"
            ]
        ),
        float(
            item[
                "packet_loss"
            ]
        ),
    )
    for item
    in selected
}


selected_runs = [
    (
        run_id,
        config,
    )
    for run_id, config
    in all_runs.items()
    if (
        config.protocol
        in PROTOCOLS
        and
        (
            config.topology,
            config.member_count,
            float(
                config.packet_loss
            ),
        )
        in selected_keys
    )
]


expected_runs = (
    7
    * 3
    * 20
)


if len(selected_runs) != expected_runs:
    raise RuntimeError(
        f"Expected {expected_runs} bridge runs, "
        f"got {len(selected_runs)}"
    )


selected_runs.sort(
    key=lambda item:
        item[0]
)


print(
    f"BRIDGE_RUN_COUNT={len(selected_runs)}"
)


# ==================================================================
# Execute deterministic reruns + RS byte oracle
# ==================================================================

if TMP.exists():
    shutil.rmtree(TMP)

TMP.mkdir(
    parents=True
)


run_rows = []
member_rows = []


for ordinal, (
    run_id,
    config,
) in enumerate(
    selected_runs,
    start=1,
):

    print(
        f"[{ordinal:03d}/{len(selected_runs):03d}] "
        f"{run_id}"
    )


    CAPTURED.clear()


    run_dir = (
        TMP
        / run_id
    )


    result = run_experiment(
        config,
        run_dir,
    )


    protocols = list(
        CAPTURED.values()
    )


    unique_protocols = {
        id(protocol):
            protocol
        for protocol
        in protocols
    }


    if len(unique_protocols) != 1:
        raise RuntimeError(
            f"{run_id}: expected exactly one captured "
            f"protocol instance, got {len(unique_protocols)}"
        )


    protocol = next(
        iter(
            unique_protocols.values()
        )
    )


    epochs = getattr(
        protocol,
        "_epochs",
        None,
    )


    if not epochs:
        raise RuntimeError(
            f"{run_id}: protocol exposes no epoch state"
        )


    if len(epochs) != 1:
        raise RuntimeError(
            f"{run_id}: expected one rekey epoch, "
            f"got {sorted(epochs)}"
        )


    epoch = next(
        iter(
            epochs
        )
    )


    state = epochs[
        epoch
    ]


    capsule = protocol.capsule(
        epoch
    )


    ideal_fragments = tuple(
        state.fragments
    )


    if not ideal_fragments:
        raise RuntimeError(
            f"{run_id}: no idealized fragments"
        )


    k = int(
        ideal_fragments[
            0
        ].data_fragments
    )

    n = int(
        ideal_fragments[
            0
        ].total_fragments
    )


    if (
        k,
        n,
    ) != (
        3,
        5,
    ):
        raise RuntimeError(
            f"{run_id}: bridge contract requires "
            f"canonical 3-of-5 profile, got {k}-of-{n}"
        )


    capsule_length = int(
        capsule.payload_bytes
    )


    seed_material = (
        f"RANGER-IOT:STEP7D2CB:"
        f"{run_id}:"
        f"{capsule.capsule_id}:"
        f"{capsule.group_id}:"
        f"{capsule.epoch}:"
        f"{capsule_length}"
    ).encode(
        "utf-8"
    )


    payload = hashlib.shake_256(
        seed_material
    ).digest(
        capsule_length
    )


    real_fragments = rs_encode(
        payload
    )


    if len(real_fragments) != n:
        raise RuntimeError(
            f"{run_id}: real RS returned "
            f"{len(real_fragments)} shards"
        )


    by_index = {
        int(
            getattr(
                fragment,
                "index",
            )
        ):
            fragment
        for fragment
        in real_fragments
    }


    if sorted(by_index) != list(
        range(n)
    ):
        raise RuntimeError(
            f"{run_id}: real RS shard-index mismatch"
        )


    real_shard_sizes = {
        len(
            fragment_bytes(
                fragment
            )
        )
        for fragment
        in real_fragments
    }


    if len(real_shard_sizes) != 1:
        raise RuntimeError(
            f"{run_id}: unequal real shard sizes"
        )


    real_shard_size = next(
        iter(
            real_shard_sizes
        )
    )


    ideal_fragment_size = int(
        ideal_fragments[
            0
        ].payload_bytes
    )


    shard_size_parity = (
        real_shard_size
        ==
        ideal_fragment_size
    )


    if not shard_size_parity:
        raise RuntimeError(
            f"{run_id}: real shard data size "
            f"{real_shard_size} != ideal fragment "
            f"payload size {ideal_fragment_size}"
        )


    subset_cache: dict[
        tuple[int, ...],
        tuple[bool, bool],
    ] = {}


    rs_accepted = 0
    actual_accepted = 0


    for member_id, accumulator in sorted(
        state.accumulators.items()
    ):
        indexes = tuple(
            int(index)
            for index
            in accumulator.received_indexes
        )


        ideal_decodable = bool(
            accumulator.decodable
        )


        actual_member_accepted = (
            protocol._group.member_epoch(
                member_id
            )
            ==
            epoch
        )


        if actual_member_accepted:
            actual_accepted += 1


        if indexes not in subset_cache:

            subset = tuple(
                by_index[
                    index
                ]
                for index
                in indexes
            )


            if len(
                indexes
            ) >= k:

                try:
                    reconstructed = rs_decode(
                        subset
                    )

                except Exception:
                    rs_decodable = False
                    payload_equal = False

                else:
                    rs_decodable = True
                    payload_equal = (
                        reconstructed
                        ==
                        payload
                    )

            else:

                try:
                    reconstructed = rs_decode(
                        subset
                    )

                except Exception:
                    rs_decodable = False
                    payload_equal = False

                else:
                    rs_decodable = True
                    payload_equal = (
                        reconstructed
                        ==
                        payload
                    )


            subset_cache[
                indexes
            ] = (
                rs_decodable,
                payload_equal,
            )


        (
            rs_decodable,
            payload_equal,
        ) = subset_cache[
            indexes
        ]


        if rs_decodable:
            rs_accepted += 1


        decision_parity = (
            ideal_decodable
            ==
            rs_decodable
            ==
            actual_member_accepted
        )


        byte_or_threshold_valid = (
            (
                rs_decodable
                and
                payload_equal
            )
            or
            (
                not rs_decodable
                and
                len(indexes) < k
            )
        )


        member_rows.append(
            {
                "run_id":
                    run_id,

                "protocol":
                    config.protocol,

                "topology":
                    config.topology,

                "member_count":
                    config.member_count,

                "packet_loss":
                    config.packet_loss,

                "seed":
                    config.seed,

                "member_id":
                    member_id,

                "received_indexes":
                    ",".join(
                        str(value)
                        for value
                        in indexes
                    ),

                "received_count":
                    len(indexes),

                "k":
                    k,

                "n":
                    n,

                "ideal_decodable":
                    ideal_decodable,

                "actual_protocol_accept":
                    actual_member_accepted,

                "real_rs_decodable":
                    rs_decodable,

                "real_rs_payload_exact":
                    payload_equal,

                "decision_parity":
                    decision_parity,

                "byte_or_threshold_valid":
                    byte_or_threshold_valid,

                "ideal_fragment_payload_bytes":
                    ideal_fragment_size,

                "real_rs_shard_bytes":
                    real_shard_size,

                "shard_size_parity":
                    shard_size_parity,
            }
        )


        if not decision_parity:
            raise RuntimeError(
                f"{run_id}/member={member_id}: "
                f"ideal={ideal_decodable}, "
                f"actual={actual_member_accepted}, "
                f"realRS={rs_decodable}"
            )


        if not byte_or_threshold_valid:
            raise RuntimeError(
                f"{run_id}/member={member_id}: "
                "real-RS byte/threshold oracle failed"
            )


    target_count = len(
        state.accumulators
    )


    rs_completion = (
        rs_accepted
        ==
        target_count
    )


    rs_convergence = (
        rs_accepted
        /
        target_count
    )


    summary = result.summary


    if (
        int(
            summary[
                "accepted_count"
            ]
        )
        != actual_accepted
    ):
        raise RuntimeError(
            f"{run_id}: accepted-count mismatch"
        )


    if (
        bool(
            summary[
                "completed"
            ]
        )
        != rs_completion
    ):
        raise RuntimeError(
            f"{run_id}: RS completion parity failure"
        )


    if not math.isclose(
        float(
            summary[
                "convergence_fraction"
            ]
        ),
        rs_convergence,
        rel_tol=1e-12,
        abs_tol=1e-12,
    ):
        raise RuntimeError(
            f"{run_id}: RS convergence parity failure"
        )


    historical = historical_by_run[
        run_id
    ]


    replay_checks = {
        "completed":
            as_bool(
                historical[
                    "completed"
                ]
            )
            ==
            bool(
                summary[
                    "completed"
                ]
            ),

        "convergence_fraction":
            same_number(
                historical[
                    "convergence_fraction"
                ],
                summary[
                    "convergence_fraction"
                ],
            ),

        "physical_transmissions":
            same_number(
                historical[
                    "physical_transmissions"
                ],
                summary[
                    "physical_transmissions"
                ],
            ),

        "manager_transmissions":
            same_number(
                historical[
                    "manager_transmissions"
                ],
                summary[
                    "manager_transmissions"
                ],
            ),

        "bytes_sent":
            same_number(
                historical[
                    "bytes_sent"
                ],
                summary[
                    "bytes_sent"
                ],
            ),

        "drops":
            same_number(
                historical[
                    "drops"
                ],
                summary[
                    "drops"
                ],
            ),

        "t100_us":
            same_number(
                historical[
                    "t100_us"
                ],
                summary[
                    "t100_us"
                ],
            ),
    }


    if not all(
        replay_checks.values()
    ):
        raise RuntimeError(
            f"{run_id}: historical deterministic "
            f"replay mismatch {replay_checks}"
        )


    run_rows.append(
        {
            "run_id":
                run_id,

            "protocol":
                config.protocol,

            "topology":
                config.topology,

            "member_count":
                config.member_count,

            "packet_loss":
                config.packet_loss,

            "seed":
                config.seed,

            "target_count":
                target_count,

            "historical_completed":
                as_bool(
                    historical[
                        "completed"
                    ]
                ),

            "rerun_completed":
                bool(
                    summary[
                        "completed"
                    ]
                ),

            "real_rs_completed":
                rs_completion,

            "historical_convergence":
                float(
                    historical[
                        "convergence_fraction"
                    ]
                ),

            "rerun_convergence":
                float(
                    summary[
                        "convergence_fraction"
                    ]
                ),

            "real_rs_convergence":
                rs_convergence,

            "actual_accepted":
                actual_accepted,

            "real_rs_accepted":
                rs_accepted,

            "capsule_payload_bytes":
                capsule_length,

            "ideal_fragment_payload_bytes":
                ideal_fragment_size,

            "real_rs_shard_bytes":
                real_shard_size,

            "shard_size_parity":
                shard_size_parity,

            "historical_replay_exact":
                all(
                    replay_checks.values()
                ),
        }
    )


# ==================================================================
# Write compact evidence
# ==================================================================

def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                rows[0]
            ),
            lineterminator="\n",
        )

        writer.writeheader()
        writer.writerows(rows)


write_csv(
    OUT / "bridge-runs.csv",
    run_rows,
)


write_csv(
    OUT / "bridge-members.csv",
    member_rows,
)


# ==================================================================
# Grouped real-RS / historical comparison
# ==================================================================

grouped_bridge: dict[
    tuple[str, int, float, str],
    list[dict[str, Any]],
] = defaultdict(list)


for row in run_rows:
    key = (
        row["topology"],
        int(
            row[
                "member_count"
            ]
        ),
        float(
            row[
                "packet_loss"
            ]
        ),
        row["protocol"],
    )

    grouped_bridge[
        key
    ].append(row)


group_rows = []


for key, rows in sorted(
    grouped_bridge.items()
):
    topology, n_members, loss, protocol = key

    historical_completion = sum(
        bool(
            row[
                "historical_completed"
            ]
        )
        for row in rows
    ) / len(rows)

    real_completion = sum(
        bool(
            row[
                "real_rs_completed"
            ]
        )
        for row in rows
    ) / len(rows)


    historical_convergence = sum(
        float(
            row[
                "historical_convergence"
            ]
        )
        for row in rows
    ) / len(rows)


    real_convergence = sum(
        float(
            row[
                "real_rs_convergence"
            ]
        )
        for row in rows
    ) / len(rows)


    group_rows.append(
        {
            "topology":
                topology,

            "member_count":
                n_members,

            "packet_loss":
                loss,

            "protocol":
                protocol,

            "runs":
                len(rows),

            "historical_completion":
                historical_completion,

            "real_rs_completion":
                real_completion,

            "completion_delta":
                real_completion
                -
                historical_completion,

            "historical_convergence":
                historical_convergence,

            "real_rs_convergence":
                real_convergence,

            "convergence_delta":
                real_convergence
                -
                historical_convergence,
        }
    )


write_csv(
    OUT / "bridge-grouped.csv",
    group_rows,
)


member_parity = all(
    row[
        "decision_parity"
    ]
    for row in member_rows
)


byte_valid = all(
    row[
        "byte_or_threshold_valid"
    ]
    for row in member_rows
)


size_parity = all(
    row[
        "shard_size_parity"
    ]
    for row in member_rows
)


historical_replay = all(
    row[
        "historical_replay_exact"
    ]
    for row in run_rows
)


group_exact = all(
    math.isclose(
        float(
            row[
                "completion_delta"
            ]
        ),
        0.0,
        abs_tol=1e-12,
    )
    and
    math.isclose(
        float(
            row[
                "convergence_delta"
            ]
        ),
        0.0,
        abs_tol=1e-12,
    )
    for row
    in group_rows
)


summary = {
    "schema_version":
        1,

    "step":
        "STEP7D2CB_REAL_RS_COMPARATIVE_DECISION_BRIDGE",

    "selected_scenario_cells":
        len(selected),

    "protocols":
        list(PROTOCOLS),

    "seeds_per_cell":
        20,

    "bridge_run_count":
        len(run_rows),

    "member_decision_count":
        len(member_rows),

    "member_decision_parity":
        member_parity,

    "real_rs_byte_reconstruction_or_threshold_valid":
        byte_valid,

    "real_rs_shard_size_matches_ideal_fragment_payload":
        size_parity,

    "historical_deterministic_replay_exact":
        historical_replay,

    "grouped_completion_and_convergence_exact":
        group_exact,

    "step7c3_real_wire_anchor":
        True,

    "historical_step7b_modified":
        False,

    "protocol_implementation_modified":
        False,

    "bridge_scope":
        (
            "canonical byte-level RS decode over exact "
            "received-index sets from deterministic "
            "comparative network reruns"
        ),

    "important_boundary":
        (
            "The bridge proves decision/byte reconstruction "
            "equivalence and shard-data-size parity. "
            "It does not claim that all STEP7B comparative "
            "runs physically transmitted serialized RS bytes; "
            "actual RS bytes on Cooja/RPL wire are established "
            "separately by STEP7C3."
        ),

    "scientific_state":
        (
            "REAL_RS_COMPARATIVE_DECISION_BRIDGE_PASS"
            if (
                member_parity
                and
                byte_valid
                and
                size_parity
                and
                historical_replay
                and
                group_exact
            )
            else
            "REAL_RS_COMPARATIVE_DECISION_BRIDGE_FAILURE"
        ),
}


write_json(
    OUT / "bridge-summary.json",
    summary,
)


print()
print("=" * 78)
print("REAL-RS COMPARATIVE BRIDGE")
print("=" * 78)

print(
    f"SELECTED_SCENARIO_CELLS={len(selected)}"
)

print(
    f"BRIDGE_RUNS={len(run_rows)}"
)

print(
    f"MEMBER_DECISIONS={len(member_rows)}"
)

print(
    f"MEMBER_DECISION_PARITY={member_parity}"
)

print(
    f"BYTE_RECONSTRUCTION_OR_THRESHOLD={byte_valid}"
)

print(
    f"SHARD_SIZE_PARITY={size_parity}"
)

print(
    f"HISTORICAL_REPLAY_EXACT={historical_replay}"
)

print(
    f"GROUPED_RESULTS_EXACT={group_exact}"
)

print(
    f"STATE={summary['scientific_state']}"
)


if (
    summary[
        "scientific_state"
    ]
    !=
    "REAL_RS_COMPARATIVE_DECISION_BRIDGE_PASS"
):
    raise SystemExit(20)
