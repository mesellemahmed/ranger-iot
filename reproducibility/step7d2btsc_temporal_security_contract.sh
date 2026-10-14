#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"
FORMAL_COMPOSE="compose.reproducibility.yaml"

V2="formal/tamarin/ranger_lkh_multi_epoch_4member_session_bound.spthy"
V3="formal/tamarin/ranger_lkh_multi_epoch_4member_temporal_security.spthy"

AUDIT="artifacts/article-evidence/36-step7d2b-session-bound-secrecy-audit"
STEP7D2A="artifacts/article-evidence/32-step7d2a-lkh-semantic-freeze"

OUT="artifacts/article-evidence/37-step7d2b-temporal-security-contract"
LOG_DIR="$OUT/logs"
SUMMARY="$OUT/proof-matrix-temporal-security.json"

MUTANT="$OUT/ranger_lkh_multi_epoch_4member_temporal_security_MUTATION.spthy"
MUTATION_LOG="$OUT/mutation-control.log"

mkdir -p "$LOG_DIR"

echo "===================================================================="
echo "RANGER-IOT — STEP 7D.2-B-TSC"
echo "TEMPORAL SECURITY CONTRACT"
echo
echo "PURPOSE:"
echo "  separate current-rekey confidentiality from"
echo "  historical-key exposure after later authorized possession"
echo
echo "PROTOCOL RULE CHANGE       = NONE"
echo "IMPLEMENTATION CHANGE      = NONE"
echo "CRYPTOGRAPHIC CHANGE       = NONE"
echo
echo "PRESERVED NEGATIVE EVIDENCE:"
echo "  original two falsified secrecy lemmas"
echo "  counterexample JSON/DOT/SVG"
echo
echo "ADDED:"
echo "  temporally scoped security properties"
echo "  historical-exposure witness"
echo "  formal mutation negative control"
echo
echo "DOCKER ONLY"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="


# ==================================================================
# 1. Audit prerequisite
# ==================================================================

echo
echo "===== 1. CAUSAL AUDIT PREREQUISITE ====="

test -f "$V2"
test -f "$AUDIT/causality-audit.json"
test -f "$AUDIT/causality-highlights.txt"
test -f "$STEP7D2A/implemented-semantics.sha256"

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$AUDIT/causality-audit.json" \
    "$OUT/property-reclassification.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


audit_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])

audit = json.loads(
    audit_path.read_text(
        encoding="utf-8"
    )
)


targets = {
    "new_epoch_key_secret_without_relevant_compromise",
    "revoked_old_key_does_not_reveal_new_root_key",
}


results = audit.get(
    "results",
    {},
)


checks = {
    "counterexamples_reproduced":
        audit.get(
            "counterexamples_reproduced"
        )
        is True,

    "learned_secret_extraction":
        audit.get(
            "learned_secret_extraction_complete"
        )
        is True,

    "exact_target_set":
        set(
            results
        )
        == targets,
}


diagnostics = {}


for lemma in sorted(targets):

    graphs = results[
        lemma
    ][
        "graphs"
    ]

    if not graphs:
        raise SystemExit(
            f"No graph for {lemma}"
        )

    graph = graphs[0]

    patterns = graph[
        "patterns"
    ]


    diagnostics[
        lemma
    ] = {
        "single_setup":
            (
                patterns.get(
                    "setup_rule_count"
                )
                == 1
            ),

        "single_secret_sid":
            (
                patterns.get(
                    "secret_sid_count"
                )
                == 1
            ),

        "same_epoch_direct_root":
            patterns.get(
                "same_epoch_old_key_direct_disclosure_candidate"
            ),

        "other_epoch_historical_root":
            patterns.get(
                "historical_secret_revealed_by_other_epoch_leak_candidate"
            ),

        "member_compromise":
            patterns.get(
                "contains_member_compromise"
            ),

        "manager_compromise":
            patterns.get(
                "contains_manager_compromise"
            ),
    }


