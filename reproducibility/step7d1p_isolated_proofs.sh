#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"
FORMAL_COMPOSE="compose.reproducibility.yaml"

MODEL="formal/tamarin/ranger_authorization_transport.spthy"
IMAGE="ranger-tamarin:1.12.0-repro"

PREV="artifacts/article-evidence/26-step7d1-docker-reproducible"
OUT="artifacts/article-evidence/27-step7d1-isolated-proof-matrix"

LOG_DIR="$OUT/logs"
RC_FILE="$OUT/return-codes.tsv"
SUMMARY="$OUT/isolated-proof-matrix.json"
CSV="$OUT/isolated-proof-matrix.csv"

mkdir -p "$LOG_DIR"
: > "$RC_FILE"

echo "===================================================================="
echo "RANGER-IOT — STEP 7D.1-P"
echo "ISOLATED TAMARIN LEMMA PROOF MATRIX"
echo
echo "MODEL UNCHANGED"
echo "DOCKER ONLY"
echo "PROOF NETWORK = NONE"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="


# -------------------------------------------------------------------
# 1. Preconditions
# -------------------------------------------------------------------

echo
echo "===== 1. PREFLIGHT ====="

test -f "$MODEL"
test -f "$FORMAL_COMPOSE"
test -f "$PREV/tamarin-image-id.txt"

docker image inspect "$IMAGE" >/dev/null

ACTUAL_IMAGE_ID="$(
    docker image inspect \
        "$IMAGE" \
        --format '{{.Id}}'
)"

EXPECTED_IMAGE_ID="$(
    tr -d '\r\n' \
        < "$PREV/tamarin-image-id.txt"
)"

echo "EXPECTED_IMAGE_ID=$EXPECTED_IMAGE_ID"
echo "ACTUAL_IMAGE_ID=$ACTUAL_IMAGE_ID"

if [ "$ACTUAL_IMAGE_ID" != "$EXPECTED_IMAGE_ID" ]; then
    echo "ERROR: TAMARIN IMAGE ID DRIFT"
    exit 1
fi

echo "TAMARIN_IMAGE_IDENTITY=PASS"


# -------------------------------------------------------------------
# 2. Runtime sanity — offline
# -------------------------------------------------------------------

echo
echo "===== 2. OFFLINE RUNTIME SANITY ====="

docker compose \
    -f "$FORMAL_COMPOSE" \
    run \
    --rm \
    -T \
    --no-deps \
    tamarin \
    bash -lc '
        set -euo pipefail

        tamarin-prover --version
        tamarin-prover test

        echo "ISOLATED_PROOF_RUNTIME=PASS"
    '

echo "OFFLINE_RUNTIME_SANITY=PASS"


# -------------------------------------------------------------------
# 3. Lemma matrix
#
# Format:
#   lemma | kind | budget_seconds | search
#
# exists-trace:
#   BFS is used only to locate an execution witness.
#
# all-traces:
#   default Tamarin strategy is preserved.
# -------------------------------------------------------------------

LEMMAS=(
"executable_initial_accept|exists-trace|120|bfs"
"executable_same_epoch_recovery|exists-trace|180|bfs"
"revocation_reachable|exists-trace|120|bfs"
"accept_has_rekey_origin|all-traces|180|default"
"accept_requires_authorization|all-traces|180|default"
"revoked_never_accepts|all-traces|180|default"
"recovery_requester_authorized|all-traces|180|default"
"recovery_helper_authorized|all-traces|180|default"
"recovery_same_epoch|all-traces|180|default"
"recovery_accept_has_rekey_origin|all-traces|240|default"
"epoch_key_secrecy_unless_compromised|all-traces|300|default"
)


echo
echo "===== 3. ISOLATED LEMMA PROOFS ====="


for spec in "${LEMMAS[@]}"; do

    IFS='|' read -r \
        lemma kind budget search \
        <<< "$spec"

    LOG="$LOG_DIR/${lemma}.log"

    echo
    echo "----------------------------------------------------------------"
    echo "LEMMA=$lemma"
    echo "KIND=$kind"
    echo "BUDGET=$budget"
    echo "SEARCH=$search"
    echo "----------------------------------------------------------------"

    set +e

    if [ "$search" = "bfs" ]; then

        docker compose \
            -f "$FORMAL_COMPOSE" \
            run \
            --rm \
            -T \
            --no-deps \
            tamarin \
            bash -lc "
                timeout ${budget}s \
                tamarin-prover \
                    '${MODEL}' \
                    '--prove=${lemma}' \
                    --stop-on-trace=BFS \
                    +RTS -N2 -RTS
            " \
            > "$LOG" \
            2>&1

    else

        docker compose \
            -f "$FORMAL_COMPOSE" \
            run \
            --rm \
            -T \
            --no-deps \
            tamarin \
            bash -lc "
                timeout ${budget}s \
                tamarin-prover \
                    '${MODEL}' \
                    '--prove=${lemma}' \
                    +RTS -N2 -RTS
            " \
            > "$LOG" \
            2>&1

    fi

    RC=$?

    set -e

    printf '%s\t%s\t%s\t%s\t%s\n' \
        "$lemma" \
        "$kind" \
        "$budget" \
        "$search" \
        "$RC" \
        >> "$RC_FILE"

    echo "LEMMA_RC=$RC"

    if [ "$RC" -eq 124 ]; then
        echo "LEMMA_EXECUTION=TIMEOUT"
    elif [ "$RC" -eq 0 ]; then
        echo "LEMMA_EXECUTION=COMPLETED"
    else
        echo "LEMMA_EXECUTION=ERROR"
    fi

