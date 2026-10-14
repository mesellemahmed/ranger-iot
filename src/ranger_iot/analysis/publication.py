from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

Z_95 = 1.959963984540054
DEFAULT_BOOTSTRAP_RESAMPLES = 2000
DEFAULT_BOOTSTRAP_SEED = 20260923

HIGHER_IS_BETTER = {
    "convergence_fraction": True,
    "radio_transmissions": False,
    "radio_bytes_sent": False,
    "manager_radio_transmissions": False,
    "t100_us": False,
}
COMPARATORS = (
    "ranger-recovery",
    "ranger-static",
    "lkh-flood",
    "lkh-unicast",
    "skdc",
)

GROUP_FIELDS = (
    "protocol",
    "topology",
    "member_count",
    "packet_loss",
    "runs",
    "completed",
    "completion_rate",
    "completion_ci95_low",
    "completion_ci95_high",
    "mean_convergence",
    "convergence_ci95_low",
    "convergence_ci95_high",
    "median_convergence",
    "mean_radio_transmissions",
    "radio_transmissions_ci95_low",
    "radio_transmissions_ci95_high",
    "median_radio_transmissions",
    "mean_radio_bytes_sent",
    "radio_bytes_sent_ci95_low",
    "radio_bytes_sent_ci95_high",
    "mean_manager_radio_transmissions",
    "manager_radio_transmissions_ci95_low",
    "manager_radio_transmissions_ci95_high",
    "completed_t100_samples",
    "mean_t100_us_completed",
    "t100_us_completed_ci95_low",
    "t100_us_completed_ci95_high",
)

PAIR_FIELDS = (
    "adaptive_protocol",
    "comparator",
    "topology",
    "member_count",
    "packet_loss",
    "metric",
    "direction",
    "paired_samples",
    "adaptive_mean",
    "comparator_mean",
    "mean_delta_adaptive_minus_comparator",
    "benefit_delta_mean",
    "benefit_ci95_low",
    "benefit_ci95_high",
    "adaptive_better_count",
    "tie_count",
    "adaptive_worse_count",
    "adaptive_win_rate_excluding_ties",
)


def _float(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    if value == "":
        raise ValueError(f"missing required numeric field: {key}")
    return float(value)


def _optional_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key, "")
    if value in ("", None):
        return None
    return float(value)


def _int(row: dict[str, str], key: str) -> int:
    value = row.get(key, "")
    if value == "":
        raise ValueError(f"missing required integer field: {key}")
    return int(value)


def _bool(row: dict[str, str], key: str) -> bool:
    value = row.get(key, "")
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"invalid boolean field {key}: {value!r}")


