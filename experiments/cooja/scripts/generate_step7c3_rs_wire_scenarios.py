from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path.cwd()

BASE = ROOT / "experiments/cooja/scenarios/generated/ranger-static-coded-rpl-line-8nodes.csc"

BASE_MANIFEST = (
    ROOT / "experiments/cooja/scenarios/generated/ranger-static-coded-rpl-line-8nodes.manifest.json"
)

OUT_DIR = ROOT / "experiments/cooja/scenarios/generated"

EVIDENCE = ROOT / "artifacts/article-evidence/23-step7c3-cooja-real-rs-wire"

ASSERTION = "experiments/cooja/tests/ranger-rs-wire-rpl-line-assert.js"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(
    mode: int,
    output: Path,
) -> dict[str, object]:
    source = BASE.read_text(encoding="utf-8")

    required = [
        ("ranger-static-coded-rpl/ranger-static-coded-rpl.c"),
        ("ranger-static-coded-rpl.cooja"),
        ("ranger-static-coded-rpl-line-assert.js"),
    ]

    for token in required:
        if token not in source:
            raise RuntimeError(f"base scenario missing {token}")

    generated = source.replace(
        "ranger-static-coded-rpl",
        "ranger-rs-wire-rpl",
    )

    command_token = "TARGET=cooja</commands>"

    replacement = f"TARGET=cooja RANGER_RS_WIRE_MODE={mode}</commands>"

    if generated.count(command_token) != 1:
        raise RuntimeError("unexpected Cooja build-command shape")

    generated = generated.replace(
        command_token,
        replacement,
        1,
    )

    output.write_text(
        generated,
        encoding="utf-8",
        newline="\n",
    )

    checks = {
        "app_source": ("apps/ranger-rs-wire-rpl/ranger-rs-wire-rpl.c") in generated,
        "app_binary": "ranger-rs-wire-rpl.cooja" in generated,
        "assertion": ("ranger-rs-wire-rpl-line-assert.js") in generated,
        "mode": (f"RANGER_RS_WIRE_MODE={mode}") in generated,
    }

    if not all(checks.values()):
        raise RuntimeError(f"scenario contract failed: {checks}")

    return {
        "mode": mode,
        "scenario": output.relative_to(ROOT).as_posix(),
        "sha256": sha256(output),
        "checks": checks,
    }


def main() -> None:
    EVIDENCE.mkdir(
        parents=True,
        exist_ok=True,
    )

    base_manifest = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))

    if base_manifest.get("direct_root_to_farthest") is not False:
        raise RuntimeError("base line scenario is not validated as multi-hop")

    scenarios = [
        build(
            0,
            OUT_DIR / ("ranger-rs-wire-rpl-line-8nodes-noloss.csc"),
        ),
        build(
            1,
            OUT_DIR / ("ranger-rs-wire-rpl-line-8nodes-controlled-loss.csc"),
        ),
    ]

    manifest = {
        "schema_version": 1,
        "step": "STEP7C3_COOJA_REAL_RS_WIRE",
        "base_scenario": BASE.relative_to(ROOT).as_posix(),
        "base_scenario_sha256": sha256(BASE),
        "base_direct_root_to_farthest": False,
        "mote_count": 8,
        "topology": "validated-line-multihop",
        "assertion_script": ASSERTION,
        "modes": {
            "0": "no-loss",
            "1": ("deterministic-application-level-fragment-omission"),
        },
        "scenarios": scenarios,
    }

    path = EVIDENCE / "step7c3-scenario-manifest.json"

    path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
    )

    print()
    print("STEP7C3_SCENARIO_GENERATION=PASS")


if __name__ == "__main__":
    main()
