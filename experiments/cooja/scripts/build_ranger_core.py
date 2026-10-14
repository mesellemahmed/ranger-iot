#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

COMPOSE = (
    ROOT
    / "experiments"
    / "cooja"
    / "compose.yaml"
)

APP = (
    ROOT
    / "experiments"
    / "cooja"
    / "apps"
    / "ranger-core"
)

OUTPUT = (
    APP
    / "build"
    / "cooja"
    / "ranger-core.cooja"
)


def main() -> None:
    print("=" * 72)
    print("RANGER-IoT — COOJA CORE BUILD")
    print("=" * 72)

    if not COMPOSE.is_file():
        print("FAIL: compose.yaml not found")
        return

    if not (APP / "Makefile").is_file():
        print("FAIL: ranger-core Makefile not found")
        return

    if not (APP / "ranger-core.c").is_file():
        print("FAIL: ranger-core.c not found")
        return

    command = [
        "docker",
        "compose",
        "-f",
        str(COMPOSE),
        "run",
        "--rm",
        "-T",

        # IMPORTANT:
        # Python passes this Linux container path directly
        # to Docker. Git Bash cannot rewrite it.
        "--workdir",
        "/workspace/experiments/cooja/apps/ranger-core",

        "--entrypoint",
        "make",

        "cooja",

        "TARGET=cooja",
        "ranger-core.cooja",
    ]

    print()
    print("Docker Compose command:")
    print(" ".join(command))
    print()

    result = subprocess.run(
        command,
        cwd=ROOT,
        shell=False,
    )

    print()

    if result.returncode != 0:
        print("=" * 72)
        print(
            "RANGER-CORE-BUILD: FAIL "
            f"(code={result.returncode})"
        )
        print("=" * 72)
        print("Git Bash remains open.")
        return

    if not OUTPUT.is_file():
        print("=" * 72)
        print("RANGER-CORE-BUILD: FAIL")
        print("Compilation returned success but binary was not found:")
        print(OUTPUT)
        print("=" * 72)
        return

    print("Generated:")
    print(
        OUTPUT.relative_to(ROOT).as_posix()
    )

    print(
        "Size:",
        OUTPUT.stat().st_size,
        "bytes",
    )

    print()
    print("=" * 72)
    print("RANGER-CORE-BUILD: PASS")
    print("=" * 72)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("=" * 72)
        print("RANGER-CORE-BUILD: ERROR")
        print(
            f"{type(exc).__name__}: {exc}"
        )
        print("Git Bash remains open.")
        print("=" * 72)
