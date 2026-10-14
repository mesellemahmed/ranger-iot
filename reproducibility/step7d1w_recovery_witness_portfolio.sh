#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"
FORMAL_COMPOSE="compose.reproducibility.yaml"

MODEL="formal/tamarin/ranger_authorization_transport_v2.spthy"

PREV="artifacts/article-evidence/30-step7d1-semantic-repair"
TOOLCHAIN="artifacts/article-evidence/26-step7d1-docker-reproducible"

OUT="artifacts/article-evidence/31-step7d1-recovery-witness-portfolio"

ATTEMPT_DIR="$OUT/attempts"
SUMMARY="$OUT/step7d1w-summary.json"

IMAGE="ranger-tamarin:1.12.0-repro"

LEMMA="executable_same_epoch_recovery"

mkdir -p "$ATTEMPT_DIR"

echo "===================================================================="
echo "RANGER-IOT — STEP 7D.1-W"
echo "RECOVERY EXECUTABILITY WITNESS PORTFOLIO"
echo
echo "TARGET:"
echo "  $LEMMA"
echo
echo "MODEL MODIFICATION     = NONE"
echo "IMPLEMENTATION CHANGE = NONE"
echo "DOCKER ONLY"
echo "PROOF NETWORK          = NONE"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="


# ==================================================================
# 1. PRECONDITIONS
# ==================================================================

echo
echo "===== 1. PRECONDITIONS ====="

test -f "$MODEL"
test -f "$PREV/proof-matrix-v2.json"
test -f "$TOOLCHAIN/tamarin-image-id.txt"


EXPECTED_IMAGE_ID="$(
    tr -d '\r\n' \
      < "$TOOLCHAIN/tamarin-image-id.txt"
)"

ACTUAL_IMAGE_ID="$(
    docker image inspect \
      "$IMAGE" \
      --format '{{.Id}}'
)"


echo "EXPECTED_IMAGE_ID=$EXPECTED_IMAGE_ID"
echo "ACTUAL_IMAGE_ID=$ACTUAL_IMAGE_ID"


if [ "$EXPECTED_IMAGE_ID" != "$ACTUAL_IMAGE_ID" ]; then
    echo "ERROR: TAMARIN IMAGE DRIFT"
    exit 1
fi


echo "TAMARIN_IMAGE_IDENTITY=PASS"


# ==================================================================
# 2. VERIFY THAT V2 REALLY IS 10/11 WITH THIS ONE TIMEOUT
# ==================================================================

echo
echo "===== 2. VERIFY V2 BASELINE ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$PREV/proof-matrix-v2.json" \
    "$LEMMA" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


summary_path = Path(sys.argv[1])
target = sys.argv[2]


data = json.loads(
    summary_path.read_text(
        encoding="utf-8"
    )
)


checks = {
    "verified_10":
        data.get(
            "verified_count"
        )
        == 10,

    "falsified_0":
        data.get(
            "falsified_count"
        )
        == 0,

    "timeout_1":
        data.get(
            "timeout_count"
        )
        == 1,

    "only_target_timeout":
        data.get(
            "timeout_lemmas"
        )
        == [
            target
        ],

    "no_execution_anomaly":
        data.get(
            "execution_anomaly_count"
        )
        == 0,
}


for name, passed in checks.items():

    print(
        f"{name:32s}",
        "PASS"
        if passed
        else "FAIL",
    )


if not all(
    checks.values()
):
    raise SystemExit(
        "Unexpected STEP7D1-SR baseline"
    )


print()
print(
    "STEP7D1_V2_10_OF_11_BASELINE=PASS"
)
PY


# ==================================================================
# 3. FREEZE MODEL IDENTITY
# ==================================================================

echo
echo "===== 3. FREEZE MODEL IDENTITY ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
    "$MODEL" \
    > "$OUT/model-before.sha256"


cat "$OUT/model-before.sha256"


echo "MODEL_IDENTITY_BEFORE=PASS"


# ==================================================================
# 4. OFFLINE UTF-8 RUNTIME CONTRACT
# ==================================================================

echo
echo "===== 4. OFFLINE RUNTIME CONTRACT ====="

docker compose \
  -f "$FORMAL_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  -e LANG=C.UTF-8 \
  -e LC_ALL=C.UTF-8 \
  tamarin \
  bash -lc '
    set -euo pipefail

    test "$LANG" = "C.UTF-8"
    test "$LC_ALL" = "C.UTF-8"
    test "$(locale charmap)" = "UTF-8"

    tamarin-prover --version

    echo "STEP7D1W_RUNTIME=PASS"
  '


# ==================================================================
# 5. ATTEMPT EXECUTOR
# ==================================================================

