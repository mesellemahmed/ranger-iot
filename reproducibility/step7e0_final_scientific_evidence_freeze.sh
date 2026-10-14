#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"

OUT="artifacts/article-evidence/40-final-scientific-evidence-freeze"

STEP7A="artifacts/article-evidence/13-step7a-statistical-hardening"
STEP7B1="artifacts/article-evidence/16-step7b1-model-external-validity"
STEP7B2="artifacts/article-evidence/17-step7b2-statistical-analysis"
STEP7B3="artifacts/article-evidence/18-step7b3-cooja-topology"

STEP7C1="artifacts/article-evidence/21-step7c1-python-byte-codec"
STEP7C2="artifacts/article-evidence/22-step7c2-c-differential"
STEP7C3="artifacts/article-evidence/23-step7c3-cooja-real-rs-wire"

STEP7D2A="artifacts/article-evidence/32-step7d2a-lkh-semantic-freeze"
STEP7D2B="artifacts/article-evidence/37-step7d2b-temporal-security-contract"
STEP7D2CA="artifacts/article-evidence/38-step7d2ca-structural-lkh-generalization"
STEP7D2CB="artifacts/article-evidence/39-step7d2cb-real-rs-comparative-bridge"

AGG="experiments/results/step7b1/model-external-validity-20261003T134431/aggregate.csv"

FORMAL_MODEL="formal/tamarin/ranger_lkh_multi_epoch_4member_temporal_security.spthy"

echo "===================================================================="
echo "RANGER-IOT — STEP 7E.0"
echo "FINAL SCIENTIFIC EVIDENCE FREEZE"
echo
echo "PURPOSE:"
echo "  freeze claims"
echo "  freeze limitations"
echo "  freeze evidence mapping"
echo "  freeze reproducibility identifiers"
echo "  authorize manuscript drafting from evidence only"
echo
echo "NO NEW EXPERIMENT"
echo "NO PROTOCOL CHANGE"
echo "NO RESULT MODIFICATION"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="

if [ -e "$OUT" ]; then
    echo "ERROR: final freeze directory already exists:"
    echo "  $OUT"
    echo "Refusing to overwrite frozen scientific evidence."
    exit 2
fi

mkdir -p "$OUT"


# ==================================================================
# 1. Required evidence presence
# ==================================================================

echo
echo "===== 1. REQUIRED EVIDENCE PRESENCE ====="

REQUIRED_DIRS=(
"$STEP7A"
"$STEP7B1"
"$STEP7B2"
"$STEP7B3"
"$STEP7C1"
"$STEP7C2"
"$STEP7C3"
"$STEP7D2A"
"$STEP7D2B"
"$STEP7D2CA"
"$STEP7D2CB"
)

for dir in "${REQUIRED_DIRS[@]}"; do
    test -d "$dir"
    echo "PASS: $dir"
done

test -f "$AGG"
test -f "$FORMAL_MODEL"

echo "REQUIRED_EVIDENCE_PRESENCE=PASS"


# ==================================================================
# 2. Machine-audit all scientific gates
# ==================================================================

echo
echo "===== 2. SCIENTIFIC GATE AUDIT ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$STEP7A" \
    "$STEP7B1" \
    "$STEP7B2" \
    "$STEP7B3" \
    "$STEP7C1" \
    "$STEP7C2" \
    "$STEP7C3" \
    "$STEP7D2B" \
    "$STEP7D2CA" \
    "$STEP7D2CB" \
    "$OUT/final-gates.json" <<'PY'
from __future__ import annotations

import json
import sys

from pathlib import Path
from typing import Any, Callable


(
    step7a,
    step7b1,
    step7b2,
    step7b3,
    step7c1,
    step7c2,
    step7c3,
    step7d2b,
    step7d2ca,
    step7d2cb,
    output,
) = map(Path, sys.argv[1:])


