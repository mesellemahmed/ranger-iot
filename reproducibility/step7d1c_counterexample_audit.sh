#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"
FORMAL_COMPOSE="compose.reproducibility.yaml"

MODEL="formal/tamarin/ranger_authorization_transport.spthy"

PREV26="artifacts/article-evidence/26-step7d1-docker-reproducible"
PREV28="artifacts/article-evidence/28-step7d1-utf8-isolated-proof-matrix"

OUT="artifacts/article-evidence/29-step7d1-counterexample-audit"

RAW="$OUT/raw"
SUMMARY="$OUT/counterexample-audit.json"
MODEL_EXTRACT="$OUT/relevant-formal-semantics.txt"

IMAGE="ranger-tamarin:1.12.0-repro"

mkdir -p "$RAW"

echo "===================================================================="
echo "RANGER-IOT — STEP 7D.1-CEX"
echo "COUNTEREXAMPLE AUDIT"
echo
echo "TARGETS:"
echo "  revoked_never_accepts"
echo "  epoch_key_secrecy_unless_compromised"
echo
echo "MODEL MODIFICATION = NONE"
echo "DOCKER ONLY"
echo "PROOF NETWORK = NONE"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="


# ------------------------------------------------------------------
# 1. Freeze / identity checks
# ------------------------------------------------------------------

echo
echo "===== 1. IDENTITY PREFLIGHT ====="

test -f "$MODEL"
test -f "$PREV26/tamarin-image-id.txt"
test -f "$PREV28/isolated-proof-matrix.json"

EXPECTED_IMAGE_ID="$(
    tr -d '\r\n' \
      < "$PREV26/tamarin-image-id.txt"
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

echo "IMAGE_IDENTITY=PASS"


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

echo "FORMAL_INPUT_HASHES=PASS"


# ------------------------------------------------------------------
# 2. Verify previous scientific classification
# ------------------------------------------------------------------

echo
echo "===== 2. VERIFY P2 RESULT ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$PREV28/isolated-proof-matrix.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


data = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)


expected_verified = {
    "executable_initial_accept",
    "executable_same_epoch_recovery",
    "revocation_reachable",
    "accept_has_rekey_origin",
    "accept_requires_authorization",
    "recovery_requester_authorized",
    "recovery_same_epoch",
    "recovery_accept_has_rekey_origin",
}


expected_falsified = {
    "revoked_never_accepts",
    "epoch_key_secrecy_unless_compromised",
}


expected_timeout = {
    "recovery_helper_authorized",
}


checks = {
    "verified_8":
        set(data["verified_lemmas"])
        == expected_verified,

    "falsified_2":
        set(data["falsified_lemmas"])
        == expected_falsified,

    "timeout_1":
        set(data["timeout_lemmas"])
        == expected_timeout,

    "nonvacuity_all":
        all(
            data["nonvacuity"].values()
        ),
}


for name, value in checks.items():
    print(
        f"{name:28s}",
        "PASS" if value else "FAIL",
    )


if not all(checks.values()):
    raise SystemExit(
        "Unexpected P2 formal result"
    )


print()
print("P2_RESULT_CONTRACT=PASS")
PY


# ------------------------------------------------------------------
# 3. Extract the formal semantics relevant to the two failures
# ------------------------------------------------------------------

echo
echo "===== 3. EXTRACT RELEVANT MODEL SECTIONS ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$MODEL" \
    "$MODEL_EXTRACT" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


source = Path(sys.argv[1]).read_text(
    encoding="utf-8"
)

output = Path(sys.argv[2])


wanted = [
    "Setup",
    "Start_Rekey",
    "Accept_Initial",
    "Start_Recovery",
    "Recovery_Response",
    "Accept_Recovery",
    "Compromise_Authorized_Member",
    "Compromise_Group_Manager",
]


chunks = []


for name in wanted:

    pattern = re.compile(
        rf"(?ms)"
        rf"^rule\s+{re.escape(name)}\s*:"
        rf".*?"
        rf"(?="
        rf"^rule\s+"
        rf"|^lemma\s+"
        rf"|^restriction\s+"
        rf"|^end\s*$"
        rf")"
    )

    match = pattern.search(source)

    chunks.append(
        "=" * 72
    )

    chunks.append(
        f"RULE {name}"
    )

    chunks.append(
        "=" * 72
    )

    if match:
        chunks.append(
            match.group(0).rstrip()
        )
    else:
        chunks.append(
            "<NOT FOUND>"
        )

    chunks.append("")


