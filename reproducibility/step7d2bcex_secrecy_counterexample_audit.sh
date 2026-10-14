#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"
FORMAL_COMPOSE="compose.reproducibility.yaml"

MODEL="formal/tamarin/ranger_lkh_multi_epoch_4member.spthy"

PREV="artifacts/article-evidence/33-step7d2b-lkh-multi-epoch-tamarin"
OUT="artifacts/article-evidence/34-step7d2b-secrecy-counterexample-audit"

RAW="$OUT/raw"
SUMMARY="$OUT/counterexample-audit.json"
SEMANTICS="$OUT/relevant-formal-semantics.txt"

IMAGE="ranger-tamarin:1.12.0-repro"

mkdir -p "$RAW"

echo "===================================================================="
echo "RANGER-IOT — STEP 7D.2-B-CEX"
echo "SECRECY COUNTEREXAMPLE AUDIT"
echo
echo "TARGETS:"
echo "  new_epoch_key_secret_without_relevant_compromise"
echo "  revoked_old_key_does_not_reveal_new_root_key"
echo
echo "MODEL MODIFICATION     = NONE"
echo "IMPLEMENTATION CHANGE = NONE"
echo "DOCKER ONLY"
echo "PROOF NETWORK          = NONE"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="


# ==================================================================
# 1. Preconditions
# ==================================================================

echo
echo "===== 1. PREFLIGHT ====="

test -f "$MODEL"
test -f "$PREV/proof-matrix.json"
test -f "$PREV/formal-inputs.sha256"


docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$PREV/proof-matrix.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


data = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)


expected_falsified = {
    "new_epoch_key_secret_without_relevant_compromise",
    "revoked_old_key_does_not_reveal_new_root_key",
}


checks = {
    "verified_14":
        data.get("verified_count") == 14,

    "falsified_2":
        data.get("falsified_count") == 2,

    "exact_falsified_set":
        set(
            data.get(
                "falsified_lemmas",
                [],
            )
        )
        == expected_falsified,

    "timeout_0":
        data.get("timeout_count") == 0,

    "incomplete_0":
        data.get("incomplete_count") == 0,

    "execution_errors_0":
        data.get("execution_anomaly_count") == 0,

    "state":
        data.get("scientific_state")
        ==
        "STEP7D2B_CONFIRMED_COUNTEREXAMPLE_AUDIT_REQUIRED",
}


for name, passed in checks.items():

    print(
        f"{name:34s}",
        "PASS" if passed else "FAIL",
    )


if not all(checks.values()):

    raise SystemExit(
        "Unexpected STEP7D2-B baseline"
    )


print()
print(
    "STEP7D2B_COUNTEREXAMPLE_BASELINE=PASS"
)
PY


# ==================================================================
# 2. Freeze model
# ==================================================================

echo
echo "===== 2. FREEZE MODEL ====="

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

echo "MODEL_FREEZE_BEFORE=PASS"


# ==================================================================
# 3. Extract security-relevant model semantics
# ==================================================================

echo
echo "===== 3. EXTRACT SECURITY-RELEVANT SEMANTICS ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$MODEL" \
    "$SEMANTICS" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


model = Path(sys.argv[1])

output = Path(sys.argv[2])

text = model.read_text(
    encoding="utf-8"
)


rules = [
    "Setup",
    "Start_Epoch1",
    "M3_Derive_N3_V1",
    "Start_Epoch2",
    "Compromise_M1",
    "Compromise_M2",
    "Compromise_M3",
    "Compromise_M4",
    "Compromise_GM_E1",
    "Compromise_GM_E2",
    "Leak_M4_Old_Keys_After_E1",
    "Leak_M3_Old_Keys_After_E2",
]


lemmas = [
    "new_epoch_key_secret_without_relevant_compromise",
    "revoked_old_key_does_not_reveal_new_root_key",
]


chunks: list[str] = []


def extract_rule(name: str) -> str:

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

    match = pattern.search(text)

    return (
        match.group(0).rstrip()
        if match
        else "<NOT FOUND>"
    )


