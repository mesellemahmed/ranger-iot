#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "experiments/cooja/compose.yaml"
APP = ROOT / "experiments/cooja/apps/ranger-rpl-core"
OUTPUT = APP / "build/cooja/ranger-rpl-core.cooja"


def main() -> None:
    command = [
        "docker", "compose", "-f", str(COMPOSE),
        "run", "--rm", "-T",
        "--workdir", "/workspace/experiments/cooja/apps/ranger-rpl-core",
        "--entrypoint", "make",
        "cooja",
        "TARGET=cooja",
        "ranger-rpl-core.cooja",
    ]

    print("$", " ".join(command))
    result = subprocess.run(command, cwd=ROOT, shell=False)

    if result.returncode != 0:
        print(f"RANGER-RPL-BUILD: FAIL code={result.returncode}")
        return

    if not OUTPUT.is_file():
        print("RANGER-RPL-BUILD: FAIL — output missing")
        return

    print("Generated:", OUTPUT.relative_to(ROOT).as_posix())
    print("Size     :", OUTPUT.stat().st_size)
    print("RANGER-RPL-BUILD: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RANGER-RPL-BUILD: ERROR: {type(exc).__name__}: {exc}")
        print("Git Bash remains open.")
