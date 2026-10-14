# STEP 5E — Publication-grade deterministic evaluation

The protocol core is frozen before this checkpoint.

## Main campaign

`step5e-publication-main.yaml` evaluates:

- 6 protocols
- 4 deterministic topology families
- group sizes 8, 16, 32, 64
- packet loss 0%, 5%, 10%, 20%, 30%, 40%
- 30 independent seeds

Total: **17,280 runs**.

## Scalability extension

`step5e-publication-scalability.yaml` evaluates group sizes 128 and 256,
loss levels 0%, 10%, and 20%, with 10 seeds.

Total: **1,440 runs**.

## Primary metrics

Use sender-side radio metrics as primary cost metrics:

- `radio_transmissions`
- `radio_bytes_sent`
- `manager_radio_transmissions`

Reliability/timeliness:

- completion rate
- convergence fraction
- T50 / T95 / T100

Link-attempt metrics remain diagnostics.

## Statistical analysis

Run:

```bash
python -m ranger_iot.analysis.publication   --aggregate <campaign>/aggregate.csv   --output <analysis-dir>
```

Outputs:

- `group_summary.csv`
- `paired_effects.csv`
- `analysis_manifest.json`

Completion rates use Wilson 95% intervals.
Continuous metrics use deterministic percentile-bootstrap 95% intervals.

Pairwise comparisons use matched seeds within the same topology, group size,
and loss level. `benefit_delta_mean` is oriented so that a positive value
always favors RANGER-ADAPTIVE.

The analysis emphasizes effect magnitude and uncertainty rather than relying
on p-values alone.

## Scope

This remains a deterministic graph-level wireless broadcast model with
receiver-specific losses. It does not model CSMA/CA, collisions, interference,
capture, duty cycling, or full IEEE 802.15.4 timing. Those effects belong to
the later Contiki-NG/Cooja validation.
