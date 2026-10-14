from __future__ import annotations

import csv
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


K = 3
N = 5

CODED_FRAGMENT_BYTES = 9

TX_VALUES = (
    0.50,
    0.30,
    0.20,
)

SEEDS = tuple(
    range(201, 211)
)

BOOTSTRAP_RESAMPLES = 20_000
BOOTSTRAP_SEED = 20261002


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(
            csv.DictReader(handle)
        )


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        raise ValueError(
            f"Cannot write empty CSV: {path}"
        )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(rows)


def load_result(
    root: Path,
    case_id: str,
) -> dict[str, Any]:
    path = (
        root
        / "cases"
        / case_id
        / "cooja-result.json"
    )

    if not path.exists():
        raise FileNotFoundError(path)

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def int_field(
    data: dict[str, Any],
    name: str,
    default: int = 0,
) -> int:
    value = data.get(
        name,
        default,
    )

    if value is None:
        return default

    return int(value)


def percentile(
    values: list[float],
    q: float,
) -> float:
    if not values:
        raise ValueError(
            "percentile on empty values"
        )

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (
        (len(ordered) - 1)
        * q
    )

    lower = int(position)
    upper = min(
        lower + 1,
        len(ordered) - 1,
    )

    fraction = (
        position - lower
    )

    return (
        ordered[lower]
        * (1.0 - fraction)
        + ordered[upper]
        * fraction
    )


def paired_bootstrap_ci(
    values: list[float],
    *,
    seed: int,
) -> tuple[float, float]:
    if not values:
        raise ValueError(
            "bootstrap on empty values"
        )

    rng = random.Random(seed)

    means: list[float] = []

    for _ in range(
        BOOTSTRAP_RESAMPLES
    ):
        sample = [
            values[
                rng.randrange(
                    len(values)
                )
            ]
            for _ in values
        ]

        means.append(
            statistics.mean(sample)
        )

    return (
        percentile(means, 0.025),
        percentile(means, 0.975),
    )


def case_key(
    tx: float,
    seed: int,
) -> tuple[float, int]:
    return (
        round(tx, 2),
        seed,
    )


def load_protocol(
    protocol: str,
    root: Path,
) -> dict[
    tuple[float, int],
    dict[str, Any],
]:
    aggregate = load_csv(
        root / "aggregate.csv"
    )

    selected: dict[
        tuple[float, int],
        dict[str, Any],
    ] = {}

    for row in aggregate:
        tx = round(
            float(
                row[
                    "target_success_ratio_tx"
                ]
            ),
            2,
        )

        seed = int(
            row["simulation_seed"]
        )

        if (
            tx not in TX_VALUES
            or seed not in SEEDS
        ):
            continue

        # 6F compares Static 3-of-5,
        # not the 3-of-3 calibration branch.
        if (
            protocol == "STATIC"
            and int(row["n"]) != N
        ):
            continue

        key = case_key(
            tx,
            seed,
        )

        if key in selected:
            raise ValueError(
                f"Duplicate {protocol} case "
                f"for {key}"
            )

        result = load_result(
            root,
            row["case_id"],
        )

        selected[key] = {
            "row": row,
            "result": result,
        }

    expected = {
        case_key(tx, seed)
        for tx in TX_VALUES
        for seed in SEEDS
    }

    observed = set(
        selected
    )

    if observed != expected:
        missing = sorted(
            expected - observed
        )

        extra = sorted(
            observed - expected
        )

        raise ValueError(
            f"{protocol} matrix mismatch. "
            f"missing={missing} "
            f"extra={extra}"
        )

    return selected


