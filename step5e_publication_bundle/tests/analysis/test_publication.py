import csv
from pathlib import Path

import pytest

from ranger_iot.analysis.publication import (
    analyze_campaign,
    bootstrap_mean_ci,
    wilson_interval,
)


def _write_aggregate(path: Path) -> None:
    fields = (
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
    )
    rows = []
    for seed in (1, 2, 3, 4):
        rows.extend(
            [
                {
                    "protocol": "ranger-adaptive",
                    "topology": "line",
                    "member_count": 8,
                    "packet_loss": 0.2,
                    "seed": seed,
                    "completed": "True",
                    "convergence_fraction": 1.0,
                    "radio_transmissions": 30 + seed,
                    "radio_bytes_sent": 3000 + seed,
                    "manager_radio_transmissions": 4,
                    "t100_us": 100,
                },
                {
                    "protocol": "ranger-static",
                    "topology": "line",
                    "member_count": 8,
                    "packet_loss": 0.2,
                    "seed": seed,
                    "completed": "True" if seed < 4 else "False",
                    "convergence_fraction": 1.0 if seed < 4 else 0.75,
                    "radio_transmissions": 40 + seed,
                    "radio_bytes_sent": 4000 + seed,
                    "manager_radio_transmissions": 5,
                    "t100_us": 120 if seed < 4 else "",
                },
            ]
        )

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_wilson_interval_contains_observed_proportion() -> None:
    low, high = wilson_interval(8, 10)
    assert 0.0 <= low < 0.8 < high <= 1.0


def test_bootstrap_is_deterministic() -> None:
    values = [1.0, 2.0, 3.0, 4.0]
    first = bootstrap_mean_ci(values, resamples=200, seed=7, label="x")
    second = bootstrap_mean_ci(values, resamples=200, seed=7, label="x")
    assert first == second


def test_analyze_campaign_writes_deterministic_tables(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.csv"
    _write_aggregate(aggregate)

    out1 = tmp_path / "analysis1"
    out2 = tmp_path / "analysis2"

    first = analyze_campaign(
        aggregate,
        out1,
        bootstrap_resamples=200,
        bootstrap_seed=123,
    )
    second = analyze_campaign(
        aggregate,
        out2,
        bootstrap_resamples=200,
        bootstrap_seed=123,
    )

    assert first["input_rows"] == 8
    assert first["group_summary_rows"] == 2
    assert first == second

    assert (out1 / "group_summary.csv").read_bytes() == (
        out2 / "group_summary.csv"
    ).read_bytes()
    assert (out1 / "paired_effects.csv").read_bytes() == (
        out2 / "paired_effects.csv"
    ).read_bytes()

    paired = list(csv.DictReader((out1 / "paired_effects.csv").open()))
    radio = next(
        row for row in paired if row["metric"] == "radio_transmissions"
    )
    assert float(radio["benefit_delta_mean"]) == pytest.approx(10.0)
    assert int(radio["adaptive_better_count"]) == 4


def test_analysis_rejects_nonempty_output_directory(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.csv"
    _write_aggregate(aggregate)
    output = tmp_path / "analysis"
    output.mkdir()
    (output / "existing.txt").write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="must be empty"):
        analyze_campaign(aggregate, output, bootstrap_resamples=10)
