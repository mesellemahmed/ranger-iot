#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]

COMPOSE = ROOT / "experiments/cooja/compose.yaml"

CONFIG = (
    ROOT
    / "experiments/cooja/config/"
    "step6c3-radio-loss.json"
)

TEMPLATE = (
    ROOT
    / "experiments/cooja/tests/"
    "ranger-radio-loss-campaign-template.js"
)

SOURCE = (
    ROOT
    / "experiments/cooja/apps/"
    "ranger-static-coded-rpl/"
    "ranger-static-coded-rpl.c"
)

TOOLCHAIN = (
    ROOT
    / "experiments/cooja/config/"
    "toolchain-lock.json"
)

BASE_RESULT_ROOT = (
    ROOT
    / "experiments/cooja/results/"
    "step6c2-controlled-fragment-loss"
)

RESULT_ROOT = (
    ROOT
    / "experiments/cooja/results/"
    "step6c3-radio-loss"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(block)

    return digest.hexdigest()


def capture(
    args: list[str],
    *,
    timeout: int = 900,
) -> subprocess.CompletedProcess[str]:

    print()
    print("$", " ".join(args))

    return subprocess.run(
        args,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=timeout,
    )


def current_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        check=True,
    )

    return result.stdout.strip()


def locate_base_scenario() -> Path:
    campaigns = sorted(
        BASE_RESULT_ROOT.glob("campaign-*-full")
    )

    if not campaigns:
        raise RuntimeError(
            "No frozen STEP 6C.2 full campaign found."
        )

    scenario = (
        campaigns[-1]
        / "cases/n5-loss0000-seed000101/"
        "scenario.csc"
    )

    if not scenario.is_file():
        raise RuntimeError(
            f"Base scenario missing: {scenario}"
        )

    return scenario


def popcount_authorized(mask: int) -> int:
    return sum(
        bool(mask & (1 << node))
        for node in range(2, 8)
    )


def make_assertion(
    case_dir: Path,
    *,
    n: int,
    rx_success: float,
    simulation_seed: int,
) -> Path:

    output_file = case_dir / "cooja-result.json"

    output_linux = (
        "/workspace/"
        + output_file.relative_to(ROOT).as_posix()
    )

    text = TEMPLATE.read_text(encoding="utf-8")

    replacements = {
        "@@RESULT_PATH@@": output_linux,
        "@@N@@": str(n),
        "@@RX_SUCCESS@@": repr(rx_success),
        "@@SIMULATION_SEED@@": str(simulation_seed),
    }

    for old, new in replacements.items():
        if old not in text:
            raise RuntimeError(
                f"Template token missing: {old}"
            )

        text = text.replace(old, new)

    if "@@" in text:
        raise RuntimeError(
            "Unresolved assertion template token."
        )

    assertion = case_dir / "assertion.js"

    assertion.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    return assertion


def make_scenario(
    case_dir: Path,
    *,
    n: int,
    rx_success: float,
    simulation_seed: int,
    assertion: Path,
) -> tuple[Path, str]:

    base_scenario = locate_base_scenario()

    tree = ET.parse(base_scenario)
    root = tree.getroot()

    title = root.find("./simulation/title")
    randomseed = root.find("./simulation/randomseed")

    tx = root.find(
        "./simulation/radiomedium/success_ratio_tx"
    )

    rx = root.find(
        "./simulation/radiomedium/success_ratio_rx"
    )

    source = root.find("./simulation/motetype/source")
    commands = root.find("./simulation/motetype/commands")
    scriptfile = root.find(".//scriptfile")

    required = {
        "title": title,
        "randomseed": randomseed,
        "tx": tx,
        "rx": rx,
        "source": source,
        "commands": commands,
        "scriptfile": scriptfile,
    }

    missing = [
        name
        for name, element in required.items()
        if element is None
    ]

    if missing:
        raise RuntimeError(
            "Unexpected base scenario structure: "
            + ", ".join(missing)
        )

    assert title is not None
    assert randomseed is not None
    assert tx is not None
    assert rx is not None
    assert source is not None
    assert commands is not None
    assert scriptfile is not None

    title.text = (
        "RANGER UDGM radio-loss "
        f"k3-n{n}-rx{rx_success:.2f}-"
        f"seed{simulation_seed}"
    )

    randomseed.text = str(simulation_seed)

    tx.text = "1.0"
    rx.text = f"{rx_success:.6f}"

    source.text = (
        "/workspace/experiments/cooja/apps/"
        "ranger-static-coded-rpl/"
        "ranger-static-coded-rpl.c"
    )

    defines = ",".join(
        [
            "RANGER_CODING_K=3",
            f"RANGER_CODING_N={n}",
            "RANGER_LOSS_BP=0",
            "RANGER_LOSS_SEED=1",
            "RANGER_CAMPAIGN_MODE=0",
        ]
    )

    commands.text = (
        "$(MAKE) -j$(CPUS) "
        "ranger-static-coded-rpl.cooja "
        "TARGET=cooja "
        f"DEFINES={defines}"
    )

    scriptfile.text = (
        "/workspace/"
        + assertion.relative_to(ROOT).as_posix()
    )

    scenario = case_dir / "scenario.csc"

    ET.indent(tree, space="  ")

    tree.write(
        scenario,
        encoding="utf-8",
        xml_declaration=True,
    )

    return scenario, defines