run_attempt()
{
    local name="$1"
    local search="$2"
    local heuristic="$3"
    local budget="$4"
    local auto_sources="$5"

    local log="$ATTEMPT_DIR/${name}.log"
    local json="$ATTEMPT_DIR/${name}.json"
    local dot="$ATTEMPT_DIR/${name}.dot"
    local result="$ATTEMPT_DIR/${name}-result.json"
    local rc_file="$ATTEMPT_DIR/${name}.rc"

    local auto_flag=""

    if [ "$auto_sources" = "yes" ]; then
        auto_flag="--auto-sources"
    fi


    echo
    echo "----------------------------------------------------------------"
    echo "ATTEMPT=$name"
    echo "LEMMA=$LEMMA"
    echo "SEARCH=$search"
    echo "HEURISTIC=$heuristic"
    echo "AUTO_SOURCES=$auto_sources"
    echo "BUDGET=$budget"
    echo "----------------------------------------------------------------"


    # --------------------------------------------------------------
    # IMPORTANT:
    #
    # Never toggle global errexit inside this function.
    #
    # Commands expected to return non-zero are executed as the
    # condition of an if statement. Bash therefore permits us to
    # capture:
    #
    #   0   completed
    #   124 timeout
    #   other execution status
    #
    # without aborting the parent portfolio.
    # --------------------------------------------------------------

    local tamarin_rc=0

    if docker compose \
      -f "$FORMAL_COMPOSE" \
      run \
      --rm \
      -T \
      --no-deps \
      -e LANG=C.UTF-8 \
      -e LC_ALL=C.UTF-8 \
      tamarin \
      bash -lc "
        timeout ${budget}s \
          tamarin-prover \
            '$MODEL' \
            '--prove=${LEMMA}' \
            '--stop-on-trace=${search}' \
            '--heuristic=${heuristic}' \
            ${auto_flag} \
            '--output-json=/workspace/${json}' \
            '--output-dot=/workspace/${dot}' \
            +RTS -N2 -RTS
      " \
      > "$log" \
      2>&1
    then
        tamarin_rc=0
    else
        tamarin_rc=$?
    fi


    echo "$tamarin_rc" \
      > "$rc_file"


    echo "TAMARIN_RC=$tamarin_rc"


    # --------------------------------------------------------------
    # Scientific classification inside ranger Docker.
    # Again, non-zero classifier codes are DATA, not shell failures:
    #
    #   0  = verified
    #   10 = timeout/unresolved
    #   11 = incomplete
    #   20 = falsified
    #   30+ execution anomaly
    # --------------------------------------------------------------

    local classifier_rc=0

    if docker compose \
      -f "$ROOT_COMPOSE" \
      run \
      --rm \
      -T \
      --no-deps \
      ranger \
      python - \
        "$log" \
        "$LEMMA" \
        "$tamarin_rc" \
        "$name" \
        "$search" \
        "$heuristic" \
        "$budget" \
        "$auto_sources" \
        "$result" <<'PYCLASS'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


log_path = Path(sys.argv[1])
lemma = sys.argv[2]
rc = int(sys.argv[3])

name = sys.argv[4]
search = sys.argv[5]
heuristic = sys.argv[6]
budget = int(sys.argv[7])
auto_sources = sys.argv[8] == "yes"

result_path = Path(sys.argv[9])


text = log_path.read_text(
    encoding="utf-8",
    errors="replace",
)


match = re.search(
    rf"(?m)^\s*"
    rf"{re.escape(lemma)}"
    rf"\s+\(exists-trace\):"
    rf"\s+"
    rf"(verified|falsified|"
    rf"analysis incomplete|"
    rf"unproven|unknown)"
    rf"(?:\s+\(([^)]*)\))?",
    text,
)


status = (
    match.group(1)
    if match
    else None
)


details = (
    match.group(2)
    if (
        match
        and match.group(2)
    )
    else None
)


depths = [
    int(value)
    for value in re.findall(
        r"searching for attacks at depth:\s*(\d+)",
        text,
    )
]


attack_depths = [
    int(value)
    for value in re.findall(
        r"attack found at depth:\s*(\d+)",
        text,
    )
]


if rc == 124:
    classification = "timeout"
    exit_code = 10

elif rc != 0:
    classification = "execution_error"
    exit_code = 30

elif status == "verified":
    classification = "verified"
    exit_code = 0

elif status == "falsified":
    classification = "falsified"
    exit_code = 20

elif status in {
    "analysis incomplete",
    "unproven",
    "unknown",
}:
    classification = "incomplete"
    exit_code = 11

else:
    classification = "missing_summary"
    exit_code = 31


payload = {
    "schema_version":
        2,

    "attempt":
        name,

    "lemma":
        lemma,

    "search":
        search,

    "heuristic":
        heuristic,

    "auto_sources":
        auto_sources,

    "budget_seconds":
        budget,

    "return_code":
        rc,

    "tamarin_status":
        status,

    "details":
        details,

    "classification":
        classification,

    "maximum_search_depth_seen":
        max(
            depths,
            default=None,
        ),

    "attack_depths":
        attack_depths,

    "attack_found":
        bool(
            attack_depths
        ),
}


result_path.write_text(
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


raise SystemExit(
    exit_code
)
PYCLASS
    then
        classifier_rc=0
    else
        classifier_rc=$?
    fi


    echo "CLASSIFIER_RC=$classifier_rc"


    #
    # Important:
    # this return is now safe because the function itself never
    # re-enabled errexit.
    #

    return "$classifier_rc"
}


# ==================================================================
# 6. SEARCH PORTFOLIO
#
# No model change.
# Different automatic search orders only.
# ==================================================================

echo
echo "===== 5. RECOVERY WITNESS SEARCH PORTFOLIO ====="


VERIFIED_ATTEMPT=""
SCIENTIFIC_FAILURE="false"
EXECUTION_FAILURE="false"


ATTEMPTS=(
  "seqdfs-smart|SEQDFS|s|180|no"
  "dfs-consecutive|DFS|C|240|no"
  "bfs-consecutive|BFS|C|300|no"
  "dfs-smart-autosources|DFS|s|300|yes"
)


for spec in "${ATTEMPTS[@]}"; do

    IFS='|' read -r \
      name \
      search \
      heuristic \
      budget \
      auto_sources \
      <<< "$spec"


    set +e

    run_attempt \
      "$name" \
      "$search" \
      "$heuristic" \
      "$budget" \
      "$auto_sources"

    ATTEMPT_RC=$?

    set -e


    if [ "$ATTEMPT_RC" -eq 0 ]; then

        VERIFIED_ATTEMPT="$name"

        echo
        echo "RECOVERY_WITNESS_FOUND=YES"
        echo "VERIFIED_ATTEMPT=$VERIFIED_ATTEMPT"

        break

    fi


    if [ "$ATTEMPT_RC" -eq 20 ]; then

        SCIENTIFIC_FAILURE="true"

        echo
        echo "RECOVERY_EXECUTABILITY=FALSIFIED"

        break

    fi


    if [ "$ATTEMPT_RC" -ge 30 ]; then

        EXECUTION_FAILURE="true"

        echo
        echo "RECOVERY_WITNESS_EXECUTION_ANOMALY=YES"

        break

    fi


    echo "ATTEMPT_UNRESOLVED_CONTINUING=YES"

done


# ==================================================================
# 7. MODEL IDENTITY AFTER PORTFOLIO
# ==================================================================

echo
echo "===== 6. VERIFY MODEL UNCHANGED ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
    "$MODEL" \
    > "$OUT/model-after.sha256"


docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$OUT/model-before.sha256" \
    "$OUT/model-after.sha256" <<'PY'
from pathlib import Path
import sys


before = Path(
    sys.argv[1]
).read_text(
    encoding="utf-8"
).strip()


after = Path(
    sys.argv[2]
).read_text(
    encoding="utf-8"
).strip()


print(
    f"BEFORE={before}"
)

print(
    f"AFTER ={after}"
)


if before != after:
    raise SystemExit(
        "MODEL CHANGED DURING WITNESS PORTFOLIO"
    )


print()
print(
    "MODEL_UNCHANGED=PASS"
)
PY


# ==================================================================
# 8. FINAL SCIENTIFIC AGGREGATION
# ==================================================================

echo
echo "===== 7. AGGREGATE STEP7D1 V2 RESULT ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$PREV/proof-matrix-v2.json" \
    "$ATTEMPT_DIR" \
    "$VERIFIED_ATTEMPT" \
    "$SCIENTIFIC_FAILURE" \
    "$EXECUTION_FAILURE" \
    "$SUMMARY" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


previous = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

attempt_dir = Path(sys.argv[2])

verified_attempt = sys.argv[3] or None

scientific_failure = (
    sys.argv[4].lower()
    == "true"
)

execution_failure = (
    sys.argv[5].lower()
    == "true"
)

summary_path = Path(sys.argv[6])


attempts = []


for path in sorted(
    attempt_dir.glob(
        "*-result.json"
    )
):

    attempts.append(
        json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    )


target = (
    "executable_same_epoch_recovery"
)


base_verified = set(
    previous[
        "verified_lemmas"
    ]
)


if verified_attempt:
    final_verified = (
        base_verified
        | {
            target
        }
    )
else:
    final_verified = (
        base_verified
    )


all_11 = (
    len(
        final_verified
    )
    == 11
    and
    not scientific_failure
    and
    not execution_failure
)


if all_11:

    state = (
        "STEP7D1_V2_ALL_11_LEMMAS_VERIFIED"
    )

elif scientific_failure:

    state = (
        "STEP7D1_V2_RECOVERY_NONVACUITY_FALSIFIED"
    )

elif execution_failure:

    state = (
        "STEP7D1_V2_WITNESS_EXECUTION_ANOMALY"
    )

else:

    state = (
        "STEP7D1_V2_10_VERIFIED_"
        "RECOVERY_WITNESS_UNRESOLVED"
    )


payload = {
    "schema_version":
        1,

    "step":
        "STEP7D1_RECOVERY_WITNESS_PORTFOLIO",

    "model":
        (
            "formal/tamarin/"
            "ranger_authorization_transport_v2.spthy"
        ),

    "model_class":
        (
            "LKH_AUTHORIZATION_TRANSPORT_"
            "ABSTRACTION_V2"
        ),

    "model_modified":
        False,

    "implementation_modified":
        False,

    "previous_verified_count":
        previous[
            "verified_count"
        ],

    "previous_falsified_count":
        previous[
            "falsified_count"
        ],

    "previous_timeout_count":
        previous[
            "timeout_count"
        ],

    "target_lemma":
        target,

    "attempts":
        attempts,

    "verified_attempt":
        verified_attempt,

    "verified_count":
        len(
            final_verified
        ),

    "verified_lemmas":
        sorted(
            final_verified
        ),

    "all_11_verified":
        all_11,

    "scientific_state":
        state,

    "formal_security_claim_ready_for_step7d1":
        all_11,

    "full_ranger_formally_verified":
        False,

    "remaining_scope_if_all_11_verified": [
        "Exact LKH tree cryptographic semantics",
        "Multiple sequential epochs",
        "Replay and freshness across epochs",
        "Compromise timing refinement",
        "Implementation-to-action correspondence"
    ],
}


summary_path.write_text(
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
        {
            "verified_attempt":
                verified_attempt,

            "verified_count":
                len(
                    final_verified
                ),

            "all_11_verified":
                all_11,

            "scientific_state":
                state,

            "full_ranger_formally_verified":
                False,
        },
        indent=2,
        sort_keys=True,
    )
)
PY


