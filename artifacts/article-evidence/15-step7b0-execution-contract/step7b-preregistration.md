# RANGER-IoT — STEP 7B Preregistration

## Goal

External-validity testing across topology and scale.

## Python model layer

- Topologies: line, star, balanced-tree, grid.
- Sizes: 8, 16, 32, 64 nodes.
- Protocols: Static, Recovery, Adaptive-V2.
- 20 independent deterministic non-consecutive seeds.
- Paired comparisons by seed.

## Cooja layer

- Keep the currently validated 8-node embedded scale.
- Add topology/layout robustness without pretending current embedded code already scales arbitrarily.

## Statistical contract

- Holm multiplicity correction.
- Paired 95% bootstrap confidence intervals.
- No optional stopping.
- No extra seeds merely to obtain significance.