def build_cost_row(
    protocol: str,
    tx: float,
    seed: int,
    item: dict[str, Any],
) -> dict[str, Any]:
    row = item["row"]
    result = item["result"]

    registered = int(
        row["registered_count"]
    )

    reconstructed = int(
        row[
            "authorized_reconstructed_count"
        ]
    )

    complete = (
        row["outcome"]
        == "REKEY_COMPLETE"
    )

    if registered != 7:
        raise ValueError(
            f"{protocol} TX={tx} "
            f"seed={seed}: "
            f"registered_count={registered}"
        )

    if protocol in {
        "STATIC",
        "RECOVERY",
    }:
        initial_fragments_per_target = N

    elif protocol == "ADAPTIVE_V2":
        # Frozen Adaptive V2 initial-k
        # dissemination.
        initial_fragments_per_target = K

    else:
        raise ValueError(protocol)

    initial_send_count = (
        registered
        * initial_fragments_per_target
    )

    initial_bytes = (
        initial_send_count
        * CODED_FRAGMENT_BYTES
    )

    epoch_prime_bytes = 0
    recovery_request_bytes = 0
    recovery_fragment_bytes = 0
    adaptive_control_bytes = 0
    adaptive_parity_bytes = 0

    if protocol in {
        "RECOVERY",
        "ADAPTIVE_V2",
    }:
        epoch_prime_bytes = int_field(
            result,
            "recovery_epoch_prime_bytes",
        )

        recovery_request_bytes = int_field(
            result,
            "recovery_request_bytes",
        )

        recovery_fragment_bytes = int_field(
            result,
            "recovery_fragment_send_bytes",
        )

    if protocol == "ADAPTIVE_V2":
        adaptive_control_bytes = int_field(
            result,
            "adaptive_control_bytes",
        )

        adaptive_parity_bytes = int_field(
            result,
            "adaptive_parity_bytes",
        )

        adaptive_overhead = int_field(
            result,
            "adaptive_overhead_bytes",
        )

        if adaptive_overhead != (
            adaptive_control_bytes
            + adaptive_parity_bytes
        ):
            raise ValueError(
                f"Adaptive overhead mismatch "
                f"TX={tx} seed={seed}: "
                f"{adaptive_overhead} != "
                f"{adaptive_control_bytes} + "
                f"{adaptive_parity_bytes}"
            )

    recovery_side_bytes = (
        epoch_prime_bytes
        + recovery_request_bytes
        + recovery_fragment_bytes
    )

    adaptive_specific_bytes = (
        adaptive_control_bytes
        + adaptive_parity_bytes
    )

    total_bytes = (
        initial_bytes
        + recovery_side_bytes
        + adaptive_specific_bytes
    )

    if total_bytes <= 0:
        raise ValueError(
            "Non-positive application cost"
        )

    bytes_per_reconstructed = (
        total_bytes / reconstructed
        if reconstructed > 0
        else ""
    )

    return {
        "protocol": protocol,
        "tx": tx,
        "seed": seed,
        "case_id": row["case_id"],
        "outcome": row["outcome"],
        "complete": complete,
        "authorized_reconstructed":
            reconstructed,
        "registered_count":
            registered,
        "initial_fragments_per_target":
            initial_fragments_per_target,
        "initial_coded_send_count":
            initial_send_count,
        "initial_coded_bytes":
            initial_bytes,
        "epoch_prime_bytes":
            epoch_prime_bytes,
        "recovery_request_bytes":
            recovery_request_bytes,
        "recovery_fragment_bytes":
            recovery_fragment_bytes,
        "adaptive_control_bytes":
            adaptive_control_bytes,
        "adaptive_parity_bytes":
            adaptive_parity_bytes,
        "recovery_side_bytes":
            recovery_side_bytes,
        "adaptive_specific_bytes":
            adaptive_specific_bytes,
        "total_rekey_tx_payload_bytes":
            total_bytes,
        "bytes_per_reconstructed_member":
            bytes_per_reconstructed,
    }


