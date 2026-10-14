#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "experiments/cooja/compose.yaml"
GENERATOR = ROOT / "experiments/cooja/scripts/generate_ranger_rpl_line_scenario.py"

SCENARIO_LINUX = (
    "/workspace/experiments/cooja/scenarios/generated/"
    "ranger-rpl-line-8nodes.csc"
)


def capture(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    print()
    print("$", " ".join(args))
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
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
    generated = subprocess.run(
        ["python", str(GENERATOR)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    print(generated.stdout.rstrip())

    if "RANGER-RPL-SCENARIO-GENERATE: PASS" not in generated.stdout:
        print("RANGER-RPL-GUI: FAIL — scenario generation")
        return

    env = dict(os.environ)
    env["RANGER_COOJA_SCENARIO"] = SCENARIO_LINUX

    base = ["docker", "compose", "-f", str(COMPOSE)]

    up = capture(
        base + ["up", "-d", "--build", "--force-recreate", "cooja-gui"],
        env,
    )

    if up.returncode != 0:
        print("RANGER-RPL-GUI: FAIL — compose up")
        return

    time.sleep(15)

    ps = capture(base + ["ps", "-a", "cooja-gui"], env)

    inspect = capture(
        [
            "docker", "inspect", "ranger-cooja-gui",
            "--format",
            "status={{.State.Status}} running={{.State.Running}} exit={{.State.ExitCode}}",
        ],
        env,
    )

    if "running=true" not in inspect.stdout.lower():
        capture(base + ["logs", "--no-color", "--tail", "250", "cooja-gui"], env)
        print("RANGER-RPL-GUI: FAIL — container not running")
        return

    print()
    print("RANGER-RPL-GUI: PASS")
    print("Scenario: ranger-rpl-line-8nodes.csc")
    print("Open: http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale")
    print("Git Bash remains open.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RANGER-RPL-GUI: ERROR: {type(exc).__name__}: {exc}")
        print("Git Bash remains open.")
