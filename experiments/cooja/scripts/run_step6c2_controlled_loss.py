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

ROOT = Path(__file__).resolve().parents[3]

COMPOSE = ROOT / "experiments/cooja/compose.yaml"
CONFIG = ROOT / "experiments/cooja/config/step6c2-controlled-fragment-loss.json"

BASE_SCENARIO = (
    ROOT
    / "experiments/cooja/scenarios/generated/"
    "ranger-static-coded-rpl-line-8nodes.csc"
)

ASSERTION = (
    ROOT
    / "experiments/cooja/tests/"
    "ranger-static-loss-campaign-assert.js"
)

SOURCE = (
    ROOT
    / "experiments/cooja/apps/ranger-static-coded-rpl/"
    "ranger-static-coded-rpl.c"
)

TOOLCHAIN = ROOT / "experiments/cooja/config/toolchain-lock.json"

RESULT_ROOT = (
    ROOT
    / "experiments/cooja/results/"
    "step6c2-controlled-fragment-loss"
)

AUTHORIZED = tuple(range(2, 8))
ALL_TARGETS = tuple(range(2, 9))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def loss_hash(seed: int, target: int, fragment_index: int) -> int:
    x = seed & 0xFFFFFFFF
    x ^= (target * 0x9E37) & 0xFFFFFFFF
    x ^= ((fragment_index + 1) * 0x85EB) & 0xFFFFFFFF

    x ^= (x << 13) & 0xFFFFFFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFFFFFF

    return x & 0xFFFFFFFF


def should_drop(seed: int, target: int, fragment: int, loss_bp: int) -> bool:
    return loss_hash(seed, target, fragment) % 10000 < loss_bp


def expected_nodes(n: int, loss_bp: int, seed: int) -> tuple[int, ...]:
    result: list[int] = []

    for node in AUTHORIZED:
        delivered = sum(
            not should_drop(seed, node, fragment, loss_bp)
            for fragment in range(n)
        )

        if delivered >= 3:
            result.append(node)

    return tuple(result)


def mask(nodes: tuple[int, ...]) -> int:
    value = 0

    for node in nodes:
        value |= 1 << node

    return value


def planned_counts(n: int, loss_bp: int, seed: int) -> tuple[int, int]:
    opportunities = len(ALL_TARGETS) * n

    drops = sum(
        should_drop(seed, target, fragment, loss_bp)
        for target in ALL_TARGETS
        for fragment in range(n)
    )

    return opportunities - drops, drops


def capture(args: list[str], timeout: int = 900) -> subprocess.CompletedProcess[str]:
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


def make_scenario(
    case_dir: Path,
    *,
    n: int,
    loss_bp: int,
    seed: int,
) -> tuple[Path, str]:
    tree = ET.parse(BASE_SCENARIO)
    root = tree.getroot()

    title = root.find("./simulation/title")
    source = root.find("./simulation/motetype/source")
    commands = root.find("./simulation/motetype/commands")

    if title is None or source is None or commands is None:
        raise RuntimeError("unexpected base scenario structure")

    title.text = (
        f"RANGER controlled fragment loss — "
        f"k3-n{n}-loss{loss_bp}-seed{seed}"
    )

    source.text = (
        "/workspace/experiments/cooja/apps/"
        "ranger-static-coded-rpl/ranger-static-coded-rpl.c"
    )

    defines = ",".join(
        [
            "RANGER_CODING_K=3",
            f"RANGER_CODING_N={n}",
            f"RANGER_LOSS_BP={loss_bp}",
            f"RANGER_LOSS_SEED={seed}",
            "RANGER_CAMPAIGN_MODE=1",
        ]
    )

    commands.text = (
        "$(MAKE) -j$(CPUS) "
        "ranger-static-coded-rpl.cooja "
        "TARGET=cooja "
        f"DEFINES={defines}"
    )

    scriptfile = root.find(".//scriptfile")

    if scriptfile is None:
        raise RuntimeError("ScriptRunner scriptfile not found")

    scriptfile.text = (
        "/workspace/experiments/cooja/tests/"
        "ranger-static-loss-campaign-assert.js"
    )

    scenario = case_dir / "scenario.csc"

    ET.indent(tree, space="  ")
    tree.write(scenario, encoding="utf-8", xml_declaration=True)

    return scenario, defines