def documents(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    result = []

    for path in sorted(root.rglob("*.json")):
        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            continue

        if isinstance(data, dict):
            result.append((path, data))

    return result


def find_document(
    root: Path,
    predicate: Callable[[dict[str, Any]], bool],
    label: str,
) -> tuple[Path, dict[str, Any]]:
    matches = [
        (path, data)
        for path, data
        in documents(root)
        if predicate(data)
    ]

    if not matches:
        raise SystemExit(
            f"Cannot find authoritative JSON for {label} in {root}"
        )

    # Prefer final-state/readiness documents if several qualify.
    matches.sort(
        key=lambda item: (
            "final-state" not in item[0].name,
            "final-readiness" not in item[0].name,
            len(str(item[0])),
        )
    )

    return matches[0]


p7a, j7a = find_document(
    step7a,
    lambda d:
        d.get("step7a_pass") is True
        and
        d.get("scientific_state")
        == "STATISTICAL_HARDENING_COMPLETE",
    "STEP7A",
)

p7b1, j7b1 = find_document(
    step7b1,
    lambda d:
        d.get("step7b1_pass") is True
        and
        d.get("run_count") == 2880,
    "STEP7B1",
)

p7b2, j7b2 = find_document(
    step7b2,
    lambda d:
        d.get("step7b2_pass") is True
        and
        d.get("scientific_state")
        == "EXTERNAL_VALIDITY_STATISTICS_COMPLETE",
    "STEP7B2",
)

p7b3, j7b3 = find_document(
    step7b3,
    lambda d:
        d.get("step7b3_pass") is True
        and
        d.get("scientific_state")
        == "COOJA_TOPOLOGY_EXTERNAL_VALIDITY_COMPLETE",
    "STEP7B3",
)

p7c1, j7c1 = find_document(
    step7c1,
    lambda d:
        d.get("step7c1_pass") is True
        and
        d.get("primary_exact_reconstructions") == 2560,
    "STEP7C1",
)

p7c2, j7c2 = find_document(
    step7c2,
    lambda d:
        d.get("step7c2_pass") is True
        and
        d.get("scientific_state")
        == "C_PYTHON_BYTE_LEVEL_CODEC_EQUIVALENCE_VALIDATED",
    "STEP7C2",
)

p7c3, j7c3 = find_document(
    step7c3,
    lambda d:
        d.get("step7c3_pass") is True
        and
        d.get("scientific_state")
        == "REAL_RS_BYTES_VALIDATED_ON_COOJA_RPL_WIRE",
    "STEP7C3",
)

p7d2b, j7d2b = find_document(
    step7d2b,
    lambda d:
        d.get("reference_instance_closed") is True
        and
        d.get("all_17_verified") is True
        and
        d.get("negative_control_pass") is True,
    "STEP7D2B",
)

p7d2ca, j7d2ca = find_document(
    step7d2ca,
    lambda d:
        d.get("step7d2ca_closed") is True
        and
        d.get("structural_case_count") == 10386
        and
        d.get("structural_failure_count") == 0,
    "STEP7D2CA",
)

p7d2cb, j7d2cb = find_document(
    step7d2cb,
    lambda d:
        d.get("step7d2cb_closed") is True
        and
        d.get("bridge_runs") == 420
        and
        d.get("member_rs_decisions") == 16380,
    "STEP7D2CB",
)


checks = {
    "step7a_statistical_hardening":
        j7a.get("step7a_pass") is True,

    "step7b1_2880_runs":
        (
            j7b1.get("step7b1_pass") is True
            and
            j7b1.get("run_count") == 2880
            and
            j7b1.get("paired_scenario_seed_cells") == 960
            and
            j7b1.get("grouped_cells") == 144
        ),

    "step7b2_statistics":
        j7b2.get("step7b2_pass") is True,

    "step7b3_cooja":
        j7b3.get("step7b3_pass") is True,

    "step7c1_python_rs":
        (
            j7c1.get("step7c1_pass") is True
            and
            j7c1.get("primary_exact_reconstructions") == 2560
        ),

    "step7c2_cross_language":
        (
            j7c2.get("step7c2_pass") is True
            and
            j7c2.get("validation", {}).get("vector_count") == 259
            and
            j7c2.get("validation", {}).get(
                "c_encoder_to_c_decoder_subsets"
            )
            == 2588
            and
            j7c2.get("validation", {}).get(
                "python_encoder_to_c_decoder_subsets"
            )
            == 2588
            and
            j7c2.get("validation", {}).get(
                "c_encoder_to_python_decoder_subsets"
            )
            == 2588
        ),

    "step7c3_real_wire":
        j7c3.get("step7c3_pass") is True,

    "step7d2b_formal_temporal":
        (
            j7d2b.get("reference_instance_closed") is True
            and
            j7d2b.get("all_17_verified") is True
            and
            j7d2b.get("negative_control_pass") is True
            and
            j7d2b.get(
                "historical_key_exposure_boundary_demonstrated"
            )
            is True
        ),

    "step7d2ca_structural":
        (
            j7d2ca.get("step7d2ca_closed") is True
            and
            j7d2ca.get("structural_case_count") == 10386
            and
            j7d2ca.get("structural_rekey_epoch_count") == 17180
            and
            j7d2ca.get("structural_failure_count") == 0
        ),

    "step7d2cb_real_rs_bridge":
        (
            j7d2cb.get("step7d2cb_closed") is True
            and
            j7d2cb.get("bridge_runs") == 420
            and
            j7d2cb.get("member_rs_decisions") == 16380
            and
            j7d2cb.get("real_rs_comparative_bridge") is True
        ),

    "no_arbitrary_n_overclaim":
        (
            j7d2b.get("arbitrary_n_generalization") is False
            and
            j7d2ca.get("arbitrary_n_theorem") is False
            and
            j7d2cb.get("arbitrary_n_theorem") is False
        ),

    "no_full_formal_overclaim":
        (
            j7d2b.get("full_ranger_formally_verified") is False
            and
            j7d2ca.get("full_ranger_formally_verified") is False
            and
            j7d2cb.get("full_ranger_formally_verified") is False
        ),
}


for key, passed in checks.items():
    print(
        f"{key:46s}",
        "PASS" if passed else "FAIL",
    )


if not all(checks.values()):
    raise SystemExit(
        "FINAL SCIENTIFIC GATE FAILURE"
    )


payload = {
    "schema_version":
        1,

    "step":
        "STEP7E0_FINAL_SCIENTIFIC_EVIDENCE_FREEZE",

    "all_scientific_gates_pass":
        True,

    "checks":
        checks,

    "authoritative_documents": {
        "step7a":
            str(p7a),

        "step7b1":
            str(p7b1),

        "step7b2":
            str(p7b2),

        "step7b3":
            str(p7b3),

        "step7c1":
            str(p7c1),

        "step7c2":
            str(p7c2),

        "step7c3":
            str(p7c3),

        "step7d2b":
            str(p7d2b),

        "step7d2ca":
            str(p7d2ca),

        "step7d2cb":
            str(p7d2cb),
    },

    "quantitative_anchor": {
        "step7b1_simulation_runs":
            2880,

        "step7b1_scenario_seed_cells":
            960,

        "step7b1_grouped_cells":
            144,

        "step7c1_exact_python_rs_reconstructions":
            2560,

        "step7c2_cross_language_vectors":
            259,

        "step7c2_subset_decodes_per_direction":
            2588,

        "formal_temporal_lemmas":
            17,

        "finite_structural_cases":
            10386,

        "finite_structural_rekey_epochs":
            17180,

        "finite_structural_failures":
            0,

        "real_rs_bridge_runs":
            420,

        "real_rs_member_decisions":
            16380,
    },
}


output.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


print()
print(
    "ALL_SCIENTIFIC_GATES=PASS"
)
PY


# ==================================================================
# 3. Freeze claims and evidence boundaries
# ==================================================================

echo
echo "===== 3. CLAIM ↔ EVIDENCE MATRIX ====="

cat > "$OUT/claim-evidence-matrix.md" <<'EOF'
# RANGER-IoT — Final Scientific Claim/Evidence Matrix

This document freezes the scientific interpretation of the evidence used
for the manuscript.

No manuscript statement may exceed the boundaries below without new
evidence and a new explicitly identified experiment/proof stage.

## C1 — Resilience benefit relative to static dissemination

### Permitted claim

Recovery-enabled and adaptive RANGER variants improve resilience relative
to static coded dissemination in multiple tested lossy contexts.

The strongest and most consistent comparative evidence is Recovery versus
Static.

### Evidence

- STEP 7A:
  30 paired seeds per target TX condition for the original Cooja scenario.
- STEP 7B1:
  2880 deterministic model runs.
- STEP 7B2:
  paired inference with Holm multiplicity control.
- STEP 7B3:
  480 confirmatory Cooja topology/layout runs.

### Boundary

Do NOT claim that one protocol universally dominates all contexts.

Adaptive-V2 versus Recovery is explicitly context dependent.


## C2 — External validity across topology, scale, and loss

### Permitted claim

The comparative behavior of RANGER depends materially on topology,
member count, and loss conditions; its benefits and trade-offs were
evaluated across multiple topological and scale regimes.

### Evidence

STEP 7B1:

- topologies:
  line, star, balanced-tree, grid;
- member counts:
  8, 16, 32, 64;
- packet-loss levels:
  0.0, 0.1, 0.2;
- 20 independent frozen seeds;
- 2880 total runs.

STEP 7B3:

- line;
- balanced-tree;
- grid;
- compact-onehop;
- fixed 8-mote Cooja implementation.

### Boundary

`compact-onehop` is not called an exact star.

Python `packet_loss` is not equated to Cooja `SUCCESS_RATIO_TX`.

The Cooja scale evidence is fixed at 8 motes.


## C3 — Byte-level Reed-Solomon realism

### Permitted claim

The canonical systematic GF(256) Reed-Solomon codec has been validated
at the byte level in Python and C, with bidirectional cross-language
decode equivalence and actual shard bytes validated on Cooja/RPL.

### Evidence

STEP 7C1:

- systematic GF(256);
- primitive polynomial 0x11D;
- primary profile 3-of-5;
- 2560 exact Python reconstructions.

STEP 7C2:

- 259 vectors;
- exact generator/shard parity;
- 2588 C-to-C subset decodes;
- 2588 Python-to-C subset decodes;
- 2588 C-to-Python subset decodes;
- -O0 / -O2 identical outputs.

STEP 7C3:

- actual RS shard bytes over isolated Cooja/RPL;
- C and Python reconstruction from actual received bytes;
- below-k rejection.

### Boundary

Reed-Solomon provides reconstruction/availability redundancy.

It does NOT provide secrecy, authentication, or Byzantine integrity.

CRC32 is only a reconstruction/corruption oracle.


## C4 — Comparative conclusions survive the real RS codec

### Permitted claim

For the seven frozen discriminant contexts used by the comparative bridge,
the idealized k-of-n reconstruction decision is exactly preserved by the
canonical byte-level Reed-Solomon implementation for the same received
fragment-index sets.

### Evidence

STEP 7D2-C-B:

- 7 frozen scenario cells;
- 3 protocols;
- 20 seeds per cell;
- 420 deterministic reruns;
- 16380 member-level decisions;
- exact idealized/protocol/RS decision parity;
- exact byte reconstruction for decodable sets;
- below-threshold rejection;
- exact historical deterministic replay;
- exact grouped completion/convergence reproduction.

### Boundary

This does NOT mean that all historical STEP7B simulations physically
transmitted serialized RS bytes.

Actual byte-level Cooja/RPL transmission is separately established by
STEP 7C3.


## C5 — Temporal security of the formal reference instance

### Permitted claim

The session-bound, multi-epoch four-member temporal-security reference
model satisfies all 17 specified Tamarin properties under the explicit
symbolic assumptions of the model.

### Evidence

STEP 7D2-B:

- 17/17 verified;
- 0 falsified;
- 0 timeout;
- 0 execution errors;
- intentional epoch-2 root disclosure mutation is detected as falsified;
- historical key-exposure boundary is explicitly demonstrated.

### Boundary

Do NOT claim:

- arbitrary-N formal proof;
- complete formal verification of all RANGER implementation code;
- network liveness under packet loss;
- formal equivalence between Python, C, Cooja, and Tamarin.


## C6 — Finite structural LKH generalization

### Permitted claim

The exact implemented LkhKeyTree was exhaustively checked over the
specified finite structural domain for survivor derivability, revoked
member exclusion, revoked-coalition exclusion, root freshness, and
historical-key retention.

### Evidence

STEP 7D2-C-A:

- group sizes:
  4, 5, 7, 8, 9, 16, 17, 32, 33, 64;
- all single revocations;
- all ordered two-epoch revocation pairs;
- all simultaneous two-member revocations;
- 10386 cases;
- 17180 rekey epochs;
- 0 failures.

### Boundary

This is finite exhaustive implementation-derived validation.

It is NOT an arbitrary-N theorem.


## C7 — Historical-key exposure boundary

### Permitted claim

A key held legitimately by an authorized member during an earlier epoch
cannot reasonably be required to remain confidential after that former
holder's retained historical state is later explicitly exposed.

The formal results distinguish this historical-exposure boundary from
confidentiality of newly generated post-revocation keys.

### Evidence

- preserved diagnostic counterexamples;
- mono-session causal audit;
- temporal-property reclassification;
- positive temporal contract;
- historical exposure witness;
- negative mutation control.

### Boundary

Do not describe the preserved historical exposure trace as a break of the
new epoch key unless the causal derivation actually establishes that fact.
EOF

echo "CLAIM_EVIDENCE_MATRIX=PASS"


# ==================================================================
# 4. Freeze manuscript RQs
# ==================================================================

echo
echo "===== 4. MANUSCRIPT RQ CONTRACT ====="

cat > "$OUT/manuscript-rq-contract.md" <<'EOF'
# RANGER-IoT — Proposed Final Research-Question Contract

These RQs are the recommended manuscript structure because each one has
a closed evidence chain.

## RQ1 — Resilience

How do static coded dissemination, neighbor-assisted recovery, and
adaptive dissemination differ in rekey completion and convergence under
loss?

Evidence:
STEP7A + STEP7B1 + STEP7B2.

Expected conclusion:
Recovery and adaptive mechanisms can substantially outperform Static in
lossy settings, but their relative benefit depends on context.


## RQ2 — External validity

How stable are the comparative conclusions across topology, group size,
loss regime, and embedded Cooja layouts?

Evidence:
STEP7B1 + STEP7B2 + STEP7B3.

Expected conclusion:
The results are topology- and scale-sensitive; no universal protocol
winner is supported.


## RQ3 — Coding realism

Do conclusions obtained under the idealized k-of-n abstraction remain
valid when reconstruction uses the actual byte-level Reed-Solomon codec?

Evidence:
STEP7C1 + STEP7C2 + STEP7C3 + STEP7D2-C-B.

Expected conclusion:
For the frozen bridge contexts, member acceptance/reconstruction
decisions are exactly preserved by real RS byte-level decoding.


## RQ4 — Security

Under which explicit assumptions does the rekey protocol preserve
authorization, replay/freshness, post-revocation key confidentiality,
and recovery authorization across epochs?

Evidence:
STEP7D2-B + STEP7D2-C-A.

Expected conclusion:
The bounded reference model verifies the specified temporal properties,
while finite structural analysis extends implementation-derived evidence
across multiple tree shapes and revocation configurations.


## RQ5 — Security boundary

What confidentiality guarantee ceases to be meaningful after later
exposure of a former authorized holder's historical state?

Evidence:
counterexample preservation + causal audit + temporal contract.

Expected conclusion:
Post-revocation secrecy of newly generated keys must be distinguished
from everlasting confidentiality of historical keys legitimately held
before later compromise/exposure.
EOF

echo "MANUSCRIPT_RQ_CONTRACT=PASS"


# ==================================================================
# 5. Freeze overclaim guardrails
# ==================================================================

echo
echo "===== 5. CLAIM GUARDRAILS ====="

cat > "$OUT/forbidden-overclaims.md" <<'EOF'
# RANGER-IoT — Frozen Overclaim Guardrails

The manuscript MUST NOT state or imply any of the following:

1. Adaptive-V2 is universally superior to Recovery.
2. RANGER has been formally verified for arbitrary group size.
3. The complete executable RANGER implementation is formally verified.
4. Tamarin proves lossy-network liveness or delivery.
5. Reed-Solomon provides confidentiality or authentication.
6. CRC32 provides cryptographic integrity/authentication.
7. Cooja experiments establish scalability beyond the validated fixed
   8-mote implementation.
8. `compact-onehop` is an exact graph-theoretic star.
9. Python `packet_loss` is numerically equivalent to Cooja
   `SUCCESS_RATIO_TX`.
10. Every historical STEP7A/STEP7B packet physically contained serialized
    RS bytes.
11. A preserved historical-key exposure counterexample demonstrates
    compromise of a newly generated epoch key without a causal derivation.
12. Zero Holm-significant completion cells in the broad STEP7B2 matrix
    means there is no resilience effect.
13. Absence of a universal winner is a negative result; it is instead
    evidence of context dependence.
14. The finite 10386-case structural audit constitutes an arbitrary-N
    mathematical theorem.
EOF

echo "OVERCLAIM_GUARDRAILS=PASS"


# ==================================================================
# 6. Article architecture
# ==================================================================

echo
echo "===== 6. MANUSCRIPT ARCHITECTURE ====="

cat > "$OUT/manuscript-architecture.md" <<'EOF'
# RANGER-IoT — Final Manuscript Architecture

## 1. Introduction
- constrained IoT rekeying problem;
- reliability/security tension;
- why static dissemination is insufficient;
- contributions stated with bounded wording.

## 2. Background and Related Work
- group-key management;
- LKH;
- reliable dissemination;
- erasure coding;
- recovery/adaptation;
- formal verification of rekey protocols.

## 3. System and Threat Model
- group manager;
- members;
- revoked members;
- lossy network;
- trusted/compromised states;
- attacker knowledge;
- explicit exclusions.

## 4. RANGER-IoT Design
- Static;
- Recovery;
- Adaptive-V2;
- authorization remains LKH;
- transport/coding separated from key authorization.

## 5. Coding Layer
- historical idealized k-of-n abstraction;
- real systematic RS GF(256);
- codec parameters;
- C/Python equivalence;
- exact boundary between redundancy and security.

## 6. Experimental Methodology
- frozen seeds;
- topologies;
- scales;
- packet loss;
- Cooja layouts;
- pairing;
- exact tests;
- bootstrap;
- Holm correction;
- stopping rules.

## 7. Experimental Results
### 7.1 Original scenario hardening
### 7.2 Topology/scale/loss external validity
### 7.3 Cooja external validity
### 7.4 Static vs Recovery
### 7.5 Static vs Adaptive
### 7.6 Adaptive vs Recovery context dependence
### 7.7 Cost and latency trade-offs

## 8. Coding-Realism Validation
- Python RS;
- C differential;
- Cooja/RPL bytes;
- 420-run bridge;
- 16380 exact member-level decisions.

## 9. Formal Security Analysis
### 9.1 Authorization/transport abstraction
### 9.2 Multi-epoch LKH model
### 9.3 Preserved counterexamples
### 9.4 Causal reclassification
### 9.5 17-property temporal contract
### 9.6 Negative mutation control
### 9.7 Finite structural generalization

## 10. Discussion
- when Recovery dominates;
- when Adaptive is useful;
- why context dependence matters;
- historical-key exposure boundary;
- relationship between formal and empirical evidence.

## 11. Threats to Validity
- finite topology set;
- fixed 8-mote Cooja scale;
- symbolic cryptography;
- finite structural audit not arbitrary-N;
- idealized historical network model;
- bridge methodology;
- no Tamarin liveness claim.

## 12. Reproducibility
- Docker;
- frozen seeds;
- evidence manifests;
- source hashes;
- pinned formal environment;
- exact commands.

## 13. Conclusion
- bounded conclusions only;
- no universal winner;
- evidence convergence across simulation, embedded emulation,
  byte-level codec validation, and formal analysis.
EOF

echo "MANUSCRIPT_ARCHITECTURE=PASS"


# ==================================================================
# 7. Hash complete scientific evidence corpus
# ==================================================================

echo
echo "===== 7. COMPLETE EVIDENCE HASH MANIFEST ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  bash -lc "
    set -euo pipefail
    cd /workspace

    find \
      '$STEP7A' \
      '$STEP7B1' \
      '$STEP7B2' \
      '$STEP7B3' \
      '$STEP7C1' \
      '$STEP7C2' \
      '$STEP7C3' \
      '$STEP7D2A' \
      '$STEP7D2B' \
      '$STEP7D2CA' \
      '$STEP7D2CB' \
      -type f \
      -print0 \
    | sort -z \
    | xargs -0 sha256sum \
      > '$OUT/scientific-evidence.sha256'

    sha256sum \
      -c \
      '$OUT/scientific-evidence.sha256' \
      > '$OUT/scientific-evidence-verify.log'
  "

echo "SCIENTIFIC_EVIDENCE_HASH_MANIFEST=PASS"


# ==================================================================
# 8. Freeze authoritative source code + formal model
# ==================================================================

echo
echo "===== 8. SOURCE FREEZE ====="

SOURCES=(
src/ranger_iot/group.py
src/ranger_iot/rekey.py
src/ranger_iot/protocols/lkh.py
src/ranger_iot/ranger/capsule.py
src/ranger_iot/ranger/coding.py
src/ranger_iot/ranger/rs_codec.py
src/ranger_iot/ranger/static_protocol.py
src/ranger_iot/ranger/recovery_protocol.py
src/ranger_iot/ranger/adaptive_protocol.py
src/ranger_iot/ranger/adaptive_v2_protocol.py
src/ranger_iot/experiments/config.py
src/ranger_iot/experiments/campaign.py
src/ranger_iot/experiments/runner.py
experiments/cooja/codec/ranger_rs_codec.c
experiments/cooja/codec/ranger_rs_codec.h
formal/tamarin/ranger_lkh_multi_epoch_4member_temporal_security.spthy
)


docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
    "${SOURCES[@]}" \
  > "$OUT/final-source-freeze.sha256"

cat "$OUT/final-source-freeze.sha256"

echo "FINAL_SOURCE_FREEZE=PASS"


# ==================================================================
# 9. Repository metadata — informational, not scientific execution
# ==================================================================

echo
echo "===== 9. REPOSITORY STATE ====="

set +e

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  bash -lc '
    {
      echo "branch=$(git branch --show-current 2>/dev/null || echo UNKNOWN)"
      echo "head=$(git rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
      echo
      echo "[status]"
      git status --short 2>/dev/null || true
    }
  ' \
  > "$OUT/repository-state.txt"

REPO_RC=$?

set -e

cat "$OUT/repository-state.txt"

echo "REPOSITORY_METADATA_RC=$REPO_RC"
echo "NOTE: no clean-tree requirement is imposed because evidence artifacts"
echo "      are intentionally uncommitted at this stage."


# ==================================================================
# 10. Final CI
# ==================================================================

echo
echo "===== 10. FINAL PROJECT CI ====="

set +e

./run.sh check \
  2>&1 \
  | tee "$OUT/final-project-ci.log"

CI_RC=${PIPESTATUS[0]}

set -e

echo "FINAL_CI_RC=$CI_RC"

if [ "$CI_RC" -ne 0 ]; then
    exit "$CI_RC"
fi

echo "FINAL_PROJECT_CI=PASS"


# ==================================================================
# 11. Source identity after CI
# ==================================================================

echo
echo "===== 11. SOURCE IDENTITY AFTER CI ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
  -c \
  "$OUT/final-source-freeze.sha256"

echo "FINAL_SOURCE_IDENTITY_AFTER_CI=PASS"


# ==================================================================
# 12. Build final manuscript-readiness state
# ==================================================================

echo
echo "===== 12. FINAL MANUSCRIPT READINESS ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$OUT/final-gates.json" \
    "$OUT/final-readiness.json" <<'PY'
from __future__ import annotations

import json
import sys

from pathlib import Path


gates = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)


