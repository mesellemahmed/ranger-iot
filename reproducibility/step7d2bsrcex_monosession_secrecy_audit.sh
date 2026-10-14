#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"
FORMAL_COMPOSE="compose.reproducibility.yaml"

MODEL="formal/tamarin/ranger_lkh_multi_epoch_4member_session_bound.spthy"

PREV="artifacts/article-evidence/35-step7d2b-session-bound-repair"
STEP7D2A="artifacts/article-evidence/32-step7d2a-lkh-semantic-freeze"

OUT="artifacts/article-evidence/36-step7d2b-session-bound-secrecy-audit"
RAW="$OUT/raw"

SUMMARY="$OUT/causality-audit.json"
HIGHLIGHTS="$OUT/causality-highlights.txt"

mkdir -p "$RAW"

echo "===================================================================="
echo "RANGER-IOT — STEP 7D.2-B-SR-CEX"
echo "MONO-SESSION SECRECY CAUSALITY AUDIT"
echo
echo "TARGETS:"
echo "  new_epoch_key_secret_without_relevant_compromise"
echo "  revoked_old_key_does_not_reveal_new_root_key"
echo
echo "MODEL MODIFICATION          = NONE"
echo "LEMMA MODIFICATION          = NONE"
echo "IMPLEMENTATION MODIFICATION = NONE"
echo "DOCKER ONLY"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="


# ==================================================================
# 1. Baseline contract
# ==================================================================

echo
echo "===== 1. VERIFY SESSION-BOUND BASELINE ====="

test -f "$MODEL"
test -f "$PREV/proof-matrix-session-bound.json"
test -f "$PREV/v2-model.sha256"

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$PREV/proof-matrix-session-bound.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


data = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

expected = {
    "new_epoch_key_secret_without_relevant_compromise",
    "revoked_old_key_does_not_reveal_new_root_key",
}


checks = {
    "verified_14":
        data.get("verified_count") == 14,

    "falsified_2":
        data.get("falsified_count") == 2,

    "exact_falsified":
        set(
            data.get(
                "falsified_lemmas",
                [],
            )
        )
        == expected,

    "timeout_0":
        data.get("timeout_count") == 0,

    "incomplete_0":
        data.get("incomplete_count") == 0,

    "errors_0":
        data.get(
            "execution_anomaly_count"
        )
        == 0,

    "repair_did_not_hide_failures":
        data.get(
            "previously_falsified_now_verified"
        )
        is False,

    "expected_state":
        data.get("scientific_state")
        ==
        "STEP7D2B_SESSION_BOUND_COUNTEREXAMPLE_REAUDIT_REQUIRED",
}


for key, value in checks.items():

    print(
        f"{key:38s}",
        "PASS"
        if value
        else "FAIL",
    )


if not all(checks.values()):

    raise SystemExit(
        "Unexpected STEP7D2-B-SR baseline"
    )


print()
print(
    "SESSION_BOUND_COUNTEREXAMPLE_BASELINE=PASS"
)
PY


# ==================================================================
# 2. Freeze model and implementation
# ==================================================================

echo
echo "===== 2. FREEZE MODEL + IMPLEMENTATION ====="

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


docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
  -c \
  "$STEP7D2A/implemented-semantics.sha256"


echo "MODEL_AND_IMPLEMENTATION_FREEZE=PASS"


# ==================================================================
# 3. Runtime contract
# ==================================================================

echo
echo "===== 3. FORMAL RUNTIME CONTRACT ====="

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

    echo "SESSION_BOUND_CEX_RUNTIME=PASS"
  '


# ==================================================================
# 4. Counterexample executor
# ==================================================================

