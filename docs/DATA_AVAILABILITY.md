# Data and Code Availability

This repository contains the public-source candidate for the
RANGER-IoT scientific study.

## Included material

- Python research implementation under `src/ranger_iot/`.
- Python tests under `tests/`.
- Formal specifications under `formal/tamarin/`.
- Cooja applications and scenario definitions under `experiments/cooja/`.
- Reed-Solomon implementation and experimental support material.
- Experimental aggregate tables, campaign configurations,
  reproducibility scripts, and scientific evidence artifacts.

The final network-model campaign is located at:

`experiments/results/step7b1/model-external-validity-20261003T134431/`

Its aggregate contains 2,880 factor combinations:
3 protocols, 4 topologies, 4 group sizes, 3 loss levels,
and 20 random seeds. Structural completeness and uniqueness
have been checked.

## Consolidated historical experiments

The following campaigns retain their aggregate tables and
campaign-level metadata, but not all individual run outputs:

- `experiments/results/step5e/publication-main/`
- `experiments/results/step5f3/adaptive-v2-confirmatory/`
- `experiments/results/step5e/publication-scalability/`

The removed per-run files include configuration, summary,
and/or event-level files, depending on the campaign.

The excluded raw files remain in the protected internal
development history. They are NOT part of this independent
publication snapshot and are NOT currently claimed to be
publicly downloadable.

## Validation scope

An isolated extraction of the cleaned repository passed
209 Python tests. Checks of historical aggregate tables
found no differences among compared scalar fields.

These checks do not constitute an end-to-end rerun of Cooja
simulations, Tamarin proofs, or all experimental analyses.

The Cooja workflow depends on the Contiki-NG submodule;
the submodule must be initialized separately after cloning.

## Reproduction and provenance

Consult the existing `reproducibility/` scripts, formal
models, experiments, and evidence artifacts for the relevant
commands and input configurations.

Availability of aggregated data must not be interpreted as
availability of the excluded raw packet/event traces.
Analyses requiring those traces may require a fresh simulation
or a separately published archive.

The precise commands, version requirements, computational
environment, and artifact availability must be checked
against the frozen manuscript before final public release.

## Public Distribution Hold

The available research artifacts constitute a local
technical release candidate. They have not been
authorized for public distribution.

Excluded historical raw traces remain outside the
independent publication snapshot. Their availability
must not be represented as public or guaranteed.

No claim of public availability is made by this section.
Scientific validation and distribution authorization
are separate matters.