def validate_result(
    result: dict[str, Any],
    *,
    n: int,
    rx_success: float,
    simulation_seed: int,
) -> list[str]:

    errors: list[str] = []

    if result.get("schema_version") != 1:
        errors.append("schema_version")

    if result.get("expected_k") != 3:
        errors.append("expected_k")

    if result.get("expected_n") != n:
        errors.append("expected_n")

    observed_seed = result.get(
        "observed_simulation_seed"
    )

    if observed_seed != simulation_seed:
        errors.append(
            "observed_simulation_seed"
        )

    recorded_rx = result.get(
        "expected_success_ratio_rx"
    )

    if (
        not isinstance(recorded_rx, (int, float))
        or abs(float(recorded_rx) - rx_success) > 1e-9
    ):
        errors.append(
            "expected_success_ratio_rx"
        )

    mask = int(
        result.get(
            "authorized_reconstructed_mask",
            0,
        )
    )

    count = int(
        result.get(
            "authorized_reconstructed_count",
            -1,
        )
    )

    if popcount_authorized(mask) != count:
        errors.append(
            "reconstruction_mask_count"
        )

    if bool(result.get("bootstrap_complete")):
        if int(
            result.get(
                "registered_count",
                -1,
            )
        ) != 7:
            errors.append(
                "bootstrap_registration_count"
            )

    outcome = result.get("outcome")

    allowed_outcomes = {
        "BOOTSTRAP_FAIL",
        "REKEY_INCOMPLETE",
        "REKEY_COMPLETE",
        "SAFETY_FAIL",
    }

    if outcome not in allowed_outcomes:
        errors.append("outcome")

    if (
        outcome == "REKEY_COMPLETE"
        and count != 6
    ):
        errors.append(
            "complete_without_six"
        )

    if (
        outcome == "REKEY_INCOMPLETE"
        and (
            not bool(
                result.get(
                    "bootstrap_complete"
                )
            )
            or count >= 6
        )
    ):
        errors.append(
            "invalid_incomplete"
        )

    if (
        outcome == "BOOTSTRAP_FAIL"
        and bool(
            result.get(
                "bootstrap_complete"
            )
        )
    ):
        errors.append(
            "invalid_bootstrap_fail"
        )

    if (
        outcome == "SAFETY_FAIL"
        and not bool(
            result.get(
                "revoked_reconstructed"
            )
        )
    ):
        errors.append(
            "invalid_safety_fail"
        )

    return errors


