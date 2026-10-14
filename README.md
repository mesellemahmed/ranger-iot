# RANGER-IoT

**Resilient Adaptive Network Group Epoch Rekeying for Constrained IoT Networks**

RANGER-IoT is a research-grade implementation and experimentation framework for resilient group rekeying in constrained IoT networks. The project studies how authenticated epoch updates can be disseminated over lossy multi-hop networks while reducing Group Manager load and preserving revocation safety.

## Research scope

The repository is structured around three validation layers:

1. A deterministic discrete-event simulator for algorithmic evaluation and large-scale parameter sweeps.
2. A Contiki-NG/Cooja implementation for IEEE 802.15.4/6LoWPAN experiments.
3. Tamarin models for formal security analysis of epoch authenticity, replay resistance, recovery authenticity, and revocation safety.

The first implementation milestone focuses on reproducible infrastructure and baseline correctness before protocol optimization.

## Repository layout

```text
ranger-iot/
├── analysis/                 Result aggregation and statistical analysis
├── experiments/
│   ├── configs/              Versioned experiment configurations
│   └── results/              Generated experiment outputs
├── firmware/contiki-ng/      Contiki-NG implementation
├── formal/tamarin/           Formal security models
├── scripts/                  CI and execution scripts
├── src/ranger_iot/           Python research package
├── tests/                    Unit and integration tests
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── run.sh                    Single project entry point
```

## Prerequisites

- Docker Engine 24+
- Docker Compose v2
- Bash

No host Python environment is required.

## Quick start

Run the complete reproducibility gate:

```bash
./run.sh
```

This command builds the Docker image and executes formatting checks, linting, type checking, and the test suite inside the container.

Useful commands:

```bash
./run.sh build
./run.sh test
./run.sh lint
./run.sh typecheck
./run.sh check
./run.sh shell
./run.sh down
./run.sh clean
```

## Reproducibility policy

- All experiments must run inside Docker.
- Every stochastic experiment must expose and persist its random seed.
- Raw outputs are immutable once used for a paper result.
- Aggregated results and figures must be generated from scripts committed to the repository.
- No manually edited result files or figures are accepted.
- Baseline implementations are frozen before RANGER-specific optimization starts.

## Current milestone

**Phase 2 / Stage 1 — repository and execution foundation**

Acceptance criteria:

- Docker image builds successfully.
- `./run.sh` is the only required entry point for local validation.
- Python package uses a `src/` layout and `pyproject.toml`.
- CI executes the same validation command as local development.
- Tests verify deterministic configuration behavior.

## License

No open-source license has been selected yet. Until a license is explicitly added, all rights are reserved by the copyright holders.

## Data and Code Availability

See [Data and Code Availability](docs/DATA_AVAILABILITY.md) for the exact scope of the distributed results, excluded historical traces, and validation limits.

For redistribution conditions, see [Licensing and Redistribution Status](docs/LICENSING_STATUS.md). Licensing review is pending.

## Distribution Status

**Private research release candidate — public
distribution not authorized.**

No public license has been selected or granted.
See [Licensing and Redistribution Status]
(docs/LICENSING_STATUS.md) and
[Data and Code Availability](docs/DATA_AVAILABILITY.md)
for the documented limitations.

Do not publish this snapshot until redistribution
rights have been reviewed and explicitly cleared.
