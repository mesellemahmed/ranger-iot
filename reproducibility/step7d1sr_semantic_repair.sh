#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"
FORMAL_COMPOSE="compose.reproducibility.yaml"

V1="formal/tamarin/ranger_authorization_transport.spthy"
V2="formal/tamarin/ranger_authorization_transport_v2.spthy"

PREV="artifacts/article-evidence/29-step7d1-counterexample-audit"
OUT="artifacts/article-evidence/30-step7d1-semantic-repair"

LOG_DIR="$OUT/logs"
SUMMARY="$OUT/proof-matrix-v2.json"

mkdir -p "$LOG_DIR"

echo "===================================================================="
echo "RANGER-IOT — STEP 7D.1-SR"
echo "SEMANTIC REPAIR AFTER COUNTEREXAMPLE AUDIT"
echo
echo "V1 PRESERVED"
echo "V2 CREATED"
echo "IMPLEMENTATION MODIFIED = NO"
echo "DOCKER ONLY"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="

test -f "$V1"
test -f "$PREV/counterexample-audit.json"


echo
echo "===== 1. CREATE V2 INSIDE DOCKER ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - "$V1" "$V2" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path


src = Path(sys.argv[1])
dst = Path(sys.argv[2])

text = src.read_text(
    encoding="utf-8"
)


# ============================================================
# A. SETUP
#
# Bind manager, survivors, revoked identity and authorization
# key into one persistent group context.
# ============================================================

old = """  [
      !SurvivorKey(~ksurvivor),
      !MemberKey($A,~ksurvivor),
      !MemberKey($H,~ksurvivor),
      !RevokedOldKey($R,~krevoked)
  ]
"""

new = """  [
      !GroupContext($GM,$A,$H,$R,~ksurvivor),
      !MemberKey($A,~ksurvivor),
      !MemberKey($H,~ksurvivor),
      !RevokedOldKey($R,~krevoked)
  ]
"""

if old not in text:
    raise SystemExit(
        "Setup output block not found"
    )

text = text.replace(
    old,
    new,
    1,
)


# ============================================================
# B. DISTINCT PRINCIPALS
#
# Mirrors implemented semantics:
# manager and the three modeled member roles are distinct.
# ============================================================

setup_end = """  ]


/*
 * One rekey instance.
"""

restriction = """  ]


restriction Distinct_Group_Principals:
  "
    All gm a h r #i.
      Setup(gm,a,h,r) @ i
      ==>
      (
          not (gm = a)
        & not (gm = h)
        & not (gm = r)
        & not (a = h)
        & not (a = r)
        & not (h = r)
      )
  "


/*
 * One rekey instance.
"""

if setup_end not in text:
    raise SystemExit(
        "Setup insertion point not found"
    )

text = text.replace(
    setup_end,
    restriction,
    1,
)


# ============================================================
# C. START_REKEY
#
# It can no longer independently choose A/H/R.
# All principals come from GroupContext.
# ============================================================

old = """  [
      !SurvivorKey(ksurvivor),
      Fr(~epoch),
      Fr(~groupkey)
  ]
"""

new = """  [
      !GroupContext($GM,$A,$H,$R,ksurvivor),
      Fr(~epoch),
      Fr(~groupkey)
  ]
"""

if old not in text:
    raise SystemExit(
        "Start_Rekey premise not found"
    )

text = text.replace(
    old,
    new,
    1,
)


old = """      SecretEpoch(~epoch,~groupkey)
"""

new = """      SecretEpoch($GM,~epoch,~groupkey)
"""

if old not in text:
    raise SystemExit(
        "SecretEpoch action not found"
    )

text = text.replace(
    old,
    new,
    1,
)


old = """      !EpochCipher(
          ~epoch,
          ~groupkey,
          senc(<'ranger-capsule',~epoch,~groupkey>,ksurvivor)
      ),

      Stale($A,~epoch,~groupkey),
      Stale($H,~epoch,~groupkey),
"""

