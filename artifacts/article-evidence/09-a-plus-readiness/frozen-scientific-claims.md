# RANGER-IoT Scientific Evidence Freeze

This file is generated directly from the authoritative Cooja campaign aggregates.

## Grouped results

| Protocol | TX | Complete | Completion | Mean reconstructed | Range |
|---|---:|---:|---:|---:|---:|
| static | 0.50 | 10/10 | 1.000 | 6.000/6 | 6-6 |
| static | 0.30 | 2/10 | 0.200 | 5.200/6 | 5-6 |
| static | 0.20 | 0/10 | 0.000 | 3.600/6 | 2-5 |
| recovery | 0.50 | 10/10 | 1.000 | 6.000/6 | 6-6 |
| recovery | 0.30 | 8/10 | 0.800 | 5.800/6 | 5-6 |
| recovery | 0.20 | 4/10 | 0.400 | 5.100/6 | 3-6 |
| adaptive_v2 | 0.50 | 10/10 | 1.000 | 6.000/6 | 6-6 |
| adaptive_v2 | 0.30 | 10/10 | 1.000 | 6.000/6 | 6-6 |
| adaptive_v2 | 0.20 | 3/10 | 0.300 | 4.900/6 | 4-6 |

## Seed-paired comparisons

| Left vs right | TX | Mean Δ reconstructed | Better / Equal / Worse | Sign p | Left-only complete / Right-only complete | McNemar exact p |
|---|---:|---:|---:|---:|---:|---:|
| recovery vs static | 0.50 | +0.000 | 0 / 10 / 0 | 1.000000 | 0 / 0 | 1.000000 |
| recovery vs static | 0.30 | +0.600 | 7 / 2 / 1 | 0.070312 | 7 / 1 | 0.070312 |
| recovery vs static | 0.20 | +1.500 | 6 / 4 / 0 | 0.031250 | 4 / 0 | 0.125000 |
| adaptive_v2 vs static | 0.50 | +0.000 | 0 / 10 / 0 | 1.000000 | 0 / 0 | 1.000000 |
| adaptive_v2 vs static | 0.30 | +0.800 | 8 / 2 / 0 | 0.007812 | 8 / 0 | 0.007812 |
| adaptive_v2 vs static | 0.20 | +1.300 | 8 / 1 / 1 | 0.039062 | 3 / 0 | 0.250000 |
| adaptive_v2 vs recovery | 0.50 | +0.000 | 0 / 10 / 0 | 1.000000 | 0 / 0 | 1.000000 |
| adaptive_v2 vs recovery | 0.30 | +0.200 | 2 / 8 / 0 | 0.500000 | 2 / 0 | 0.500000 |
| adaptive_v2 vs recovery | 0.20 | -0.200 | 4 / 2 / 4 | 1.000000 | 2 / 3 | 1.000000 |

## Claim boundary

The comparative claim is restricted to the measured 8-node Cooja/RPL-Lite environment, 3-of-5 coding, post-bootstrap TX degradation, and seeds 201-210.