for lemma, diagnostic in diagnostics.items():

    checks[
        f"{lemma}:single_setup"
    ] = (
        diagnostic[
            "single_setup"
        ]
        is True
    )

    checks[
        f"{lemma}:single_sid"
    ] = (
        diagnostic[
            "single_secret_sid"
        ]
        is True
    )

    checks[
        f"{lemma}:not_same_epoch_direct"
    ] = (
        diagnostic[
            "same_epoch_direct_root"
        ]
        is False
    )

    checks[
        f"{lemma}:historical_later_exposure"
    ] = (
        diagnostic[
            "other_epoch_historical_root"
        ]
        is True
    )


for name, passed in checks.items():

    print(
        f"{name:82s}",
        "PASS"
        if passed
        else "FAIL",
    )


if not all(
    checks.values()
):

    raise SystemExit(
        "Causal evidence insufficient "
        "for property reclassification"
    )


payload = {
    "schema_version":
        1,

    "classification":
        (
            "OVERSTRONG_OR_NONCAUSAL_"
            "SECRECY_PROPERTIES_CONFIRMED"
        ),

    "retired_diagnostic_lemmas": [
        "new_epoch_key_secret_without_relevant_compromise",
        "revoked_old_key_does_not_reveal_new_root_key",
    ],

    "reason": {
        "new_epoch_key_secret_without_relevant_compromise":
            (
                "The lemma requires historical epoch-e1 "
                "confidentiality even after a member that "
                "legitimately possessed root1 in e1 is later "
                "revoked in e2 and explicitly exposes its "
                "historical e1 state."
            ),

        "revoked_old_key_does_not_reveal_new_root_key":
            (
                "The lemma conjoins OldKeyLeak(m4,e1) with "
                "K(root1) but does not establish that the "
                "m4 leak caused root1 knowledge. The captured "
                "trace derives root1 from the later "
                "OldKeyLeak(m3,e2)."
            ),
    },

    "replacement_contract": [
        (
            "epoch1 root confidentiality against "
            "the state of member m4 revoked in e1, "
            "unless an authorized e1 holder is "
            "subsequently exposed or compromised"
        ),
        (
            "epoch2 root confidentiality against "
            "the historical state of member m3 "
            "revoked in e2, unless an authorized "
            "e2 survivor or the manager is compromised"
        ),
        (
            "explicit reachability of historical "
            "e1 root exposure after later leakage "
            "of m3, an authorized e1 holder"
        ),
    ],

    "protocol_changed":
        False,

    "cryptographic_model_changed":
        False,

    "implementation_changed":
        False,

    "negative_evidence_preserved":
        True,
}


out_path.write_text(
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
    "TEMPORAL_PROPERTY_RECLASSIFICATION=PASS"
)
PY


# ==================================================================
# 2. Freeze V2 / implementation
# ==================================================================

echo
echo "===== 2. FREEZE INPUTS ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
    "$V2" \
  > "$OUT/v2-before.sha256"

cat "$OUT/v2-before.sha256"


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

echo "INPUT_FREEZE=PASS"


# ==================================================================
# 3. Generate V3 by replacing ONLY the two diagnostic lemmas
# ==================================================================

echo
echo "===== 3. GENERATE TEMPORAL SECURITY V3 ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$V2" \
    "$V3" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path


src = Path(sys.argv[1])
dst = Path(sys.argv[2])


text = src.read_text(
    encoding="utf-8"
)


start_marker = (
    "lemma "
    "new_epoch_key_secret_without_relevant_compromise:"
)

end_marker = (
    "lemma "
    "recovery_requester_authorized_in_same_epoch:"
)


start = text.find(
    start_marker
)

end = text.find(
    end_marker,
    start,
)


if start < 0:
    raise SystemExit(
        "First diagnostic secrecy lemma not found"
    )


if end < 0:
    raise SystemExit(
        "Recovery lemma marker not found"
    )