new = """      !EpochCipher(
          ~epoch,
          ~groupkey,
          senc(<'ranger-capsule',~epoch,~groupkey>,ksurvivor)
      ),

      !AuthorizedEpoch($A,~epoch),
      !AuthorizedEpoch($H,~epoch),

      Stale($A,~epoch,~groupkey),
      Stale($H,~epoch,~groupkey),
"""

if old not in text:
    raise SystemExit(
        "Start_Rekey output not found"
    )

text = text.replace(
    old,
    new,
    1,
)


# ============================================================
# D. ACCEPT INITIAL
# ============================================================

old = """      Stale(a,e,gk),
      !MemberKey(a,k),
      In(senc(<'ranger-capsule',e,gk>,k))
"""

new = """      Stale(a,e,gk),
      !AuthorizedEpoch(a,e),
      !MemberKey(a,k),
      In(senc(<'ranger-capsule',e,gk>,k))
"""

if old not in text:
    raise SystemExit(
        "Accept_Initial block not found"
    )

text = text.replace(
    old,
    new,
    1,
)


# ============================================================
# E. START RECOVERY
# ============================================================

old = """  [
      Stale(a,e,gk)
  ]
"""

new = """  [
      Stale(a,e,gk),
      !AuthorizedEpoch(a,e)
  ]
"""

if old not in text:
    raise SystemExit(
        "Start_Recovery block not found"
    )

text = text.replace(
    old,
    new,
    1,
)


# ============================================================
# F. RECOVERY RESPONSE
#
# Explicitly encode implementation checks:
# requester and helper both authorized for same epoch.
# ============================================================

old = """      Current(h,e,gk),
      !EpochCipher(e,gk,ciphertext),
      In(<'ranger-recovery-request',a,e>)
"""

new = """      Current(h,e,gk),
      !AuthorizedEpoch(h,e),
      !AuthorizedEpoch(a,e),
      !EpochCipher(e,gk,ciphertext),
      In(<'ranger-recovery-request',a,e>)
"""

if old not in text:
    raise SystemExit(
        "Recovery_Response block not found"
    )

text = text.replace(
    old,
    new,
    1,
)


# ============================================================
# G. RECOVERY ACCEPT
# ============================================================

old = """      Recovering(a,e,gk),
      !MemberKey(a,k),
      In(senc(<'ranger-capsule',e,gk>,k))
"""

new = """      Recovering(a,e,gk),
      !AuthorizedEpoch(a,e),
      !MemberKey(a,k),
      In(senc(<'ranger-capsule',e,gk>,k))
"""

if old not in text:
    raise SystemExit(
        "Accept_Recovery block not found"
    )

text = text.replace(
    old,
    new,
    1,
)


# ============================================================
# H. MANAGER COMPROMISE
#
# Tie the exposed authorization key to the actual manager/group
# context rather than choosing another independent $GM.
# ============================================================

pattern = re.compile(
    r"""rule Compromise_Group_Manager:
\s*\[
\s*!SurvivorKey\(k\)
\s*\]
\s*--\[
\s*CompromiseGM\(\$GM\)
\s*\]->
\s*\[
\s*Out\(k\)
\s*\]""",
    re.MULTILINE,
)

replacement = """rule Compromise_Group_Manager:
  [
      !GroupContext(gm,a,h,r,k)
  ]
  --[
      CompromiseGM(gm)
  ]->
  [
      Out(k)
  ]"""

text, count = pattern.subn(
    replacement,
    text,
    count=1,
)

if count != 1:
    raise SystemExit(
        "Compromise_Group_Manager replacement failed"
    )


# ============================================================
# I. SECRECY PROPERTY
#
# Do NOT weaken secrecy.
# Bind the exception to the manager owning this epoch.
# ============================================================

pattern = re.compile(
    r"""lemma epoch_key_secrecy_unless_compromised:
\s*"
.*?
\s*"
""",
    re.DOTALL,
)