capture_cex()
{
    local lemma="$1"
    local budget="$2"

    local log="$RAW/${lemma}.log"
    local json="$RAW/${lemma}.json"
    local dot="$RAW/${lemma}.dot"
    local rcfile="$RAW/${lemma}.rc"

    echo
    echo "----------------------------------------------------------------"
    echo "LEMMA=$lemma"
    echo "SEARCH=DFS"
    echo "HEURISTIC=s"
    echo "BUDGET=$budget"
    echo "----------------------------------------------------------------"

    local rc=0

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
            '--stop-on-trace=DFS' \
            '--heuristic=s' \
            '--output-json=/workspace/${json}' \
            '--output-dot=/workspace/${dot}' \
            +RTS -N2 -RTS
      " \
      > "$log" \
      2>&1
    then
        rc=0
    else
        rc=$?
    fi

    echo "$rc" \
      > "$rcfile"

    echo "TAMARIN_RC=$rc"

    if [ "$rc" -ne 0 ]; then
        echo "COUNTEREXAMPLE_CAPTURE_EXECUTION_ERROR"
        tail -100 "$log"
        return "$rc"
    fi


    docker compose \
      -f "$ROOT_COMPOSE" \
      run \
      --rm \
      -T \
      --no-deps \
      ranger \
      python - \
        "$log" \
        "$lemma" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


log = Path(sys.argv[1]).read_text(
    encoding="utf-8",
    errors="replace",
)

lemma = sys.argv[2]


match = re.search(
    rf"(?m)^\s*"
    rf"{re.escape(lemma)}"
    rf"\s+\(all-traces\):\s+"
    rf"(verified|falsified|"
    rf"analysis incomplete|"
    rf"unproven|unknown)",
    log,
)


status = (
    match.group(1)
    if match
    else None
)


print(
    f"TAMARIN_STATUS={status}"
)


if status != "falsified":

    raise SystemExit(
        "Expected falsified lemma "
        "was not reproduced"
    )


print(
    "COUNTEREXAMPLE_REPRODUCED=PASS"
)
PY


    test -s "$json"
    test -s "$dot"

    echo "JSON_TRACE=PASS"
    echo "DOT_TRACE=PASS"
}


# ==================================================================
# 5. Reproduce both mono-session falsifications
# ==================================================================

echo
echo "===== 4. CAPTURE SESSION-BOUND COUNTEREXAMPLES ====="


capture_cex \
  new_epoch_key_secret_without_relevant_compromise \
  600


capture_cex \
  revoked_old_key_does_not_reveal_new_root_key \
  600


# ==================================================================
# 6. DOT -> SVG
# ==================================================================

echo
echo "===== 5. RENDER TRACE GRAPHS ====="

for lemma in \
  new_epoch_key_secret_without_relevant_compromise \
  revoked_old_key_does_not_reveal_new_root_key
do

    docker compose \
      -f "$FORMAL_COMPOSE" \
      run \
      --rm \
      -T \
      --no-deps \
      tamarin \
      bash -lc "
        cd /workspace

        dot \
          -Tsvg \
          -O \
          '$RAW/${lemma}.dot'
      "

    echo "${lemma}_SVG=PASS"

done


# ==================================================================
# 7. Deep JSON forensic extraction
# ==================================================================

echo
echo "===== 6. DEEP CAUSALITY EXTRACTION ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$RAW" \
    "$SUMMARY" \
    "$HIGHLIGHTS" <<'PY'
from __future__ import annotations

import json
import re
import sys

from collections import Counter
from pathlib import Path
from typing import Any


raw_dir = Path(sys.argv[1])
summary_path = Path(sys.argv[2])
highlight_path = Path(sys.argv[3])


lemmas = [
    "new_epoch_key_secret_without_relevant_compromise",
    "revoked_old_key_does_not_reveal_new_root_key",
]


interesting_names = {
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
    "!KU",
    "!KD",
}


def load(path: Path) -> Any:

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def clean(text: str | None) -> str | None:

    if text is None:
        return None

    return re.sub(
        r"\s+",
        " ",
        text.strip(),
    )


