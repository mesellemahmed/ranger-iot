#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOCK = ROOT / "experiments" / "cooja" / "config" / "toolchain-lock.json"
COMPOSE = ROOT / "experiments" / "cooja" / "compose.yaml"
SCENARIO = ROOT / "third_party" / "contiki-ng" / "tests" / "07-simulation-base" / "02-ringbufindex.csc"
RESULTS = ROOT / "experiments" / "cooja" / "results" / "step6a2-compose-smoke"
COOJA = ROOT / "third_party" / "contiki-ng" / "tools" / "cooja"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    print("\n$", " ".join(args))
    p = subprocess.run(
        args,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    print(p.stdout.rstrip())
    return p


def git_value(args: list[str]) -> str | None:
    p = subprocess.run(
        args,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    if p.returncode != 0:
        print(p.stdout.rstrip())
        return None
    return p.stdout.strip()


def stop(message: str) -> None:
    print("\n" + "=" * 68)
    print("COOJA-COMPOSE-INFRA: FAIL")
    print(message)
    print("Git Bash remains open.")
    print("=" * 68)


def ensure_gradlew_lf() -> bool:
    gradlew = COOJA / "gradlew"
    if not gradlew.is_file():
        stop("Cooja gradlew is missing")
        return False

    head_blob = git_value(["git", "-C", str(COOJA), "rev-parse", "HEAD:gradlew"])
    worktree_blob = git_value(["git", "-C", str(COOJA), "hash-object", "gradlew"])
    data = gradlew.read_bytes()

    if head_blob != worktree_blob or b"\r\n" in data:
        blob = subprocess.check_output(
            ["git", "-C", str(COOJA), "cat-file", "blob", "HEAD:gradlew"]
        )
        gradlew.write_bytes(blob)
        data = gradlew.read_bytes()
        worktree_blob = git_value(["git", "-C", str(COOJA), "hash-object", "gradlew"])

    if head_blob != worktree_blob or b"\r\n" in data:
        stop("gradlew is not identical to HEAD with LF endings")
        return False

    print("gradlew content/LF: PASS")
    return True


def main() -> None:
    print("=" * 68)
    print("COOJA-COMPOSE-INFRA")
    print("=" * 68)

    for path in (LOCK, COMPOSE, SCENARIO):
        if not path.is_file():
            stop(f"missing required file: {path}")
            return

    if not ensure_gradlew_lf():
        return

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    image = lock.get("docker_image")
    if not isinstance(image, str) or "@sha256:" not in image:
        stop("toolchain lock does not contain an immutable docker image")
        return

    compose_text = COMPOSE.read_text(encoding="utf-8")
    if image not in compose_text:
        stop("compose.yaml image does not match toolchain-lock.json")
        return

    config = run([
        "docker", "compose",
        "-f", str(COMPOSE),
        "config",
    ])
    if config.returncode != 0:
        stop("docker compose config failed")
        return

    if RESULTS.exists():
        shutil.rmtree(RESULTS)
    RESULTS.mkdir(parents=True, exist_ok=False)

    records = []
    for number in (1, 2):
        print(f"\n=== COMPOSE COOJA RUN {number}/2 ===")
        p = run([
            "docker", "compose",
            "-f", str(COMPOSE),
            "run", "--rm", "-T",
            "cooja",
            "run",
            "--args=--no-gui ../../tests/07-simulation-base/02-ringbufindex.csc",
        ])

        log = RESULTS / f"run-{number}.log"
        log.write_text(p.stdout, encoding="utf-8", newline="\n")
        test_ok = "TEST OK" in p.stdout
        records.append({
            "run": number,
            "exit_code": p.returncode,
            "test_ok": test_ok,
            "log": log.relative_to(ROOT).as_posix(),
            "log_sha256": sha256(log),
        })

        if p.returncode != 0 or not test_ok:
            stop(f"compose Cooja run {number} failed")
            return

    manifest = {
        "schema_version": 1,
        "experiment": "COOJA-COMPOSE-INFRA-1",
        "result": "PASS",
        "contiki_ng_commit": lock.get("contiki_ng_commit"),
        "cooja_commit": lock.get("cooja_commit"),
        "docker_image": image,
        "compose_file": COMPOSE.relative_to(ROOT).as_posix(),
        "compose_sha256": sha256(COMPOSE),
        "toolchain_lock": LOCK.relative_to(ROOT).as_posix(),
        "toolchain_lock_sha256": sha256(LOCK),
        "scenario": SCENARIO.relative_to(ROOT).as_posix(),
        "scenario_sha256": sha256(SCENARIO),
        "runs": records,
    }
    manifest_path = RESULTS / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("\n" + manifest_path.read_text(encoding="utf-8"))
    print("COOJA-COMPOSE-INFRA-1: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        stop(f"{type(exc).__name__}: {exc}")
