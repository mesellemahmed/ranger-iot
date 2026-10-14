#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "experiments/cooja/scenarios/config/ranger-core-5nodes-onehop.json"
OUTPUT = ROOT / "experiments/cooja/scenarios/generated/ranger-core-5nodes-onehop.csc"
MANIFEST = ROOT / "experiments/cooja/scenarios/generated/ranger-core-5nodes-onehop.manifest.json"


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
    add_text(simulation, "speedlimit", "1.0")
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
    add_text(events, "logoutput", "40000")

    motetype = ET.SubElement(simulation, "motetype")
    motetype.text = "\norg.contikios.cooja.contikimote.ContikiMoteType\n"
    add_text(motetype, "description", "RANGER Core Mote")
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
        ET.SubElement(pos, "pos", {"x": str(mote_cfg["x"]), "y": str(mote_cfg["y"])})

        mote_id = ET.SubElement(mote, "interface_config")
        mote_id.text = "\norg.contikios.cooja.contikimote.interfaces.ContikiMoteID\n"
        add_text(mote_id, "id", str(mote_cfg["id"]))

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
    ET.SubElement(visualizer, "bounds", {"x": "0", "y": "0", "height": "650", "width": "850", "z": "1"})

    log_listener = ET.SubElement(simconf, "plugin")
    log_listener.text = "\norg.contikios.cooja.plugins.LogListener\n"
    lcfg = ET.SubElement(log_listener, "plugin_config")
    ET.SubElement(lcfg, "filter")
    ET.SubElement(lcfg, "formatted_time")
    ET.SubElement(lcfg, "coloring")
    ET.SubElement(log_listener, "bounds", {"x": "850", "y": "0", "height": "420", "width": "720", "z": "2"})

    timeline = ET.SubElement(simconf, "plugin")
    timeline.text = "\norg.contikios.cooja.plugins.TimeLine\n"
    tcfg = ET.SubElement(timeline, "plugin_config")
    for index in range(len(cfg["motes"])):
        add_text(tcfg, "mote", str(index))
    add_text(tcfg, "showRadioRXTX", "true")
    add_text(tcfg, "showRadioHW", "true")
    add_text(tcfg, "showLEDs", "true")
    add_text(tcfg, "showLogOutput", "false")
    ET.SubElement(timeline, "bounds", {"x": "0", "y": "650", "height": "300", "width": "1570", "z": "3"})

    radio_logger = ET.SubElement(simconf, "plugin")
    radio_logger.text = "\norg.contikios.cooja.plugins.RadioLogger\n"
    rcfg = ET.SubElement(radio_logger, "plugin_config")
    add_text(rcfg, "split", "256")
    ET.SubElement(rcfg, "formatted_time")
    ET.SubElement(rcfg, "analyzers", {"name": "6lowpan-pcap"})
    ET.SubElement(radio_logger, "bounds", {"x": "850", "y": "420", "height": "230", "width": "720", "z": "4"})

    ET.indent(simconf, space="  ")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(simconf).write(OUTPUT, encoding="utf-8", xml_declaration=True)

    parsed = ET.parse(OUTPUT)
    ids = [int(e.text) for e in parsed.findall(".//interface_config/id")]
    expected_ids = [m["id"] for m in cfg["motes"]]
    if ids != expected_ids:
        raise RuntimeError(f"mote ids mismatch: {ids} != {expected_ids}")

    manifest = {
        "schema_version": 1,
        "scenario_id": cfg["scenario_id"],
        "generator": "experiments/cooja/scripts/generate_ranger_core_scenario.py",
        "source_config": "experiments/cooja/scenarios/config/ranger-core-5nodes-onehop.json",
        "generated_scenario": "experiments/cooja/scenarios/generated/ranger-core-5nodes-onehop.csc",
        "config_sha256": sha256(CONFIG),
        "scenario_sha256": sha256(OUTPUT),
        "random_seed": cfg["random_seed"],
        "mote_count": len(cfg["motes"]),
        "mote_ids": expected_ids,
        "expected": cfg["expected"],
        "generation_policy": "generated from versioned code/config; no manual GUI creation",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    print("Generated:", OUTPUT.relative_to(ROOT).as_posix())
    print("Manifest :", MANIFEST.relative_to(ROOT).as_posix())
    print("Motes    :", expected_ids)
    print("SHA256   :", manifest["scenario_sha256"])
    print("RANGER-SCENARIO-GENERATE: PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RANGER-SCENARIO-GENERATE: FAIL: {type(exc).__name__}: {exc}")