replacement = """lemma epoch_key_secrecy_unless_compromised:
  "
    All gm e gk #i #j.
      SecretEpoch(gm,e,gk) @ i
    & K(gk) @ j
      ==>
      (
          (Ex a #r.
             Compromise(a) @ r
           & r < j)
        |
          (Ex #r.
             CompromiseGM(gm) @ r
           & r < j)
      )
  "
"""

text, count = pattern.subn(
    replacement,
    text,
    count=1,
)

if count != 1:
    raise SystemExit(
        "Secrecy lemma replacement failed"
    )


dst.write_text(
    text,
    encoding="utf-8",
    newline="\n",
)

print(
    f"V2_CREATED={dst}"
)

print(
    "SEMANTIC_REPAIR_MODEL_GENERATION=PASS"
)
PY


echo
echo "===== 2. V1/V2 DIFF + HASHES ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - "$V1" "$V2" "$OUT/model-v1-v2.diff" <<'PY'
from __future__ import annotations

import difflib
import sys
from pathlib import Path


v1 = Path(sys.argv[1])
v2 = Path(sys.argv[2])
out = Path(sys.argv[3])


a = v1.read_text(
    encoding="utf-8"
).splitlines(
    keepends=True
)

b = v2.read_text(
    encoding="utf-8"
).splitlines(
    keepends=True
)


diff = "".join(
    difflib.unified_diff(
        a,
        b,
        fromfile=v1.as_posix(),
        tofile=v2.as_posix(),
    )
)


out.write_text(
    diff,
    encoding="utf-8",
)


print(diff)

