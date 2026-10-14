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
PREPARE = ROOT / "experiments/cooja/scripts/prepare_ranger_core_scenario.py"
SCENARIO = ROOT / "experiments/cooja/scenarios/generated/ranger-core-5nodes-onehop.csc"
SCENARIO_MANIFEST = ROOT / "experiments/cooja/scenarios/generated/ranger-core-5nodes-onehop.manifest.json"
TOOLCHAIN_LOCK = ROOT / "experiments/cooja/config/toolchain-lock.json"
RESULT_BASE = ROOT / "experiments/cooja/results/step6b2-ranger-core-onehop"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def capture(args: list[str]) -> subprocess.CompletedProcess[str]:
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
    )


def main() -> None:
    print("=" * 72)
    print("STEP 6B.2 — RANGER CORE HEADLESS REVIEWER RUN")
    print("=" * 72)

    prep = capture(["python", str(PREPARE)])
    print(prep.stdout.rstrip())
    if "RANGER-PREPARE: PASS" not in prep.stdout:
        print("RANGER-CORE-HEADLESS: FAIL — preparation")
        return

    run_id = datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%SZ")
    run_dir = RESULT_BASE / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    scenario_linux = (
        "/workspace/experiments/cooja/scenarios/generated/"
        "ranger-core-5nodes-onehop.csc"
    )

    command = [
        "docker", "compose", "-f", str(COMPOSE),
        "run", "--rm", "-T", "cooja",
        "run", f"--args=--no-gui {scenario_linux}",
    ]

    result = capture(command)
    raw_log = run_dir / "raw.log"
    raw_log.write_text(result.stdout, encoding="utf-8", newline="\n")

    print()
    print("\n".join(result.stdout.splitlines()[-100:]))

    accepted = sorted(
        {int(x) for x in re.findall(r"RANGER_ACCEPT node=(\d+) epoch=1 revoked=5", result.stdout)}
    )
    rejected = sorted(
        {int(x) for x in re.findall(r"RANGER_REJECT node=(\d+) epoch=1 revoked=5", result.stdout)}
    )

    markers = {
        "core_pass": result.stdout.count("RANGER_CORE_PASS epoch=1 accepted=3 rejected=1"),
        "assert_pass": result.stdout.count("RANGER_ASSERT_PASS"),
        "test_ok": result.stdout.count("TEST OK"),
    }

    passed = (
        result.returncode == 0
        and accepted == [2, 3, 4]
        and rejected == [5]
        and markers["core_pass"] >= 1
        and markers["assert_pass"] >= 1
        and markers["test_ok"] >= 1
    )

    metrics = {
        "schema_version": 1,
        "experiment": "RANGER-COOJA-CORE-ONEHOP",
        "run_id": run_id,
        "exit_code": result.returncode,
        "accepted_nodes": accepted,
        "rejected_nodes": rejected,
        "marker_counts": markers,
        "result": "PASS" if passed else "FAIL",
    }
    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    toolchain = json.loads(TOOLCHAIN_LOCK.read_text(encoding="utf-8"))
    scenario_meta = json.loads(SCENARIO_MANIFEST.read_text(encoding="utf-8"))

    manifest = {
        "schema_version": 1,
        "experiment": "RANGER-COOJA-CORE-ONEHOP",
        "run_id": run_id,
        "result": metrics["result"],
        "scenario": SCENARIO.relative_to(ROOT).as_posix(),
        "scenario_sha256": sha256(SCENARIO),
        "scenario_manifest_sha256": sha256(SCENARIO_MANIFEST),
        "toolchain_lock_sha256": sha256(TOOLCHAIN_LOCK),
        "docker_image": toolchain.get("docker_image"),
        "contiki_ng_commit": toolchain.get("contiki_ng_commit"),
        "cooja_commit": toolchain.get("cooja_commit"),
        "random_seed": scenario_meta.get("random_seed"),
        "raw_log": raw_log.relative_to(ROOT).as_posix(),
        "raw_log_sha256": sha256(raw_log),
        "metrics": metrics_path.relative_to(ROOT).as_posix(),
        "metrics_sha256": sha256(metrics_path),
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    checksum_path = run_dir / "CHECKSUMS.sha256"
    checksum_path.write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in (raw_log, metrics_path, manifest_path)),
        encoding="utf-8",
        newline="\n",
    )

    print()
    print("Run dir :", run_dir.relative_to(ROOT).as_posix())
    print("Accepted:", accepted)
    print("Rejected:", rejected)
    print("Markers :", markers)
    print("Result  :", metrics["result"])
    print("RANGER-CORE-HEADLESS:", "PASS" if passed else "FAIL")
    print("Git Bash remains open.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RANGER-CORE-HEADLESS: ERROR: {type(exc).__name__}: {exc}")
        print("Git Bash remains open.")