lemma_names = [
    "accept_requires_authorization",
    "revoked_never_accepts",
    "epoch_key_secrecy_unless_compromised",
    "recovery_helper_authorized",
]


for name in lemma_names:

    pattern = re.compile(
        rf"(?ms)"
        rf"^lemma\s+{re.escape(name)}"
        rf"\s*:"
        rf".*?"
        rf"(?="
        rf"^lemma\s+"
        rf"|^restriction\s+"
        rf"|^end\s*$"
        rf")"
    )

    match = pattern.search(source)

    chunks.append(
        "=" * 72
    )

    chunks.append(
        f"LEMMA {name}"
    )

    chunks.append(
        "=" * 72
    )

    if match:
        chunks.append(
            match.group(0).rstrip()
        )
    else:
        chunks.append(
            "<NOT FOUND>"
        )

    chunks.append("")


output.write_text(
    "\n".join(chunks) + "\n",
    encoding="utf-8",
)


print(
    output.read_text(
        encoding="utf-8"
    )
)

print(
    "RELEVANT_MODEL_EXTRACTION=PASS"
)
PY


# ------------------------------------------------------------------
# 4. Dedicated shortest counterexample traces
# ------------------------------------------------------------------

echo
echo "===== 4. EXTRACT COUNTEREXAMPLES ====="


run_cex()
{
    local lemma="$1"
    local budget="$2"

    local json="$RAW/${lemma}.json"
    local dot="$RAW/${lemma}.dot"
    local log="$RAW/${lemma}.log"

    echo
    echo "----------------------------------------------------------------"
    echo "LEMMA=$lemma"
    echo "BUDGET=$budget"
    echo "SEARCH=BFS"
    echo "----------------------------------------------------------------"

    set +e

    docker compose \
      -f "$FORMAL_COMPOSE" \
      run \
      --rm \
      -T \
      --no-deps \
      -e LANG=C.UTF-8 \
      -e LC_ALL=C.UTF-8 \
      tamarin \
      bash -lc "
        set -o pipefail

        timeout ${budget}s \
          tamarin-prover \
            --prove='${lemma}' \
            --stop-on-trace=BFS \
            --output-json='/workspace/${json}' \
            --output-dot='/workspace/${dot}' \
            '${MODEL}' \
            +RTS -N2 -RTS
      " \
      > "$log" \
      2>&1

    local rc=$?

    set -e

    echo "$rc" > "$RAW/${lemma}.rc"

    echo "RC=$rc"

    test -s "$log"

    if [ -s "$json" ]; then
        echo "JSON_TRACE=PASS"
    else
        echo "JSON_TRACE=MISSING"
    fi

    if [ -s "$dot" ]; then
        echo "DOT_TRACE=PASS"
    else
        echo "DOT_TRACE=MISSING"
    fi
}


run_cex \
  "revoked_never_accepts" \
  180

run_cex \
  "epoch_key_secrecy_unless_compromised" \
  300


# ------------------------------------------------------------------
# 5. Render DOT traces without network
# ------------------------------------------------------------------

echo
echo "===== 5. RENDER DOT TRACES ====="

for lemma in \
  revoked_never_accepts \
  epoch_key_secrecy_unless_compromised
do

    DOT="$RAW/${lemma}.dot"

    if [ -s "$DOT" ]; then

        docker compose \
          -f "$FORMAL_COMPOSE" \
          run \
          --rm \
          -T \
          --no-deps \
          -e LANG=C.UTF-8 \
          -e LC_ALL=C.UTF-8 \
          tamarin \
          bash -lc "
            cd /workspace

            dot \
              -Tsvg \
              -O \
              '${DOT}'
          "

        echo "${lemma}_DOT_RENDER=PASS"

    fi

done


# ------------------------------------------------------------------
# 6. Parse both proof summaries and raw exported graphs
# ------------------------------------------------------------------

echo
echo "===== 6. COUNTEREXAMPLE STRUCTURAL ANALYSIS ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$RAW" \
    "$SUMMARY" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


raw = Path(sys.argv[1])
summary_path = Path(sys.argv[2])


