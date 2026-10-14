import csv
from pathlib import Path

import pytest

from ranger_iot.analysis.publication import (
    analyze_campaign,
    bootstrap_mean_ci,
    wilson_interval,
)

REQUIRED_FIELDS = (
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


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=REQUIRED_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _minimal_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "protocol": "ranger-adaptive",
        "topology": "line",
        "member_count": 8,
        "packet_loss": 0.1,
        "seed": 1,
        "completed": "True",
        "convergence_fraction": 1.0,
        "radio_transmissions": 12,
        "radio_bytes_sent": 768,
        "manager_radio_transmissions": 3,
        "t100_us": 70,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("successes", "total", "message"),
    [
        (0, 0, "total must be positive"),
        (-1, 10, "successes must be"),
        (11, 10, "successes must be"),
    ],
)
def test_wilson_interval_rejects_invalid_inputs(
    successes: int,
    total: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        wilson_interval(successes, total)


def test_bootstrap_rejects_empty_sample() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        bootstrap_mean_ci([], resamples=10)


def test_bootstrap_rejects_nonpositive_resamples() -> None:
    with pytest.raises(ValueError, match="resamples must be positive"):
        bootstrap_mean_ci([1.0, 2.0], resamples=0)


def test_bootstrap_singleton_has_zero_width_interval() -> None:
    assert bootstrap_mean_ci([4.25], resamples=10) == (4.25, 4.25)


def test_analyze_rejects_nonpositive_bootstrap_resamples(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.csv"
    _write_rows(aggregate, [_minimal_row()])

    with pytest.raises(ValueError, match="bootstrap_resamples must be positive"):
        analyze_campaign(
            aggregate,
            tmp_path / "analysis",
            bootstrap_resamples=0,
        )


def test_analyze_rejects_empty_aggregate(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.csv"
    aggregate.write_text(",".join(REQUIRED_FIELDS) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="contains no data rows"):
        analyze_campaign(aggregate, tmp_path / "analysis")


def test_analyze_rejects_missing_required_columns(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.csv"
    aggregate.write_text(
        "protocol,topology\nranger-adaptive,line\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required fields"):
        analyze_campaign(aggregate, tmp_path / "analysis")


def test_analysis_handles_group_without_completed_t100(tmp_path: Path) -> None:
    aggregate = tmp_path / "aggregate.csv"
    _write_rows(
        aggregate,
        [
            _minimal_row(
                completed="False",
                convergence_fraction=0.5,
                t100_us="",
            ),
            _minimal_row(
                seed=2,
                completed="False",
                convergence_fraction=0.75,
                t100_us="",
            ),
        ],
    )

    output = tmp_path / "analysis"
    manifest = analyze_campaign(
        aggregate,
        output,
        bootstrap_resamples=20,
        bootstrap_seed=9,
    )

    assert manifest["input_rows"] == 2

    rows = list(csv.DictReader((output / "group_summary.csv").open()))
    assert len(rows) == 1
    assert rows[0]["completed_t100_samples"] == "0"
    assert rows[0]["mean_t100_us_completed"] == ""
    assert rows[0]["t100_us_completed_ci95_low"] == ""
    assert rows[0]["t100_us_completed_ci95_high"] == ""


def test_analysis_with_no_adaptive_pair_produces_empty_pair_table(
    tmp_path: Path,
) -> None:
    aggregate = tmp_path / "aggregate.csv"
    _write_rows(
        aggregate,
        [
            _minimal_row(
                protocol="skdc",
                completed="True",
                convergence_fraction=1.0,
            )
        ],
    )

    output = tmp_path / "analysis"
    manifest = analyze_campaign(
        aggregate,
        output,
        bootstrap_resamples=20,
        bootstrap_seed=11,
    )

    assert manifest["paired_effect_rows"] == 0
    paired_lines = (output / "paired_effects.csv").read_text(encoding="utf-8").splitlines()
    assert len(paired_lines) == 1
