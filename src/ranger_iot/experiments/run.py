from __future__ import annotations

import argparse
from pathlib import Path

from ranger_iot.experiments.config import ExperimentConfig
from ranger_iot.experiments.runner import run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one deterministic RANGER-IoT experiment")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = ExperimentConfig.from_yaml(args.config)
    result = run_experiment(config, args.output)
    print(f"experiment_id={config.experiment_id}")
    print(f"protocol={config.protocol}")
    print(f"completed={result.summary['completed']}")
    print(f"output={result.output_dir}")


if __name__ == "__main__":
    main()
