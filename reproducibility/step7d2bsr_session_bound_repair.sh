#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"
FORMAL_COMPOSE="compose.reproducibility.yaml"

V1="formal/tamarin/ranger_lkh_multi_epoch_4member.spthy"
V2="formal/tamarin/ranger_lkh_multi_epoch_4member_session_bound.spthy"

CEX="artifacts/article-evidence/34-step7d2b-secrecy-counterexample-audit"
STEP7D2A="artifacts/article-evidence/32-step7d2a-lkh-semantic-freeze"

OUT="artifacts/article-evidence/35-step7d2b-session-bound-repair"
LOG_DIR="$OUT/logs"
SUMMARY="$OUT/proof-matrix-session-bound.json"

mkdir -p "$LOG_DIR"

echo "===================================================================="
echo "RANGER-IOT — STEP 7D.2-B-SR"
echo "SESSION-BOUND SEMANTIC REPAIR"
echo
echo "V1 COUNTEREXAMPLES PRESERVED"
echo "V1 MODEL PRESERVED"
echo "IMPLEMENTATION MODIFIED = NO"
echo
echo "REPAIR:"
echo "  fresh public session/group identifier sid"
echo "  Setup -> epoch1 -> epoch2 bound to same sid"
echo "  cryptographic state bound to same sid"
echo "  recovery/replay/compromise/leak facts bound to sid"
echo "  all 16 lemmas quantified within one sid"
echo
echo "NOT CHANGED:"
echo "  LKH update topology"
echo "  target/wrapper/recipient mapping"
echo "  revoke 4 -> revoke 3 sequence"
echo "  cryptographic assumptions"
echo "  implementation"
echo
echo "DOCKER ONLY"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="

test -f "$V1"
test -f "$CEX/counterexample-audit.json"
test -f "$STEP7D2A/implemented-semantics.sha256"


# ==================================================================
# 1. Confirm that captured counterexamples exhibit session mixing
# ==================================================================

echo
echo "===== 1. COUNTEREXAMPLE REPAIR JUSTIFICATION ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$CEX/counterexample-audit.json" \
    "$OUT/repair-rationale.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


src = Path(sys.argv[1])
out = Path(sys.argv[2])

data = json.loads(
    src.read_text(
        encoding="utf-8"
    )
)


targets = [
    "new_epoch_key_secret_without_relevant_compromise",
    "revoked_old_key_does_not_reveal_new_root_key",
]


checks: dict[str, bool] = {}

evidence = {}


for lemma in targets:

    result = data[
        "results"
    ][lemma]

    indicators = result[
        "indicators"
    ]

    evidence[
        lemma
    ] = {
        "status":
            result[
                "tamarin_status"
            ],

        "graph_count":
            result[
                "graph_count"
            ],

        "indicators":
            indicators,
    }

    checks[
        f"{lemma}:falsified"
    ] = (
        result[
            "tamarin_status"
        ]
        == "falsified"
    )

    checks[
        f"{lemma}:multiple_setup"
    ] = (
        indicators.get(
            "has_multiple_setup_instances"
        )
        is True
    )

    checks[
        f"{lemma}:multiple_epoch1"
    ] = (
        indicators.get(
            "has_multiple_epoch1_instances"
        )
        is True
    )


for name, passed in checks.items():

    print(
        f"{name:80s}",
        "PASS"
        if passed
        else "FAIL",
    )


if not all(
    checks.values()
):

    raise SystemExit(
        "Counterexample evidence does not "
        "support session-binding repair"
    )