def run_case(
    campaign_dir: Path,
    *,
    n: int,
    rx_success: float,
    simulation_seed: int,
) -> dict[str, Any]:

    rx_bp = int(round(rx_success * 10000))

    case_id = (
        f"n{n}-"
        f"rx{rx_bp:05d}-"
        f"seed{simulation_seed:06d}"
    )

    case_dir = campaign_dir / "cases" / case_id
    case_dir.mkdir(parents=True, exist_ok=False)

    assertion = make_assertion(
        case_dir,
        n=n,
        rx_success=rx_success,
        simulation_seed=simulation_seed,
    )

    scenario, defines = make_scenario(
        case_dir,
        n=n,
        rx_success=rx_success,
        simulation_seed=simulation_seed,
        assertion=assertion,
    )

    case_input = {
        "schema_version": 1,
        "case_id": case_id,
        "k": 3,
        "n": n,
        "success_ratio_tx": 1.0,
        "success_ratio_rx": rx_success,
        "simulation_seed": simulation_seed,
        "application_loss_bp": 0,
        "defines": defines,
    }

    case_json = case_dir / "case.json"

    case_json.write_text(
        json.dumps(
            case_input,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # Force recompilation of the parameterized application.
    # Cooja <commands> is not a shell, so cleanup happens here.
    app_build = (
        ROOT
        / "experiments/cooja/apps/"
        "ranger-static-coded-rpl/"
        "build/cooja"
    )

    for artifact in (
        app_build / "obj/ranger-static-coded-rpl.o",
        app_build / "ranger-static-coded-rpl.cooja",
    ):
        artifact.unlink(missing_ok=True)

    scenario_linux = (
        "/workspace/"
        + scenario.relative_to(ROOT).as_posix()
    )

    command = [
        "docker",
        "compose",
        "-f",
        str(COMPOSE),
        "run",
        "--rm",
        "-T",
        "cooja",
        "run",
        f"--args=--no-gui {scenario_linux}",
    ]

    try:
        completed = capture(
            command,
            timeout=900,
        )
        output = completed.stdout
        exit_code = completed.returncode

    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode(
                "utf-8",
                errors="replace",
            )

        output = stdout + "\nHOST_TIMEOUT\n"
        exit_code = 124

    raw_log = case_dir / "raw.log"

    raw_log.write_text(
        output,
        encoding="utf-8",
        newline="\n",
    )

    result_path = case_dir / "cooja-result.json"

    result_data: dict[str, Any] | None = None
    result_errors: list[str] = []

    if result_path.is_file():
        try:
            result_data = json.loads(
                result_path.read_text(
                    encoding="utf-8"
                )
            )

            result_errors = validate_result(
                result_data,
                n=n,
                rx_success=rx_success,
                simulation_seed=simulation_seed,
            )

        except Exception as exc:
            result_errors = [
                "invalid_result_json:"
                + type(exc).__name__
            ]
    else:
        result_errors = [
            "missing_cooja_result"
        ]

    cooja_testlog = case_dir / "COOJA.testlog"

    testlog_text = ""

    if cooja_testlog.is_file():
        testlog_text = cooja_testlog.read_text(
            encoding="utf-8",
            errors="replace",
        )

    test_ok = (
        "TEST OK" in output
        or "TEST OK" in testlog_text
    )

    test_failed = (
        "TEST FAILED" in output
        or "TEST FAILED" in testlog_text
    )

    script_runner_pass = (
        exit_code == 0
        and test_ok
        and not test_failed
        and result_data is not None
        and not result_errors
    )

    if script_runner_pass:
        assert result_data is not None
        outcome = str(
            result_data["outcome"]
        )
    else:
        outcome = "INFRA_FAIL"

    metrics: dict[str, Any] = {
        **case_input,
        "exit_code": exit_code,
        "script_runner_pass": script_runner_pass,
        "validation_errors": result_errors,
        "outcome": outcome,
    }

    if result_data is not None:
        metrics.update(
            {
                "bootstrap_complete":
                    result_data.get(
                        "bootstrap_complete"
                    ),
                "registered_count":
                    result_data.get(
                        "registered_count"
                    ),
                "authorized_reconstructed_count":
                    result_data.get(
                        "authorized_reconstructed_count"
                    ),
                "authorized_reconstruction_ratio":
                    result_data.get(
                        "authorized_reconstruction_ratio"
                    ),
                "revoked_reconstructed":
                    result_data.get(
                        "revoked_reconstructed"
                    ),
                "revoked_reject_observed":
                    result_data.get(
                        "revoked_reject_observed"
                    ),
                "report_count":
                    result_data.get(
                        "report_count"
                    ),
                "observed_simulation_seed":
                    result_data.get(
                        "observed_simulation_seed"
                    ),
                "bootstrap_time":
                    result_data.get(
                        "bootstrap_time"
                    ),
                "coded_all_sent_time":
                    result_data.get(
                        "coded_all_sent_time"
                    ),
                "finish_time":
                    result_data.get(
                        "finish_time"
                    ),
            }
        )

    metrics_path = case_dir / "metrics.json"

    metrics_path.write_text(
        json.dumps(
            metrics,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest = {
        "schema_version": 1,
        "experiment":
            "RANGER-COOJA-UDGM-RADIO-LOSS",
        "case_id": case_id,
        "source_commit": current_commit(),
        "result": outcome,
        "validation_source":
            "cooja-script-runner-structured-json",
        "radio_model": "UDGM",
        "application_loss": False,
        "success_ratio_tx": 1.0,
        "success_ratio_rx": rx_success,
        "simulation_seed": simulation_seed,
        "scenario_sha256": sha256(scenario),
        "assertion_sha256": sha256(assertion),
        "source_sha256": sha256(SOURCE),
        "config_sha256": sha256(CONFIG),
        "template_sha256": sha256(TEMPLATE),
        "runner_sha256": sha256(
            Path(__file__)
        ),
        "toolchain_lock_sha256":
            sha256(TOOLCHAIN),
    }

    manifest_path = case_dir / "manifest.json"

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    checksum_paths = [
        case_json,
        scenario,
        assertion,
        raw_log,
    ]

    if result_path.is_file():
        checksum_paths.append(
            result_path
        )

    if cooja_testlog.is_file():
        checksum_paths.append(
            cooja_testlog
        )

    checksum_paths.extend(
        [
            metrics_path,
            manifest_path,
        ]
    )

    checksums = (
        case_dir
        / "CHECKSUMS.sha256"
    )

    checksums.write_text(
        "".join(
            f"{sha256(path)}  {path.name}\n"
            for path in checksum_paths
        ),
        encoding="utf-8",
        newline="\n",
    )

    print(
        case_id,
        "outcome=",
        outcome,
        "validated=",
        script_runner_pass,
        "registered=",
        metrics.get(
            "registered_count"
        ),
        "reconstructed=",
        metrics.get(
            "authorized_reconstructed_count"
        ),
        "seed_observed=",
        metrics.get(
            "observed_simulation_seed"
        ),
    )

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        choices=(
            "pilot",
            "calibration",
            "confirmatory",
        ),
        default="pilot",
    )

    args = parser.parse_args()

    cfg = json.loads(
        CONFIG.read_text(
            encoding="utf-8"
        )
    )

    if args.mode == "pilot":
        seeds = cfg[
            "pilot_simulation_seeds"
        ]
    elif args.mode == "calibration":
        seeds = cfg[
            "calibration_simulation_seeds"
        ]
    else:
        seeds = cfg[
            "confirmatory_simulation_seeds"
        ]

    cases = list(
        itertools.product(
            cfg[
                "coding_n_values"
            ],
            cfg[
                "success_ratio_rx_values"
            ],
            seeds,
        )
    )

    campaign_id = (
        "campaign-"
        + datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        + "-"
        + args.mode
    )

    campaign_dir = (
        RESULT_ROOT
        / campaign_id
    )

    campaign_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    (
        campaign_dir
        / "campaign-config.json"
    ).write_text(
        json.dumps(
            cfg,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    rows: list[
        dict[str, Any]
    ] = []

    for n, rx_success, seed in cases:
        rows.append(
            run_case(
                campaign_dir,
                n=int(n),
                rx_success=float(
                    rx_success
                ),
                simulation_seed=int(
                    seed
                ),
            )
        )

    aggregate = (
        campaign_dir
        / "aggregate.csv"
    )

    fields = [
        "case_id",
        "n",
        "success_ratio_rx",
        "simulation_seed",
        "script_runner_pass",
        "outcome",
        "bootstrap_complete",
        "registered_count",
        "authorized_reconstructed_count",
        "authorized_reconstruction_ratio",
        "revoked_reconstructed",
        "revoked_reject_observed",
        "report_count",
        "observed_simulation_seed",
        "bootstrap_time",
        "coded_all_sent_time",
        "finish_time",
    ]

    with aggregate.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field: row.get(
                        field
                    )
                    for field in fields
                }
            )

    outcome_names = (
        "BOOTSTRAP_FAIL",
        "REKEY_INCOMPLETE",
        "REKEY_COMPLETE",
        "SAFETY_FAIL",
        "INFRA_FAIL",
    )

    outcomes = {
        name: sum(
            row["outcome"] == name
            for row in rows
        )
        for name in outcome_names
    }

    summary = {
        "schema_version": 1,
        "campaign_id":
            campaign_id,
        "mode": args.mode,
        "case_count":
            len(rows),
        "validated":
            sum(
                bool(
                    row[
                        "script_runner_pass"
                    ]
                )
                for row in rows
            ),
        "bootstrap_fail":
            outcomes[
                "BOOTSTRAP_FAIL"
            ],
        "rekey_incomplete":
            outcomes[
                "REKEY_INCOMPLETE"
            ],
        "rekey_complete":
            outcomes[
                "REKEY_COMPLETE"
            ],
        "safety_fail":
            outcomes[
                "SAFETY_FAIL"
            ],
        "infra_fail":
            outcomes[
                "INFRA_FAIL"
            ],
    }

    summary_path = (
        campaign_dir
        / "summary.json"
    )

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print()
    print(
        "Campaign :",
        campaign_dir.relative_to(
            ROOT
        ).as_posix(),
    )

    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    print()
    print(
        aggregate.read_text(
            encoding="utf-8"
        ).rstrip()
    )


if __name__ == "__main__":
    main()