print(
    "MODEL_DIFF_CAPTURED=PASS"
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
    "$V1" \
    "$V2" \
  > "$OUT/model-hashes.sha256"


echo
echo "===== 3. SEMANTIC REPAIR CONTRACT ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - "$V1" "$V2" <<'PY'
from pathlib import Path
import sys


v1 = Path(sys.argv[1]).read_text(
    encoding="utf-8"
)

v2 = Path(sys.argv[2]).read_text(
    encoding="utf-8"
)


checks = {
    "v1_preserved":
        (
            "GroupContext("
            not in v1
        ),

    "group_context":
        (
            "!GroupContext($GM,$A,$H,$R,~ksurvivor)"
            in v2
        ),

    "rekey_bound_to_context":
        (
            "!GroupContext($GM,$A,$H,$R,ksurvivor)"
            in v2
        ),

    "distinct_restriction":
        (
            "restriction Distinct_Group_Principals:"
            in v2
        ),

    "a_not_r":
        (
            "not (a = r)"
            in v2
        ),

    "h_not_r":
        (
            "not (h = r)"
            in v2
        ),

    "auth_epoch_A":
        (
            "!AuthorizedEpoch($A,~epoch)"
            in v2
        ),

    "auth_epoch_H":
        (
            "!AuthorizedEpoch($H,~epoch)"
            in v2
        ),

    "helper_auth_gate":
        (
            "!AuthorizedEpoch(h,e)"
            in v2
        ),

    "requester_auth_gate":
        (
            "!AuthorizedEpoch(a,e)"
            in v2
        ),

    "secret_manager_binding":
        (
            "SecretEpoch($GM,~epoch,~groupkey)"
            in v2
        ),

    "compromise_manager_binding":
        (
            "CompromiseGM(gm)"
            in v2
        ),

    "secrecy_quantifies_manager":
        (
            "All gm e gk #i #j."
            in v2
        ),

    "no_survivor_key_fact":
        (
            "!SurvivorKey("
            not in v2
        ),

    "same_11_lemma_names":
        all(
            f"lemma {name}:"
            in v2
            for name in [
                "executable_initial_accept",
                "executable_same_epoch_recovery",
                "revocation_reachable",
                "accept_has_rekey_origin",
                "accept_requires_authorization",
                "revoked_never_accepts",
                "recovery_requester_authorized",
                "recovery_helper_authorized",
                "recovery_same_epoch",
                "recovery_accept_has_rekey_origin",
                "epoch_key_secrecy_unless_compromised",
            ]
        ),
}


for name, passed in checks.items():

    print(
        f"{name:34s}",
        "PASS"
        if passed
        else "FAIL",
    )


if not all(checks.values()):
    raise SystemExit(
        "SEMANTIC REPAIR CONTRACT FAILED"
    )


print()
print(
    "SEMANTIC_REPAIR_CONTRACT=PASS"
)
PY


echo
echo "===== 4. TAMARIN PRECOMPUTE V2 ====="

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
      --precompute-only \
      '$V2'
  " \
  > "$OUT/precompute-v2.log" \
  2>&1

PRE_RC=$?

set -e

echo "PRECOMPUTE_RC=$PRE_RC"

if [ "$PRE_RC" -ne 0 ]; then
    echo "V2_PRECOMPUTE=FAIL"
    cat "$OUT/precompute-v2.log"
    exit "$PRE_RC"
fi

echo "V2_PRECOMPUTE=PASS"


echo
echo "===== 5. ISOLATED V2 PROOF MATRIX ====="

: > "$OUT/return-codes.tsv"

LEMMAS=(
"executable_initial_accept|exists-trace|120|bfs"
"executable_same_epoch_recovery|exists-trace|180|bfs"
"revocation_reachable|exists-trace|120|bfs"
"accept_has_rekey_origin|all-traces|180|default"
"accept_requires_authorization|all-traces|180|default"
"revoked_never_accepts|all-traces|180|default"
"recovery_requester_authorized|all-traces|180|default"
"recovery_helper_authorized|all-traces|300|default"
"recovery_same_epoch|all-traces|180|default"
"recovery_accept_has_rekey_origin|all-traces|240|default"
"epoch_key_secrecy_unless_compromised|all-traces|300|default"
)


for spec in "${LEMMAS[@]}"; do

    IFS='|' read -r lemma kind budget search <<< "$spec"

    LOG="$LOG_DIR/${lemma}.log"

    echo
    echo "LEMMA=$lemma"
    echo "KIND=$kind"
    echo "BUDGET=$budget"

    set +e

    if [ "$search" = "bfs" ]; then

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
              '$V2' \
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
          -e LANG=C.UTF-8 \
          -e LC_ALL=C.UTF-8 \
          tamarin \
          bash -lc "
            timeout ${budget}s \
              tamarin-prover \
              '$V2' \
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
      >> "$OUT/return-codes.tsv"

    echo "RC=$RC"

done


echo
echo "===== 6. CLASSIFY V2 RESULTS ====="

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
summary_path = Path(sys.argv[3])


rows = []


for raw in rc_path.read_text(
    encoding="utf-8"
).splitlines():

    if not raw.strip():
        continue

    lemma, kind, budget, search, rc_s = raw.split("\t")

    rc = int(rc_s)

    log_path = log_dir / f"{lemma}.log"

    text = log_path.read_text(
        encoding="utf-8",
        errors="replace",
    )


    match = re.search(
        rf"(?m)^\s*"
        rf"{re.escape(lemma)}"
        rf"\s+\((all-traces|exists-trace)\):"
        rf"\s+"
        rf"(verified|falsified|analysis incomplete|unproven|unknown)"
        rf"(?:\s+\(([^)]*)\))?",
        text,
    )


    status = (
        match.group(2)
        if match
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
            "lemma": lemma,
            "kind": kind,
            "budget_seconds": int(budget),
            "search": search,
            "return_code": rc,
            "status": status,
            "classification": classification,
        }
    )


verified = [
    r["lemma"]
    for r in rows
    if r["classification"] == "verified"
]

falsified = [
    r["lemma"]
    for r in rows
    if r["classification"] == "falsified"
]

timeouts = [
    r["lemma"]
    for r in rows
    if r["classification"] == "timeout"
]