def extract_lemma(name: str) -> str:

    pattern = re.compile(
        rf"(?ms)"
        rf"^lemma\s+{re.escape(name)}\s*:"
        rf".*?"
        rf"(?="
        rf"^lemma\s+"
        rf"|^restriction\s+"
        rf"|^end\s*$"
        rf")"
    )

    match = pattern.search(text)

    return (
        match.group(0).rstrip()
        if match
        else "<NOT FOUND>"
    )


for name in rules:

    chunks.extend(
        [
            "=" * 78,
            f"RULE {name}",
            "=" * 78,
            extract_rule(name),
            "",
        ]
    )


for name in lemmas:

    chunks.extend(
        [
            "=" * 78,
            f"LEMMA {name}",
            "=" * 78,
            extract_lemma(name),
            "",
        ]
    )


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
    "SECURITY_RELEVANT_SEMANTICS_EXTRACTION=PASS"
)
PY


# ==================================================================
# 4. Capture shortest counterexamples
# ==================================================================

echo
echo "===== 4. CAPTURE COUNTEREXAMPLES ====="


run_cex()
{
    local lemma="$1"
    local budget="$2"

    local log="$RAW/${lemma}.log"
    local json="$RAW/${lemma}.json"
    local dot="$RAW/${lemma}.dot"
    local rc="$RAW/${lemma}.rc"

    echo
    echo "----------------------------------------------------------------"
    echo "LEMMA=$lemma"
    echo "BUDGET=$budget"
    echo "SEARCH=BFS"
    echo "----------------------------------------------------------------"


    local proof_rc=0

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
            '--prove=${lemma}' \
            --stop-on-trace=BFS \
            '--output-json=/workspace/${json}' \
            '--output-dot=/workspace/${dot}' \
            +RTS -N2 -RTS
      " \
      > "$log" \
      2>&1
    then
        proof_rc=0
    else
        proof_rc=$?
    fi


    echo "$proof_rc" > "$rc"

    echo "RC=$proof_rc"


    if [ "$proof_rc" -ne 0 ]; then

        echo "COUNTEREXAMPLE_EXECUTION=ERROR"

        tail -100 "$log"

        return "$proof_rc"

    fi


    if [ ! -s "$json" ]; then
        echo "COUNTEREXAMPLE_JSON=MISSING"
        return 31
    fi


    if [ ! -s "$dot" ]; then
        echo "COUNTEREXAMPLE_DOT=MISSING"
        return 32
    fi


    echo "COUNTEREXAMPLE_JSON=PASS"
    echo "COUNTEREXAMPLE_DOT=PASS"

    return 0
}


run_cex \
  new_epoch_key_secret_without_relevant_compromise \
  360


run_cex \
  revoked_old_key_does_not_reveal_new_root_key \
  360


# ==================================================================
# 5. Render DOT
# ==================================================================

echo
echo "===== 5. RENDER TRACE GRAPHS ====="

for lemma in \
  new_epoch_key_secret_without_relevant_compromise \
  revoked_old_key_does_not_reveal_new_root_key
do

    DOT="$RAW/${lemma}.dot"

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
          '$DOT'
      "

    echo "${lemma}_DOT_RENDER=PASS"

done


# ==================================================================
# 6. Deep structural trace extraction
# ==================================================================

echo
echo "===== 6. STRUCTURAL COUNTEREXAMPLE ANALYSIS ====="

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
from collections import Counter
from pathlib import Path
from typing import Any


raw_dir = Path(sys.argv[1])

summary_path = Path(sys.argv[2])


lemmas = [
    "new_epoch_key_secret_without_relevant_compromise",
    "revoked_old_key_does_not_reveal_new_root_key",
]


interesting_fact_names = {
    "Setup",
    "RekeyStarted",
    "NextEpoch",
    "AuthorizedAt",
    "RevokedAt",
    "KeyVersion",
    "EpochRoot",
    "SecretEpoch",
    "LkhUpdate",
    "LkhRecipient",
    "DerivedKey",
    "Accept",
    "RecoveryAccept",
    "RecoveryRequest",
    "RecoveryResponse",
    "ReplayOldCipher",
    "ReplayOldRecoveryResponse",
    "CompromiseMember",
    "CompromiseManager",
    "OldKeyLeak",
    "K",
}


