from __future__ import annotations

import csv
import json
import math
import random
import statistics
import sys
from pathlib import Path


TX_VALUES = (0.50, 0.30, 0.20)
SEEDS = tuple(range(201, 211))

PROTOCOLS = (
    "STATIC",
    "RECOVERY",
    "ADAPTIVE_V2",
)

PAIRS = (
    ("RECOVERY", "STATIC"),
    ("ADAPTIVE_V2", "STATIC"),
    ("ADAPTIVE_V2", "RECOVERY"),
)

BOOTSTRAP_RESAMPLES = 20000
BOOTSTRAP_SEED = 20261001


def load_rows(
    root: Path,
    protocol: str,
) -> dict[tuple[float, int], dict[str, str]]:

    path = root / "aggregate.csv"

    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(
            csv.DictReader(handle)
        )

    selected = {}

    for row in rows:
        n = int(row["n"])

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
            n == 5
            and tx in TX_VALUES
            and seed in SEEDS
        ):
            key = (tx, seed)

            if key in selected:
                raise RuntimeError(
                    f"{protocol}: duplicate {key}"
                )

            selected[key] = row

    expected = {
        (tx, seed)
        for tx in TX_VALUES
        for seed in SEEDS
    }

    observed = set(selected)

    if observed != expected:
        missing = sorted(
            expected - observed
        )

        extra = sorted(
            observed - expected
        )

        raise RuntimeError(
            f"{protocol}: matrix mismatch "
            f"missing={missing} extra={extra}"
        )

    return selected


def exact_two_sided_binomial(
    positive: int,
    negative: int,
) -> float:

    n = positive + negative

    if n == 0:
        return 1.0

    k = min(
        positive,
        negative,
    )

    probability = (
        2.0
        * sum(
            math.comb(n, i)
            for i in range(k + 1)
        )
        / (2**n)
    )

    return min(
        1.0,
        probability,
    )


def bootstrap_mean_ci(
    values: list[int],
    seed_offset: int,
) -> tuple[float, float]:

    if not values:
        return (0.0, 0.0)

    rng = random.Random(
        BOOTSTRAP_SEED
        + seed_offset
    )

    n = len(values)

    means = []

    for _ in range(
        BOOTSTRAP_RESAMPLES
    ):
        sample = [
            values[
                rng.randrange(n)
            ]
            for _ in range(n)
        ]

        means.append(
            statistics.mean(sample)
        )

    means.sort()

    low_index = int(
        0.025
        * (
            len(means) - 1
        )
    )

    high_index = int(
        0.975
        * (
            len(means) - 1
        )
    )

    return (
        means[low_index],
        means[high_index],
    )


def holm_adjust(
    values: list[float],
) -> list[float]:

    indexed = sorted(
        enumerate(values),
        key=lambda item:
            item[1],
    )

    m = len(values)

    adjusted = [1.0] * m

    previous = 0.0

    for rank, (
        original_index,
        p_value,
    ) in enumerate(
        indexed,
        start=1,
    ):
        candidate = min(
            1.0,
            (
                m - rank + 1
            )
            * p_value,
        )

        candidate = max(
            candidate,
            previous,
        )

        adjusted[
            original_index
        ] = candidate

        previous = candidate

    return adjusted


