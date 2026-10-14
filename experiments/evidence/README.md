# RANGER-IoT Reviewer Artifacts

This directory is the integrity and navigation registry for the
scientific artifacts produced by the RANGER-IoT project.

## Artifact preservation policy

All scientific results used during protocol development,
confirmatory evaluation, Cooja validation, statistical analysis,
figure generation, or publication are versioned in Git.

Raw per-run outputs are preserved. They are not replaced by
aggregated tables.

## Result roots

- `experiments/results/`
  Custom deterministic simulator campaigns, analyses and
  publication artifacts.

- `experiments/cooja/results/`
  Contiki-NG/Cooja validation results executed through the
  project's Docker Compose infrastructure.

## Integrity

Every result file is indexed in:

- `experiments/evidence/artifact-index.csv`
- `experiments/evidence/CHECKSUMS.sha256`
- `experiments/evidence/evidence-manifest.json`

SHA-256 checksums allow independent researchers to verify that result artifacts
have not changed.

## Campaign inventory

- `results`: 6 files
- `step4d`: 8 files
- `step4e`: 1452 files
- `step5b`: 1542 files
- `step5c`: 3846 files
- `step5d`: 2307 files
- `step5e`: 74895 files
- `step5e0`: 774 files
- `step5f2`: 15363 files
- `step5f3`: 80643 files
- `step5g`: 19 files

## Reproducibility

The Cooja toolchain is pinned by:

- Contiki-NG commit
- Cooja submodule commit
- immutable Docker image digest
- Java major version

See:

`experiments/cooja/config/toolchain-lock.json`

Cooja execution is performed through Docker Compose and the project
`run.sh` interface.

## Scientific interpretation

Development/tuning campaigns and confirmatory campaigns must remain
distinguishable. Confirmatory results must not be retrospectively
used to tune protocol parameters.

## Preservation rule

Do not delete or overwrite a published result directory.

A new experiment must create a new result directory and a new
manifest.