interesting_rule_names = {
    "Setup",
    "Start_Epoch1",
    "Start_Epoch2",
    "M3_Derive_N3_V1",
    "Accept_E1_M1",
    "Accept_E1_M2",
    "Accept_E1_M3",
    "Accept_E2_M1",
    "Accept_E2_M2",
    "Compromise_M1",
    "Compromise_M2",
    "Compromise_M3",
    "Compromise_M4",
    "Compromise_GM_E1",
    "Compromise_GM_E2",
    "Leak_M4_Old_Keys_After_E1",
    "Leak_M3_Old_Keys_After_E2",
}


def load_json(path: Path) -> Any:

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def fact_records(metadata: dict) -> list[dict]:

    result = []

    categories = [
        ("actions", "jgnActs"),
        ("premises", "jgnPrems"),
        ("conclusions", "jgnConcs"),
    ]

    for category, key in categories:

        for fact in metadata.get(
            key,
            [],
        ):

            name = fact.get(
                "jgnFactName"
            )

            shown = fact.get(
                "jgnFactShow"
            )

            if (
                name in interesting_fact_names
                or
                (
                    isinstance(shown, str)
                    and
                    (
                        "K(" in shown
                        or
                        "KU(" in shown
                        or
                        "KD(" in shown
                    )
                )
            ):
                result.append(
                    {
                        "category":
                            category,

                        "name":
                            name,

                        "shown":
                            shown,
                    }
                )

    return result


def analyse_graph(graph: dict) -> dict:

    nodes_out = []

    rule_counter = Counter()

    action_counter = Counter()


    for ordinal, node in enumerate(
        graph.get(
            "jgNodes",
            [],
        )
    ):

        label = node.get(
            "jgnLabel"
        )

        metadata = node.get(
            "jgnMetadata",
            {},
        ) or {}


        facts = fact_records(
            metadata
        )


        for fact in facts:

            if fact[
                "category"
            ] == "actions":

                action_counter[
                    fact["name"]
                ] += 1


        if label in interesting_rule_names:

            rule_counter[
                label
            ] += 1


        if (
            label in interesting_rule_names
            or
            facts
        ):

            nodes_out.append(
                {
                    "ordinal":
                        ordinal,

                    "label":
                        label,

                    "facts":
                        facts,
                }
            )


    return {
        "label":
            graph.get(
                "jgLabel"
            ),

        "rules":
            dict(
                rule_counter
            ),

        "actions":
            dict(
                action_counter
            ),

        "interesting_nodes":
            nodes_out,

        "setup_count":
            rule_counter[
                "Setup"
            ],

        "epoch1_start_count":
            rule_counter[
                "Start_Epoch1"
            ],

        "epoch2_start_count":
            rule_counter[
                "Start_Epoch2"
            ],

        "member_compromise_count":
            action_counter[
                "CompromiseMember"
            ],

        "manager_compromise_count":
            action_counter[
                "CompromiseManager"
            ],

        "old_key_leak_count":
            action_counter[
                "OldKeyLeak"
            ],

        "adversary_knowledge_count":
            action_counter[
                "K"
            ],
    }