def run_case(
    campaign_dir: Path,
    *,
    n: int,
    loss_bp: int,
    seed: int,
) -> dict[str, object]:
    case_id = f"n{n}-loss{loss_bp:04d}-seed{seed:06d}"
    case_dir = campaign_dir / "cases" / case_id
    case_dir.mkdir(parents=True, exist_ok=False)

    expected = expected_nodes(n, loss_bp, seed)
    expected_mask = mask(expected)
    send_count, drop_count = planned_counts(n, loss_bp, seed)

    scenario, defines = make_scenario(
        case_dir,
        n=n,
        loss_bp=loss_bp,
        seed=seed,
    )

    case_input = {
        "schema_version": 1,
        "case_id": case_id,
        "k": 3,
        "n": n,
        "loss_bp": loss_bp,
        "loss_rate": loss_bp / 10000,
        "loss_seed": seed,
        "expected_reconstructed_nodes": list(expected),
        "expected_reconstructed_count": len(expected),
        "expected_mask": expected_mask,
        "fragment_send_opportunities": len(ALL_TARGETS) * n,
        "planned_fragment_sends": send_count,
        "planned_fragment_drops": drop_count,
        "defines": defines,
    }

    case_json = case_dir / "case.json"
    case_json.write_text(
        json.dumps(case_input, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # Cooja executes <commands> directly, not through a shell.
    # Force recompilation here on the host-backed worktree instead of using
    # shell operators such as && inside the scenario build command.
    app_build = (
        ROOT
        / "experiments/cooja/apps/ranger-static-coded-rpl/build/cooja"
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
        result = capture(command)
        output = result.stdout
        exit_code = result.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\nHOST_TIMEOUT\n"
        exit_code = 124

    raw_log = case_dir / "raw.log"
    raw_log.write_text(output, encoding="utf-8", newline="\n")

    script_runner_pass = (
        exit_code == 0
        and "TEST OK" in output
        and "TEST FAILED" not in output
    )

    if script_runner_pass:
        outcome = (
            "COMPLETE"
            if len(expected) == len(AUTHORIZED)
            else "INCOMPLETE"
        )
    else:
        outcome = "INFRA_FAIL"

    metrics = {
        **case_input,
        "exit_code": exit_code,
        "script_runner_pass": script_runner_pass,
        "outcome": outcome,
        "authorized_members": len(AUTHORIZED),
        "reconstruction_ratio": len(expected) / len(AUTHORIZED),
        "redundancy_fragments": n - 3,
        "nominal_coding_overhead": n / 3,
    }

    metrics_path = case_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    toolchain = json.loads(TOOLCHAIN.read_text(encoding="utf-8"))

    manifest = {
        "schema_version": 1,
        "experiment": "RANGER-COOJA-CONTROLLED-FRAGMENT-LOSS",
        "case_id": case_id,
        "result": outcome,
        "validation_source": "cooja-script-runner",
        "validation_contract": (
            "Cooja compares planned, reported, and observed "
            "reconstruction masks before TEST OK."
        ),
        "loss_scope": "RANGER coded-fragment application sends only",
        "radio_loss": False,
        "scenario_sha256": sha256(scenario),
        "assertion_sha256": sha256(ASSERTION),
        "source_sha256": sha256(SOURCE),
        "toolchain_lock_sha256": sha256(TOOLCHAIN),
        "docker_image": toolchain.get("docker_image"),
        "contiki_ng_commit": toolchain.get("contiki_ng_commit"),
        "cooja_commit": toolchain.get("cooja_commit"),
    }

    manifest_path = case_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    checksum_paths = [
        case_json,
        scenario,
        raw_log,
        metrics_path,
        manifest_path,
    ]

    (case_dir / "CHECKSUMS.sha256").write_text(
        "".join(
            f"{sha256(path)}  {path.name}\n"
            for path in checksum_paths
        ),
        encoding="utf-8",
        newline="\n",
    )

    print(
        case_id,
        "expected=",
        list(expected),
        "outcome=",
        outcome,
        "validation=",
        script_runner_pass,
    )

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("pilot", "full"),
        default="pilot",
    )
    args = parser.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

    campaign_id = (
        "campaign-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + args.mode
    )

    campaign_dir = RESULT_ROOT / campaign_id
    campaign_dir.mkdir(parents=True, exist_ok=False)

    (campaign_dir / "campaign-config.json").write_text(
        json.dumps(cfg, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    if args.mode == "pilot":
        cases = [
            (int(item["n"]), int(item["loss_bp"]), int(item["seed"]))
            for item in cfg["pilot_cases"]
        ]
    else:
        cases = list(
            itertools.product(
                cfg["total_fragment_values"],
                cfg["loss_basis_points"],
                cfg["full_seeds"],
            )
        )

    rows: list[dict[str, object]] = []

    for n, loss_bp, seed in cases:
        rows.append(
            run_case(
                campaign_dir,
                n=int(n),
                loss_bp=int(loss_bp),
                seed=int(seed),
            )
        )

    aggregate = campaign_dir / "aggregate.csv"

    fields = [
        "case_id",
        "n",
        "loss_bp",
        "loss_rate",
        "loss_seed",
        "expected_reconstructed_count",
        "reconstruction_ratio",
        "planned_fragment_sends",
        "planned_fragment_drops",
        "redundancy_fragments",
        "nominal_coding_overhead",
        "script_runner_pass",
        "outcome",
    ]

    with aggregate.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()

        for row in rows:
            writer.writerow({key: row[key] for key in fields})

    summary = {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "mode": args.mode,
        "case_count": len(rows),
        "complete": sum(row["outcome"] == "COMPLETE" for row in rows),
        "incomplete": sum(row["outcome"] == "INCOMPLETE" for row in rows),
        "infra_fail": sum(row["outcome"] == "INFRA_FAIL" for row in rows),
        "validated": sum(bool(row["script_runner_pass"]) for row in rows),
    }

    summary_path = campaign_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print()
    print("Campaign :", campaign_dir.relative_to(ROOT).as_posix())
    print("Cases    :", len(rows))
    print("Complete :", summary["complete"])
    print("Incomplete:", summary["incomplete"])
    print("InfraFail:", summary["infra_fail"])
    print("Validated:", summary["validated"])
    print()
    print(aggregate.read_text(encoding="utf-8").rstrip())


if __name__ == "__main__":
    main()
