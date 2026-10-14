# RANGER-IoT — STEP 7A Scientific Claim Matrix

Prespecified stopping point: 30 paired seeds per protocol/TX.

| Claim comparison | TX | Mean Δ reconstructed | 95% paired bootstrap CI | W/L/T | Holm p | Completion RD | Completion Holm p | Interpretation | Additional same-scenario seeds? |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| recovery vs static | 0.30 | +0.300 | [+0.100, +0.500] | 10/1/19 | 0.0351562 | +0.300 | 0.0351562 | SUPPORTED_FOR_CURRENT_SCENARIO | No — current-scenario statistical hardening complete |
| recovery vs static | 0.20 | +1.933 | [+1.467, +2.433] | 25/0/5 | 3.57628e-07 | +0.433 | 0.00146484 | SUPPORTED_FOR_CURRENT_SCENARIO | No — current-scenario statistical hardening complete |
| adaptive-v2 vs static | 0.30 | +0.367 | [+0.200, +0.533] | 11/0/19 | 0.00390625 | +0.367 | 0.00390625 | SUPPORTED_FOR_CURRENT_SCENARIO | No — current-scenario statistical hardening complete |
| adaptive-v2 vs static | 0.20 | +1.733 | [+1.233, +2.267] | 24/1/5 | 7.7486e-06 | +0.400 | 0.00244141 | SUPPORTED_FOR_CURRENT_SCENARIO | No — current-scenario statistical hardening complete |
| adaptive-v2 vs recovery | 0.30 | +0.067 | [+0.000, +0.167] | 2/0/28 | 1 | +0.067 | 1 | UNCERTAIN_OR_SMALL_EFFECT | No — report uncertainty/effect honestly |
| adaptive-v2 vs recovery | 0.20 | -0.200 | [-0.667, +0.267] | 11/12/7 | 1 | -0.033 | 1 | UNCERTAIN_OR_SMALL_EFFECT | No — report uncertainty/effect honestly |

## Reviewer-attack status

- Small-sample attack: substantially reduced by 30 paired seeds per TX.
- Multiple-comparison attack: addressed with Holm correction.
- Effect-size attack: paired deltas, W/L/T and bootstrap confidence intervals retained.
- Optional-stopping attack: controlled by stopping at the prespecified 30 paired seeds.
- External-validity attack: NOT closed by STEP 7A; requires STEP 7B.
- Coding-realism attack: NOT closed by STEP 7A; requires STEP 7C.
- Formal-security attack: NOT closed by STEP 7A; requires STEP 7D.