ready = (
    gates.get(
        "all_scientific_gates_pass"
    )
    is True
)


payload = {
    "schema_version":
        1,

    "step":
        "STEP7E0_FINAL_SCIENTIFIC_EVIDENCE_FREEZE",

    "scientific_evidence_content_frozen":
        ready,

    "manuscript_drafting_authorized":
        ready,

    "new_experiments_required_before_manuscript":
        False,

    "new_formal_proofs_required_before_manuscript":
        False,

    "claim_matrix_frozen":
        True,

    "rq_contract_frozen":
        True,

    "overclaim_guardrails_frozen":
        True,

    "evidence_hash_manifest_created":
        True,

    "source_hash_manifest_created":
        True,

    "repository_release_tag_created":
        False,

    "repository_release_immutability":
        False,

    "important_release_note":
        (
            "Scientific content is frozen, but a final repository "
            "commit/tag has intentionally not been created because "
            "this step performs no commit or push."
        ),

    "arbitrary_n_theorem":
        False,

    "full_ranger_formally_verified":
        False,

    "publication_guaranteed":
        False,

    "scientific_state":
        (
            "SCIENTIFIC_EVIDENCE_FREEZE_COMPLETE_FOR_A_PLUS_TARGET_MANUSCRIPT"
            if ready
            else
            "SCIENTIFIC_EVIDENCE_FREEZE_FAILED"
        ),

    "next_step":
        (
            "STEP7E1_MANUSCRIPT_FROM_FROZEN_EVIDENCE"
            if ready
            else
            "STEP7E0_FAILURE_AUDIT"
        ),
}