lemmas = [
    "revoked_never_accepts",
    "epoch_key_secrecy_unless_compromised",
]


KEYWORDS = (
    "Accept",
    "RecoveryAccept",
    "Authorized",
    "Revoked",
    "RevokedAt",
    "Rekey",
    "Start",
    "K(",
    "KU(",
    "KD(",
    "Compromise",
    "CompromiseGM",
    "MemberKey",
    "SurvivorKey",
    "EpochCipher",
    "Stale",
    "Current",
    "RecoveryRequest",
    "RecoveryResponse",
)


def walk(
    value: Any,
    prefix: str = "",
) -> list[str]:

    output: list[str] = []


    if isinstance(value, dict):

        for key, item in value.items():

            child = (
                f"{prefix}.{key}"
                if prefix
                else str(key)
            )

            output.extend(
                walk(
                    item,
                    child,
                )
            )


    elif isinstance(value, list):

        for index, item in enumerate(value):

            output.extend(
                walk(
                    item,
                    f"{prefix}[{index}]",
                )
            )


    elif isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):

        rendered = str(value)

        if any(
            keyword.lower()
            in rendered.lower()
            for keyword in KEYWORDS
        ):
            output.append(
                f"{prefix} = {rendered}"
            )


    return output


results = {}


for lemma in lemmas:

    log_path = raw / f"{lemma}.log"
    json_path = raw / f"{lemma}.json"
    dot_path = raw / f"{lemma}.dot"
    rc_path = raw / f"{lemma}.rc"


    log = log_path.read_text(
        encoding="utf-8",
        errors="replace",
    )


    rc = int(
        rc_path.read_text(
            encoding="utf-8"
        ).strip()
    )


    status_match = re.search(
        rf"(?m)^\s*"
        rf"{re.escape(lemma)}"
        rf"\s+\(all-traces\):"
        rf"\s+"
        rf"(verified|falsified|"
        rf"analysis incomplete|"
        rf"unproven|unknown)"
        rf"(?:\s+\(([^)]*)\))?",
        log,
    )


    status = (
        status_match.group(1)
        if status_match
        else None
    )


    details = (
        status_match.group(2)
        if (
            status_match
            and status_match.group(2)
        )
        else None
    )


    graph_count = None
    top_keys: list[str] = []
    interesting_json: list[str] = []


    if json_path.exists() and json_path.stat().st_size:

        try:
            data = json.loads(
                json_path.read_text(
                    encoding="utf-8"
                )
            )

            if isinstance(data, dict):

                top_keys = list(
                    data.keys()
                )

                graphs = data.get(
                    "graphs"
                )

                if isinstance(graphs, list):
                    graph_count = len(
                        graphs
                    )


            interesting_json = walk(
                data
            )

        except Exception as exc:

            interesting_json = [
                "JSON_PARSE_ERROR="
                + repr(exc)
            ]


    dot_interesting: list[str] = []


    if dot_path.exists():

        for line in dot_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():

            if any(
                keyword.lower()
                in line.lower()
                for keyword in KEYWORDS
            ):
                dot_interesting.append(
                    line.strip()
                )


    # Deduplicate while preserving order.
    interesting_json = list(
        dict.fromkeys(
            interesting_json
        )
    )[:500]


    dot_interesting = list(
        dict.fromkeys(
            dot_interesting
        )
    )[:500]


    results[lemma] = {
        "return_code":
            rc,

        "tamarin_status":
            status,

        "details":
            details,

        "json_trace_present":
            json_path.exists()
            and json_path.stat().st_size > 0,

        "dot_trace_present":
            dot_path.exists()
            and dot_path.stat().st_size > 0,

        "json_top_keys":
            top_keys,

        "graph_count":
            graph_count,

        "interesting_json":
            interesting_json,

        "interesting_dot":
            dot_interesting,
    }


revoked = results[
    "revoked_never_accepts"
]

secrecy = results[
    "epoch_key_secrecy_unless_compromised"
]


classification = {
    "revoked_counterexample_confirmed":
        (
            revoked["tamarin_status"]
            == "falsified"
            and
            revoked["json_trace_present"]
        ),

    "secrecy_counterexample_confirmed":
        (
            secrecy["tamarin_status"]
            == "falsified"
            and
            secrecy["json_trace_present"]
        ),
}