def facts_from_metadata(
    metadata: dict,
) -> list[dict]:

    records = []

    for category, key in [
        ("actions", "jgnActs"),
        ("premises", "jgnPrems"),
        ("conclusions", "jgnConcs"),
    ]:

        for fact in metadata.get(
            key,
            [],
        ):

            name = fact.get(
                "jgnFactName"
            )

            shown = clean(
                fact.get(
                    "jgnFactShow"
                )
            )


            interesting = (
                name in interesting_names
                or
                (
                    shown is not None
                    and
                    any(
                        token in shown
                        for token in [
                            "SecretEpoch(",
                            "OldKeyLeak(",
                            "CompromiseMember(",
                            "CompromiseManager(",
                            "K(",
                            "KU(",
                            "KD(",
                            "senc(",
                            "sdec(",
                        ]
                    )
                )
            )


            if interesting:

                records.append(
                    {
                        "category":
                            category,

                        "name":
                            name,

                        "shown":
                            shown,
                    }
                )

    return records


def parse_arguments(
    shown: str,
    fact: str,
) -> list[str] | None:

    prefix = fact + "("

    start = shown.find(prefix)

    if start < 0:
        return None

    inner = shown[
        start + len(prefix):
    ]

    depth = 0
    chars = []

    for char in inner:

        if char == "(":
            depth += 1

        elif char == ")":

            if depth == 0:
                break

            depth -= 1

        chars.append(char)


    content = "".join(
        chars
    )


    result = []
    current = []
    angle_depth = 0
    paren_depth = 0


    for char in content:

        if char == "<":
            angle_depth += 1

        elif char == ">":
            angle_depth -= 1

        elif char == "(":
            paren_depth += 1

        elif char == ")":
            paren_depth -= 1


        if (
            char == ","
            and
            angle_depth == 0
            and
            paren_depth == 0
        ):

            result.append(
                clean(
                    "".join(current)
                )
                or ""
            )

            current = []

        else:

            current.append(char)


    result.append(
        clean(
            "".join(current)
        )
        or ""
    )


    return result


def all_fact_strings(
    graph: dict,
) -> list[dict]:

    records = []

    for ordinal, node in enumerate(
        graph.get(
            "jgNodes",
            [],
        )
    ):

        label = node.get(
            "jgnLabel"
        )

        metadata = (
            node.get(
                "jgnMetadata"
            )
            or {}
        )

        for fact in facts_from_metadata(
            metadata
        ):

            records.append(
                {
                    "ordinal":
                        ordinal,

                    "rule":
                        label,

                    **fact,
                }
            )

    return records


