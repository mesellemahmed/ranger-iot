# Baseline Campaign v1

## Purpose

This campaign runner executes a deterministic Cartesian product of baseline
protocols and experiment parameters. It is intended to validate experimental
orchestration before larger scientific campaigns are introduced.

The first campaign compares:

- SKDC;
- LKH-UNICAST;
- LKH-FLOOD.

The initial topology is deliberately restricted to `line`. Additional topology
families are introduced in a later checkpoint so that campaign orchestration
and topology effects are not debugged at the same time.

## Reproducibility

For a fixed repository revision, campaign configuration, and seed set, the
runner must produce byte-identical artifacts.

No wall-clock timestamp is embedded in generated files.

The output layout is:

```text
campaign-output/
├── campaign.json
├── campaign_summary.json
├── aggregate.csv
└── runs/
    ├── <deterministic-run-id>/
    │   ├── config.json
    │   ├── events.csv
    │   ├── nodes.csv
    │   └── summary.json
    └── ...
```

## Smoke matrix

`step4e-baseline-line-smoke.yaml` executes:

- 3 protocols;
- 1 topology;
- 3 group sizes: 4, 8, 16;
- 2 packet-loss rates: 0% and 10%;
- 2 deterministic seeds.

This yields 36 runs.

The smoke campaign is not a publication experiment and must not be interpreted
as statistical evidence. Its role is to validate orchestration, artifact
generation, deterministic ordering, and aggregation.

## Execution

```bash
docker compose run --rm ranger \
  python -m ranger_iot.experiments.campaign \
  --config experiments/configs/step4e-baseline-line-smoke.yaml \
  --output experiments/results/step4e/baseline-line-smoke
```

## Aggregate metrics

The aggregate CSV records protocol, topology, group size, packet-loss rate,
seed, convergence status, logical ciphertext count, routed/flood injection
counts, physical transmissions, manager transmissions, bytes sent, drops, and
T50/T95/T100.

The runner intentionally does not calculate scientific means, confidence
intervals, significance tests, or effect sizes. Those belong to the later
analysis stage after the campaign design has been frozen.