payload = {
    "schema_version":
        1,

    "step":
        "STEP7D1_CEX_COUNTEREXAMPLE_AUDIT",

    "model_modified":
        False,

    "results":
        results,

    "classification":
        classification,

    "next_decision_rule": {
        "if_counterexamples_confirmed":
            (
                "Interpret exact traces against "
                "implemented semantics before any "
                "formal-model correction."
            ),

        "if_json_missing":
            (
                "Do not change the model; diagnose "
                "trace-export invocation first."
            ),
    },
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


print("=" * 78)
print("COUNTEREXAMPLE AUDIT SUMMARY")
print("=" * 78)


for lemma, item in results.items():

    print()
    print(f"LEMMA={lemma}")
    print(
        f"STATUS={item['tamarin_status']}"
    )
    print(
        f"RC={item['return_code']}"
    )
    print(
        "JSON_TRACE="
        f"{item['json_trace_present']}"
    )
    print(
        "DOT_TRACE="
        f"{item['dot_trace_present']}"
    )
    print(
        "GRAPH_COUNT="
        f"{item['graph_count']}"
    )


    print()
    print("KEY TRACE ELEMENTS:")


    elements = (
        item["interesting_json"]
        +
        item["interesting_dot"]
    )


    for value in list(
        dict.fromkeys(elements)
    )[:100]:
        print(
            "  " + value
        )


print()
print("=" * 78)
print(
    json.dumps(
        classification,
        indent=2,
        sort_keys=True,
    )
)
print("=" * 78)
PY


# ------------------------------------------------------------------
# 7. Timeout lemma: preserve only diagnostic metadata
# ------------------------------------------------------------------

echo
echo "===== 7. TIMEOUT LEMMA STATUS ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$PREV28/isolated-proof-matrix.json" <<'PY'
import json
import sys
from pathlib import Path


data = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)


for row in data["rows"]:

    if (
        row["lemma"]
        == "recovery_helper_authorized"
    ):

        print(
            json.dumps(
                row,
                indent=2,
                sort_keys=True,
            )
        )

        break
else:
    raise SystemExit(
        "timeout lemma not found"
    )


print()
print(
    "RECOVERY_HELPER_STATUS="
    "TIMEOUT_NOT_FALSIFIED"
)
PY


# ------------------------------------------------------------------
# 8. Evidence manifest/package
#
# Build archive OUTSIDE OUT, then copy it back.
# This fixes the P2 "file changed as we read it" issue.
# ------------------------------------------------------------------

echo
echo "===== 8. EVIDENCE PACKAGE ====="

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

    TMP_MANIFEST=/tmp/step7d1c-evidence.sha256
    TMP_ARCHIVE=/tmp/step7d1c-evidence.tar.gz

    rm -f \
      \"\$TMP_MANIFEST\" \
      \"\$TMP_ARCHIVE\"

    find '$OUT' \
      -type f \
      ! -name 'evidence.sha256' \
      ! -name 'evidence-verify.log' \
      ! -name 'step7d1c-evidence.tar.gz' \
      ! -name 'step7d1c-evidence.tar.gz.sha256' \
      -print0 \
    | sort -z \
    | xargs -0 sha256sum \
      > \"\$TMP_MANIFEST\"

    cp \
      \"\$TMP_MANIFEST\" \
      '$OUT/evidence.sha256'

    sha256sum \
      -c \
      '$OUT/evidence.sha256' \
      > '$OUT/evidence-verify.log'

    tar \
      -czf \
      \"\$TMP_ARCHIVE\" \
      '$OUT'

    tar \
      -tzf \
      \"\$TMP_ARCHIVE\" \
      >/dev/null

    cp \
      \"\$TMP_ARCHIVE\" \
      '$OUT/step7d1c-evidence.tar.gz'

    sha256sum \
      '$OUT/step7d1c-evidence.tar.gz' \
      > '$OUT/step7d1c-evidence.tar.gz.sha256'

    sha256sum \
      -c \
      '$OUT/step7d1c-evidence.tar.gz.sha256'
  "


echo
echo "===================================================================="
echo "STEP 7D.1-CEX COMPLETE"
echo
echo "MODEL MODIFIED = NO"
echo
echo "SUMMARY:"
echo "  $SUMMARY"
echo
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