def wilson_interval(successes: int, total: int, z: float = Z_95) -> tuple[float, float]:
    if total <= 0:
        raise ValueError("total must be positive")
    if successes < 0 or successes > total:
        raise ValueError("successes must be in [0, total]")

    p = successes / total
    denominator = 1.0 + (z * z) / total
    center = (p + (z * z) / (2.0 * total)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / total + (z * z) / (4.0 * total * total)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def _stable_seed(base_seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def bootstrap_mean_ci(
    values: Iterable[float],
    *,
    resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
    label: str = "",
) -> tuple[float, float]:
    sample = tuple(float(value) for value in values)
    if not sample:
        raise ValueError("bootstrap sample must not be empty")
    if resamples <= 0:
        raise ValueError("resamples must be positive")
    if len(sample) == 1:
        return sample[0], sample[0]

    rng = random.Random(_stable_seed(seed, label))
    n = len(sample)
    means = [statistics.fmean(sample[rng.randrange(n)] for _ in range(n)) for _ in range(resamples)]
    means.sort()
    low_index = max(0, math.floor(0.025 * (resamples - 1)))
    high_index = min(resamples - 1, math.ceil(0.975 * (resamples - 1)))
    return means[low_index], means[high_index]


def _mean_ci(
    values: list[float], *, resamples: int, seed: int, label: str
) -> tuple[float, float, float]:
    mean = statistics.fmean(values)
    low, high = bootstrap_mean_ci(values, resamples=resamples, seed=seed, label=label)
    return mean, low, high


def _canon(value: float | int | None) -> float | int | str:
    if value is None:
        return ""
    if isinstance(value, int):
        return value
    return round(value, 9) if math.isfinite(value) else ""


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _group_summary(
    rows: list[dict[str, str]], *, resamples: int, seed: int
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int, float], list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        key = (
            row["protocol"],
            row["topology"],
            _int(row, "member_count"),
            _float(row, "packet_loss"),
        )
        groups[key].append(row)

    output: list[dict[str, Any]] = []
    for key in sorted(groups):
        protocol, topology, member_count, packet_loss = key
        group = groups[key]
        runs = len(group)
        completed = sum(_bool(row, "completed") for row in group)
        completion_low, completion_high = wilson_interval(completed, runs)

        convergence = [_float(row, "convergence_fraction") for row in group]
        radio_tx = [_float(row, "radio_transmissions") for row in group]
        radio_bytes = [_float(row, "radio_bytes_sent") for row in group]
        manager_radio = [_float(row, "manager_radio_transmissions") for row in group]
        t100 = [
            value
            for row in group
            if _bool(row, "completed")
            for value in [_optional_float(row, "t100_us")]
            if value is not None
        ]

        label = f"{protocol}|{topology}|{member_count}|{packet_loss}"
        conv_mean, conv_low, conv_high = _mean_ci(
            convergence,
            resamples=resamples,
            seed=seed,
            label=f"{label}|convergence",
        )
        tx_mean, tx_low, tx_high = _mean_ci(
            radio_tx,
            resamples=resamples,
            seed=seed,
            label=f"{label}|radio_tx",
        )
        bytes_mean, bytes_low, bytes_high = _mean_ci(
            radio_bytes,
            resamples=resamples,
            seed=seed,
            label=f"{label}|radio_bytes",
        )
        manager_mean, manager_low, manager_high = _mean_ci(
            manager_radio,
            resamples=resamples,
            seed=seed,
            label=f"{label}|manager_radio",
        )

        t100_mean: float | None
        t100_low: float | None
        t100_high: float | None

        if t100:
            t100_mean, t100_low, t100_high = _mean_ci(
                t100,
                resamples=resamples,
                seed=seed,
                label=f"{label}|t100",
            )
        else:
            t100_mean = None
            t100_low = None
            t100_high = None

        output.append(
            {
                "protocol": protocol,
                "topology": topology,
                "member_count": member_count,
                "packet_loss": packet_loss,
                "runs": runs,
                "completed": completed,
                "completion_rate": _canon(completed / runs),
                "completion_ci95_low": _canon(completion_low),
                "completion_ci95_high": _canon(completion_high),
                "mean_convergence": _canon(conv_mean),
                "convergence_ci95_low": _canon(conv_low),
                "convergence_ci95_high": _canon(conv_high),
                "median_convergence": _canon(statistics.median(convergence)),
                "mean_radio_transmissions": _canon(tx_mean),
                "radio_transmissions_ci95_low": _canon(tx_low),
                "radio_transmissions_ci95_high": _canon(tx_high),
                "median_radio_transmissions": _canon(statistics.median(radio_tx)),
                "mean_radio_bytes_sent": _canon(bytes_mean),
                "radio_bytes_sent_ci95_low": _canon(bytes_low),
                "radio_bytes_sent_ci95_high": _canon(bytes_high),
                "mean_manager_radio_transmissions": _canon(manager_mean),
                "manager_radio_transmissions_ci95_low": _canon(manager_low),
                "manager_radio_transmissions_ci95_high": _canon(manager_high),
                "completed_t100_samples": len(t100),
                "mean_t100_us_completed": _canon(t100_mean),
                "t100_us_completed_ci95_low": _canon(t100_low),
                "t100_us_completed_ci95_high": _canon(t100_high),
            }
        )
    return output


def _paired_effects(
    rows: list[dict[str, str]], *, resamples: int, seed: int
) -> list[dict[str, Any]]:
    indexed: dict[tuple[str, int, float, int], dict[str, dict[str, str]]] = defaultdict(dict)

    for row in rows:
        key = (
            row["topology"],
            _int(row, "member_count"),
            _float(row, "packet_loss"),
            _int(row, "seed"),
        )
        indexed[key][row["protocol"]] = row

    scenarios = sorted({key[:3] for key in indexed})
    adaptive_name = "ranger-adaptive"
    output: list[dict[str, Any]] = []

    for topology, member_count, packet_loss in scenarios:
        keys = sorted(key for key in indexed if key[:3] == (topology, member_count, packet_loss))

        for comparator in COMPARATORS:
            for metric, higher_is_better in HIGHER_IS_BETTER.items():
                adaptive_values: list[float] = []
                comparator_values: list[float] = []

                for key in keys:
                    protocols = indexed[key]
                    adaptive = protocols.get(adaptive_name)
                    baseline = protocols.get(comparator)
                    if adaptive is None or baseline is None:
                        continue

                    adaptive_value = _optional_float(adaptive, metric)
                    baseline_value = _optional_float(baseline, metric)
                    if adaptive_value is None or baseline_value is None:
                        continue

                    adaptive_values.append(adaptive_value)
                    comparator_values.append(baseline_value)

                if not adaptive_values:
                    continue

                raw_deltas = [
                    a - b for a, b in zip(adaptive_values, comparator_values, strict=True)
                ]
                benefit = [delta if higher_is_better else -delta for delta in raw_deltas]
                low, high = bootstrap_mean_ci(
                    benefit,
                    resamples=resamples,
                    seed=seed,
                    label=(f"{comparator}|{topology}|{member_count}|{packet_loss}|{metric}"),
                )

                better = sum(delta > 0 for delta in benefit)
                ties = sum(delta == 0 for delta in benefit)
                worse = sum(delta < 0 for delta in benefit)
                non_ties = better + worse
                win_rate = better / non_ties if non_ties else None

                output.append(
                    {
                        "adaptive_protocol": adaptive_name,
                        "comparator": comparator,
                        "topology": topology,
                        "member_count": member_count,
                        "packet_loss": packet_loss,
                        "metric": metric,
                        "direction": "higher" if higher_is_better else "lower",
                        "paired_samples": len(adaptive_values),
                        "adaptive_mean": _canon(statistics.fmean(adaptive_values)),
                        "comparator_mean": _canon(statistics.fmean(comparator_values)),
                        "mean_delta_adaptive_minus_comparator": _canon(
                            statistics.fmean(raw_deltas)
                        ),
                        "benefit_delta_mean": _canon(statistics.fmean(benefit)),
                        "benefit_ci95_low": _canon(low),
                        "benefit_ci95_high": _canon(high),
                        "adaptive_better_count": better,
                        "tie_count": ties,
                        "adaptive_worse_count": worse,
                        "adaptive_win_rate_excluding_ties": _canon(win_rate),
                    }
                )

    return output


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze_campaign(
    aggregate_path: Path,
    output_dir: Path,
    *,
    bootstrap_resamples: int = DEFAULT_BOOTSTRAP_RESAMPLES,
    bootstrap_seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> dict[str, Any]:
    if bootstrap_resamples <= 0:
        raise ValueError("bootstrap_resamples must be positive")

    with aggregate_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError("aggregate CSV contains no data rows")

    required = {
        "protocol",
        "topology",
        "member_count",
        "packet_loss",
        "seed",
        "completed",
        "convergence_fraction",
        "radio_transmissions",
        "radio_bytes_sent",
        "manager_radio_transmissions",
        "t100_us",
    }
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"aggregate CSV is missing required fields: {sorted(missing)}")

    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError(f"analysis output directory must be empty: {output_dir}")

    groups = _group_summary(rows, resamples=bootstrap_resamples, seed=bootstrap_seed)
    pairs = _paired_effects(rows, resamples=bootstrap_resamples, seed=bootstrap_seed)

    _write_csv(output_dir / "group_summary.csv", GROUP_FIELDS, groups)
    _write_csv(output_dir / "paired_effects.csv", PAIR_FIELDS, pairs)

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "input": str(aggregate_path),
        "input_sha256": _sha256(aggregate_path),
        "input_rows": len(rows),
        "bootstrap_resamples": bootstrap_resamples,
        "bootstrap_seed": bootstrap_seed,
        "group_summary_rows": len(groups),
        "paired_effect_rows": len(pairs),
        "protocols": sorted({row["protocol"] for row in rows}),
        "topologies": sorted({row["topology"] for row in rows}),
        "member_counts": sorted({_int(row, "member_count") for row in rows}),
        "packet_losses": sorted({_float(row, "packet_loss") for row in rows}),
        "seeds": sorted({_int(row, "seed") for row in rows}),
    }
    (output_dir / "analysis_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic publication tables for RANGER"
    )
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--bootstrap-resamples",
        type=int,
        default=DEFAULT_BOOTSTRAP_RESAMPLES,
    )
    parser.add_argument(
        "--bootstrap-seed",
        type=int,
        default=DEFAULT_BOOTSTRAP_SEED,
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = analyze_campaign(
        args.aggregate,
        args.output,
        bootstrap_resamples=args.bootstrap_resamples,
        bootstrap_seed=args.bootstrap_seed,
    )
    print(f"input_rows={manifest['input_rows']}")
    print(f"group_summary_rows={manifest['group_summary_rows']}")
    print(f"paired_effect_rows={manifest['paired_effect_rows']}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