# ==================================================================
# 9. IMPLEMENTATION FREEZE
# ==================================================================

echo
echo "===== 8. IMPLEMENTATION FREEZE CHECK ====="

FREEZE="artifacts/article-evidence/25-step7d1-formal-model/implemented-semantics-before.sha256"


if [ -f "$FREEZE" ]; then

    docker compose \
      -f "$ROOT_COMPOSE" \
      run \
      --rm \
      -T \
      --no-deps \
      ranger \
      sha256sum \
      -c \
      "$FREEZE"

    echo "IMPLEMENTATION_UNCHANGED=PASS"

else

    echo "IMPLEMENTATION_FREEZE_BASELINE=MISSING"
    exit 1

fi


# ==================================================================
# 10. EVIDENCE MANIFEST/PACKAGE
# ==================================================================

echo
echo "===== 9. EVIDENCE PACKAGE ====="

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

    MAN=/tmp/step7d1w.sha256
    TAR=/tmp/step7d1w.tar.gz

    rm -f \
      \"\$MAN\" \
      \"\$TAR\"

    find '$OUT' \
      -type f \
      ! -name 'evidence.sha256' \
      ! -name 'evidence-verify.log' \
      ! -name 'step7d1w-evidence.tar.gz' \
      ! -name 'step7d1w-evidence.tar.gz.sha256' \
      -print0 \
    | sort -z \
    | xargs -0 sha256sum \
      > \"\$MAN\"

    cp \
      \"\$MAN\" \
      '$OUT/evidence.sha256'

    sha256sum \
      -c \
      '$OUT/evidence.sha256' \
      > '$OUT/evidence-verify.log'

    tar \
      -czf \
      \"\$TAR\" \
      '$OUT' \
      '$MODEL'

    tar \
      -tzf \
      \"\$TAR\" \
      >/dev/null

    cp \
      \"\$TAR\" \
      '$OUT/step7d1w-evidence.tar.gz'

    sha256sum \
      '$OUT/step7d1w-evidence.tar.gz' \
      > '$OUT/step7d1w-evidence.tar.gz.sha256'

    sha256sum \
      -c \
      '$OUT/step7d1w-evidence.tar.gz.sha256'
  "


echo
echo "===================================================================="
echo "STEP 7D.1-W COMPLETE"
echo
echo "SUMMARY:"
echo "  $SUMMARY"
echo
echo "MODEL MODIFIED          = NO"
echo "IMPLEMENTATION MODIFIED = NO"
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