def write_csv(
    path: Path,
    rows: list[dict[str, object]],
) -> None:

    if not rows:
        raise RuntimeError(
            f"No rows for {path}"
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


def reconstructed(
    row: dict[str, str],
) -> int:
    return int(
        row[
            "authorized_reconstructed_count"
        ]
    )


def completed(
    row: dict[str, str],
) -> int:
    return int(
        row["outcome"]
        == "REKEY_COMPLETE"
    )


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

    data = {
        "STATIC":
            load_rows(
                static_root,
                "STATIC",
            ),

        "RECOVERY":
            load_rows(
                recovery_root,
                "RECOVERY",
            ),

        "ADAPTIVE_V2":
            load_rows(
                adaptive_root,
                "ADAPTIVE_V2",
            ),
    }

    regime_rows = []

    for protocol in PROTOCOLS:
        for tx in TX_VALUES:
            values = [
                reconstructed(
                    data[protocol][
                        (tx, seed)
                    ]
                )
                for seed in SEEDS
            ]

            complete = sum(
                completed(
                    data[protocol][
                        (tx, seed)
                    ]
                )
                for seed in SEEDS
            )

            regime_rows.append(
                {
                    "protocol":
                        protocol,

                    "tx":
                        tx,

                    "runs":
                        len(SEEDS),

                    "complete":
                        complete,

                    "completion_rate":
                        complete
                        / len(SEEDS),

                    "mean_reconstructed":
                        statistics.mean(
                            values
                        ),

                    "median_reconstructed":
                        statistics.median(
                            values
                        ),

                    "min_reconstructed":
                        min(values),

                    "max_reconstructed":
                        max(values),
                }
            )

    reconstruction_rows = []
    completion_rows = []

    seed_offset = 0

    for tx in TX_VALUES:
        for left, right in PAIRS:

            left_recon = [
                reconstructed(
                    data[left][
                        (tx, seed)
                    ]
                )
                for seed in SEEDS
            ]

            right_recon = [
                reconstructed(
                    data[right][
                        (tx, seed)
                    ]
                )
                for seed in SEEDS
            ]

            deltas = [
                left_value
                - right_value
                for (
                    left_value,
                    right_value,
                ) in zip(
                    left_recon,
                    right_recon,
                )
            ]

            better = sum(
                delta > 0
                for delta in deltas
            )

            equal = sum(
                delta == 0
                for delta in deltas
            )

            worse = sum(
                delta < 0
                for delta in deltas
            )

            low, high = (
                bootstrap_mean_ci(
                    deltas,
                    seed_offset,
                )
            )

            seed_offset += 1

            p_value = (
                exact_two_sided_binomial(
                    better,
                    worse,
                )
            )

            reconstruction_rows.append(
                {
                    "tx":
                        tx,

                    "left_protocol":
                        left,

                    "right_protocol":
                        right,

                    "pairs":
                        len(SEEDS),

                    "better":
                        better,

                    "equal":
                        equal,

                    "worse":
                        worse,

                    "mean_delta_reconstructed":
                        statistics.mean(
                            deltas
                        ),

                    "median_delta_reconstructed":
                        statistics.median(
                            deltas
                        ),

                    "bootstrap95_low":
                        low,

                    "bootstrap95_high":
                        high,

                    "exact_sign_p":
                        p_value,

                    "exact_sign_p_holm":
                        1.0,
                }
            )

            left_completion = [
                completed(
                    data[left][
                        (tx, seed)
                    ]
                )
                for seed in SEEDS
            ]

            right_completion = [
                completed(
                    data[right][
                        (tx, seed)
                    ]
                )
                for seed in SEEDS
            ]

            left_only = sum(
                a == 1 and b == 0
                for a, b
                in zip(
                    left_completion,
                    right_completion,
                )
            )

            right_only = sum(
                a == 0 and b == 1
                for a, b
                in zip(
                    left_completion,
                    right_completion,
                )
            )

            both_complete = sum(
                a == 1 and b == 1
                for a, b
                in zip(
                    left_completion,
                    right_completion,
                )
            )

            neither_complete = sum(
                a == 0 and b == 0
                for a, b
                in zip(
                    left_completion,
                    right_completion,
                )
            )

            completion_rows.append(
                {
                    "tx":
                        tx,

                    "left_protocol":
                        left,

                    "right_protocol":
                        right,

                    "pairs":
                        len(SEEDS),

                    "left_only_complete":
                        left_only,

                    "right_only_complete":
                        right_only,

                    "both_complete":
                        both_complete,

                    "neither_complete":
                        neither_complete,

                    "completion_rate_delta":
                        (
                            sum(
                                left_completion
                            )
                            - sum(
                                right_completion
                            )
                        )
                        / len(SEEDS),

                    "exact_mcnemar_p":
                        exact_two_sided_binomial(
                            left_only,
                            right_only,
                        ),

                    "exact_mcnemar_p_holm":
                        1.0,
                }
            )

    recon_adjusted = holm_adjust(
        [
            float(
                row[
                    "exact_sign_p"
                ]
            )
            for row
            in reconstruction_rows
        ]
    )

    for row, value in zip(
        reconstruction_rows,
        recon_adjusted,
    ):
        row[
            "exact_sign_p_holm"
        ] = value

    completion_adjusted = holm_adjust(
        [
            float(
                row[
                    "exact_mcnemar_p"
                ]
            )
            for row
            in completion_rows
        ]
    )

    for row, value in zip(
        completion_rows,
        completion_adjusted,
    ):
        row[
            "exact_mcnemar_p_holm"
        ] = value

    write_csv(
        out / "regime-summary.csv",
        regime_rows,
    )

    write_csv(
        out
        / "paired-reconstruction-stats.csv",
        reconstruction_rows,
    )

    write_csv(
        out
        / "paired-completion-stats.csv",
        completion_rows,
    )

    summary = {
        "schema_version": 1,

        "analysis":
            "RANGER-THREE-PROTOCOL-PAIRED-STATISTICS",

        "source_roots": {
            "static":
                str(static_root),

            "recovery":
                str(recovery_root),

            "adaptive_v2":
                str(adaptive_root),
        },

        "tx_values":
            list(TX_VALUES),

        "seeds":
            list(SEEDS),

        "pairs_per_tx":
            len(SEEDS),

        "bootstrap_resamples":
            BOOTSTRAP_RESAMPLES,

        "bootstrap_seed":
            BOOTSTRAP_SEED,

        "interpretation_guardrails": [
            (
                "The analysis is paired by "
                "simulation seed."
            ),
            (
                "n=10 per TX level gives "
                "limited inferential precision."
            ),
            (
                "No universal dominance is "
                "assumed across reliability "
                "regimes."
            ),
            (
                "Bootstrap intervals describe "
                "the observed paired-delta "
                "distribution and do not replace "
                "independent replication."
            ),
        ],
    }

    (
        out
        / "analysis-summary.json"
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
        "===== REGIME SUMMARY ====="
    )

    print(
        "PROTO       TX   COMPLETE "
        "MEAN_RECON MEDIAN"
    )

    for row in regime_rows:
        print(
            f"{row['protocol']:11s} "
            f"{row['tx']:.2f} "
            f"{row['complete']:2d}/10    "
            f"{row['mean_reconstructed']:.3f}      "
            f"{row['median_reconstructed']:.1f}"
        )

    print()
    print(
        "===== PAIRED RECONSTRUCTION ====="
    )

    for row in reconstruction_rows:
        print(
            f"TX={row['tx']:.2f} "
            f"{row['left_protocol']} vs "
            f"{row['right_protocol']} "
            f"B/E/W="
            f"{row['better']}/"
            f"{row['equal']}/"
            f"{row['worse']} "
            f"delta="
            f"{row['mean_delta_reconstructed']:+.3f} "
            f"CI=["
            f"{row['bootstrap95_low']:+.3f},"
            f"{row['bootstrap95_high']:+.3f}] "
            f"p={row['exact_sign_p']:.5f} "
            f"Holm="
            f"{row['exact_sign_p_holm']:.5f}"
        )

    print()
    print(
        "===== PAIRED COMPLETION ====="
    )

    for row in completion_rows:
        print(
            f"TX={row['tx']:.2f} "
            f"{row['left_protocol']} vs "
            f"{row['right_protocol']} "
            f"Lonly/Ronly="
            f"{row['left_only_complete']}/"
            f"{row['right_only_complete']} "
            f"delta_rate="
            f"{row['completion_rate_delta']:+.3f} "
            f"p="
            f"{row['exact_mcnemar_p']:.5f} "
            f"Holm="
            f"{row['exact_mcnemar_p_holm']:.5f}"
        )

    print()
    print(
        "THREE-PROTOCOL STATISTICS: PASS"
    )


if __name__ == "__main__":
    main()