replacement = r'''/********************************************************************
 * TEMPORALLY SCOPED SECURITY CONTRACT
 *
 * The previous two diagnostic secrecy lemmas are intentionally
 * preserved in the V2 evidence package but are not certification
 * properties here.
 *
 * They were falsified because historical root1 is deliberately
 * exposed when m3 -- a legitimate e1 holder -- is later revoked
 * in e2.
 *
 * The properties below separate:
 *
 *   (1) confidentiality of a newly generated root against the
 *       member revoked at that rekey,
 *
 *   (2) later exposure of a historical key by a former legitimate
 *       holder.
 ********************************************************************/


lemma epoch1_root_confidential_against_m4_revoked_state:
  "
    All sid root #s #l #k.
      SecretEpoch(
          sid,
          'e1',
          'v1',
          root
      ) @ s

    & OldKeyLeak(
          sid,
          'm4',
          'e1'
      ) @ l

    & l < k

    & K(root) @ k

      ==>

      (
        /*
         * A later leak of m3 is an explicit exposure
         * of a legitimate e1 holder of root1.
         */
        (Ex #x.
           OldKeyLeak(
               sid,
               'm3',
               'e2'
           ) @ x
         & x < k)

        |

        /*
         * Or a member authorized in e1 was compromised.
         */
        (Ex m #a #c.
           AuthorizedAt(
               sid,
               m,
               'e1'
           ) @ a

         & CompromiseMember(
               sid,
               m
           ) @ c

         & c < k)

        |

        /*
         * Or the e1 manager state was compromised.
         */
        (Ex #c.
           CompromiseManager(
               sid,
               'e1'
           ) @ c

         & c < k)
      )
  "


lemma epoch2_root_confidential_against_m3_revoked_state:
  "
    All sid root #s #l #k.
      SecretEpoch(
          sid,
          'e2',
          'v2',
          root
      ) @ s

    & OldKeyLeak(
          sid,
          'm3',
          'e2'
      ) @ l

    & l < k

    & K(root) @ k

      ==>

      (
        /*
         * Only e2 survivors may legitimately hold
         * material protecting root2.
         */
        (Ex m #a #c.
           AuthorizedAt(
               sid,
               m,
               'e2'
           ) @ a

         & CompromiseMember(
               sid,
               m
           ) @ c

         & c < k)

        |

        /*
         * Or the e2 manager state was compromised.
         */
        (Ex #c.
           CompromiseManager(
               sid,
               'e2'
           ) @ c

         & c < k)
      )
  "


lemma historical_e1_root_exposure_after_later_holder_leak:
  exists-trace
  "
    Ex sid root #e1 #l #k.
      SecretEpoch(
          sid,
          'e1',
          'v1',
          root
      ) @ e1

    & AuthorizedAt(
          sid,
          'm3',
          'e1'
      ) @ e1

    & OldKeyLeak(
          sid,
          'm3',
          'e2'
      ) @ l

    & K(root) @ k

    & e1 < l
    & l < k
  "


'''


new_text = (
    text[:start]
    + replacement
    + text[end:]
)


# Rename theory so V2 and V3 can coexist unambiguously.

new_text = new_text.replace(
    (
        "theory "
        "RangerIoT_LKH_MultiEpoch_4Member_SessionBound"
    ),
    (
        "theory "
        "RangerIoT_LKH_MultiEpoch_4Member_TemporalSecurity"
    ),
    1,
)


dst.write_text(
    new_text,
    encoding="utf-8",
    newline="\n",
)


print(
    f"V3_CREATED={dst}"
)

print(
    "PROTOCOL_RULE_MODIFICATION=NONE"
)

print(
    "SECURITY_CONTRACT_REPLACEMENT=PASS"
)
PY


# ==================================================================
# 4. Verify semantic delta
# ==================================================================

echo
echo "===== 4. VERIFY PROPERTY-ONLY DELTA ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$V2" \
    "$V3" \
    "$OUT/v2-v3-semantic-delta.json" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


