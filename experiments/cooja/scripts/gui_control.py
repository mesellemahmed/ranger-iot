#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LOCK = ROOT / "experiments" / "cooja" / "config" / "toolchain-lock.json"
BASE = ROOT / "experiments" / "cooja" / "compose.yaml"
COOJA = ROOT / "third_party" / "contiki-ng" / "tools" / "cooja"

URL = "http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    print()
    print("$", " ".join(args))
    p = subprocess.run(
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
    if p.stdout.strip():
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
        return None
    return p.stdout.strip()


def ensure_gradlew_lf() -> bool:
    gradlew = COOJA / "gradlew"
    if not gradlew.is_file():
        print("ERROR: missing Cooja gradlew")
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
        worktree_blob = git_value(
            ["git", "-C", str(COOJA), "hash-object", "gradlew"]
        )

    ok = head_blob == worktree_blob and b"\r\n" not in data
    print("gradlew content/LF:", "PASS" if ok else "FAIL")
    return ok


def compose_args() -> list[str]:
    return [
        "docker",
        "compose",
        "-f",
        str(BASE),
    ]


def load_env() -> tuple[dict[str, str], str] | None:
    if not LOCK.is_file():
        print("ERROR: missing toolchain lock")
        return None

    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    image = lock.get("docker_image")

    if not isinstance(image, str) or "@sha256:" not in image:
        print("ERROR: invalid docker_image in toolchain lock")
        return None

    env = dict(os.environ)
    env["COOJA_BASE_IMAGE"] = image
    return env, image


def wait_for_gui(seconds: int = 90) -> bool:
    deadline = time.time() + seconds

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:6080/vnc.html",
                timeout=2,
            ) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass

        time.sleep(2)

    return False


def start() -> None:
    loaded = load_env()
    if loaded is None:
        return

    env, image = loaded

    if not ensure_gradlew_lf():
        return

    print("=" * 72)
    print("COOJA GUI — DOCKER COMPOSE")
    print("=" * 72)
    print("Pinned base:", image)
    print("Cooja compose SHA256:", sha256(BASE))

    config = run(compose_args() + ["config"], env)
    if config.returncode != 0:
        print("COOJA-GUI: FAIL — docker compose config")
        return

    build = run(compose_args() + ["build", "cooja-gui"], env)
    if build.returncode != 0:
        print("COOJA-GUI: FAIL — image build")
        return

    up = run(compose_args() + ["up", "-d", "cooja-gui"], env)
    if up.returncode != 0:
        print("COOJA-GUI: FAIL — container start")
        return

    print()
    print("Waiting for noVNC/Cooja GUI...")

    if wait_for_gui():
        print()
        print("COOJA-GUI: PASS")
        print("Open this URL in your browser:")
        print(URL)
        print()
        print("The GUI container stays running.")
        print("Git Bash remains open.")
    else:
        print("COOJA-GUI: STARTED BUT WEB UI NOT READY")
        logs(env)


def stop() -> None:
    loaded = load_env()
    if loaded is None:
        return
    env, _ = loaded
    run(compose_args() + ["stop", "cooja-gui"], env)
    print("COOJA-GUI: STOPPED")


def status() -> None:
    loaded = load_env()
    if loaded is None:
        return
    env, _ = loaded
    run(compose_args() + ["ps", "cooja-gui"], env)
    print("GUI URL:", URL)


def logs(env_override: dict[str, str] | None = None) -> None:
    if env_override is None:
        loaded = load_env()
        if loaded is None:
            return
        env, _ = loaded
    else:
        env = env_override

    run(
        compose_args()
        + ["logs", "--no-color", "--tail", "200", "cooja-gui"],
        env,
    )


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "start"

    if action == "start":
        start()
    elif action == "stop":
        stop()
    elif action == "status":
        status()
    elif action == "logs":
        logs()
    else:
        print("Usage: gui_control.py [start|stop|status|logs]")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"COOJA-GUI ERROR: {type(exc).__name__}: {exc}")
        print("Git Bash remains open.")