errors = [
    r["lemma"]
    for r in rows
    if r["classification"]
    in {
        "execution_error",
        "missing_summary",
    }
]

incomplete = [
    r["lemma"]
    for r in rows
    if r["classification"] == "incomplete"
]


all_verified = (
    len(verified) == 11
    and
    not falsified
    and
    not timeouts
    and
    not errors
    and
    not incomplete
)


if all_verified:
    state = (
        "STEP7D1_ABSTRACT_MODEL_V2_ALL_11_VERIFIED"
    )

elif falsified:
    state = (
        "V2_HAS_CONFIRMED_COUNTEREXAMPLES"
    )

elif timeouts:
    state = (
        "V2_PARTIAL_PROOF_WITH_TIMEOUTS"
    )

elif errors:
    state = (
        "V2_EXECUTION_ANOMALY"
    )

else:
    state = (
        "V2_PARTIAL_FORMAL_RESULT"
    )


payload = {
    "schema_version": 1,

    "model":
        "formal/tamarin/ranger_authorization_transport_v2.spthy",

    "model_class":
        "LKH_AUTHORIZATION_TRANSPORT_ABSTRACTION_V2",

    "v1_preserved":
        True,

    "implementation_modified":
        False,

    "rows":
        rows,

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

    "execution_anomaly_count":
        len(errors),

    "execution_anomalies":
        errors,

    "incomplete_count":
        len(incomplete),

    "all_11_verified":
        all_verified,

    "scientific_state":
        state,

    "full_ranger_formally_verified":
        False,
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
    f"{'LEMMA':44s} {'RESULT':22s}"
)

print("-" * 68)


for row in rows:

    print(
        f"{row['lemma'][:44]:44s} "
        f"{row['classification']:22s}"
    )


print()
print(
    f"VERIFIED={len(verified)}/11"
)

print(
    f"FALSIFIED={len(falsified)}"
)

print(
    f"TIMEOUT={len(timeouts)}"
)

print(
    f"ERRORS={len(errors)}"
)

print(
    f"STATE={state}"
)
PY


echo
echo "===== 7. IMPLEMENTATION FREEZE CHECK ====="

if [ -f \
  "artifacts/article-evidence/25-step7d1-formal-model/implemented-semantics-before.sha256" \
]; then

    docker compose \
      -f "$ROOT_COMPOSE" \
      run \
      --rm \
      -T \
      --no-deps \
      ranger \
      sha256sum \
      -c \
      artifacts/article-evidence/25-step7d1-formal-model/implemented-semantics-before.sha256

    echo "IMPLEMENTATION_UNCHANGED=PASS"

fi


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

    MAN=/tmp/step7d1sr.sha256
    TAR=/tmp/step7d1sr.tar.gz

    rm -f \"\$MAN\" \"\$TAR\"

    find '$OUT' \
      -type f \
      ! -name 'evidence.sha256' \
      ! -name 'evidence-verify.log' \
      ! -name 'step7d1sr-evidence.tar.gz' \
      ! -name 'step7d1sr-evidence.tar.gz.sha256' \
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
      '$V1' \
      '$V2'

    tar -tzf \"\$TAR\" >/dev/null

    cp \
      \"\$TAR\" \
      '$OUT/step7d1sr-evidence.tar.gz'

    sha256sum \
      '$OUT/step7d1sr-evidence.tar.gz' \
      > '$OUT/step7d1sr-evidence.tar.gz.sha256'

    sha256sum \
      -c \
      '$OUT/step7d1sr-evidence.tar.gz.sha256'
  "


echo
echo "===================================================================="
echo "STEP 7D.1-SR COMPLETE"
echo
echo "V1:"
echo "  $V1"
echo
echo "V2:"
echo "  $V2"
echo
echo "RESULT:"
echo "  $SUMMARY"
echo
echo "IMPLEMENTATION MODIFIED = NO"
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