def parse_status(
    lemma: str,
    log: str,
) -> dict:

    match = re.search(
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


    return {
        "status":
            (
                match.group(1)
                if match
                else None
            ),

        "details":
            (
                match.group(2)
                if (
                    match
                    and
                    match.group(2)
                )
                else None
            ),
    }


results = {}


for lemma in lemmas:

    json_path = (
        raw_dir
        / f"{lemma}.json"
    )

    log_path = (
        raw_dir
        / f"{lemma}.log"
    )

    dot_path = (
        raw_dir
        / f"{lemma}.dot"
    )


    data = load_json(
        json_path
    )


    log_text = log_path.read_text(
        encoding="utf-8",
        errors="replace",
    )


    status = parse_status(
        lemma,
        log_text,
    )


    graphs = []


    if isinstance(data, dict):

        raw_graphs = data.get(
            "graphs",
            [],
        )

    else:

        raw_graphs = []


    for graph in raw_graphs:

        if isinstance(
            graph,
            dict,
        ):

            graphs.append(
                analyse_graph(
                    graph
                )
            )


    indicators = {
        "has_multiple_setup_instances":
            any(
                graph[
                    "setup_count"
                ]
                > 1
                for graph in graphs
            ),

        "has_multiple_epoch1_instances":
            any(
                graph[
                    "epoch1_start_count"
                ]
                > 1
                for graph in graphs
            ),

        "has_multiple_epoch2_instances":
            any(
                graph[
                    "epoch2_start_count"
                ]
                > 1
                for graph in graphs
            ),

        "contains_member_compromise":
            any(
                graph[
                    "member_compromise_count"
                ]
                > 0
                for graph in graphs
            ),

        "contains_manager_compromise":
            any(
                graph[
                    "manager_compromise_count"
                ]
                > 0
                for graph in graphs
            ),

        "contains_old_key_leak":
            any(
                graph[
                    "old_key_leak_count"
                ]
                > 0
                for graph in graphs
            ),
    }


    results[
        lemma
    ] = {
        "tamarin_status":
            status["status"],

        "details":
            status["details"],

        "graph_count":
            len(graphs),

        "indicators":
            indicators,

        "graphs":
            graphs,

        "dot_present":
            dot_path.exists()
            and
            dot_path.stat().st_size
            > 0,
    }


confirmed = all(
    result[
        "tamarin_status"
    ] == "falsified"
    and
    result[
        "graph_count"
    ] >= 1
    for result
    in results.values()
)


payload = {
    "schema_version":
        1,

    "step":
        "STEP7D2B_SECRECY_COUNTEREXAMPLE_AUDIT",

    "model_modified":
        False,

    "implementation_modified":
        False,

    "counterexamples_confirmed":
        confirmed,

    "results":
        results,

    "scientific_state":
        (
            "SECRECY_COUNTEREXAMPLES_CAPTURED_"
            "SEMANTIC_INTERPRETATION_REQUIRED"
            if confirmed
            else
            "COUNTEREXAMPLE_CAPTURE_INCOMPLETE"
        ),

    "interpretation_guardrails": [
        (
            "Presence of CompromiseMember or "
            "CompromiseManager does not by itself "
            "invalidate the lemma; temporal ordering "
            "must be inspected."
        ),
        (
            "Presence of OldKeyLeak without relevant "
            "compromise is evidence requiring exact "
            "LKH derivation analysis."
        ),
        (
            "Multiple Setup or epoch-start instances "
            "may indicate cross-session mixing rather "
            "than an implementation vulnerability."
        ),
        (
            "No formal-model modification is justified "
            "until the exact derivation path to K(root) "
            "is identified."
        ),
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


print("=" * 78)
print("STEP7D2-B SECRECY COUNTEREXAMPLE AUDIT")
print("=" * 78)


for lemma, result in results.items():

    print()
    print(
        f"LEMMA={lemma}"
    )

    print(
        f"STATUS="
        f"{result['tamarin_status']}"
    )

    print(
        f"GRAPH_COUNT="
        f"{result['graph_count']}"
    )

    print(
        "INDICATORS="
        + json.dumps(
            result[
                "indicators"
            ],
            sort_keys=True,
        )
    )


    for index, graph in enumerate(
        result[
            "graphs"
        ],
        start=1,
    ):

        print()
        print(
            f"--- GRAPH {index} ---"
        )

        print(
            f"LABEL="
            f"{graph['label']}"
        )

        print(
            "RULES="
            + json.dumps(
                graph[
                    "rules"
                ],
                sort_keys=True,
            )
        )

        print(
            "ACTIONS="
            + json.dumps(
                graph[
                    "actions"
                ],
                sort_keys=True,
            )
        )


        print(
            "TRACE ELEMENTS:"
        )


        for node in graph[
            "interesting_nodes"
        ]:

            print(
                f"  NODE[{node['ordinal']}] "
                f"{node['label']}"
            )

            for fact in node[
                "facts"
            ]:

                print(
                    "    "
                    f"{fact['category']}: "
                    f"{fact['shown']}"
                )


print()
print("=" * 78)

print(
    "COUNTEREXAMPLES_CONFIRMED="
    + str(confirmed)
)

print(
    "SCIENTIFIC_STATE="
    + payload[
        "scientific_state"
    ]
)

print("=" * 78)
PY


# ==================================================================
# 7. Extract compact human-readable DOT evidence
# ==================================================================

echo
echo "===== 7. COMPACT DOT TRACE EXTRACTION ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$RAW" \
    "$OUT/dot-trace-highlights.txt" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


raw = Path(sys.argv[1])

out = Path(sys.argv[2])


keywords = [
    "Setup",
    "Start_Epoch1",
    "Start_Epoch2",
    "SecretEpoch",
    "EpochRoot",
    "AuthorizedAt",
    "RevokedAt",
    "CompromiseMember",
    "CompromiseManager",
    "OldKeyLeak",
    "K(",
    "!KU(",
    "!KD(",
    "sdec",
    "senc",
]


chunks = []


for dot in sorted(
    raw.glob(
        "*.dot"
    )
):

    chunks.append(
        "=" * 78
    )

    chunks.append(
        dot.name
    )

    chunks.append(
        "=" * 78
    )


    lines = dot.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()


    for number, line in enumerate(
        lines,
        start=1,
    ):

        if any(
            keyword.lower()
            in line.lower()
            for keyword
            in keywords
        ):

            clean = re.sub(
                r"\s+",
                " ",
                line.strip(),
            )

            chunks.append(
                f"{number:05d}: {clean}"
            )


    chunks.append("")


out.write_text(
    "\n".join(chunks)
    + "\n",
    encoding="utf-8",
)


print(
    out.read_text(
        encoding="utf-8"
    )
)

print(
    "DOT_TRACE_HIGHLIGHTS=PASS"
)
PY


# ==================================================================
# 8. Verify model remained unchanged
# ==================================================================

echo
echo "===== 8. VERIFY MODEL UNCHANGED ====="

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
        "Formal model changed during counterexample audit"
    )


print()
print(
    "FORMAL_MODEL_UNCHANGED=PASS"
)
PY


# ==================================================================
# 9. Implementation freeze
# ==================================================================

echo
echo "===== 9. IMPLEMENTATION FREEZE ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
  -c \
  artifacts/article-evidence/32-step7d2a-lkh-semantic-freeze/implemented-semantics.sha256


echo "IMPLEMENTATION_UNCHANGED=PASS"


# ==================================================================
# 10. Evidence package
# ==================================================================

echo
echo "===== 10. EVIDENCE PACKAGE ====="

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

    MAN=/tmp/step7d2bcex.sha256
    TAR=/tmp/step7d2bcex.tar.gz

    rm -f \
      \"\$MAN\" \
      \"\$TAR\"

    find '$OUT' \
      -type f \
      ! -name 'evidence.sha256' \
      ! -name 'evidence-verify.log' \
      ! -name 'step7d2bcex-evidence.tar.gz' \
      ! -name 'step7d2bcex-evidence.tar.gz.sha256' \
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
      '$OUT/step7d2bcex-evidence.tar.gz'

    sha256sum \
      '$OUT/step7d2bcex-evidence.tar.gz' \
      > '$OUT/step7d2bcex-evidence.tar.gz.sha256'

    sha256sum \
      -c \
      '$OUT/step7d2bcex-evidence.tar.gz.sha256'
  "


echo
echo "===================================================================="
echo "STEP 7D.2-B-CEX COMPLETE"
echo
echo "SUMMARY:"
echo "  $SUMMARY"
echo
echo "TRACE HIGHLIGHTS:"
echo "  $OUT/dot-trace-highlights.txt"
echo
echo "MODEL MODIFIED          = NO"
echo "IMPLEMENTATION MODIFIED = NO"
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
