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
    "step6c3f-post-bootstrap-tx-stress.json"
)

TEMPLATE = (
    ROOT
    / "experiments/cooja/tests/"
    "ranger-post-bootstrap-tx-stress-template.js"
)

SOURCE = (
    ROOT
    / "experiments/cooja/apps/"
    "ranger-static-coded-rpl/"
    "ranger-static-coded-rpl.c"
)

BASE_RESULT_ROOT = (
    ROOT
    / "experiments/cooja/results/"
    "step6c2-controlled-fragment-loss"
)

RESULT_ROOT = (
    ROOT
    / "experiments/cooja/results/"
    "step6c3f-post-bootstrap-tx-stress"
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


def locate_base_scenario() -> Path:
    campaigns = sorted(
        BASE_RESULT_ROOT.glob(
            "campaign-*-full"
        )
    )

    if not campaigns:
        raise RuntimeError(
            "No frozen STEP 6C.2 campaign."
        )

    scenario = (
        campaigns[-1]
        / "cases/"
        "n5-loss0000-seed000101/"
        "scenario.csc"
    )

    if not scenario.is_file():
        raise RuntimeError(
            f"Base scenario missing: "
            f"{scenario}"
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
    target_tx: float,
    simulation_seed: int,
) -> Path:

    output_file = (
        case_dir
        / "cooja-result.json"
    )

    output_linux = (
        "/workspace/"
        + output_file.relative_to(
            ROOT
        ).as_posix()
    )

    text = TEMPLATE.read_text(
        encoding="utf-8"
    )

    replacements = {
        "@@RESULT_PATH@@":
            output_linux,
        "@@N@@":
            str(n),
        "@@TARGET_TX@@":
            repr(target_tx),
        "@@SIMULATION_SEED@@":
            str(simulation_seed),
    }

    for old, new in replacements.items():
        if old not in text:
            raise RuntimeError(
                f"Template token missing: "
                f"{old}"
            )

        text = text.replace(
            old,
            new,
        )

    if "@@" in text:
        raise RuntimeError(
            "Unresolved template token."
        )

    assertion = (
        case_dir
        / "assertion.js"
    )

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
    target_tx: float,
    simulation_seed: int,
    assertion: Path,
) -> tuple[Path, str]:

    tree = ET.parse(
        locate_base_scenario()
    )

    root = tree.getroot()

    title = root.find(
        "./simulation/title"
    )

    randomseed = root.find(
        "./simulation/randomseed"
    )

    tx = root.find(
        "./simulation/radiomedium/"
        "success_ratio_tx"
    )

    rx = root.find(
        "./simulation/radiomedium/"
        "success_ratio_rx"
    )

    source = root.find(
        "./simulation/motetype/source"
    )

    commands = root.find(
        "./simulation/motetype/commands"
    )

    scriptfile = root.find(
        ".//scriptfile"
    )

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
        for name, element
        in required.items()
        if element is None
    ]

    if missing:
        raise RuntimeError(
            "Unexpected base scenario: "
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
        "RANGER post-bootstrap stress "
        f"k3-n{n}-"
        f"target-rx{target_tx:.2f}-"
        f"seed{simulation_seed}"
    )

    randomseed.text = str(
        simulation_seed
    )

    # Bootstrap always occurs under the
    # controlled healthy radio condition.
    tx.text = "1.000000"
    rx.text = "1.000000"

    source.text = (
        "/workspace/"
        "experiments/cooja/apps/"
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
        + assertion.relative_to(
            ROOT
        ).as_posix()
    )

    scenario = (
        case_dir
        / "scenario.csc"
    )

    ET.indent(
        tree,
        space="  ",
    )

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
    target_tx: float,
    simulation_seed: int,
) -> list[str]:

    errors: list[str] = []

    if result.get(
        "schema_version"
    ) != 1:
        errors.append(
            "schema_version"
        )

    if result.get(
        "expected_k"
    ) != 3:
        errors.append(
            "expected_k"
        )

    if result.get(
        "expected_n"
    ) != n:
        errors.append(
            "expected_n"
        )

    if result.get(
        "observed_simulation_seed"
    ) != simulation_seed:
        errors.append(
            "simulation_seed"
        )

    target = result.get(
        "target_success_ratio_tx"
    )

    if (
        not isinstance(
            target,
            (int, float),
        )
        or abs(
            float(target)
            - target_tx
        ) > 1e-12
    ):
        errors.append(
            "target_tx"
        )

    outcome = result.get(
        "outcome"
    )

    allowed = {
        "BOOTSTRAP_FAIL",
        "REKEY_INCOMPLETE",
        "REKEY_COMPLETE",
        "SAFETY_FAIL",
    }

    if outcome not in allowed:
        errors.append(
            "outcome"
        )

    bootstrap = bool(
        result.get(
            "bootstrap_complete"
        )
    )

    if bootstrap:
        if result.get(
            "registered_count"
        ) != 7:
            errors.append(
                "registration_count"
            )

        if not bool(
            result.get(
                "radio_switch_applied"
            )
        ):
            errors.append(
                "radio_switch_not_applied"
            )

        before = result.get(
            "radio_success_ratio_tx_before"
        )

        after = result.get(
            "radio_success_ratio_tx_after"
        )

        if (
            not isinstance(
                before,
                (int, float),
            )
            or abs(
                float(before) - 1.0
            ) > 1e-12
        ):
            errors.append(
                "radio_before"
            )

        if (
            not isinstance(
                after,
                (int, float),
            )
            or abs(
                float(after)
                - target_tx
            ) > 1e-12
        ):
            errors.append(
                "radio_after"
            )

        switch_time = result.get(
            "radio_switch_time"
        )

        first_send = result.get(
            "first_coded_send_time"
        )

        if (
            not isinstance(
                switch_time,
                (int, float),
            )
            or switch_time < 0
        ):
            errors.append(
                "switch_time"
            )

        if (
            not isinstance(
                first_send,
                (int, float),
            )
            or first_send < 0
        ):
            errors.append(
                "first_send_time"
            )

        if (
            isinstance(
                switch_time,
                (int, float),
            )
            and isinstance(
                first_send,
                (int, float),
            )
            and not (
                switch_time
                < first_send
            )
        ):
            errors.append(
                "switch_not_before_send"
            )

        if (
            result.get(
                "switch_before_first_coded_send"
            )
            is not True
        ):
            errors.append(
                "switch_order_flag"
            )

        radio_class = str(
            result.get(
                "radio_medium_class",
                "",
            )
        )

        if "UDGM" not in radio_class:
            errors.append(
                "radio_medium_class"
            )

    elif outcome != "BOOTSTRAP_FAIL":
        errors.append(
            "non_bootstrap_outcome"
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

    if (
        popcount_authorized(mask)
        != count
    ):
        errors.append(
            "reconstruction_mask_count"
        )

    if (
        outcome
        == "REKEY_COMPLETE"
        and count != 6
    ):
        errors.append(
            "complete_without_six"
        )

    if (
        outcome
        == "REKEY_INCOMPLETE"
        and (
            not bootstrap
            or count >= 6
        )
    ):
        errors.append(
            "invalid_incomplete"
        )

    if (
        outcome
        == "SAFETY_FAIL"
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
    target_tx: float,
    simulation_seed: int,
) -> dict[str, Any]:

    rx_bp = int(
        round(
            target_tx
            * 10000
        )
    )

    case_id = (
        f"n{n}-"
        f"posttx{rx_bp:05d}-"
        f"seed{simulation_seed:06d}"
    )

    case_dir = (
        campaign_dir
        / "cases"
        / case_id
    )

    case_dir.mkdir(
        parents=True,
        exist_ok=False,
    )

    assertion = make_assertion(
        case_dir,
        n=n,
        target_tx=target_tx,
        simulation_seed=simulation_seed,
    )

    scenario, defines = (
        make_scenario(
            case_dir,
            n=n,
            target_tx=target_tx,
            simulation_seed=
                simulation_seed,
            assertion=assertion,
        )
    )

    case_input = {
        "schema_version": 1,
        "case_id": case_id,
        "k": 3,
        "n": n,
        "initial_success_ratio_tx":
            1.0,
        "initial_success_ratio_rx":
            1.0,
        "target_success_ratio_tx":
            target_tx,
        "simulation_seed":
            simulation_seed,
        "application_loss_bp": 0,
        "defines": defines,
    }

    case_json = (
        case_dir
        / "case.json"
    )

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

    app_build = (
        ROOT
        / "experiments/cooja/apps/"
        "ranger-static-coded-rpl/"
        "build/cooja"
    )

    for artifact in (
        app_build
        / "obj/"
        "ranger-static-coded-rpl.o",
        app_build
        / "ranger-static-coded-rpl.cooja",
    ):
        artifact.unlink(
            missing_ok=True
        )

    scenario_linux = (
        "/workspace/"
        + scenario.relative_to(
            ROOT
        ).as_posix()
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
        f"--args=--no-gui "
        f"{scenario_linux}",
    ]

    try:
        completed = capture(
            command,
            timeout=900,
        )

        output = completed.stdout
        exit_code = (
            completed.returncode
        )

    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""

        if isinstance(
            stdout,
            bytes,
        ):
            stdout = stdout.decode(
                "utf-8",
                errors="replace",
            )

        output = (
            stdout
            + "\nHOST_TIMEOUT\n"
        )

        exit_code = 124

    raw_log = (
        case_dir
        / "raw.log"
    )

    raw_log.write_text(
        output,
        encoding="utf-8",
        newline="\n",
    )

    result_path = (
        case_dir
        / "cooja-result.json"
    )

    result_data: (
        dict[str, Any] | None
    ) = None

    validation_errors: list[str] = []

    if result_path.is_file():
        try:
            result_data = json.loads(
                result_path.read_text(
                    encoding="utf-8"
                )
            )

            validation_errors = (
                validate_result(
                    result_data,
                    n=n,
                    target_tx=
                        target_tx,
                    simulation_seed=
                        simulation_seed,
                )
            )

        except Exception as exc:
            validation_errors = [
                "invalid_result_json:"
                + type(exc).__name__
            ]

    else:
        validation_errors = [
            "missing_cooja_result"
        ]

    test_ok = (
        "TEST OK"
        in output
    )

    test_failed = (
        "TEST FAILED"
        in output
    )

    script_runner_pass = (
        exit_code == 0
        and test_ok
        and not test_failed
        and result_data
            is not None
        and not
            validation_errors
    )

    if script_runner_pass:
        assert (
            result_data
            is not None
        )

        outcome = str(
            result_data[
                "outcome"
            ]
        )

    else:
        outcome = "INFRA_FAIL"

    metrics: dict[str, Any] = {
        **case_input,
        "exit_code":
            exit_code,
        "script_runner_pass":
            script_runner_pass,
        "validation_errors":
            validation_errors,
        "outcome":
            outcome,
    }

    if result_data is not None:
        for key in (
            "bootstrap_complete",
            "bootstrap_time",
            "registered_count",
            "radio_medium_class",
            "radio_switch_applied",
            "radio_switch_time",
            "radio_success_ratio_tx_before",
            "radio_success_ratio_tx_after",
            "first_coded_send_time",
            "switch_before_first_coded_send",
            "coded_all_sent",
            "coded_all_sent_time",
            "authorized_reconstructed_count",
            "authorized_reconstruction_ratio",
            "revoked_reconstructed",
            "revoked_reject_observed",
            "report_count",
            "observed_simulation_seed",
            "finish_time",
        ):
            metrics[key] = (
                result_data.get(
                    key
                )
            )

    metrics_path = (
        case_dir
        / "metrics.json"
    )

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
            "RANGER-COOJA-POST-BOOTSTRAP-UDGM-TX-STRESS",
        "case_id":
            case_id,
        "source_commit":
            current_commit(),
        "validation_source":
            "cooja-script-runner-dynamic-radio-json",
        "bootstrap_radio_rx":
            1.0,
        "target_rekey_radio_tx":
            target_tx,
        "simulation_seed":
            simulation_seed,
        "application_loss":
            False,
        "scenario_sha256":
            sha256(scenario),
        "assertion_sha256":
            sha256(assertion),
        "source_sha256":
            sha256(SOURCE),
        "config_sha256":
            sha256(CONFIG),
        "template_sha256":
            sha256(TEMPLATE),
        "runner_sha256":
            sha256(
                Path(__file__)
            ),
        "result":
            outcome,
    }

    manifest_path = (
        case_dir
        / "manifest.json"
    )

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
            f"{sha256(path)}  "
            f"{path.name}\n"
            for path
            in checksum_paths
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
        "bootstrap=",
        metrics.get(
            "bootstrap_complete"
        ),
        "switch=",
        metrics.get(
            "radio_switch_applied"
        ),
        "reconstructed=",
        metrics.get(
            "authorized_reconstructed_count"
        ),
        "seed=",
        metrics.get(
            "observed_simulation_seed"
        ),
    )

    return metrics