done


# -------------------------------------------------------------------
# 4. Parse every result inside ranger Docker.
# -------------------------------------------------------------------

echo
echo "===== 4. DOCKER RESULT CLASSIFICATION ====="

docker compose \
    -f "$ROOT_COMPOSE" \
    run \
    --rm \
    -T \
    --no-deps \
    ranger \
    python - \
        "$RC_FILE" \
        "$LOG_DIR" \
        "$SUMMARY" \
        "$CSV" <<'PY'
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path


rc_path = Path(sys.argv[1])
log_dir = Path(sys.argv[2])
json_path = Path(sys.argv[3])
csv_path = Path(sys.argv[4])


rows: list[dict[str, object]] = []


for raw in rc_path.read_text(
    encoding="utf-8"
).splitlines():

    if not raw.strip():
        continue

    lemma, kind, budget, search, rc_raw = (
        raw.split("\t")
    )

    rc = int(rc_raw)

    log_path = (
        log_dir
        / f"{lemma}.log"
    )

    text = log_path.read_text(
        encoding="utf-8",
        errors="replace",
    )


    pattern = re.compile(
        rf"(?m)^\s*"
        rf"{re.escape(lemma)}"
        rf"\s+\("
        rf"(all-traces|exists-trace)"
        rf"\):\s+"
        rf"(verified|falsified|"
        rf"analysis incomplete|"
        rf"unproven|unknown)"
        rf"(?:\s+\(([^)]*)\))?"
    )


    matches = list(
        pattern.finditer(text)
    )


    status = None
    reported_kind = None
    details = None


    if matches:
        match = matches[-1]

        reported_kind = match.group(1)
        status = match.group(2)
        details = match.group(3)


    if rc == 124:
        classification = "timeout"

    elif rc != 0:
        classification = "execution_error"

    elif status == "verified":
        classification = "verified"

    elif status == "falsified":
        classification = "falsified"

    elif status in {
        "analysis incomplete",
        "unproven",
        "unknown",
    }:
        classification = "incomplete"

    else:
        classification = "completed_without_summary"


    partial_matches = re.findall(
        r"(\d+)\s+partial deconstructions? left",
        text,
        flags=re.IGNORECASE,
    )

    partial = (
        max(
            (int(x) for x in partial_matches),
            default=0,
        )
    )


    row = {
        "lemma":
            lemma,

        "declared_kind":
            kind,

        "reported_kind":
            reported_kind,

        "budget_seconds":
            int(budget),

        "search":
            search,

        "return_code":
            rc,

        "tamarin_status":
            status,

        "details":
            details,

        "classification":
            classification,

        "max_partial_deconstructions":
            partial,

        "log":
            log_path.as_posix(),
    }


    rows.append(row)


verified = [
    row["lemma"]
    for row in rows
    if row["classification"] == "verified"
]

falsified = [
    row["lemma"]
    for row in rows
    if row["classification"] == "falsified"
]

timeouts = [
    row["lemma"]
    for row in rows
    if row["classification"] == "timeout"
]

errors = [
    row["lemma"]
    for row in rows
    if row["classification"]
    in {
        "execution_error",
        "completed_without_summary",
    }
]

incomplete = [
    row["lemma"]
    for row in rows
    if row["classification"] == "incomplete"
]


nonvacuity = {
    name:
        name in verified
    for name in [
        "executable_initial_accept",
        "executable_same_epoch_recovery",
        "revocation_reachable",
    ]
}


if len(verified) == 11:
    scientific_state = (
        "ALL_11_ISOLATED_LEMMAS_VERIFIED"
    )

elif falsified:
    scientific_state = (
        "ONE_OR_MORE_LEMMAS_FALSIFIED_"
        "SEMANTIC_ANALYSIS_REQUIRED"
    )

elif errors:
    scientific_state = (
        "ISOLATED_PROOF_EXECUTION_ANOMALY"
    )

elif timeouts:
    scientific_state = (
        "PARTIAL_FORMAL_RESULT_WITH_TIMEOUTS"
    )

elif incomplete:
    scientific_state = (
        "PARTIAL_FORMAL_RESULT_INCOMPLETE"
    )

else:
    scientific_state = (
        "UNCLASSIFIED_FORMAL_RESULT"
    )