v2_path = Path(sys.argv[1])
v3_path = Path(sys.argv[2])
out_path = Path(sys.argv[3])


v2 = v2_path.read_text(
    encoding="utf-8"
)

v3 = v3_path.read_text(
    encoding="utf-8"
)


def prefix_before_first_lemma(
    text: str,
) -> str:

    pos = re.search(
        r"(?m)^lemma\s+",
        text,
    )

    if pos is None:
        raise RuntimeError(
            "No lemma found"
        )

    return text[
        :pos.start()
    ]


p2 = prefix_before_first_lemma(
    v2
)

p3 = prefix_before_first_lemma(
    v3
)


# Normalize only the theory declaration.

p2 = re.sub(
    r"(?m)^theory\s+\S+",
    "theory NORMALIZED",
    p2,
    count=1,
)

p3 = re.sub(
    r"(?m)^theory\s+\S+",
    "theory NORMALIZED",
    p3,
    count=1,
)


rules_unchanged = (
    p2
    == p3
)


old_diagnostic = {
    "new_epoch_key_secret_without_relevant_compromise",
    "revoked_old_key_does_not_reveal_new_root_key",
}


v2_lemmas = re.findall(
    r"(?m)^lemma\s+([A-Za-z0-9_]+)\s*:",
    v2,
)

v3_lemmas = re.findall(
    r"(?m)^lemma\s+([A-Za-z0-9_]+)\s*:",
    v3,
)


new_temporal = {
    "epoch1_root_confidential_against_m4_revoked_state",
    "epoch2_root_confidential_against_m3_revoked_state",
    "historical_e1_root_exposure_after_later_holder_leak",
}


checks = {
    "protocol_rules_identical":
        rules_unchanged,

    "v2_has_16":
        len(v2_lemmas) == 16,

    "v3_has_17":
        len(v3_lemmas) == 17,

    "old_diagnostic_removed_from_contract":
        old_diagnostic.isdisjoint(
            v3_lemmas
        ),

    "new_temporal_present":
        new_temporal
        <= set(
            v3_lemmas
        ),

    "14_previous_nonsecrecy_properties_preserved":
        len(
            (
                set(v2_lemmas)
                - old_diagnostic
            )
            &
            set(v3_lemmas)
        )
        == 14,
}


for name, passed in checks.items():

    print(
        f"{name:46s}",
        "PASS"
        if passed
        else "FAIL",
    )


if not all(
    checks.values()
):

    raise SystemExit(
        "V2/V3 semantic delta contract failed"
    )


payload = {
    "schema_version":
        1,

    "protocol_rules_identical":
        True,

    "implementation_modified":
        False,

    "old_diagnostic_lemmas":
        sorted(
            old_diagnostic
        ),

    "new_temporal_lemmas":
        sorted(
            new_temporal
        ),

    "v2_lemma_count":
        len(v2_lemmas),

    "v3_lemma_count":
        len(v3_lemmas),

    "checks":
        checks,
}


out_path.write_text(
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
    "PROPERTY_ONLY_SEMANTIC_DELTA=PASS"
)
PY


# ==================================================================
# 5. Hash V3
# ==================================================================

echo
echo "===== 5. V3 HASH ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
    "$V3" \
  > "$OUT/v3-model.sha256"

cat "$OUT/v3-model.sha256"


# ==================================================================
# 6. Precompute
# ==================================================================

echo
echo "===== 6. V3 TAMARIN PRECOMPUTE ====="

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
    timeout 420s \
      tamarin-prover \
        --precompute-only \
        '$V3'
  " \
  > "$OUT/precompute.log" \
  2>&1

PRE_RC=$?

set -e

echo "PRECOMPUTE_RC=$PRE_RC"

if [ "$PRE_RC" -ne 0 ]; then

    cat "$OUT/precompute.log"

    echo "TEMPORAL_SECURITY_PRECOMPUTE=FAIL"

    exit "$PRE_RC"

fi


