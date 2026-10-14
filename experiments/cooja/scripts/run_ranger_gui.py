#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PREPARE = ROOT / "experiments/cooja/scripts/prepare_ranger_core_scenario.py"
RESTART = ROOT / "experiments/cooja/scripts/restart_ranger_gui.py"


def call(path: Path) -> str:
    result = subprocess.run(
        ["python", str(path)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    print(result.stdout.rstrip())
    return result.stdout


def main() -> None:
    out = call(PREPARE)
    if "RANGER-PREPARE: PASS" not in out:
        print("RANGER-GUI: FAIL — preparation")
        return

    out = call(RESTART)
    if "RANGER-GUI-RESTART: PASS" not in out:
        print("RANGER-GUI: FAIL — restart")
        return

    print("RANGER-GUI: PASS")
    print("Open: http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RANGER-GUI: ERROR: {type(exc).__name__}: {exc}")
        print("Git Bash remains open.")