payload = {
    "schema_version": 1,

    "step":
        "STEP7D1P_ISOLATED_PROOF_MATRIX",

    "model_class":
        "LKH_AUTHORIZATION_TRANSPORT_ABSTRACTION",

    "docker_only":
        True,

    "proof_network":
        "none",

    "expected_lemmas":
        11,

    "verified_count":
        len(verified),

    "falsified_count":
        len(falsified),

    "timeout_count":
        len(timeouts),

    "incomplete_count":
        len(incomplete),

    "execution_anomaly_count":
        len(errors),

    "verified_lemmas":
        verified,

    "falsified_lemmas":
        falsified,

    "timeout_lemmas":
        timeouts,

    "incomplete_lemmas":
        incomplete,

    "execution_anomalies":
        errors,

    "nonvacuity":
        nonvacuity,

    "rows":
        rows,

    "scientific_state":
        scientific_state,

    "formal_security_claim_ready":
        len(verified) == 11,

    "full_ranger_formally_verified":
        False,
}


json_path.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


with csv_path.open(
    "w",
    encoding="utf-8",
    newline="",
) as handle:

    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "lemma",
            "declared_kind",
            "reported_kind",
            "budget_seconds",
            "search",
            "return_code",
            "tamarin_status",
            "details",
            "classification",
            "max_partial_deconstructions",
            "log",
        ],
    )

    writer.writeheader()

    for row in rows:
        writer.writerow(row)


print(
    json.dumps(
        {
            "verified_count":
                len(verified),

            "falsified_count":
                len(falsified),

            "timeout_count":
                len(timeouts),

            "incomplete_count":
                len(incomplete),

            "execution_anomaly_count":
                len(errors),

            "verified_lemmas":
                verified,

            "falsified_lemmas":
                falsified,

            "timeout_lemmas":
                timeouts,

            "nonvacuity":
                nonvacuity,

            "scientific_state":
                scientific_state,
        },
        indent=2,
        sort_keys=True,
    )
)
PY


# -------------------------------------------------------------------
# 5. Human-readable matrix
# -------------------------------------------------------------------

echo
echo "===== 5. PROOF MATRIX ====="

docker compose \
    -f "$ROOT_COMPOSE" \
    run \
    --rm \
    -T \
    --no-deps \
    ranger \
    python - "$SUMMARY" <<'PY'
import json
import sys
from pathlib import Path


data = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)


print(
    f"{'LEMMA':44s} "
    f"{'CLASSIFICATION':26s} "
    f"{'RC':>4s}"
)

print("-" * 80)


for row in data["rows"]:

    print(
        f"{row['lemma'][:44]:44s} "
        f"{row['classification'][:26]:26s} "
        f"{row['return_code']:>4d}"
    )


print()
print(
    f"VERIFIED={data['verified_count']}/11"
)

print(
    f"FALSIFIED={data['falsified_count']}"
)

print(
    f"TIMEOUT={data['timeout_count']}"
)

print(
    f"INCOMPLETE={data['incomplete_count']}"
)

print(
    "STATE="
    + data["scientific_state"]
)
PY


# -------------------------------------------------------------------
# 6. Preserve exact image and model identities.
# -------------------------------------------------------------------

echo
echo "===== 6. EVIDENCE IDENTITIES ====="

docker image inspect \
    "$IMAGE" \
    --format '{{.Id}}' \
    > "$OUT/tamarin-image-id.txt"


docker compose \
    -f "$ROOT_COMPOSE" \
    run \
    --rm \
    -T \
    --no-deps \
    ranger \
    sha256sum \
        "$MODEL" \
        docker/tamarin/Dockerfile \
        docker/tamarin/toolchain.lock.json \
        > "$OUT/formal-inputs.sha256"


echo "FORMAL_INPUT_IDENTITIES=PASS"


# -------------------------------------------------------------------
# 7. Evidence package generated and checked inside Docker.
# -------------------------------------------------------------------

echo
echo "===== 7. EVIDENCE PACKAGE ====="

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

        find '$OUT' \
            -type f \
            ! -name '*.tar.gz' \
            ! -name '*.tar.gz.sha256' \
            -print0 \
        | sort -z \
        | xargs -0 sha256sum \
        > '$OUT/evidence.sha256'

        sha256sum \
            -c \
            '$OUT/evidence.sha256' \
            > '$OUT/evidence-verify.log'

        tar \
            --exclude='*.tar.gz' \
            --exclude='*.tar.gz.sha256' \
            -czf \
            '$OUT/step7d1p-evidence.tar.gz' \
            '$OUT'

        sha256sum \
            '$OUT/step7d1p-evidence.tar.gz' \
            > '$OUT/step7d1p-evidence.tar.gz.sha256'

        sha256sum \
            -c \
            '$OUT/step7d1p-evidence.tar.gz.sha256'
    "


echo
echo "===================================================================="
echo "STEP 7D.1-P COMPLETE"
echo
echo "RESULT:"
echo "  $SUMMARY"
echo
echo "CSV:"
echo "  $CSV"
echo
echo "MODEL WAS NOT MODIFIED"
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
