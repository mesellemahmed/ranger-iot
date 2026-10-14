#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "experiments/cooja/compose.yaml"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    print()
    print("$", " ".join(args))
    result = subprocess.run(
        args,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    if result.stdout.strip():
        print(result.stdout.rstrip())
    return result


def main() -> None:
    scenario = ROOT / "experiments/cooja/scenarios/generated/ranger-core-5nodes-onehop.csc"
    if not scenario.is_file():
        print("FAIL: generated scenario missing")
        return

    base = ["docker", "compose", "-f", str(COMPOSE)]
    up = run(base + ["up", "-d", "--build", "--force-recreate", "cooja-gui"])
    if up.returncode != 0:
        print("RANGER-GUI-RESTART: FAIL")
        return

    time.sleep(15)
    run(base + ["ps", "-a", "cooja-gui"])
    inspect = run([
        "docker", "inspect", "ranger-cooja-gui",
        "--format", "status={{.State.Status}} running={{.State.Running}} exit={{.State.ExitCode}}"
    ])

    if "running=true" not in inspect.stdout.lower():
        run(base + ["logs", "--no-color", "--tail", "200", "cooja-gui"])
        print("RANGER-GUI-RESTART: FAIL")
        return

    print("RANGER-GUI-RESTART: PASS")
    print("Open: http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RANGER-GUI-RESTART: ERROR: {type(exc).__name__}: {exc}")
        print("Git Bash remains open.")