payload = {
    "schema_version":
        1,

    "classification":
        (
            "CAPTURED_COUNTEREXAMPLES_"
            "EXHIBIT_CROSS_SESSION_MIXING"
        ),

    "important_guardrail":
        (
            "This does not yet prove that "
            "session mixing is the sole cause. "
            "The repaired model must be re-proved."
        ),

    "repair":
        (
            "Introduce a fresh session/group "
            "identifier and propagate it through "
            "all protocol state and security actions."
        ),

    "counterexamples":
        evidence,

    "implementation_change":
        False,

    "cryptographic_semantics_change":
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


print()
print(
    "SESSION_MIXING_REPAIR_JUSTIFICATION=PASS"
)
PY


# ==================================================================
# 2. Freeze V1 and implementation
# ==================================================================

echo
echo "===== 2. FREEZE V1 + IMPLEMENTATION ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
    "$V1" \
  > "$OUT/v1-before.sha256"

cat "$OUT/v1-before.sha256"


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

echo "IMPLEMENTATION_FREEZE_BEFORE=PASS"


# ==================================================================
# 3. Verify implementation-level group/session discriminators
# ==================================================================

echo
echo "===== 3. IMPLEMENTATION SESSION-DISCRIMINATOR CONTRACT ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    src/ranger_iot/ranger/static_protocol.py \
    src/ranger_iot/ranger/recovery_protocol.py \
    src/ranger_iot/ranger/coding.py \
    "$OUT/implementation-session-contract.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


static = Path(
    sys.argv[1]
).read_text(
    encoding="utf-8"
)

recovery = Path(
    sys.argv[2]
).read_text(
    encoding="utf-8"
)

coding = Path(
    sys.argv[3]
).read_text(
    encoding="utf-8"
)

out = Path(
    sys.argv[4]
)


checks = {
    "capsule_contains_group_id":
        (
            "group_id=self._group.group_id"
            in static
        ),

    "capsule_id_contains_group_epoch":
        (
            'capsule_id=f"group-'
            in static
            and
            "-epoch-{epoch}"
            in static
        ),

    "static_rejects_wrong_group":
        (
            "fragment.group_id "
            "!= self._group.group_id"
            in static
        ),

    "recovery_request_contains_group_id":
        (
            "group_id=state.capsule.group_id"
            in recovery
        ),

    "recovery_rejects_wrong_group":
        (
            "request.group_id "
            "!= self._group.group_id"
            in recovery
        ),

    "recovery_checks_capsule_id":
        (
            "request.capsule_id "
            "!= state.capsule.capsule_id"
            in recovery
        ),

    "fragment_accumulator_checks_group":
        (
            "fragment.group_id != self.group_id"
            in coding
        ),

    "fragment_accumulator_checks_capsule":
        (
            "fragment.capsule_id != self.capsule_id"
            in coding
        ),

    "fragment_accumulator_checks_epoch":
        (
            "fragment.epoch != self.epoch"
            in coding
        ),
}


for key, passed in checks.items():

    print(
        f"{key:42s}",
        "PASS"
        if passed
        else "FAIL",
    )


if not all(
    checks.values()
):

    raise SystemExit(
        "Implementation session discriminator "
        "contract failed"
    )


payload = {
    "schema_version":
        1,

    "checks":
        checks,

    "formal_correspondence":
        (
            "sid abstracts the concrete group/capsule "
            "instance discriminator used to prevent "
            "cross-group/cross-epoch mixing."
        ),

    "pass":
        True,
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


print()
print(
    "IMPLEMENTATION_SESSION_DISCRIMINATOR=PASS"
)
PY


# ==================================================================
# 4. Generate session-bound V2 model
# ==================================================================

echo
echo "===== 4. GENERATE SESSION-BOUND MODEL ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - "$V2" <<'PY'
from pathlib import Path
import sys


path = Path(sys.argv[1])


model = r"""
theory RangerIoT_LKH_MultiEpoch_4Member_SessionBound

begin

builtins: symmetric-encryption


/*
 * STEP 7D.2-B-SR
 *
 * Same four-member implemented-LKH reference instance as 7D.2-B,
 * but every protocol state is bound to a fresh public session/group
 * identifier sid.
 *
 * The repair addresses a confirmed modeling gap in V1:
 * independent Setup instances could previously contribute persistent
 * key facts to the same constant epoch names 'e1' and 'e2'.
 *
 * sid is public; it is an instance discriminator, not a secret.
 */


/********************************************************************
 * SETUP
 ********************************************************************/

rule Setup:
  [
      Fr(~sid),
      Fr(~k4),
      Fr(~k5),
      Fr(~k6),
      Fr(~k7),
      Fr(~k2v0),
      Fr(~k3v0),
      Fr(~root0)
  ]
  --[
      Setup(~sid,'gm'),

      EpochRoot(
          ~sid,
          'e0',
          'v0',
          ~root0
      )
    ]->
  [
      !GroupContext(
          ~sid,
          'gm',
          'm1',
          'm2',
          'm3',
          'm4'
      ),

      !Parent(~sid,'n4','n2'),
      !Parent(~sid,'n5','n2'),
      !Parent(~sid,'n6','n3'),
      !Parent(~sid,'n7','n3'),
      !Parent(~sid,'n2','n1'),
      !Parent(~sid,'n3','n1'),

      !MemberLeaf(~sid,'m1','n4'),
      !MemberLeaf(~sid,'m2','n5'),
      !MemberLeaf(~sid,'m3','n6'),
      !MemberLeaf(~sid,'m4','n7'),

      !M1Base(
          ~sid,
          ~k4,
          ~k2v0,
          ~root0
      ),

      !M2Base(
          ~sid,
          ~k5,
          ~k2v0,
          ~root0
      ),

      !M3Base(
          ~sid,
          ~k6,
          ~k3v0,
          ~root0
      ),

      !M4Base(
          ~sid,
          ~k7,
          ~k3v0,
          ~root0
      ),

      !OwnsKey(
          ~sid,
          'm1',
          'n4',
          'v0',
          ~k4
      ),

      !OwnsKey(
          ~sid,
          'm1',
          'n2',
          'v0',
          ~k2v0
      ),

      !OwnsKey(
          ~sid,
          'm1',
          'n1',
          'v0',
          ~root0
      ),

      !OwnsKey(
          ~sid,
          'm2',
          'n5',
          'v0',
          ~k5
      ),

      !OwnsKey(
          ~sid,
          'm2',
          'n2',
          'v0',
          ~k2v0
      ),

      !OwnsKey(
          ~sid,
          'm2',
          'n1',
          'v0',
          ~root0
      ),

      !OwnsKey(
          ~sid,
          'm3',
          'n6',
          'v0',
          ~k6
      ),

      !OwnsKey(
          ~sid,
          'm3',
          'n3',
          'v0',
          ~k3v0
      ),

      !OwnsKey(
          ~sid,
          'm3',
          'n1',
          'v0',
          ~root0
      ),

      !OwnsKey(
          ~sid,
          'm4',
          'n7',
          'v0',
          ~k7
      ),

      !OwnsKey(
          ~sid,
          'm4',
          'n3',
          'v0',
          ~k3v0
      ),

      !OwnsKey(
          ~sid,
          'm4',
          'n1',
          'v0',
          ~root0
      ),

      !EpochRootKey(
          ~sid,
          'e0',
          'v0',
          ~root0
      ),

      Stage(
          ~sid,
          's0'
      ),

      Out(~sid)
  ]


/********************************************************************
 * EPOCH 1
 ********************************************************************/

rule Start_Epoch1:
  [
      Stage(
          sid,
          's0'
      ),

      !M1Base(
          sid,
          k4,
          k2v0,
          root0
      ),

      !M3Base(
          sid,
          k6,
          k3v0,
          root0
      ),

      Fr(~k3v1),
      Fr(~root1)
  ]
  --[
      RekeyStarted(
          sid,
          'e1'
      ),

      NextEpoch(
          sid,
          'e0',
          'e1'
      ),

      AuthorizedAt(
          sid,
          'm1',
          'e1'
      ),

      AuthorizedAt(
          sid,
          'm2',
          'e1'
      ),

      AuthorizedAt(
          sid,
          'm3',
          'e1'
      ),

      RevokedAt(
          sid,
          'm4',
          'e1'
      ),

      KeyVersion(
          sid,
          'n3',
          'v1',
          'e1'
      ),

      KeyVersion(
          sid,
          'n1',
          'v1',
          'e1'
      ),

      EpochRoot(
          sid,
          'e1',
          'v1',
          ~root1
      ),

      SecretEpoch(
          sid,
          'e1',
          'v1',
          ~root1
      ),

      LkhUpdate(
          sid,
          'e1',
          'n3',
          'v1',
          'n6',
          'v0'
      ),

      LkhRecipient(
          sid,
          'e1',
          'n3',
          'v1',
          'm3'
      ),

      LkhUpdate(
          sid,
          'e1',
          'n1',
          'v1',
          'n2',
          'v0'
      ),

      LkhRecipient(
          sid,
          'e1',
          'n1',
          'v1',
          'm1'
      ),

      LkhRecipient(
          sid,
          'e1',
          'n1',
          'v1',
          'm2'
      ),

      LkhUpdate(
          sid,
          'e1',
          'n1',
          'v1',
          'n3',
          'v1'
      ),

      LkhRecipient(
          sid,
          'e1',
          'n1',
          'v1',
          'm3'
      )
    ]->
  [
      !AuthorizedEpoch(
          sid,
          'm1',
          'e1'
      ),

      !AuthorizedEpoch(
          sid,
          'm2',
          'e1'
      ),

      !AuthorizedEpoch(
          sid,
          'm3',
          'e1'
      ),

      !RevokedEpoch(
          sid,
          'm4',
          'e1'
      ),

      !KeyMaterial(
          sid,
          'n3',
          'v1',
          'e1',
          ~k3v1
      ),

      !EpochRootKey(
          sid,
          'e1',
          'v1',
          ~root1
      ),

      !EpochCipher(
          sid,
          'e1',
          'n3',
          'v1',
          'n6',
          'v0',
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n3',
                  'v1',
                  ~k3v1
              >,
              k6
          )
      ),

      !EpochCipher(
          sid,
          'e1',
          'n1',
          'v1',
          'n2',
          'v0',
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  ~root1
              >,
              k2v0
          )
      ),

      !EpochCipher(
          sid,
          'e1',
          'n1',
          'v1',
          'n3',
          'v1',
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  ~root1
              >,
              ~k3v1
          )
      ),

      !ManagerEpoch1(
          sid,
          ~k3v1,
          ~root1
      ),

      Stage(
          sid,
          's1'
      ),

      Out(
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n3',
                  'v1',
                  ~k3v1
              >,
              k6
          )
      ),

      Out(
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  ~root1
              >,
              k2v0
          )
      ),

      Out(
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  ~root1
              >,
              ~k3v1
          )
      )
  ]


rule M3_Derive_N3_V1:
  [
      !M3Base(
          sid,
          k6,
          k3v0,
          root0
      ),

      !KeyMaterial(
          sid,
          'n3',
          'v1',
          'e1',
          k3v1
      ),

      In(
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n3',
                  'v1',
                  k3v1
              >,
              k6
          )
      )
  ]
  --[
      DerivedKey(
          sid,
          'm3',
          'n3',
          'v1',
          'e1'
      )
    ]->
  [
      !M3BranchE1(
          sid,
          k3v1
      ),

      !OwnsKey(
          sid,
          'm3',
          'n3',
          'v1',
          k3v1
      )
  ]


rule Accept_E1_M1:
  [
      !AuthorizedEpoch(
          sid,
          'm1',
          'e1'
      ),

      !M1Base(
          sid,
          k4,
          k2v0,
          root0
      ),

      !EpochRootKey(
          sid,
          'e1',
          'v1',
          root1
      ),

      In(
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  root1
              >,
              k2v0
          )
      )
  ]
  --[
      Accept(
          sid,
          'm1',
          'e1',
          'v1',
          root1
      ),

      AcceptCipher(
          sid,
          'm1',
          'e1',
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  root1
              >,
              k2v0
          )
      )
    ]->
  [
      !Accepted(
          sid,
          'm1',
          'e1',
          'v1',
          root1
      ),

      !OwnsKey(
          sid,
          'm1',
          'n1',
          'v1',
          root1
      )
  ]


rule Accept_E1_M2:
  [
      !AuthorizedEpoch(
          sid,
          'm2',
          'e1'
      ),

      !M2Base(
          sid,
          k5,
          k2v0,
          root0
      ),

      !EpochRootKey(
          sid,
          'e1',
          'v1',
          root1
      ),

      In(
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  root1
              >,
              k2v0
          )
      )
  ]
  --[
      Accept(
          sid,
          'm2',
          'e1',
          'v1',
          root1
      ),

      AcceptCipher(
          sid,
          'm2',
          'e1',
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  root1
              >,
              k2v0
          )
      )
    ]->
  [
      !Accepted(
          sid,
          'm2',
          'e1',
          'v1',
          root1
      ),

      !OwnsKey(
          sid,
          'm2',
          'n1',
          'v1',
          root1
      )
  ]


rule Accept_E1_M3:
  [
      !AuthorizedEpoch(
          sid,
          'm3',
          'e1'
      ),

      !M3BranchE1(
          sid,
          k3v1
      ),

      !EpochRootKey(
          sid,
          'e1',
          'v1',
          root1
      ),

      In(
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  root1
              >,
              k3v1
          )
      )
  ]
  --[
      Accept(
          sid,
          'm3',
          'e1',
          'v1',
          root1
      ),

      AcceptCipher(
          sid,
          'm3',
          'e1',
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  root1
              >,
              k3v1
          )
      )
    ]->
  [
      !Accepted(
          sid,
          'm3',
          'e1',
          'v1',
          root1
      ),

      !OwnsKey(
          sid,
          'm3',
          'n1',
          'v1',
          root1
      )
  ]


/********************************************************************
 * RECOVERY EPOCH 1
 ********************************************************************/

rule Recovery_Request_E1_M2:
  [
      !AuthorizedEpoch(
          sid,
          'm2',
          'e1'
      ),

      !EpochCipher(
          sid,
          'e1',
          'n1',
          'v1',
          'n2',
          'v0',
          cipher
      )
  ]
  --[
      RecoveryRequest(
          sid,
          'm2',
          'e1'
      )
    ]->
  [
      Recovering(
          sid,
          'm2',
          'e1'
      ),

      Out(
          <
              'recovery-request',
              sid,
              'm2',
              'e1'
          >
      )
  ]


rule Recovery_Response_E1_M1:
  [
      !AuthorizedEpoch(
          sid,
          'm1',
          'e1'
      ),

      !Accepted(
          sid,
          'm1',
          'e1',
          'v1',
          root1
      ),

      !EpochCipher(
          sid,
          'e1',
          'n1',
          'v1',
          'n2',
          'v0',
          cipher
      ),

      In(
          <
              'recovery-request',
              sid,
              'm2',
              'e1'
          >
      )
  ]
  --[
      RecoveryResponse(
          sid,
          'm1',
          'm2',
          'e1'
      )
    ]->
  [
      !RecoveryResponseCipher(
          sid,
          'e1',
          cipher
      ),

      Out(cipher)
  ]


rule Recovery_Accept_E1_M2:
  [
      Recovering(
          sid,
          'm2',
          'e1'
      ),

      !AuthorizedEpoch(
          sid,
          'm2',
          'e1'
      ),

      !M2Base(
          sid,
          k5,
          k2v0,
          root0
      ),

      !EpochRootKey(
          sid,
          'e1',
          'v1',
          root1
      ),

      In(
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  root1
              >,
              k2v0
          )
      )
  ]
  --[
      Accept(
          sid,
          'm2',
          'e1',
          'v1',
          root1
      ),

      RecoveryAccept(
          sid,
          'm2',
          'e1'
      ),

      RecoveryAcceptCipher(
          sid,
          'm2',
          'e1',
          senc(
              <
                  'lkh-update',
                  'e1',
                  'n1',
                  'v1',
                  root1
              >,
              k2v0
          )
      )
    ]->
  [
      !Accepted(
          sid,
          'm2',
          'e1',
          'v1',
          root1
      ),

      !OwnsKey(
          sid,
          'm2',
          'n1',
          'v1',
          root1
      )
  ]


/********************************************************************
 * EPOCH 2
 ********************************************************************/

rule Start_Epoch2:
  [
      Stage(
          sid,
          's1'
      ),

      !M1Base(
          sid,
          k4,
          k2v0,
          root0
      ),

      Fr(~root2)
  ]
  --[
      RekeyStarted(
          sid,
          'e2'
      ),

      NextEpoch(
          sid,
          'e1',
          'e2'
      ),

      AuthorizedAt(
          sid,
          'm1',
          'e2'
      ),

      AuthorizedAt(
          sid,
          'm2',
          'e2'
      ),

      RevokedAt(
          sid,
          'm3',
          'e2'
      ),

      KeyVersion(
          sid,
          'n1',
          'v2',
          'e2'
      ),

      EpochRoot(
          sid,
          'e2',
          'v2',
          ~root2
      ),

      SecretEpoch(
          sid,
          'e2',
          'v2',
          ~root2
      ),

      LkhUpdate(
          sid,
          'e2',
          'n1',
          'v2',
          'n2',
          'v0'
      ),

      LkhRecipient(
          sid,
          'e2',
          'n1',
          'v2',
          'm1'
      ),

      LkhRecipient(
          sid,
          'e2',
          'n1',
          'v2',
          'm2'
      )
    ]->
  [
      !AuthorizedEpoch(
          sid,
          'm1',
          'e2'
      ),

      !AuthorizedEpoch(
          sid,
          'm2',
          'e2'
      ),

      !RevokedEpoch(
          sid,
          'm3',
          'e2'
      ),

      !EpochRootKey(
          sid,
          'e2',
          'v2',
          ~root2
      ),

      !EpochCipher(
          sid,
          'e2',
          'n1',
          'v2',
          'n2',
          'v0',
          senc(
              <
                  'lkh-update',
                  'e2',
                  'n1',
                  'v2',
                  ~root2
              >,
              k2v0
          )
      ),

      !ManagerEpoch2(
          sid,
          ~root2
      ),

      Stage(
          sid,
          's2'
      ),

      Out(
          senc(
              <
                  'lkh-update',
                  'e2',
                  'n1',
                  'v2',
                  ~root2
              >,
              k2v0
          )
      )
  ]


rule Accept_E2_M1:
  [
      !AuthorizedEpoch(
          sid,
          'm1',
          'e2'
      ),

      !M1Base(
          sid,
          k4,
          k2v0,
          root0
      ),

      !EpochRootKey(
          sid,
          'e2',
          'v2',
          root2
      ),

      In(
          senc(
              <
                  'lkh-update',
                  'e2',
                  'n1',
                  'v2',
                  root2
              >,
              k2v0
          )
      )
  ]
  --[
      Accept(
          sid,
          'm1',
          'e2',
          'v2',
          root2
      ),

      AcceptCipher(
          sid,
          'm1',
          'e2',
          senc(
              <
                  'lkh-update',
                  'e2',
                  'n1',
                  'v2',
                  root2
              >,
              k2v0
          )
      )
    ]->
  [
      !Accepted(
          sid,
          'm1',
          'e2',
          'v2',
          root2
      ),

      !OwnsKey(
          sid,
          'm1',
          'n1',
          'v2',
          root2
      )
  ]


rule Accept_E2_M2:
  [
      !AuthorizedEpoch(
          sid,
          'm2',
          'e2'
      ),

      !M2Base(
          sid,
          k5,
          k2v0,
          root0
      ),

      !EpochRootKey(
          sid,
          'e2',
          'v2',
          root2
      ),

      In(
          senc(
              <
                  'lkh-update',
                  'e2',
                  'n1',
                  'v2',
                  root2
              >,
              k2v0
          )
      )
  ]
  --[
      Accept(
          sid,
          'm2',
          'e2',
          'v2',
          root2
      ),

      AcceptCipher(
          sid,
          'm2',
          'e2',
          senc(
              <
                  'lkh-update',
                  'e2',
                  'n1',
                  'v2',
                  root2
              >,
              k2v0
          )
      )
    ]->
  [
      !Accepted(
          sid,
          'm2',
          'e2',
          'v2',
          root2
      ),

      !OwnsKey(
          sid,
          'm2',
          'n1',
          'v2',
          root2
      )
  ]


/********************************************************************
 * RECOVERY EPOCH 2
 ********************************************************************/

rule Recovery_Request_E2_M2:
  [
      !AuthorizedEpoch(
          sid,
          'm2',
          'e2'
      ),

      !EpochCipher(
          sid,
          'e2',
          'n1',
          'v2',
          'n2',
          'v0',
          cipher
      )
  ]
  --[
      RecoveryRequest(
          sid,
          'm2',
          'e2'
      )
    ]->
  [
      Recovering(
          sid,
          'm2',
          'e2'
      ),

      Out(
          <
              'recovery-request',
              sid,
              'm2',
              'e2'
          >
      )
  ]


rule Recovery_Response_E2_M1:
  [
      !AuthorizedEpoch(
          sid,
          'm1',
          'e2'
      ),

      !Accepted(
          sid,
          'm1',
          'e2',
          'v2',
          root2
      ),

      !EpochCipher(
          sid,
          'e2',
          'n1',
          'v2',
          'n2',
          'v0',
          cipher
      ),

      In(
          <
              'recovery-request',
              sid,
              'm2',
              'e2'
          >
      )
  ]
  --[
      RecoveryResponse(
          sid,
          'm1',
          'm2',
          'e2'
      )
    ]->
  [
      !RecoveryResponseCipher(
          sid,
          'e2',
          cipher
      ),

      Out(cipher)
  ]


rule Recovery_Accept_E2_M2:
  [
      Recovering(
          sid,
          'm2',
          'e2'
      ),

      !AuthorizedEpoch(
          sid,
          'm2',
          'e2'
      ),

      !M2Base(
          sid,
          k5,
          k2v0,
          root0
      ),

      !EpochRootKey(
          sid,
          'e2',
          'v2',
          root2
      ),

      In(
          senc(
              <
                  'lkh-update',
                  'e2',
                  'n1',
                  'v2',
                  root2
              >,
              k2v0
          )
      )
  ]
  --[
      Accept(
          sid,
          'm2',
          'e2',
          'v2',
          root2
      ),

      RecoveryAccept(
          sid,
          'm2',
          'e2'
      ),

      RecoveryAcceptCipher(
          sid,
          'm2',
          'e2',
          senc(
              <
                  'lkh-update',
                  'e2',
                  'n1',
                  'v2',
                  root2
              >,
              k2v0
          )
      )
    ]->
  [
      !Accepted(
          sid,
          'm2',
          'e2',
          'v2',
          root2
      ),

      !OwnsKey(
          sid,
          'm2',
          'n1',
          'v2',
          root2
      )
  ]


/********************************************************************
 * REPLAY
 ********************************************************************/

rule Replay_E1_Root_Cipher_At_E2:
  [
      !EpochRootKey(
          sid,
          'e2',
          'v2',
          root2
      ),

      !EpochCipher(
          sid,
          'e1',
          'n1',
          'v1',
          'n2',
          'v0',
          oldcipher
      )
  ]
  --[
      ReplayOldCipher(
          sid,
          'e1',
          'e2',
          oldcipher
      )
    ]->
  [
      Out(oldcipher)
  ]


rule Replay_E1_Recovery_Response_At_E2:
  [
      !EpochRootKey(
          sid,
          'e2',
          'v2',
          root2
      ),

      !RecoveryResponseCipher(
          sid,
          'e1',
          oldcipher
      )
  ]
  --[
      ReplayOldRecoveryResponse(
          sid,
          'e1',
          'e2',
          oldcipher
      )
    ]->
  [
      Out(oldcipher)
  ]


/********************************************************************
 * COMPROMISE
 ********************************************************************/

rule Compromise_M1:
  [
      !M1Base(
          sid,
          k4,
          k2v0,
          root0
      )
  ]
  --[
      CompromiseMember(
          sid,
          'm1'
      )
    ]->
  [
      Out(k4),
      Out(k2v0),
      Out(root0)
  ]


rule Compromise_M2:
  [
      !M2Base(
          sid,
          k5,
          k2v0,
          root0
      )
  ]
  --[
      CompromiseMember(
          sid,
          'm2'
      )
    ]->
  [
      Out(k5),
      Out(k2v0),
      Out(root0)
  ]


rule Compromise_M3:
  [
      !M3Base(
          sid,
          k6,
          k3v0,
          root0
      )
  ]
  --[
      CompromiseMember(
          sid,
          'm3'
      )
    ]->
  [
      Out(k6),
      Out(k3v0),
      Out(root0)
  ]


rule Compromise_M4:
  [
      !M4Base(
          sid,
          k7,
          k3v0,
          root0
      )
  ]
  --[
      CompromiseMember(
          sid,
          'm4'
      )
    ]->
  [
      Out(k7),
      Out(k3v0),
      Out(root0)
  ]


rule Compromise_GM_E1:
  [
      !ManagerEpoch1(
          sid,
          k3v1,
          root1
      )
  ]
  --[
      CompromiseManager(
          sid,
          'e1'
      )
    ]->
  [
      Out(k3v1),
      Out(root1)
  ]


rule Compromise_GM_E2:
  [
      !ManagerEpoch2(
          sid,
          root2
      )
  ]
  --[
      CompromiseManager(
          sid,
          'e2'
      )
    ]->
  [
      Out(root2)
  ]


/********************************************************************
 * OLD-KEY LEAKS
 ********************************************************************/

rule Leak_M4_Old_Keys_After_E1:
  [
      !RevokedEpoch(
          sid,
          'm4',
          'e1'
      ),

      !M4Base(
          sid,
          k7,
          k3v0,
          root0
      )
  ]
  --[
      OldKeyLeak(
          sid,
          'm4',
          'e1'
      )
    ]->
  [
      Out(k7),
      Out(k3v0),
      Out(root0)
  ]


rule Leak_M3_Old_Keys_After_E2:
  [
      !RevokedEpoch(
          sid,
          'm3',
          'e2'
      ),

      !M3Base(
          sid,
          k6,
          k3v0,
          root0
      ),

      !M3BranchE1(
          sid,
          k3v1
      ),

      !Accepted(
          sid,
          'm3',
          'e1',
          'v1',
          root1
      )
  ]
  --[
      OldKeyLeak(
          sid,
          'm3',
          'e2'
      )
    ]->
  [
      Out(k6),
      Out(k3v0),
      Out(root0),
      Out(k3v1),
      Out(root1)
  ]


/********************************************************************
 * 16 ORIGINAL STEP7D2-B LEMMAS — SESSION BOUND
 ********************************************************************/

lemma executable_first_lkh_rekey:
  exists-trace
  "
    Ex sid root #i.
      RekeyStarted(sid,'e1') @ i
    & EpochRoot(sid,'e1','v1',root) @ i
  "


lemma executable_second_lkh_rekey:
  exists-trace
  "
    Ex sid root1 root2 #i #j.
      EpochRoot(sid,'e1','v1',root1) @ i
    & EpochRoot(sid,'e2','v2',root2) @ j
    & i < j
  "


lemma executable_same_epoch_recovery_after_lkh_rekey:
  exists-trace
  "
    Ex sid #q #r #a.
      RecoveryRequest(sid,'m2','e1') @ q
    & RecoveryResponse(sid,'m1','m2','e1') @ r
    & RecoveryAccept(sid,'m2','e1') @ a
    & q < r
    & r < a
  "


lemma executable_old_cipher_replay:
  exists-trace
  "
    Ex sid c #i #r.
      RekeyStarted(sid,'e2') @ i
    & ReplayOldCipher(sid,'e1','e2',c) @ r
    & i < r
  "


lemma second_epoch_follows_first:
  "
    All sid #j.
      RekeyStarted(sid,'e2') @ j
      ==>
      (Ex #i.
         RekeyStarted(sid,'e1') @ i
       & NextEpoch(sid,'e1','e2') @ j
       & i < j)
  "


lemma revoked_member_excluded_from_new_epoch:
  "
    All sid m e v root #r #a.
      RevokedAt(sid,m,e) @ r
    & Accept(sid,m,e,v,root) @ a
      ==> F
  "


lemma survivor_acceptance_has_lkh_update_chain:
  "
    All sid m e v root #a.
      Accept(sid,m,e,v,root) @ a
      ==>
      (Ex wrapper wrapperVersion #u.
         LkhUpdate(
             sid,
             e,
             'n1',
             v,
             wrapper,
             wrapperVersion
         ) @ u
       & LkhRecipient(
             sid,
             e,
             'n1',
             v,
             m
         ) @ u
       & u < a)
  "


lemma m3_acceptance_requires_branch_update:
  "
    All sid root #a.
      Accept(
          sid,
          'm3',
          'e1',
          'v1',
          root
      ) @ a
      ==>
      (Ex #d.
         DerivedKey(
             sid,
             'm3',
             'n3',
             'v1',
             'e1'
         ) @ d
       & d < a)
  "


lemma acceptance_matches_current_root_version:
  "
    All sid m e v root #a.
      Accept(sid,m,e,v,root) @ a
      ==>
      (Ex #r.
         EpochRoot(sid,e,v,root) @ r
       & r < a)
  "


lemma replay_old_capsule_cannot_accept_new_epoch:
  "
    All sid m c #r #a.
      ReplayOldCipher(
          sid,
          'e1',
          'e2',
          c
      ) @ r
    & AcceptCipher(
          sid,
          m,
          'e2',
          c
      ) @ a
      ==> F
  "


lemma replay_old_recovery_response_cannot_accept_new_epoch:
  "
    All sid m c #r #a.
      ReplayOldRecoveryResponse(
          sid,
          'e1',
          'e2',
          c
      ) @ r
    & RecoveryAcceptCipher(
          sid,
          m,
          'e2',
          c
      ) @ a
      ==> F
  "


lemma root_keys_fresh_across_epochs:
  "
    All sid root1 root2 #i #j.
      EpochRoot(
          sid,
          'e1',
          'v1',
          root1
      ) @ i
    & EpochRoot(
          sid,
          'e2',
          'v2',
          root2
      ) @ j
      ==>
      not (root1 = root2)
  "


lemma new_epoch_key_secret_without_relevant_compromise:
  "
    All sid e v root #s #k.
      SecretEpoch(
          sid,
          e,
          v,
          root
      ) @ s
    & K(root) @ k
      ==>
      (
        (Ex m #a #c.
           AuthorizedAt(
               sid,
               m,
               e
           ) @ a
         & CompromiseMember(
               sid,
               m
           ) @ c
         & c < k)
        |
        (Ex #c.
           CompromiseManager(
               sid,
               e
           ) @ c
         & c < k)
      )
  "


lemma revoked_old_key_does_not_reveal_new_root_key:
  "
    All sid m e v root #l #s #k.
      OldKeyLeak(
          sid,
          m,
          e
      ) @ l
    & SecretEpoch(
          sid,
          e,
          v,
          root
      ) @ s
    & K(root) @ k
      ==>
      (
        (Ex survivor #a #c.
           AuthorizedAt(
               sid,
               survivor,
               e
           ) @ a
         & CompromiseMember(
               sid,
               survivor
           ) @ c
         & c < k)
        |
        (Ex #c.
           CompromiseManager(
               sid,
               e
           ) @ c
         & c < k)
      )
  "


lemma recovery_requester_authorized_in_same_epoch:
  "
    All sid requester e #r.
      RecoveryRequest(
          sid,
          requester,
          e
      ) @ r
      ==>
      (Ex #a.
         AuthorizedAt(
             sid,
             requester,
             e
         ) @ a
       & a < r)
  "


lemma recovery_helper_authorized_in_same_epoch:
  "
    All sid helper requester e #r.
      RecoveryResponse(
          sid,
          helper,
          requester,
          e
      ) @ r
      ==>
      (Ex #a.
         AuthorizedAt(
             sid,
             helper,
             e
         ) @ a
       & a < r)
  "


end
"""


path.parent.mkdir(
    parents=True,
    exist_ok=True,
)


path.write_text(
    model.strip()
    + "\n",
    encoding="utf-8",
    newline="\n",
)


print(
    f"MODEL_CREATED={path}"
)

print(
    "SESSION_BOUND_MODEL_GENERATION=PASS"
)
PY


# ==================================================================
# 5. Static contract
# ==================================================================

echo
echo "===== 5. SESSION-BOUND STATIC CONTRACT ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - "$V2" "$OUT/model-static-audit.json" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


path = Path(sys.argv[1])
out = Path(sys.argv[2])

text = path.read_text(
    encoding="utf-8"
)


lemmas = re.findall(
    r"(?m)^lemma\s+([A-Za-z0-9_]+)\s*:",
    text,
)


expected = [
    "executable_first_lkh_rekey",
    "executable_second_lkh_rekey",
    "executable_same_epoch_recovery_after_lkh_rekey",
    "executable_old_cipher_replay",
    "second_epoch_follows_first",
    "revoked_member_excluded_from_new_epoch",
    "survivor_acceptance_has_lkh_update_chain",
    "m3_acceptance_requires_branch_update",
    "acceptance_matches_current_root_version",
    "replay_old_capsule_cannot_accept_new_epoch",
    "replay_old_recovery_response_cannot_accept_new_epoch",
    "root_keys_fresh_across_epochs",
    "new_epoch_key_secret_without_relevant_compromise",
    "revoked_old_key_does_not_reveal_new_root_key",
    "recovery_requester_authorized_in_same_epoch",
    "recovery_helper_authorized_in_same_epoch",
]


checks = {
    "session_bound_theory":
        (
            "RangerIoT_LKH_MultiEpoch_4Member_SessionBound"
            in text
        ),

    "fresh_sid":
        (
            "Fr(~sid)"
            in text
        ),

    "public_sid":
        (
            "Out(~sid)"
            in text
        ),

    "stage_bound_sid":
        (
            "Stage(\n          ~sid,\n          's0'"
            in text
            and
            "Stage(\n          sid,\n          's1'"
            in text
        ),

    "base_state_sid":
        (
            "!M1Base(\n          sid,"
            in text
            and
            "!M3Base(\n          sid,"
            in text
        ),

    "epoch_actions_sid":
        (
            "RekeyStarted(\n          sid,"
            in text
            and
            "SecretEpoch(\n          sid,"
            in text
        ),

    "accept_sid":
        (
            "Accept(\n          sid,"
            in text
        ),

    "compromise_sid":
        (
            "CompromiseMember(\n          sid,"
            in text
            and
            "CompromiseManager(\n          sid,"
            in text
        ),

    "old_key_leak_sid":
        (
            "OldKeyLeak(\n          sid,"
            in text
        ),

    "recovery_request_message_sid":
        (
            "'recovery-request',\n              sid,"
            in text
        ),

    "exact_epoch1_update_n3_n6":
        (
            "'e1',\n"
            "          'n3',\n"
            "          'v1',\n"
            "          'n6',\n"
            "          'v0'"
            in text
        ),

    "exact_epoch1_root_n2":
        (
            "'e1',\n"
            "          'n1',\n"
            "          'v1',\n"
            "          'n2',\n"
            "          'v0'"
            in text
        ),

    "exact_epoch1_root_n3":
        (
            "'e1',\n"
            "          'n1',\n"
            "          'v1',\n"
            "          'n3',\n"
            "          'v1'"
            in text
        ),

    "exact_epoch2_root_n2":
        (
            "'e2',\n"
            "          'n1',\n"
            "          'v2',\n"
            "          'n2',\n"
            "          'v0'"
            in text
        ),

    "same_16_lemmas":
        lemmas == expected,

    "lemma_count_16":
        len(lemmas) == 16,

    "no_old_unscoped_rekey":
        (
            "RekeyStarted('e1')"
            not in text
            and
            "RekeyStarted('e2')"
            not in text
        ),

    "no_old_unscoped_secret":
        (
            "SecretEpoch('e1'"
            not in text
            and
            "SecretEpoch('e2'"
            not in text
        ),

    "no_sorry":
        "sorry" not in text.lower(),

    "no_admit":
        "admit" not in text.lower(),
}


for key, passed in checks.items():

    print(
        f"{key:40s}",
        "PASS"
        if passed
        else "FAIL",
    )


if not all(
    checks.values()
):

    raise SystemExit(
        "SESSION-BOUND STATIC CONTRACT FAILED"
    )


payload = {
    "schema_version":
        1,

    "model":
        path.as_posix(),

    "lemma_count":
        len(lemmas),

    "lemmas":
        lemmas,

    "checks":
        checks,

    "pass":
        True,
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


print()
print(
    "SESSION_BOUND_STATIC_CONTRACT=PASS"
)
PY


# ==================================================================
# 6. Hash V2
# ==================================================================

echo
echo "===== 6. FORMAL INPUT HASH ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
    "$V2" \
  > "$OUT/v2-model.sha256"

cat "$OUT/v2-model.sha256"


# ==================================================================
# 7. Tamarin precompute
# ==================================================================

echo
echo "===== 7. TAMARIN PRECOMPUTE ====="

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
        '$V2'
  " \
  > "$OUT/precompute.log" \
  2>&1

PRE_RC=$?

set -e

echo "PRECOMPUTE_RC=$PRE_RC"

if [ "$PRE_RC" -ne 0 ]; then

    echo "SESSION_BOUND_PRECOMPUTE=FAIL"

    cat "$OUT/precompute.log"

    exit "$PRE_RC"

fi

echo "SESSION_BOUND_PRECOMPUTE=PASS"


# ==================================================================
# 8. Isolated proof matrix
# ==================================================================

echo
echo "===== 8. SESSION-BOUND 16-LEMMA PROOF MATRIX ====="

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
"new_epoch_key_secret_without_relevant_compromise|all-traces|420|DFS|s"
"revoked_old_key_does_not_reveal_new_root_key|all-traces|420|DFS|s"
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
            '$V2' \
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
# 9. Classify
# ==================================================================

echo
echo "===== 9. CLASSIFY SESSION-BOUND RESULTS ====="

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

            "budget_seconds":
                int(budget),

            "search":
                search,

            "heuristic":
                heuristic,

            "return_code":
                rc,

            "status":
                status,

            "details":
                details,

            "classification":
                classification,
        }
    )


def select(kind: str) -> list[str]:

    return [
        row["lemma"]
        for row in rows
        if (
            row["classification"]
            == kind
        )
    ]


verified = select(
    "verified"
)

falsified = select(
    "falsified"
)

timeouts = select(
    "timeout"
)

incomplete = select(
    "incomplete"
)

errors = [
    row["lemma"]
    for row in rows
    if row["classification"]
    in {
        "execution_error",
        "missing_summary",
    }
]


all_16 = (
    len(verified) == 16
    and
    not falsified
    and
    not timeouts
    and
    not incomplete
    and
    not errors
)


if all_16:

    state = (
        "STEP7D2B_SESSION_BOUND_"
        "REFERENCE_ALL_16_LEMMAS_VERIFIED"
    )

elif falsified:

    state = (
        "STEP7D2B_SESSION_BOUND_"
        "COUNTEREXAMPLE_REAUDIT_REQUIRED"
    )

elif timeouts:

    state = (
        "STEP7D2B_SESSION_BOUND_"
        "PARTIAL_PROOF_WITH_TIMEOUTS"
    )

elif errors:

    state = (
        "STEP7D2B_SESSION_BOUND_"
        "EXECUTION_ANOMALY"
    )

else:

    state = (
        "STEP7D2B_SESSION_BOUND_"
        "PARTIAL_RESULT"
    )


previously_falsified = {
    "new_epoch_key_secret_without_relevant_compromise",
    "revoked_old_key_does_not_reveal_new_root_key",
}


repair_resolved_both = (
    previously_falsified
    <= set(verified)
)


payload = {
    "schema_version":
        1,

    "step":
        "STEP7D2B_SESSION_BOUND_REPAIR",

    "model":
        (
            "formal/tamarin/"
            "ranger_lkh_multi_epoch_4member_"
            "session_bound.spthy"
        ),

    "model_class":
        (
            "SESSION_BOUND_EXACT_IMPLEMENTED_"
            "SYMBOLIC_LKH_FOUR_MEMBER_"
            "MULTI_EPOCH_REFERENCE_INSTANCE"
        ),

    "repair":
        "fresh public sid propagated through protocol state",

    "implementation_modified":
        False,

    "cryptographic_update_plan_modified":
        False,

    "arbitrary_n_theorem":
        False,

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

    "previously_falsified_lemmas":
        sorted(
            previously_falsified
        ),

    "previously_falsified_now_verified":
        repair_resolved_both,

    "all_16_verified":
        all_16,

    "rows":
        rows,

    "scientific_state":
        state,

    "full_ranger_formally_verified":
        False,

    "next_if_all_verified":
        (
            "STEP7D2C_GENERALIZE_"
            "MULTI_EPOCH_LKH_STRUCTURE"
        ),

    "next_if_falsified":
        (
            "STEP7D2B_SESSION_BOUND_"
            "COUNTEREXAMPLE_AUDIT"
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


print(
    f"{'LEMMA':54s} "
    f"{'RESULT':22s}"
)

print("-" * 80)


for row in rows:

    print(
        f"{row['lemma'][:54]:54s} "
        f"{row['classification']:22s}"
    )


print()
print(
    f"VERIFIED={len(verified)}/16"
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
    "PREVIOUSLY_FALSIFIED_NOW_VERIFIED="
    + str(
        repair_resolved_both
    )
)

print(
    f"STATE={state}"
)
PY


# ==================================================================
# 10. Verify V1 and implementation remained unchanged
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
    "$V1" \
  > "$OUT/v1-after.sha256"


docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$OUT/v1-before.sha256" \
    "$OUT/v1-after.sha256" <<'PY'
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
    f"V1_BEFORE={before}"
)

print(
    f"V1_AFTER ={after}"
)


if before != after:

    raise SystemExit(
        "V1 formal model changed"
    )


print()
print(
    "V1_FORMAL_MODEL_UNCHANGED=PASS"
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
# 11. Project CI
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
# 12. Package
# ==================================================================

echo
echo "===== 12. EVIDENCE PACKAGE ====="

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

    MAN=/tmp/step7d2bsr.sha256
    TAR=/tmp/step7d2bsr.tar.gz

    rm -f \
      \"\$MAN\" \
      \"\$TAR\"

    find '$OUT' \
      -type f \
      ! -name 'evidence.sha256' \
      ! -name 'evidence-verify.log' \
      ! -name 'step7d2bsr-evidence.tar.gz' \
      ! -name 'step7d2bsr-evidence.tar.gz.sha256' \
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

    tar \
      -tzf \
      \"\$TAR\" \
      >/dev/null

    cp \
      \"\$TAR\" \
      '$OUT/step7d2bsr-evidence.tar.gz'

    sha256sum \
      '$OUT/step7d2bsr-evidence.tar.gz' \
      > '$OUT/step7d2bsr-evidence.tar.gz.sha256'

    sha256sum \
      -c \
      '$OUT/step7d2bsr-evidence.tar.gz.sha256'
  "


echo
echo "===================================================================="
echo "STEP 7D.2-B-SR COMPLETE"
echo
echo "V1:"
echo "  $V1"
echo
echo "SESSION-BOUND V2:"
echo "  $V2"
echo
echo "RESULT:"
echo "  $SUMMARY"
echo
echo "IMPLEMENTATION MODIFIED = NO"
echo "V1 COUNTEREXAMPLES PRESERVED = YES"
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
