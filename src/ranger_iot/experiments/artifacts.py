from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from ranger_iot.experiments.config import ExperimentConfig


def canonical_config_json(config: ExperimentConfig) -> str:
    return json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"


def config_sha256(config: ExperimentConfig) -> str:
    return hashlib.sha256(canonical_config_json(config).encode()).hexdigest()


def write_json(path: Path, data: Mapping[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(
    path: Path, fieldnames: tuple[str, ...], rows: Iterable[Mapping[str, object]]
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