echo "TEMPORAL_SECURITY_PRECOMPUTE=PASS"


# ==================================================================
# 7. 17-lemma matrix
# ==================================================================

echo
echo "===== 7. 17-LEMMA TEMPORAL SECURITY MATRIX ====="

: > "$OUT/return-codes.tsv"


LEMMAS=(
"executable_first_lkh_rekey|exists-trace|120|BFS|s"
"executable_second_lkh_rekey|exists-trace|180|BFS|s"
"executable_same_epoch_recovery_after_lkh_rekey|exists-trace|300|DFS|C"
"executable_old_cipher_replay|exists-trace|180|BFS|s"

"second_epoch_follows_first|all-traces|180|DFS|s"
"revoked_member_excluded_from_new_epoch|all-traces|180|DFS|s"
"survivor_acceptance_has_lkh_update_chain|all-traces|240|DFS|s"
"m3_acceptance_requires_branch_update|all-traces|240|DFS|s"
"acceptance_matches_current_root_version|all-traces|180|DFS|s"
"replay_old_capsule_cannot_accept_new_epoch|all-traces|240|DFS|s"
"replay_old_recovery_response_cannot_accept_new_epoch|all-traces|240|DFS|s"
"root_keys_fresh_across_epochs|all-traces|180|DFS|s"

"epoch1_root_confidential_against_m4_revoked_state|all-traces|420|DFS|s"
"epoch2_root_confidential_against_m3_revoked_state|all-traces|420|DFS|s"
"historical_e1_root_exposure_after_later_holder_leak|exists-trace|300|DFS|C"

"recovery_requester_authorized_in_same_epoch|all-traces|180|DFS|s"
"recovery_helper_authorized_in_same_epoch|all-traces|240|DFS|s"
)


for spec in "${LEMMAS[@]}"; do

    IFS='|' read -r \
      lemma \
      kind \
      budget \
      search \
      heuristic \
      <<< "$spec"

    LOG="$LOG_DIR/${lemma}.log"

    echo
    echo "----------------------------------------------------------------"
    echo "LEMMA=$lemma"
    echo "KIND=$kind"
    echo "BUDGET=$budget"
    echo "SEARCH=$search"
    echo "HEURISTIC=$heuristic"
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
        timeout ${budget}s \
          tamarin-prover \
            '$V3' \
            '--prove=${lemma}' \
            '--stop-on-trace=${search}' \
            '--heuristic=${heuristic}' \
            +RTS -N2 -RTS
      " \
      > "$LOG" \
      2>&1

    RC=$?

    set -e


    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$lemma" \
      "$kind" \
      "$budget" \
      "$search" \
      "$heuristic" \
      "$RC" \
      >> "$OUT/return-codes.tsv"

    echo "RC=$RC"

done


# ==================================================================
# 8. Classify V3
# ==================================================================

echo
echo "===== 8. CLASSIFY V3 ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$OUT/return-codes.tsv" \
    "$LOG_DIR" \
    "$SUMMARY" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


rc_path = Path(sys.argv[1])
log_dir = Path(sys.argv[2])
out = Path(sys.argv[3])


rows = []


for raw in rc_path.read_text(
    encoding="utf-8"
).splitlines():

    if not raw.strip():
        continue

    (
        lemma,
        kind,
        budget,
        search,
        heuristic,
        rc_raw,
    ) = raw.split("\t")

    rc = int(rc_raw)

    log_path = (
        log_dir
        / f"{lemma}.log"
    )

    text = log_path.read_text(
        encoding="utf-8",
        errors="replace",
    )


    match = re.search(
        rf"(?m)^\s*"
        rf"{re.escape(lemma)}"
        rf"\s+\("
        rf"(all-traces|exists-trace)"
        rf"\):\s+"
        rf"(verified|falsified|"
        rf"analysis incomplete|"
        rf"unproven|unknown)"
        rf"(?:\s+\(([^)]*)\))?",
        text,
    )


    status = (
        match.group(2)
        if match
        else None
    )


    details = (
        match.group(3)
        if (
            match
            and
            match.group(3)
        )
        else None
    )


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
        classification = "missing_summary"


    rows.append(
        {
            "lemma":
                lemma,

            "kind":
                kind,

            "classification":
                classification,

            "status":
                status,

            "details":
                details,

            "return_code":
                rc,

            "budget_seconds":
                int(budget),

            "search":
                search,

            "heuristic":
                heuristic,
        }
    )