def main() -> None:
    parser = (
        argparse.ArgumentParser()
    )

    parser.add_argument(
        "--mode",
        choices=(
            "smoke",
            "pilot",
            "calibration",
        ),
        default="pilot",
    )

    args = parser.parse_args()

    cfg = json.loads(
        CONFIG.read_text(
            encoding="utf-8"
        )
    )

    if args.mode == "smoke":
        cases = [
            (
                3,
                0.00,
                int(
                    cfg[
                        "pilot_simulation_seeds"
                    ][0]
                ),
            )
        ]

    else:
        if args.mode == "calibration":
            seeds = cfg[
                "calibration_simulation_seeds"
            ]
        else:
            seeds = cfg[
                "pilot_simulation_seeds"
            ]

        cases = list(
            itertools.product(
                cfg[
                    "coding_n_values"
                ],
                cfg[
                    "target_success_ratio_tx_values"
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

    rows = []

    for n, target_tx, seed in cases:
        rows.append(
            run_case(
                campaign_dir,
                n=int(n),
                target_tx=float(
                    target_tx
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
        "target_success_ratio_tx",
        "simulation_seed",
        "script_runner_pass",
        "outcome",
        "bootstrap_complete",
        "registered_count",
        "radio_switch_applied",
        "radio_switch_time",
        "radio_success_ratio_tx_before",
        "radio_success_ratio_tx_after",
        "first_coded_send_time",
        "switch_before_first_coded_send",
        "authorized_reconstructed_count",
        "authorized_reconstruction_ratio",
        "revoked_reconstructed",
        "revoked_reject_observed",
        "report_count",
        "observed_simulation_seed",
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
                    field:
                        row.get(field)
                    for field
                    in fields
                }
            )

    names = (
        "BOOTSTRAP_FAIL",
        "REKEY_INCOMPLETE",
        "REKEY_COMPLETE",
        "SAFETY_FAIL",
        "INFRA_FAIL",
    )

    outcomes = {
        name: sum(
            row["outcome"]
            == name
            for row in rows
        )
        for name in names
    }

    summary = {
        "schema_version": 1,
        "campaign_id":
            campaign_id,
        "mode":
            args.mode,
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