Path(sys.argv[2]).write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


print(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
)


if not ready:
    raise SystemExit(20)
PY


# ==================================================================
# 13. Package compact final freeze
# ==================================================================

echo
echo "===== 13. FINAL FREEZE PACKAGE ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  bash -lc "
    set -euo pipefail
    cd /workspace

    TAR=/tmp/ranger-step7e0-final-scientific-freeze.tar.gz
    rm -f \"\$TAR\"

    tar \
      -czf \
      \"\$TAR\" \
      '$OUT' \
      reproducibility/step7e0_final_scientific_evidence_freeze.sh

    tar -tzf \"\$TAR\" >/dev/null

    cp \
      \"\$TAR\" \
      '$OUT/ranger-step7e0-final-scientific-freeze.tar.gz'

    sha256sum \
      '$OUT/ranger-step7e0-final-scientific-freeze.tar.gz' \
      > '$OUT/ranger-step7e0-final-scientific-freeze.tar.gz.sha256'

    sha256sum \
      -c \
      '$OUT/ranger-step7e0-final-scientific-freeze.tar.gz.sha256'
  "


echo
echo "===================================================================="
echo "STEP 7E.0 COMPLETE"
echo
echo "FINAL READINESS:"
echo "  $OUT/final-readiness.json"
echo
echo "CLAIM MATRIX:"
echo "  $OUT/claim-evidence-matrix.md"
echo
echo "RQ CONTRACT:"
echo "  $OUT/manuscript-rq-contract.md"
echo
echo "OVERCLAIM GUARDRAILS:"
echo "  $OUT/forbidden-overclaims.md"
echo
echo "MANUSCRIPT ARCHITECTURE:"
echo "  $OUT/manuscript-architecture.md"
echo
echo "SOURCE MANIFEST:"
echo "  $OUT/final-source-freeze.sha256"
echo
echo "EVIDENCE MANIFEST:"
echo "  $OUT/scientific-evidence.sha256"
echo
echo "NEXT:"
echo "  STEP7E1 — MANUSCRIPT FROM FROZEN EVIDENCE"
echo
echo "NO NEW EXPERIMENT"
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