def choose(
    classification: str,
) -> list[str]:

    return [
        row["lemma"]
        for row
        in rows
        if row[
            "classification"
        ]
        == classification
    ]


verified = choose(
    "verified"
)

falsified = choose(
    "falsified"
)

timeouts = choose(
    "timeout"
)

incomplete = choose(
    "incomplete"
)

errors = [
    row["lemma"]
    for row
    in rows
    if row[
        "classification"
    ]
    in {
        "execution_error",
        "missing_summary",
    }
]


all_17 = (
    len(verified) == 17
    and
    not falsified
    and
    not timeouts
    and
    not incomplete
    and
    not errors
)


temporal = {
    "epoch1_root_confidential_against_m4_revoked_state",
    "epoch2_root_confidential_against_m3_revoked_state",
    "historical_e1_root_exposure_after_later_holder_leak",
}


temporal_verified = (
    temporal
    <= set(
        verified
    )
)


if all_17:

    state = (
        "STEP7D2B_TEMPORAL_SECURITY_"
        "ALL_17_LEMMAS_VERIFIED"
    )

elif falsified:

    state = (
        "STEP7D2B_TEMPORAL_SECURITY_"
        "COUNTEREXAMPLE_AUDIT_REQUIRED"
    )

elif timeouts:

    state = (
        "STEP7D2B_TEMPORAL_SECURITY_"
        "PARTIAL_WITH_TIMEOUTS"
    )

else:

    state = (
        "STEP7D2B_TEMPORAL_SECURITY_"
        "INCOMPLETE"
    )


payload = {
    "schema_version":
        1,

    "step":
        "STEP7D2B_TEMPORAL_SECURITY_CONTRACT",

    "expected_lemmas":
        17,

    "verified_count":
        len(verified),

    "verified_lemmas":
        verified,

    "falsified_count":
        len(falsified),

    "falsified_lemmas":
        falsified,

    "timeout_count":
        len(timeouts),

    "timeout_lemmas":
        timeouts,

    "incomplete_count":
        len(incomplete),

    "execution_anomaly_count":
        len(errors),

    "execution_anomalies":
        errors,

    "temporal_contract_verified":
        temporal_verified,

    "all_17_verified":
        all_17,

    "diagnostic_negative_results_preserved":
        True,

    "protocol_modified":
        False,

    "implementation_modified":
        False,

    "arbitrary_n_theorem":
        False,

    "scientific_state":
        state,

    "rows":
        rows,

    "full_ranger_formally_verified":
        False,
}


out.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


print(
    f"{'LEMMA':62s} RESULT"
)

print(
    "-" * 84
)


for row in rows:

    print(
        f"{row['lemma'][:62]:62s} "
        f"{row['classification']}"
    )


print()
print(
    f"VERIFIED={len(verified)}/17"
)

print(
    f"FALSIFIED={len(falsified)}"
)

print(
    f"TIMEOUT={len(timeouts)}"
)

print(
    f"INCOMPLETE={len(incomplete)}"
)

print(
    f"ERRORS={len(errors)}"
)

print(
    "TEMPORAL_CONTRACT_VERIFIED="
    + str(
        temporal_verified
    )
)

print(
    f"STATE={state}"
)
PY


# ==================================================================
# 9. Formal negative control
# ==================================================================

echo
echo "===== 9. FORMAL MUTATION NEGATIVE CONTROL ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$V3" \
    "$MUTANT" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path


source = Path(sys.argv[1])

