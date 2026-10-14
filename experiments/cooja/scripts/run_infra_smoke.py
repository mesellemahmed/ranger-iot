from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path.cwd().resolve()

LOCK = (
    ROOT
    / "experiments"
    / "cooja"
    / "config"
    / "toolchain-lock.json"
)

SCENARIO = (
    ROOT
    / "third_party"
    / "contiki-ng"
    / "tests"
    / "07-simulation-base"
    / "02-ringbufindex.csc"
)

RESULTS = (
    ROOT
    / "experiments"
    / "cooja"
    / "results"
    / "step6a1-infra-smoke"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)

            if not block:
                break

            h.update(block)

    return h.hexdigest()


def fail(message: str) -> bool:
    print()
    print("COOJA-INFRA-1: FAIL")
    print(message)
    return False


def load_lock() -> dict:
    return json.loads(
        LOCK.read_text(encoding="utf-8")
    )


def docker_image(lock: dict) -> str | None:
    value = lock.get("docker_image")

    if isinstance(value, str):
        return value

    docker = lock.get("docker")

    if isinstance(docker, dict):
        value = docker.get("digest")

        if isinstance(value, str):
            return value

    return None


def run_once(
    *,
    image: str,
    number: int,
) -> tuple[bool, dict]:
    print()
    print("=" * 60)
    print(f"COOJA RUN {number}")
    print("=" * 60)

    log_path = RESULTS / f"run-{number}.log"

    mount_arg = (
        f"type=bind,"
        f"source={ROOT},"
        f"target=/workspace"
    )

    command = [
        "docker",
        "run",
        "--rm",
        "--mount",
        mount_arg,
        "--workdir",
        "/workspace/third_party/contiki-ng/tools/cooja",
        "--entrypoint",
        "/bin/bash",
        image,

        # Important:
        # bash executes gradlew directly as a file.
        # No -c and therefore no command-string parsing.
        "/workspace/third_party/contiki-ng/tools/cooja/gradlew",

        "run",

        (
            "--args=--no-gui "
            "../../tests/07-simulation-base/"
            "02-ringbufindex.csc"
        ),
    ]

    print("Starting Docker/Cooja...")

    try:
        process = subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    except FileNotFoundError:
        return False, {
            "error": "docker executable not found"
        }

    log_path.write_text(
        process.stdout,
        encoding="utf-8",
        newline="\n",
    )

    output_lines = process.stdout.splitlines()

    print()
    print("--- last Cooja lines ---")

    for line in output_lines[-30:]:
        print(line)

    test_ok = "TEST OK" in process.stdout

    record = {
        "run": number,
        "exit_code": process.returncode,
        "test_ok": test_ok,
        "log": str(
            log_path.relative_to(ROOT)
        ),
        "log_sha256": sha256(log_path),
    }

    if process.returncode != 0:
        print()
        print(
            f"Run {number}: Docker exit code "
            f"{process.returncode}"
        )

        return False, record

    if not test_ok:
        print()
        print(
            f"Run {number}: TEST OK not found"
        )

        return False, record

    print()
    print(f"Run {number}: PASS")

    return True, record


def main() -> None:
    print("=" * 60)
    print("COOJA-INFRA-1")
    print("=" * 60)

    print(f"Repository : {ROOT}")
    print(f"Lock       : {LOCK}")
    print(f"Scenario   : {SCENARIO}")

    if not LOCK.is_file():
        fail(
            "Missing toolchain-lock.json"
        )
        return

    if not SCENARIO.is_file():
        fail(
            "Official Cooja smoke scenario "
            "was not found."
        )

        print()
        print("Available matching scenarios:")

        base = (
            ROOT
            / "third_party"
            / "contiki-ng"
            / "tests"
        )

        matches = list(
            base.rglob("*ringbuf*.csc")
        )

        for match in matches[:20]:
            print(
                match.relative_to(ROOT)
            )

        return

    lock = load_lock()
    image = docker_image(lock)

    if not image:
        fail(
            "Docker image/digest is missing "
            "from toolchain-lock.json"
        )
        return

    if "@sha256:" not in image:
        fail(
            "The Docker image is not pinned "
            f"by digest: {image}"
        )
        return

    print(f"Docker     : {image}")

    if RESULTS.exists():
        shutil.rmtree(RESULTS)

    RESULTS.mkdir(
        parents=True,
        exist_ok=True,
    )

    ok1, run1 = run_once(
        image=image,
        number=1,
    )

    if not ok1:
        fail(
            "First headless Cooja run failed. "
            "Git Bash remains open."
        )
        return

    ok2, run2 = run_once(
        image=image,
        number=2,
    )

    if not ok2:
        fail(
            "Second headless Cooja run failed. "
            "Git Bash remains open."
        )
        return

    manifest = {
        "schema_version": 1,
        "experiment": "COOJA-INFRA-1",
        "result": "PASS",
        "purpose": (
            "Dockerized Cooja headless "
            "infrastructure validation"
        ),
        "contiki_ng_commit": (
            lock.get("contiki_ng_commit")
        ),
        "cooja_commit": (
            lock.get("cooja_commit")
        ),
        "docker_image": image,
        "scenario": str(
            SCENARIO.relative_to(ROOT)
        ),
        "scenario_sha256": sha256(
            SCENARIO
        ),
        "runs": [
            run1,
            run2,
        ],
    }

    manifest_path = (
        RESULTS / "manifest.json"
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)

    print(
        manifest_path.read_text(
            encoding="utf-8"
        )
    )

    print("COOJA-INFRA-1: PASS")


if __name__ == "__main__":
    main()
