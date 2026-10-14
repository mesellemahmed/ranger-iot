#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

Z95 = 1.959963984540054
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260924

FOCAL_PROTOCOLS = (
    "ranger-static",
    "ranger-recovery",
    "ranger-adaptive",
    "ranger-adaptive-v2",
)

COMPARISONS = (
    ("ranger-adaptive-v2", "ranger-adaptive", "V2-V1"),
    ("ranger-adaptive-v2", "ranger-recovery", "V2-RECOVERY"),
    ("ranger-adaptive-v2", "ranger-static", "V2-STATIC"),
)

METRICS = (
    ("convergence_fraction", True),
    ("radio_transmissions", False),
    ("radio_bytes_sent", False),
    ("manager_radio_transmissions", False),
)


def stable_seed(label: str) -> int:
    digest = hashlib.sha256(f"{BOOTSTRAP_SEED}|{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def bootstrap_mean_ci(
    values: list[float],
    *,
    label: str,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> tuple[float, float]:
    if not values:
        raise ValueError("bootstrap sample must not be empty")
    if len(values) == 1:
        return values[0], values[0]

    rng = random.Random(stable_seed(label))
    n = len(values)
    means: list[float] = []

    for _ in range(resamples):
        means.append(statistics.fmean(values[rng.randrange(n)] for _ in range(n)))

    means.sort()
    lo = means[max(0, math.floor(0.025 * (resamples - 1)))]
    hi = means[min(resamples - 1, math.ceil(0.975 * (resamples - 1)))]
    return lo, hi


def wilson_interval(successes: int, total: int) -> tuple[float, float]:
    p = successes / total
    denominator = 1 + (Z95 * Z95) / total
    center = (p + (Z95 * Z95) / (2 * total)) / denominator
    half = Z95 * math.sqrt(p * (1 - p) / total + (Z95 * Z95) / (4 * total * total)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def numeric(row: dict[str, str], field: str) -> float:
    value = row.get(field, "")
    if value == "":
        raise ValueError(f"missing numeric field {field}")
    return float(value)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def protocol_loss_summary(
    rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, float], list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        if row["protocol"] in FOCAL_PROTOCOLS:
            groups[(row["protocol"], numeric(row, "packet_loss"))].append(row)

    output: list[dict[str, Any]] = []

    for protocol, loss in sorted(groups):
        group = groups[(protocol, loss)]
        completed = sum(row["completed"] == "True" for row in group)
        completion_low, completion_high = wilson_interval(completed, len(group))

        convergence = [numeric(row, "convergence_fraction") for row in group]
        radio_tx = [numeric(row, "radio_transmissions") for row in group]
        radio_bytes = [numeric(row, "radio_bytes_sent") for row in group]
        manager_tx = [numeric(row, "manager_radio_transmissions") for row in group]

        conv_lo, conv_hi = bootstrap_mean_ci(
            convergence,
            label=f"summary|{protocol}|{loss}|convergence",
        )
        tx_lo, tx_hi = bootstrap_mean_ci(
            radio_tx,
            label=f"summary|{protocol}|{loss}|radio_tx",
        )
        bytes_lo, bytes_hi = bootstrap_mean_ci(
            radio_bytes,
            label=f"summary|{protocol}|{loss}|radio_bytes",
        )
        gm_lo, gm_hi = bootstrap_mean_ci(
            manager_tx,
            label=f"summary|{protocol}|{loss}|gm_tx",
        )

        output.append(
            {
                "protocol": protocol,
                "packet_loss": loss,
                "runs": len(group),
                "completed": completed,
                "completion_rate": completed / len(group),
                "completion_ci95_low": completion_low,
                "completion_ci95_high": completion_high,
                "mean_convergence": statistics.fmean(convergence),
                "convergence_ci95_low": conv_lo,
                "convergence_ci95_high": conv_hi,
                "mean_radio_transmissions": statistics.fmean(radio_tx),
                "radio_transmissions_ci95_low": tx_lo,
                "radio_transmissions_ci95_high": tx_hi,
                "mean_radio_bytes_sent": statistics.fmean(radio_bytes),
                "radio_bytes_sent_ci95_low": bytes_lo,
                "radio_bytes_sent_ci95_high": bytes_hi,
                "mean_manager_radio_transmissions": statistics.fmean(manager_tx),
                "manager_radio_transmissions_ci95_low": gm_lo,
                "manager_radio_transmissions_ci95_high": gm_hi,
            }
        )

    return output


def paired_effects(
    rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    index: dict[
        tuple[str, int, float, int],
        dict[str, dict[str, str]],
    ] = defaultdict(dict)

    for row in rows:
        key = (
            row["topology"],
            int(row["member_count"]),
            numeric(row, "packet_loss"),
            int(row["seed"]),
        )
        index[key][row["protocol"]] = row

    losses = sorted({key[2] for key in index})
    output: list[dict[str, Any]] = []

    for left, right, label in COMPARISONS:
        for loss in losses:
            scenario_keys = [
                key
                for key, protocols in index.items()
                if key[2] == loss and left in protocols and right in protocols
            ]

            for metric, higher_is_better in METRICS:
                effects: list[float] = []

                for key in scenario_keys:
                    left_value = numeric(index[key][left], metric)
                    right_value = numeric(index[key][right], metric)
                    raw = left_value - right_value
                    effects.append(raw if higher_is_better else -raw)

                if not effects:
                    continue

                low, high = bootstrap_mean_ci(
                    effects,
                    label=f"pair|{label}|{loss}|{metric}",
                )

                output.append(
                    {
                        "comparison": label,
                        "left_protocol": left,
                        "right_protocol": right,
                        "packet_loss": loss,
                        "metric": metric,
                        "direction": (
                            "higher-is-better" if higher_is_better else "lower-is-better"
                        ),
                        "paired_samples": len(effects),
                        "benefit_mean": statistics.fmean(effects),
                        "benefit_ci95_low": low,
                        "benefit_ci95_high": high,
                        "better": sum(effect > 0 for effect in effects),
                        "tie": sum(effect == 0 for effect in effects),
                        "worse": sum(effect < 0 for effect in effects),
                    }
                )

    return output


def nack_suppression(
    rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    topologies = sorted({row["topology"] for row in rows})
    losses = sorted(
        {numeric(row, "packet_loss") for row in rows if numeric(row, "packet_loss") > 0}
    )

    for topology in topologies:
        for loss in losses:
            v1 = [
                row
                for row in rows
                if row["protocol"] == "ranger-adaptive"
                and row["topology"] == topology
                and numeric(row, "packet_loss") == loss
            ]
            v2 = [
                row
                for row in rows
                if row["protocol"] == "ranger-adaptive-v2"
                and row["topology"] == topology
                and numeric(row, "packet_loss") == loss
            ]

            if not v1 or not v2:
                continue

            v1_hops = statistics.fmean(numeric(row, "adaptive_nack_hop_attempts") for row in v1)
            v2_hops = statistics.fmean(numeric(row, "adaptive_nack_hop_attempts") for row in v2)
            forwarded = statistics.fmean(numeric(row, "adaptive_nack_forwarded") for row in v2)
            suppressed = statistics.fmean(numeric(row, "adaptive_nack_suppressed") for row in v2)

            reduction = 100.0 * (v1_hops - v2_hops) / v1_hops if v1_hops > 0 else 0.0

            output.append(
                {
                    "topology": topology,
                    "packet_loss": loss,
                    "v1_nack_hop_attempts": v1_hops,
                    "v2_nack_hop_attempts": v2_hops,
                    "reduction_percent": reduction,
                    "v2_forwarded": forwarded,
                    "v2_suppressed": suppressed,
                }
            )

    return output


def create_plots(
    output_dir: Path,
    summary: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
    nack: list[dict[str, Any]],
) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: CSV tables created, figures skipped")
        return []

    generated: list[str] = []

    fig, ax = plt.subplots()
    for protocol in FOCAL_PROTOCOLS:
        subset = sorted(
            [row for row in summary if row["protocol"] == protocol],
            key=lambda row: row["packet_loss"],
        )
        ax.plot(
            [100 * row["packet_loss"] for row in subset],
            [100 * row["completion_rate"] for row in subset],
            marker="o",
            label=protocol,
        )
    ax.set_xlabel("Packet loss (%)")
    ax.set_ylabel("Complete rekey runs (%)")
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    for ext in ("png", "pdf"):
        name = f"fig_completion_rate.{ext}"
        fig.savefig(output_dir / name, dpi=300)
        generated.append(name)
    plt.close(fig)

    fig, ax = plt.subplots()
    for protocol in FOCAL_PROTOCOLS:
        subset = sorted(
            [row for row in summary if row["protocol"] == protocol],
            key=lambda row: row["packet_loss"],
        )
        ax.plot(
            [100 * row["packet_loss"] for row in subset],
            [row["mean_convergence"] for row in subset],
            marker="o",
            label=protocol,
        )
    ax.set_xlabel("Packet loss (%)")
    ax.set_ylabel("Mean convergence fraction")
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    for ext in ("png", "pdf"):
        name = f"fig_mean_convergence.{ext}"
        fig.savefig(output_dir / name, dpi=300)
        generated.append(name)
    plt.close(fig)

    subset = sorted(
        [
            row
            for row in pairs
            if row["comparison"] == "V2-V1" and row["metric"] == "radio_transmissions"
        ],
        key=lambda row: row["packet_loss"],
    )
    x = [100 * row["packet_loss"] for row in subset]
    y = [row["benefit_mean"] for row in subset]
    lo = [row["benefit_ci95_low"] for row in subset]
    hi = [row["benefit_ci95_high"] for row in subset]

    fig, ax = plt.subplots()
    ax.plot(x, y, marker="o")
    ax.fill_between(x, lo, hi, alpha=0.2)
    ax.axhline(0, linewidth=1)
    ax.set_xlabel("Packet loss (%)")
    ax.set_ylabel("Radio transmissions saved by V2 vs V1")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        name = f"fig_v2_v1_radio_savings.{ext}"
        fig.savefig(output_dir / name, dpi=300)
        generated.append(name)
    plt.close(fig)

    fig, ax = plt.subplots()
    for topology in sorted({row["topology"] for row in nack}):
        subset = sorted(
            [row for row in nack if row["topology"] == topology],
            key=lambda row: row["packet_loss"],
        )
        ax.plot(
            [100 * row["packet_loss"] for row in subset],
            [row["reduction_percent"] for row in subset],
            marker="o",
            label=topology,
        )
    ax.set_xlabel("Packet loss (%)")
    ax.set_ylabel("NACK-hop reduction V2 vs V1 (%)")
    ax.set_ylim(bottom=0)
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    for ext in ("png", "pdf"):
        name = f"fig_nack_hop_reduction.{ext}"
        fig.savefig(output_dir / name, dpi=300)
        generated.append(name)
    plt.close(fig)

    subset = sorted(
        [
            row
            for row in pairs
            if row["comparison"] == "V2-RECOVERY" and row["metric"] == "convergence_fraction"
        ],
        key=lambda row: row["packet_loss"],
    )
    x = [100 * row["packet_loss"] for row in subset]
    y = [100 * row["benefit_mean"] for row in subset]
    lo = [100 * row["benefit_ci95_low"] for row in subset]
    hi = [100 * row["benefit_ci95_high"] for row in subset]

    fig, ax = plt.subplots()
    ax.plot(x, y, marker="o")
    ax.fill_between(x, lo, hi, alpha=0.2)
    ax.axhline(0, linewidth=1)
    ax.set_xlabel("Packet loss (%)")
    ax.set_ylabel("V2 - Recovery convergence (percentage points)")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        name = f"fig_v2_recovery_convergence_effect.{ext}"
        fig.savefig(output_dir / name, dpi=300)
        generated.append(name)
    plt.close(fig)

    return generated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = load_csv(args.aggregate)
    if not rows:
        raise SystemExit("aggregate contains no rows")

    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise SystemExit(f"output directory must be empty: {args.output}")

    found_protocols = {row["protocol"] for row in rows}
    missing = set(FOCAL_PROTOCOLS) - found_protocols
    if missing:
        raise SystemExit(f"confirmatory aggregate missing protocols: {sorted(missing)}")

    summary = protocol_loss_summary(rows)
    pairs = paired_effects(rows)
    nack = nack_suppression(rows)

    write_csv(
        args.output / "confirmatory_protocol_loss_summary.csv",
        summary,
    )
    write_csv(
        args.output / "confirmatory_paired_effects.csv",
        pairs,
    )
    write_csv(
        args.output / "confirmatory_nack_suppression.csv",
        nack,
    )

    figures = create_plots(args.output, summary, pairs, nack)

    manifest = {
        "schema_version": 1,
        "input": str(args.aggregate),
        "input_sha256": hashlib.sha256(args.aggregate.read_bytes()).hexdigest(),
        "input_rows": len(rows),
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "protocol_loss_rows": len(summary),
        "paired_effect_rows": len(pairs),
        "nack_suppression_rows": len(nack),
        "figures": figures,
    }

    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"input_rows={len(rows)}")
    print(f"protocol_loss_rows={len(summary)}")
    print(f"paired_effect_rows={len(pairs)}")
    print(f"nack_suppression_rows={len(nack)}")
    print(f"figures={len(figures)}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
