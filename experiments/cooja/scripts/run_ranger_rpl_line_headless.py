#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "experiments/cooja/compose.yaml"
GENERATOR = ROOT / "experiments/cooja/scripts/generate_ranger_rpl_line_scenario.py"
SCENARIO = ROOT / "experiments/cooja/scenarios/generated/ranger-rpl-line-8nodes.csc"
SCENARIO_MANIFEST = ROOT / "experiments/cooja/scenarios/generated/ranger-rpl-line-8nodes.manifest.json"
TOOLCHAIN_LOCK = ROOT / "experiments/cooja/config/toolchain-lock.json"
RESULT_ROOT = ROOT / "experiments/cooja/results/step6b3-ranger-rpl-line-8nodes"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def capture(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess[str]:
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


def main() -> None:
    print("=" * 72)
    print("STEP 6B.3 — RANGER MULTI-HOP RPL LINE VALIDATION")
    print("=" * 72)

    generated = capture(["python", str(GENERATOR)])
    print(generated.stdout.rstrip())

    if "RANGER-RPL-SCENARIO-GENERATE: PASS" not in generated.stdout:
        print("RANGER-RPL-LINE: FAIL — scenario generation")
        return

    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    run_dir = RESULT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    scenario_linux = (
        "/workspace/experiments/cooja/scenarios/generated/"
        "ranger-rpl-line-8nodes.csc"
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
        result = capture(command, timeout=900)
        output = result.stdout
        exit_code = result.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + "\nHOST_TIMEOUT\n"
        exit_code = 124

    raw_log = run_dir / "raw.log"
    raw_log.write_text(output, encoding="utf-8", newline="\n")

    print()
    print("\n".join(output.splitlines()[-120:]))

    registered = sorted(
        {
            int(x)
            for x in re.findall(
                r"RANGER_RPL_REGISTER node=(\d+) registered=",
                output,
            )
        }
    )

    accepted = sorted(
        {
            int(x)
            for x in re.findall(
                r"RANGER_RPL_ACCEPT node=(\d+) epoch=1 revoked=8",
                output,
            )
        }
    )

    rejected = sorted(
        {
            int(x)
            for x in re.findall(
                r"RANGER_RPL_REJECT node=(\d+) epoch=1 revoked=8",
                output,
            )
        }
    )

    markers = {
        "root_start": output.count("RANGER_RPL_ROOT_START node=1"),
        "ready": output.count("RANGER_RPL_READY registered=7/7 epoch=1 revoked=8"),
        "all_sent": output.count("RANGER_RPL_REKEY_ALL_SENT epoch=1 targets=7"),
        "core_pass": output.count(
            "RANGER_RPL_CORE_PASS epoch=1 registered=7 accepted=6 rejected=1"
        ),
        "assert_pass": output.count("RANGER_RPL_ASSERT_PASS"),
        "test_ok": output.count("TEST OK"),
    }

    expected_registered = [2, 3, 4, 5, 6, 7, 8]
    expected_accepted = [2, 3, 4, 5, 6, 7]
    expected_rejected = [8]

    scenario_meta = json.loads(SCENARIO_MANIFEST.read_text(encoding="utf-8"))

    passed = (
        exit_code == 0
        and registered == expected_registered
        and accepted == expected_accepted
        and rejected == expected_rejected
        and markers["root_start"] >= 1
        and markers["ready"] >= 1
        and markers["core_pass"] >= 1
        and markers["assert_pass"] >= 1
        and markers["test_ok"] >= 1
        and scenario_meta.get("direct_root_to_farthest") is False
    )

    metrics = {
        "schema_version": 1,
        "experiment": "RANGER-COOJA-RPL-LINE-8",
        "run_id": run_id,
        "exit_code": exit_code,
        "registered_nodes": registered,
        "accepted_nodes": accepted,
        "rejected_nodes": rejected,
        "marker_counts": markers,
        "root_to_farthest_distance": scenario_meta.get(
            "root_to_farthest_distance"
        ),
        "transmitting_range": scenario_meta.get("transmitting_range"),
        "direct_root_to_farthest": scenario_meta.get(
            "direct_root_to_farthest"
        ),
        "result": "PASS" if passed else "FAIL",
    }

    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    toolchain = json.loads(TOOLCHAIN_LOCK.read_text(encoding="utf-8"))

    manifest = {
        "schema_version": 1,
        "experiment": "RANGER-COOJA-RPL-LINE-8",
        "run_id": run_id,
        "result": metrics["result"],
        "scenario": SCENARIO.relative_to(ROOT).as_posix(),
        "scenario_sha256": sha256(SCENARIO),
        "scenario_manifest": SCENARIO_MANIFEST.relative_to(ROOT).as_posix(),
        "scenario_manifest_sha256": sha256(SCENARIO_MANIFEST),
        "toolchain_lock_sha256": sha256(TOOLCHAIN_LOCK),
        "docker_image": toolchain.get("docker_image"),
        "contiki_ng_commit": toolchain.get("contiki_ng_commit"),
        "cooja_commit": toolchain.get("cooja_commit"),
        "random_seed": scenario_meta.get("random_seed"),
        "topology": "line",
        "mote_count": 8,
        "raw_log": raw_log.relative_to(ROOT).as_posix(),
        "raw_log_sha256": sha256(raw_log),
        "metrics": metrics_path.relative_to(ROOT).as_posix(),
        "metrics_sha256": sha256(metrics_path),
        "scientific_scope": (
            "multi-hop RPL transport and functional epoch/revocation semantics; "
            "no coded dissemination or cryptographic post-revocation claim"
        ),
    }

    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    checksums = run_dir / "CHECKSUMS.sha256"
    checksums.write_text(
        "".join(
            f"{sha256(path)}  {path.name}\n"
            for path in (raw_log, metrics_path, manifest_path)
        ),
        encoding="utf-8",
        newline="\n",
    )

    print()
    print("Run dir    :", run_dir.relative_to(ROOT).as_posix())
    print("Registered :", registered)
    print("Accepted   :", accepted)
    print("Rejected   :", rejected)
    print("Markers    :", markers)
    print("Multi-hop  :", scenario_meta.get("direct_root_to_farthest") is False)
    print("Result     :", metrics["result"])
    print()
    print("RANGER-RPL-LINE:", "PASS" if passed else "FAIL")
    print("Git Bash remains open.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RANGER-RPL-LINE: ERROR: {type(exc).__name__}: {exc}")
        print("Git Bash remains open.")