def analyze_graph(
    graph: dict,
) -> dict:

    records = all_fact_strings(
        graph
    )


    rules = Counter()

    for node in graph.get(
        "jgNodes",
        [],
    ):

        label = node.get(
            "jgnLabel"
        )

        if label:

            rules[label] += 1


    setups = []
    secrets = []
    knowledge = []
    leaks = []
    member_compromises = []
    manager_compromises = []


    for record in records:

        shown = (
            record.get(
                "shown"
            )
            or ""
        )


        if "Setup(" in shown:

            args = parse_arguments(
                shown,
                "Setup",
            )

            if args:

                setups.append(
                    {
                        **record,
                        "args":
                            args,
                    }
                )


        if "SecretEpoch(" in shown:

            args = parse_arguments(
                shown,
                "SecretEpoch",
            )

            if (
                args
                and
                len(args) >= 4
            ):

                secrets.append(
                    {
                        **record,

                        "sid":
                            args[0],

                        "epoch":
                            args[1],

                        "version":
                            args[2],

                        "root":
                            args[3],
                    }
                )


        if (
            record.get(
                "name"
            )
            == "K"
            or
            shown.startswith(
                "K("
            )
        ):

            args = parse_arguments(
                shown,
                "K",
            )

            if args:

                knowledge.append(
                    {
                        **record,

                        "term":
                            args[0],
                    }
                )


        if "OldKeyLeak(" in shown:

            args = parse_arguments(
                shown,
                "OldKeyLeak",
            )

            if (
                args
                and
                len(args) >= 3
            ):

                leaks.append(
                    {
                        **record,

                        "sid":
                            args[0],

                        "member":
                            args[1],

                        "epoch":
                            args[2],
                    }
                )


        if "CompromiseMember(" in shown:

            args = parse_arguments(
                shown,
                "CompromiseMember",
            )

            if (
                args
                and
                len(args) >= 2
            ):

                member_compromises.append(
                    {
                        **record,

                        "sid":
                            args[0],

                        "member":
                            args[1],
                    }
                )


        if "CompromiseManager(" in shown:

            args = parse_arguments(
                shown,
                "CompromiseManager",
            )

            if (
                args
                and
                len(args) >= 2
            ):

                manager_compromises.append(
                    {
                        **record,

                        "sid":
                            args[0],

                        "epoch":
                            args[1],
                    }
                )


    learned_secrets = []


    for secret in secrets:

        root = secret[
            "root"
        ]

        matching_k = [
            item
            for item
            in knowledge
            if item[
                "term"
            ]
            == root
        ]


        if not matching_k:
            continue


        root_occurrences = [
            item
            for item
            in records
            if (
                root
                in (
                    item.get(
                        "shown"
                    )
                    or ""
                )
            )
        ]


        same_sid_leaks = [
            leak
            for leak
            in leaks
            if (
                leak[
                    "sid"
                ]
                ==
                secret[
                    "sid"
                ]
            )
        ]


        same_sid_member_compromises = [
            item
            for item
            in member_compromises
            if (
                item[
                    "sid"
                ]
                ==
                secret[
                    "sid"
                ]
            )
        ]


        same_sid_manager_compromises = [
            item
            for item
            in manager_compromises
            if (
                item[
                    "sid"
                ]
                ==
                secret[
                    "sid"
                ]
            )
        ]
        learned_secrets.append(
            {
                "sid":
                    secret[
                        "sid"
                    ],

                "epoch":
                    secret[
                        "epoch"
                    ],

                "version":
                    secret[
                        "version"
                    ],

                "root":
                    root,

                "secret_fact":
                    secret,

                "knowledge_facts":
                    matching_k,

                "same_sid_old_key_leaks":
                    same_sid_leaks,

                "same_sid_member_compromises":
                    same_sid_member_compromises,

                "same_sid_manager_compromises":
                    same_sid_manager_compromises,

                "root_occurrences":
                    root_occurrences,
            }
        )


    distinct_secret_sids = sorted(
        {
            item[
                "sid"
            ]
            for item
            in secrets
        }
    )


    patterns = {
        "multiple_setup_rules":
            rules[
                "Setup"
            ]
            > 1,

        "multiple_secret_sids":
            len(
                distinct_secret_sids
            )
            > 1,

        "contains_old_key_leak":
            bool(
                leaks
            ),

        "contains_member_compromise":
            bool(
                member_compromises
            ),

        "contains_manager_compromise":
            bool(
                manager_compromises
            ),

        "learned_secret_count":
            len(
                learned_secrets
            ),

        "historical_e1_disclosure_after_e2_candidate":
            any(
                item[
                    "epoch"
                ]
                == "'e1'"
                and
                any(
                    leak[
                        "epoch"
                    ]
                    == "'e2'"
                    for leak
                    in item[
                        "same_sid_old_key_leaks"
                    ]
                )
                for item
                in learned_secrets
            ),

        "same_epoch_old_key_leak_candidate":
            any(
                any(
                    leak[
                        "epoch"
                    ]
                    ==
                    item[
                        "epoch"
                    ]
                    for leak
                    in item[
                        "same_sid_old_key_leaks"
                    ]
                )
                for item
                in learned_secrets
            ),
    }


    return {
        "graph_label":
            graph.get(
                "jgLabel"
            ),

        "rule_counts":
            dict(
                rules
            ),

        "setup_actions":
            setups,

        "secret_epochs":
            secrets,

        "knowledge":
            knowledge,

        "old_key_leaks":
            leaks,

        "member_compromises":
            member_compromises,

        "manager_compromises":
            manager_compromises,

        "learned_secrets":
            learned_secrets,

        "patterns":
            patterns,

        "interesting_records":
            records,
    }