target = Path(sys.argv[2])


text = source.read_text(
    encoding="utf-8"
)


marker = (
    "/********************************************************************\n"
    " * 16 ORIGINAL STEP7D2-B LEMMAS"
)


# V3 no longer necessarily contains that comment after replacement.
# Insert before the first lemma instead.

lemma_pos = text.find(
    "lemma executable_first_lkh_rekey:"
)


if lemma_pos < 0:

    raise SystemExit(
        "Cannot locate first lemma"
    )


mutation_rule = r'''
/********************************************************************
 * NEGATIVE CONTROL ONLY
 *
 * This rule intentionally leaks the e2 root.
 * It is NOT part of the protocol and MUST make the
 * epoch2 confidentiality property falsified.
 ********************************************************************/

rule MUTATION_Leak_E2_Root:
  [
      !EpochRootKey(
          sid,
          'e2',
          'v2',
          root2
      )
  ]
  --[
      MutationLeak(
          sid,
          'e2',
          root2
      )
    ]->
  [
      Out(root2)
  ]


'''


mutant = (
    text[:lemma_pos]
    + mutation_rule
    + text[lemma_pos:]
)


mutant = mutant.replace(
    (
        "theory "
        "RangerIoT_LKH_MultiEpoch_4Member_TemporalSecurity"
    ),
    (
        "theory "
        "RangerIoT_LKH_MultiEpoch_4Member_"
        "TemporalSecurity_MUTATION"
    ),
    1,
)


target.write_text(
    mutant,
    encoding="utf-8",
    newline="\n",
)


print(
    f"MUTATION_MODEL={target}"
)

print(
    "NEGATIVE_CONTROL_MODEL_CREATED=PASS"
)
PY


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
    timeout 300s \
      tamarin-prover \
        '$MUTANT' \
        '--prove=epoch2_root_confidential_against_m3_revoked_state' \
        '--stop-on-trace=BFS' \
        '--heuristic=s' \
        +RTS -N2 -RTS
  " \
  > "$MUTATION_LOG" \
  2>&1

MUT_RC=$?

set -e


echo "MUTATION_TAMARIN_RC=$MUT_RC"


docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$MUTATION_LOG" \
    "$OUT/mutation-control.json" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


path = Path(sys.argv[1])

out = Path(sys.argv[2])


text = path.read_text(
    encoding="utf-8",
    errors="replace",
)


lemma = (
    "epoch2_root_confidential_"
    "against_m3_revoked_state"
)


match = re.search(
    rf"(?m)^\s*"
    rf"{re.escape(lemma)}"
    rf"\s+\(all-traces\):\s+"
    rf"(verified|falsified|"
    rf"analysis incomplete|"
    rf"unproven|unknown)",
    text,
)


status = (
    match.group(1)
    if match
    else None
)


print(
    f"MUTATION_LEMMA_STATUS={status}"
)


passed = (
    status == "falsified"
)


payload = {
    "schema_version":
        1,

    "mutation":
        (
            "intentional direct disclosure "
            "of epoch2 root"
        ),

    "target_lemma":
        lemma,

    "expected":
        "falsified",

    "actual":
        status,

    "negative_control_pass":
        passed,
}


out.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


if not passed:

    raise SystemExit(
        "NEGATIVE CONTROL FAILED: "
        "security lemma did not detect "
        "intentional root-key disclosure"
    )


print(
    "FORMAL_NEGATIVE_CONTROL=PASS"
)
PY


# ==================================================================
# 10. V2 and implementation freeze
# ==================================================================

echo
echo "===== 10. FREEZE VERIFICATION ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
    "$V2" \
  > "$OUT/v2-after.sha256"


docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$OUT/v2-before.sha256" \
    "$OUT/v2-after.sha256" <<'PY'
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
    f"V2_BEFORE={before}"
)

print(
    f"V2_AFTER ={after}"
)


if before != after:

    raise SystemExit(
        "V2 changed during TSC step"
    )


