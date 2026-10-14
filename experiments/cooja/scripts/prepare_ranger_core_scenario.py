#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "experiments/cooja/scripts/generate_ranger_core_scenario.py"
SCENARIO = ROOT / "experiments/cooja/scenarios/generated/ranger-core-5nodes-onehop.csc"
MANIFEST = ROOT / "experiments/cooja/scenarios/generated/ranger-core-5nodes-onehop.manifest.json"
TEST_SCRIPT = ROOT / "experiments/cooja/tests/ranger-core-assert.js"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    result = subprocess.run(
        ["python", str(GENERATOR)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    print(result.stdout.rstrip())

    if "RANGER-SCENARIO-GENERATE: PASS" not in result.stdout:
        print("RANGER-PREPARE: FAIL — scenario generation")
        return

    tree = ET.parse(SCENARIO)
    root = tree.getroot()

    for plugin in list(root.findall("plugin")):
        if (plugin.text or "").strip() == "org.contikios.cooja.plugins.ScriptRunner":
            root.remove(plugin)

    plugin = ET.SubElement(root, "plugin")
    plugin.text = "\norg.contikios.cooja.plugins.ScriptRunner\n"
    cfg = ET.SubElement(plugin, "plugin_config")

    scriptfile = ET.SubElement(cfg, "scriptfile")
    scriptfile.text = "[CONFIG_DIR]/../../tests/ranger-core-assert.js"

    active = ET.SubElement(cfg, "active")
    active.text = "true"

    ET.SubElement(
        plugin,
        "bounds",
        {"x": "850", "y": "650", "height": "300", "width": "720", "z": "5"},
    )

    ET.indent(root, space="  ")
    tree.write(SCENARIO, encoding="utf-8", xml_declaration=True)
    ET.parse(SCENARIO)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["assertion_script"] = "experiments/cooja/tests/ranger-core-assert.js"
    manifest["assertion_script_sha256"] = sha256(TEST_SCRIPT)
    manifest["scenario_sha256"] = sha256(SCENARIO)
    manifest["script_runner_active"] = True
    manifest["headless_policy"] = (
        "same generated scenario and assertions are used for GUI and headless runs"
    )
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("RANGER-PREPARE: PASS")
    print("Scenario:", SCENARIO.relative_to(ROOT).as_posix())
    print("SHA256  :", manifest["scenario_sha256"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RANGER-PREPARE: ERROR: {type(exc).__name__}: {exc}")
        print("Git Bash remains open.")
