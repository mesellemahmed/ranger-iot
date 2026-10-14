#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "experiments/cooja/scenarios/config/ranger-static-coded-rpl-line-8nodes.json"
OUTPUT = ROOT / "experiments/cooja/scenarios/generated/ranger-static-coded-rpl-line-8nodes.csc"
MANIFEST = ROOT / "experiments/cooja/scenarios/generated/ranger-static-coded-rpl-line-8nodes.manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def add_text(parent: ET.Element, name: str, value: str) -> ET.Element:
    element = ET.SubElement(parent, name)
    element.text = value
    return element


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))

    simconf = ET.Element("simconf", {"version": "2023090101"})
    simulation = ET.SubElement(simconf, "simulation")

    add_text(simulation, "title", cfg["title"])
    add_text(simulation, "randomseed", str(cfg["random_seed"]))
    add_text(simulation, "motedelay_us", "1000000")

    radio_cfg = cfg["radio"]
    radiomedium = ET.SubElement(simulation, "radiomedium")
    radiomedium.text = "\n" + radio_cfg["medium"] + "\n"
    add_text(radiomedium, "transmitting_range", str(radio_cfg["transmitting_range"]))
    add_text(radiomedium, "interference_range", str(radio_cfg["interference_range"]))
    add_text(radiomedium, "success_ratio_tx", str(radio_cfg["success_ratio_tx"]))
    add_text(radiomedium, "success_ratio_rx", str(radio_cfg["success_ratio_rx"]))

    events = ET.SubElement(simulation, "events")
    add_text(events, "logoutput", "80000")

    motetype = ET.SubElement(simulation, "motetype")
    motetype.text = "\norg.contikios.cooja.contikimote.ContikiMoteType\n"
    add_text(motetype, "description", "RANGER Static Coded RPL Mote")
    add_text(motetype, "source", cfg["firmware"]["source"])
    add_text(motetype, "commands", cfg["firmware"]["build_command"])

    interfaces = [
        "org.contikios.cooja.interfaces.Position",
        "org.contikios.cooja.interfaces.Battery",
        "org.contikios.cooja.contikimote.interfaces.ContikiVib",
        "org.contikios.cooja.contikimote.interfaces.ContikiMoteID",
        "org.contikios.cooja.contikimote.interfaces.ContikiRS232",
        "org.contikios.cooja.contikimote.interfaces.ContikiBeeper",
        "org.contikios.cooja.interfaces.IPAddress",
        "org.contikios.cooja.contikimote.interfaces.ContikiRadio",
        "org.contikios.cooja.contikimote.interfaces.ContikiButton",
        "org.contikios.cooja.contikimote.interfaces.ContikiPIR",
        "org.contikios.cooja.contikimote.interfaces.ContikiClock",
        "org.contikios.cooja.contikimote.interfaces.ContikiLED",
        "org.contikios.cooja.contikimote.interfaces.ContikiCFS",
        "org.contikios.cooja.contikimote.interfaces.ContikiEEPROM",
        "org.contikios.cooja.interfaces.Mote2MoteRelations",
        "org.contikios.cooja.interfaces.MoteAttributes",
    ]

    for interface in interfaces:
        add_text(motetype, "moteinterface", interface)

    for mote_cfg in cfg["motes"]:
        mote = ET.SubElement(motetype, "mote")

        pos = ET.SubElement(mote, "interface_config")
        pos.text = "\norg.contikios.cooja.interfaces.Position\n"
        ET.SubElement(
            pos,
            "pos",
            {"x": str(mote_cfg["x"]), "y": str(mote_cfg["y"])},
        )

        mote_id = ET.SubElement(mote, "interface_config")
        mote_id.text = "\norg.contikios.cooja.contikimote.interfaces.ContikiMoteID\n"
        add_text(mote_id, "id", str(mote_cfg["id"]))

    # Visualizer is generated from code: GUI remains viewer-only.
    visualizer = ET.SubElement(simconf, "plugin")
    visualizer.text = "\norg.contikios.cooja.plugins.Visualizer\n"
    vcfg = ET.SubElement(visualizer, "plugin_config")
    add_text(vcfg, "moterelations", "true")
    for skin in [
        "org.contikios.cooja.plugins.skins.IDVisualizerSkin",
        "org.contikios.cooja.plugins.skins.GridVisualizerSkin",
        "org.contikios.cooja.plugins.skins.TrafficVisualizerSkin",
        "org.contikios.cooja.plugins.skins.UDGMVisualizerSkin",
        "org.contikios.cooja.plugins.skins.MoteTypeVisualizerSkin",
    ]:
        add_text(vcfg, "skin", skin)
    ET.SubElement(
        visualizer,
        "bounds",
        {"x": "0", "y": "0", "height": "600", "width": "1000", "z": "1"},
    )

    log_listener = ET.SubElement(simconf, "plugin")
    log_listener.text = "\norg.contikios.cooja.plugins.LogListener\n"
    lcfg = ET.SubElement(log_listener, "plugin_config")
    ET.SubElement(lcfg, "filter")
    ET.SubElement(lcfg, "formatted_time")
    ET.SubElement(lcfg, "coloring")
    ET.SubElement(
        log_listener,
        "bounds",
        {"x": "1000", "y": "0", "height": "420", "width": "800", "z": "2"},
    )

    timeline = ET.SubElement(simconf, "plugin")
    timeline.text = "\norg.contikios.cooja.plugins.TimeLine\n"
    tcfg = ET.SubElement(timeline, "plugin_config")
    for index in range(len(cfg["motes"])):
        add_text(tcfg, "mote", str(index))
    add_text(tcfg, "showRadioRXTX", "true")
    add_text(tcfg, "showRadioHW", "true")
    add_text(tcfg, "showLEDs", "true")
    add_text(tcfg, "showLogOutput", "false")
    ET.SubElement(
        timeline,
        "bounds",
        {"x": "0", "y": "600", "height": "340", "width": "1800", "z": "3"},
    )

    radio_logger = ET.SubElement(simconf, "plugin")
    radio_logger.text = "\norg.contikios.cooja.plugins.RadioLogger\n"
    rcfg = ET.SubElement(radio_logger, "plugin_config")
    add_text(rcfg, "split", "256")
    ET.SubElement(rcfg, "formatted_time")
    ET.SubElement(rcfg, "analyzers", {"name": "6lowpan-pcap"})
    ET.SubElement(
        radio_logger,
        "bounds",
        {"x": "1000", "y": "420", "height": "180", "width": "800", "z": "4"},
    )

    script_runner = ET.SubElement(simconf, "plugin")
    script_runner.text = "\norg.contikios.cooja.plugins.ScriptRunner\n"
    scfg = ET.SubElement(script_runner, "plugin_config")
    scriptfile = ET.SubElement(scfg, "scriptfile")
    scriptfile.text = "[CONFIG_DIR]/../../tests/ranger-static-coded-rpl-line-assert.js"
    active = ET.SubElement(scfg, "active")
    active.text = "true"
    ET.SubElement(
        script_runner,
        "bounds",
        {"x": "1000", "y": "600", "height": "340", "width": "800", "z": "5"},
    )

    ET.indent(simconf, space="  ")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(simconf).write(OUTPUT, encoding="utf-8", xml_declaration=True)

    parsed = ET.parse(OUTPUT)
    ids = [int(e.text) for e in parsed.findall(".//interface_config/id")]
    expected_ids = [m["id"] for m in cfg["motes"]]

    if ids != expected_ids:
        raise RuntimeError(f"mote ids mismatch: {ids} != {expected_ids}")

    positions = [(float(m["x"]), float(m["y"])) for m in cfg["motes"]]
    tx_range = float(cfg["radio"]["transmitting_range"])

    # Prove from geometry that the last node is not in direct GM range.
    root_x, root_y = positions[0]
    far_x, far_y = positions[-1]
    far_distance = ((far_x - root_x) ** 2 + (far_y - root_y) ** 2) ** 0.5
    if far_distance <= tx_range:
        raise RuntimeError(
            f"scenario is not multi-hop: far node distance={far_distance}, tx_range={tx_range}"
        )

    manifest = {
        "schema_version": 1,
        "scenario_id": cfg["scenario_id"],
        "generator": "experiments/cooja/scripts/generate_ranger_static_coded_rpl_line_scenario.py",
        "source_config": "experiments/cooja/scenarios/config/ranger-static-coded-rpl-line-8nodes.json",
        "generated_scenario": "experiments/cooja/scenarios/generated/ranger-static-coded-rpl-line-8nodes.csc",
        "assertion_script": "experiments/cooja/tests/ranger-static-coded-rpl-line-assert.js",
        "config_sha256": sha256(CONFIG),
        "scenario_sha256": sha256(OUTPUT),
        "assertion_script_sha256": sha256(
            ROOT / "experiments/cooja/tests/ranger-static-coded-rpl-line-assert.js"
        ),
        "random_seed": cfg["random_seed"],
        "mote_count": len(cfg["motes"]),
        "mote_ids": expected_ids,
        "root_to_farthest_distance": far_distance,
        "transmitting_range": tx_range,
        "direct_root_to_farthest": False,
        "expected": cfg["expected"],
        "coding": cfg.get("coding"),
        "generation_policy": "generated from versioned code/config; no manual GUI creation",
    }

    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("Generated :", OUTPUT.relative_to(ROOT).as_posix())
    print("Motes     :", expected_ids)
    print("Far dist  :", far_distance)
    print("TX range  :", tx_range)
    print("SHA256    :", manifest["scenario_sha256"])
    print("RANGER-STATIC-CODED-SCENARIO-GENERATE: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"RANGER-STATIC-CODED-SCENARIO-GENERATE: FAIL: "
            f"{type(exc).__name__}: {exc}"
        )
        print("Git Bash remains open.")