print(
    "V2_UNCHANGED=PASS"
)
PY


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
# 11. CI
# ==================================================================

echo
echo "===== 11. PROJECT CI ====="

set +e

./run.sh check \
  2>&1 \
  | tee "$OUT/project-ci.log"

CI_RC=${PIPESTATUS[0]}

set -e


echo "CI_RC=$CI_RC"


if [ "$CI_RC" -ne 0 ]; then
    exit "$CI_RC"
fi


echo "PROJECT_CI=PASS"


# ==================================================================
# 12. Final scientific classification
# ==================================================================

echo
echo "===== 12. FINAL SCIENTIFIC CLASSIFICATION ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$SUMMARY" \
    "$OUT/mutation-control.json" \
    "$OUT/final-state.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


proof = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

mutation = json.loads(
    Path(sys.argv[2]).read_text(
        encoding="utf-8"
    )
)

out = Path(sys.argv[3])


closed = (
    proof.get(
        "all_17_verified"
    )
    is True
    and
    proof.get(
        "temporal_contract_verified"
    )
    is True
    and
    mutation.get(
        "negative_control_pass"
    )
    is True
)


state = (
    "STEP7D2B_TEMPORAL_SECURITY_REFERENCE_INSTANCE_CLOSED"
    if closed
    else
    "STEP7D2B_TEMPORAL_SECURITY_NOT_CLOSED"
)


payload = {
    "schema_version":
        1,

    "scientific_state":
        state,

    "reference_instance_closed":
        closed,

    "all_17_verified":
        proof.get(
            "all_17_verified"
        ),

    "negative_control_pass":
        mutation.get(
            "negative_control_pass"
        ),

    "original_diagnostic_counterexamples_preserved":
        True,

    "historical_key_exposure_boundary_demonstrated":
        (
            "historical_e1_root_exposure_"
            "after_later_holder_leak"
            in proof.get(
                "verified_lemmas",
                [],
            )
        ),

    "arbitrary_n_generalization":
        False,

    "full_ranger_formally_verified":
        False,

    "next_step_if_closed":
        (
            "STEP7D2C_STRUCTURAL_"
            "GENERALIZATION_AND_RS_BRIDGE"
        ),
}


out.write_text(
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


if not closed:

    raise SystemExit(20)
PY


# ==================================================================
# 13. Package
# ==================================================================

echo
echo "===== 13. EVIDENCE PACKAGE ====="

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

    MAN=/tmp/step7d2btsc.sha256
    TAR=/tmp/step7d2btsc.tar.gz

    rm -f \
      \"\$MAN\" \
      \"\$TAR\"

    find '$OUT' \
      -type f \
      ! -name 'evidence.sha256' \
      ! -name 'evidence-verify.log' \
      ! -name 'step7d2btsc-evidence.tar.gz' \
      ! -name 'step7d2btsc-evidence.tar.gz.sha256' \
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
      '$V2' \
      '$V3'

    tar \
      -tzf \
      \"\$TAR\" \
      >/dev/null

    cp \
      \"\$TAR\" \
      '$OUT/step7d2btsc-evidence.tar.gz'

    sha256sum \
      '$OUT/step7d2btsc-evidence.tar.gz' \
      > '$OUT/step7d2btsc-evidence.tar.gz.sha256'

    sha256sum \
      -c \
      '$OUT/step7d2btsc-evidence.tar.gz.sha256'
  "


echo
echo "===================================================================="
echo "STEP 7D.2-B-TSC COMPLETE"
echo
echo "V3:"
echo "  $V3"
echo
echo "PROOF MATRIX:"
echo "  $SUMMARY"
echo
echo "FINAL STATE:"
echo "  $OUT/final-state.json"
echo
echo "DIAGNOSTIC COUNTEREXAMPLES PRESERVED = YES"
echo "IMPLEMENTATION MODIFIED              = NO"
echo "PROTOCOL MODIFIED                    = NO"
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
