# RANGER-STATIC experiment integration

This checkpoint integrates `ranger-static` into the deterministic experiment
and campaign runners without changing the RANGER coding or dissemination core.

## Configuration

Each run can select a fixed coding profile:

```yaml
protocol: ranger-static
ranger_data_fragments: 3
ranger_total_fragments: 5
ranger_capsule_overhead_bytes: 0
```

The current simulator models an ideal systematic MDS-style erasure code. A
capsule is considered decodable after any `k` distinct fragments out of `n`
have arrived. This is an algorithmic abstraction; it does not model the CPU
cost of a concrete Reed-Solomon implementation.

## Reported RANGER metrics

RANGER runs add the following protocol-level fields to `summary.json` and
`aggregate.csv`:

- `capsule_payload_bytes`
- `data_fragments`
- `total_fragments`
- `fragment_payload_bytes`
- `flood_injections`

Network-level metrics remain shared with all baselines, including physical
transmissions, manager transmissions, bytes sent, packet drops, convergence,
and T50/T95/T100.

## Smoke campaign

`step5b-ranger-static-suite-smoke.yaml` compares:

- SKDC
- LKH-UNICAST
- LKH-FLOOD
- RANGER-STATIC

across line, star, balanced-tree, and grid topologies, group sizes 4/8/16,
loss rates 0%/10%, and seeds 11/29. The Cartesian product contains 192 runs.

The smoke campaign is for integration and behavioral validation only. It is
not a statistically powered scientific evaluation.