results = {}


for lemma in lemmas:

    data = load(
        raw_dir
        / f"{lemma}.json"
    )


    if not isinstance(
        data,
        dict,
    ):

        raise SystemExit(
            f"Unexpected JSON root "
            f"for {lemma}"
        )


    graphs_raw = data.get(
        "graphs",
        [],
    )


    if not graphs_raw:

        raise SystemExit(
            f"No graph found for {lemma}"
        )


    graphs = [
        analyze_graph(
            graph
        )
        for graph
        in graphs_raw
        if isinstance(
            graph,
            dict,
        )
    ]


    results[
        lemma
    ] = {
        "graph_count":
            len(graphs),

        "graphs":
            graphs,
    }


payload = {
    "schema_version":
        1,

    "step":
        (
            "STEP7D2B_SESSION_BOUND_"
            "SECRECY_CAUSALITY_AUDIT"
        ),

    "model_modified":
        False,

    "lemmas_modified":
        False,

    "implementation_modified":
        False,

    "results":
        results,

    "decision_required":
        True,

    "allowed_interpretations": [
        (
            "historical-key disclosure property "
            "is temporally over-strong"
        ),
        (
            "old-key leak lemma lacks causal "
            "association between leak and K(root)"
        ),
        (
            "actual same-session LKH secrecy failure"
        ),
        (
            "other residual modeling defect"
        ),
    ],

    "scientific_state":
        (
            "MONO_SESSION_COUNTEREXAMPLES_CAPTURED_"
            "CAUSALITY_ANALYSIS_REQUIRED"
        ),
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


lines = []


for lemma, result in results.items():

    lines.append(
        "=" * 80
    )

    lines.append(
        f"LEMMA: {lemma}"
    )

    lines.append(
        "=" * 80
    )


    for graph_index, graph in enumerate(
        result[
            "graphs"
        ],
        start=1,
    ):

        lines.append(
            f"GRAPH {graph_index}"
        )

        lines.append(
            "RULE_COUNTS="
            + json.dumps(
                graph[
                    "rule_counts"
                ],
                sort_keys=True,
            )
        )

        lines.append(
            "PATTERNS="
            + json.dumps(
                graph[
                    "patterns"
                ],
                sort_keys=True,
            )
        )


        for learned in graph[
            "learned_secrets"
        ]:

            lines.append("")

            lines.append(
                "LEARNED_SECRET:"
            )

            lines.append(
                f"  sid={learned['sid']}"
            )

            lines.append(
                f"  epoch={learned['epoch']}"
            )

            lines.append(
                f"  version={learned['version']}"
            )

            lines.append(
                f"  root={learned['root']}"
            )


            lines.append(
                "  OLD_KEY_LEAKS:"
            )

            for leak in learned[
                "same_sid_old_key_leaks"
            ]:

                lines.append(
                    "    "
                    + str(
                        leak[
                            "shown"
                        ]
                    )
                )


            lines.append(
                "  MEMBER_COMPROMISES:"
            )

            for compromise in learned[
                "same_sid_member_compromises"
            ]:

                lines.append(
                    "    "
                    + str(
                        compromise[
                            "shown"
                        ]
                    )
                )


            lines.append(
                "  MANAGER_COMPROMISES:"
            )

            for compromise in learned[
                "same_sid_manager_compromises"
            ]:

                lines.append(
                    "    "
                    + str(
                        compromise[
                            "shown"
                        ]
                    )
                )


            lines.append(
                "  ROOT OCCURRENCES:"
            )

            for occurrence in learned[
                "root_occurrences"
            ]:

                lines.append(
                    "    "
                    f"[{occurrence['ordinal']}] "
                    f"{occurrence['rule']} :: "
                    f"{occurrence['category']} :: "
                    f"{occurrence['shown']}"
                )


    lines.append("")


highlight_path.write_text(
    "\n".join(lines)
    + "\n",
    encoding="utf-8",
)


print(
    highlight_path.read_text(
        encoding="utf-8"
    )
)


print(
    "MONO_SESSION_CAUSALITY_EXTRACTION=PASS"
)
PY


# ==================================================================
# 8. Raw DOT cryptographic deduction highlights
# ==================================================================

echo
echo "===== 7. RAW CRYPTOGRAPHIC TRACE HIGHLIGHTS ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$RAW" \
    "$OUT/dot-crypto-highlights.txt" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


raw = Path(sys.argv[1])
out = Path(sys.argv[2])


keywords = [
    "SecretEpoch",
    "OldKeyLeak",
    "CompromiseMember",
    "CompromiseManager",
    "Start_Epoch1",
    "Start_Epoch2",
    "EpochRoot",
    "K(",
    "KU(",
    "KD(",
    "senc",
    "sdec",
    "~root1",
    "~root2",
    "~k2v0",
    "~k3v0",
    "~k3v1",
]


lines_out = []


for dot in sorted(
    raw.glob(
        "*.dot"
    )
):

    lines_out.extend(
        [
            "=" * 80,
            dot.name,
            "=" * 80,
        ]
    )


    for number, raw_line in enumerate(
        dot.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines(),
        start=1,
    ):

        if any(
            key.lower()
            in raw_line.lower()
            for key
            in keywords
        ):

            line = re.sub(
                r"\s+",
                " ",
                raw_line.strip(),
            )

            lines_out.append(
                f"{number:05d}: {line}"
            )


    lines_out.append("")


out.write_text(
    "\n".join(
        lines_out
    )
    + "\n",
    encoding="utf-8",
)


print(
    out.read_text(
        encoding="utf-8"
    )
)


print(
    "DOT_CRYPTOGRAPHIC_HIGHLIGHTS=PASS"
)
PY


# ==================================================================
# 9. Formal model freeze after audit
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
        "Session-bound model changed during audit"
    )