def summarize_regimes(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[
        tuple[str, float],
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        grouped[
            (
                str(row["protocol"]),
                float(row["tx"]),
            )
        ].append(row)

    output: list[
        dict[str, Any]
    ] = []

    order = {
        "STATIC": 0,
        "RECOVERY": 1,
        "ADAPTIVE_V2": 2,
    }

    for (
        protocol,
        tx,
    ), group in sorted(
        grouped.items(),
        key=lambda item: (
            item[0][1],
            order[item[0][0]],
        ),
        reverse=False,
    ):
        costs = [
            int(
                row[
                    "total_rekey_tx_payload_bytes"
                ]
            )
            for row in group
        ]

        recon = [
            int(
                row[
                    "authorized_reconstructed"
                ]
            )
            for row in group
        ]

        completion = [
            bool(row["complete"])
            for row in group
        ]

        efficiency = [
            float(
                row[
                    "bytes_per_reconstructed_member"
                ]
            )
            for row in group
            if row[
                "bytes_per_reconstructed_member"
            ] != ""
        ]

        output.append(
            {
                "protocol": protocol,
                "tx": tx,
                "runs": len(group),
                "complete": sum(completion),
                "completion_rate":
                    sum(completion)
                    / len(group),
                "mean_reconstructed":
                    statistics.mean(recon),
                "median_reconstructed":
                    statistics.median(recon),
                "mean_total_rekey_tx_payload_bytes":
                    statistics.mean(costs),
                "median_total_rekey_tx_payload_bytes":
                    statistics.median(costs),
                "min_total_rekey_tx_payload_bytes":
                    min(costs),
                "max_total_rekey_tx_payload_bytes":
                    max(costs),
                "mean_bytes_per_reconstructed_member":
                    statistics.mean(efficiency),
            }
        )

    return output


def paired_cost_rows(
    all_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key = {
        (
            str(row["protocol"]),
            float(row["tx"]),
            int(row["seed"]),
        ): row
        for row in all_rows
    }

    comparisons = (
        ("RECOVERY", "STATIC"),
        ("ADAPTIVE_V2", "STATIC"),
        ("ADAPTIVE_V2", "RECOVERY"),
    )

    output: list[
        dict[str, Any]
    ] = []

    ci_seed = BOOTSTRAP_SEED

    for tx in TX_VALUES:
        for left, right in comparisons:
            delta_bytes: list[float] = []
            delta_recon: list[float] = []

            lower_cost = 0
            equal_cost = 0
            higher_cost = 0

            gains: list[
                tuple[float, float]
            ] = []

            for seed in SEEDS:
                lhs = by_key[
                    (left, tx, seed)
                ]

                rhs = by_key[
                    (right, tx, seed)
                ]

                db = (
                    float(
                        lhs[
                            "total_rekey_tx_payload_bytes"
                        ]
                    )
                    - float(
                        rhs[
                            "total_rekey_tx_payload_bytes"
                        ]
                    )
                )

                dr = (
                    float(
                        lhs[
                            "authorized_reconstructed"
                        ]
                    )
                    - float(
                        rhs[
                            "authorized_reconstructed"
                        ]
                    )
                )

                delta_bytes.append(db)
                delta_recon.append(dr)

                if db < 0:
                    lower_cost += 1
                elif db > 0:
                    higher_cost += 1
                else:
                    equal_cost += 1

                if dr > 0:
                    gains.append(
                        (db, dr)
                    )

            low, high = paired_bootstrap_ci(
                delta_bytes,
                seed=ci_seed,
            )

            ci_seed += 1

            incremental_cost_per_gain = ""

            if gains:
                total_delta_bytes = sum(
                    value[0]
                    for value in gains
                )

                total_delta_recon = sum(
                    value[1]
                    for value in gains
                )

                incremental_cost_per_gain = (
                    total_delta_bytes
                    / total_delta_recon
                )

            output.append(
                {
                    "tx": tx,
                    "left_protocol": left,
                    "right_protocol": right,
                    "pairs": len(SEEDS),
                    "lower_cost": lower_cost,
                    "equal_cost": equal_cost,
                    "higher_cost": higher_cost,
                    "mean_delta_bytes":
                        statistics.mean(
                            delta_bytes
                        ),
                    "median_delta_bytes":
                        statistics.median(
                            delta_bytes
                        ),
                    "bootstrap95_low_delta_bytes":
                        low,
                    "bootstrap95_high_delta_bytes":
                        high,
                    "mean_delta_reconstructed":
                        statistics.mean(
                            delta_recon
                        ),
                    "paired_seeds_with_reconstruction_gain":
                        len(gains),
                    "incremental_bytes_per_gained_reconstruction":
                        incremental_cost_per_gain,
                }
            )

    return output


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit(
            "usage: analysis.py "
            "STATIC RECOVERY ADAPTIVE OUT"
        )

    static_root = Path(
        sys.argv[1]
    )

    recovery_root = Path(
        sys.argv[2]
    )

    adaptive_root = Path(
        sys.argv[3]
    )

    out = Path(
        sys.argv[4]
    )

    out.mkdir(
        parents=True,
        exist_ok=True,
    )

    datasets = {
        "STATIC":
            load_protocol(
                "STATIC",
                static_root,
            ),

        "RECOVERY":
            load_protocol(
                "RECOVERY",
                recovery_root,
            ),

        "ADAPTIVE_V2":
            load_protocol(
                "ADAPTIVE_V2",
                adaptive_root,
            ),
    }

    rows: list[
        dict[str, Any]
    ] = []

    for protocol, dataset in datasets.items():
        for tx in TX_VALUES:
            for seed in SEEDS:
                rows.append(
                    build_cost_row(
                        protocol,
                        tx,
                        seed,
                        dataset[
                            case_key(
                                tx,
                                seed,
                            )
                        ],
                    )
                )

    if len(rows) != 90:
        raise ValueError(
            f"Expected 90 cost rows, "
            f"got {len(rows)}"
        )

    regime_rows = summarize_regimes(
        rows
    )

    paired_rows = paired_cost_rows(
        rows
    )

    write_csv(
        out / "case-costs.csv",
        rows,
    )

    write_csv(
        out / "cost-regime-summary.csv",
        regime_rows,
    )

    write_csv(
        out / "paired-cost-deltas.csv",
        paired_rows,
    )

    summary = {
        "schema_version": 1,

        "analysis":
            "RANGER-STEP6F2-APPLICATION-COST",

        "accounting_scope":
            (
                "Application-layer rekey TX payload "
                "bytes attempted by the protocol. "
                "Bootstrap registration, report "
                "messages, MAC headers, routing "
                "control traffic, retransmissions, "
                "and radio-energy costs are excluded."
            ),

        "static_baseline":
            "3-of-5 only",

        "coding": {
            "k": K,
            "n": N,
            "coded_fragment_bytes":
                CODED_FRAGMENT_BYTES,
        },

        "adaptive_initial_policy":
            (
                "initial-k dissemination "
                "followed by adaptive parity"
            ),

        "recovery_cost_components": [
            "epoch prime",
            "recovery requests",
            "recovery fragments",
        ],

        "adaptive_cost_components": [
            "initial-k coded fragments",
            "epoch prime",
            "adaptive control",
            "adaptive parity",
            "recovery requests",
            "recovery fragments",
        ],

        "tx_values":
            list(TX_VALUES),

        "seeds":
            list(SEEDS),

        "rows":
            len(rows),

        "bootstrap_resamples":
            BOOTSTRAP_RESAMPLES,

        "bootstrap_seed":
            BOOTSTRAP_SEED,

        "guardrails": [
            (
                "These are application-level "
                "payload-byte costs, not radio "
                "energy measurements."
            ),
            (
                "A lower byte count is not "
                "interpreted independently of "
                "reconstruction and completion."
            ),
            (
                "Static uses the same 3-of-5 "
                "baseline as the 6F.1 "
                "three-protocol comparison."
            ),
            (
                "Paired results use identical "
                "simulation-seed identifiers but "
                "do not imply identical packet-level "
                "loss realizations across protocols."
            ),
        ],
    }

    (
        out
        / "cost-analysis-summary.json"
    ).write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print(
        "===== APPLICATION COST REGIMES ====="
    )

    print(
        "PROTO       TX   COMPLETE "
        "MEAN_RECON MEAN_BYTES MEDIAN_BYTES "
        "BYTES/RECON"
    )

    for row in regime_rows:
        print(
            f"{row['protocol']:11s} "
            f"{row['tx']:.2f} "
            f"{row['complete']:2d}/10    "
            f"{row['mean_reconstructed']:.3f}      "
            f"{row['mean_total_rekey_tx_payload_bytes']:.1f}      "
            f"{row['median_total_rekey_tx_payload_bytes']:.1f}        "
            f"{row['mean_bytes_per_reconstructed_member']:.2f}"
        )

    print()
    print(
        "===== PAIRED COST DELTAS ====="
    )

    for row in paired_rows:
        print(
            f"TX={row['tx']:.2f} "
            f"{row['left_protocol']} vs "
            f"{row['right_protocol']} "
            f"L/E/H="
            f"{row['lower_cost']}/"
            f"{row['equal_cost']}/"
            f"{row['higher_cost']} "
            f"deltaB="
            f"{row['mean_delta_bytes']:+.1f} "
            f"CI=["
            f"{row['bootstrap95_low_delta_bytes']:+.1f},"
            f"{row['bootstrap95_high_delta_bytes']:+.1f}] "
            f"deltaR="
            f"{row['mean_delta_reconstructed']:+.2f}"
        )

    print()
    print(
        "STEP 6F.2 APPLICATION COST: PASS"
    )


if __name__ == "__main__":
    main()
