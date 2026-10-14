# Experimental Runner v1

The v1 runner executes one deterministic rekey experiment and writes four stable artifacts:

- `config.json`: normalized validated configuration;
- `events.csv`: link-layer transmit, delivery, and drop trace;
- `nodes.csv`: final per-node state;
- `summary.json`: protocol, convergence, and network metrics.

No wall-clock timestamp is written. Two executions with the same configuration and software revision must produce byte-identical artifacts.

## Scope

The initial runner intentionally supports only:

- `skdc`;
- `lkh-unicast`;
- `lkh-flood`;
- line topology;
- Bernoulli packet loss;
- constant per-hop delay;
- one rekey operation per run.

This is a validation runner, not the final experimental campaign framework. Additional topologies, burst-loss models, batch execution, statistical aggregation, and RANGER variants are introduced only after the two baselines are frozen.

## Commands

```bash
python -m ranger_iot.experiments.run \
  --config experiments/configs/step4c-skdc.yaml \
  --output experiments/results/step4c/skdc

python -m ranger_iot.experiments.run \
  --config experiments/configs/step4c-lkh-unicast.yaml \
  --output experiments/results/step4c/lkh-unicast
```

The output directory must be empty. Existing artifacts are never overwritten silently.