print()
print(
    "SESSION_BOUND_MODEL_UNCHANGED=PASS"
)
PY


# ==================================================================
# 10. Implementation freeze after audit
# ==================================================================

echo
echo "===== 9. VERIFY IMPLEMENTATION UNCHANGED ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
  -c \
  "$STEP7D2A/implemented-semantics.sha256"


echo "IMPLEMENTATION_UNCHANGED=PASS"


# ==================================================================
# 11. Evidence package
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

    MAN=/tmp/step7d2bsrcex.sha256
    TAR=/tmp/step7d2bsrcex.tar.gz

    rm -f \
      \"\$MAN\" \
      \"\$TAR\"

    find '$OUT' \
      -type f \
      ! -name 'evidence.sha256' \
      ! -name 'evidence-verify.log' \
      ! -name 'step7d2bsrcex-evidence.tar.gz' \
      ! -name 'step7d2bsrcex-evidence.tar.gz.sha256' \
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
      '$OUT/step7d2bsrcex-evidence.tar.gz'

    sha256sum \
      '$OUT/step7d2bsrcex-evidence.tar.gz' \
      > '$OUT/step7d2bsrcex-evidence.tar.gz.sha256'

    sha256sum \
      -c \
      '$OUT/step7d2bsrcex-evidence.tar.gz.sha256'
  "


echo
echo "===================================================================="
echo "STEP 7D.2-B-SR-CEX COMPLETE"
echo
echo "SUMMARY:"
echo "  $SUMMARY"
echo
echo "CAUSALITY:"
echo "  $HIGHLIGHTS"
echo
echo "DOT CRYPTO:"
echo "  $OUT/dot-crypto-highlights.txt"
echo
echo "MODEL MODIFIED          = NO"
echo "LEMMA MODIFIED          = NO"
echo "IMPLEMENTATION MODIFIED = NO"
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
