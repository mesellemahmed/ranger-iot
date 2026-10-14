#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"
FORMAL_COMPOSE="compose.reproducibility.yaml"

PREV="artifacts/article-evidence/32-step7d2a-lkh-semantic-freeze"

OUT="artifacts/article-evidence/33-step7d2b-lkh-multi-epoch-tamarin"
LOG_DIR="$OUT/logs"

MODEL="formal/tamarin/ranger_lkh_multi_epoch_4member.spthy"
MAPPING="$OUT/semantic-mapping.json"
SUMMARY="$OUT/proof-matrix.json"

mkdir -p "$LOG_DIR"

echo "===================================================================="
echo "RANGER-IOT — STEP 7D.2-B"
echo "IMPLEMENTED LKH MULTI-EPOCH TAMARIN REFERENCE MODEL"
echo
echo "INSTANCE:"
echo "  members = 1,2,3,4"
echo "  epoch1: revoke member 4"
echo "  epoch2: revoke member 3"
echo
echo "SCOPE:"
echo "  symbolic key versions"
echo "  exact observed LKH target/wrapper/recipient relations"
echo "  two sequential epochs"
echo "  replay/freshness"
echo "  recovery same-epoch"
echo "  explicit compromise timing"
echo
echo "NOT CLAIMED:"
echo "  arbitrary-N LKH theorem"
echo "  byte-level LKH cryptography"
echo "  implementation equivalence proof"
echo
echo "DOCKER ONLY"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="


# ==================================================================
# 1. STEP7D2-A prerequisite
# ==================================================================

echo
echo "===== 1. STEP7D2-A PREREQUISITE ====="

test -f "$PREV/step7d2a-readiness.json"
test -f "$PREV/lkh-semantic-probe.json"
test -f "$PREV/implemented-semantics.sha256"

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$PREV/step7d2a-readiness.json" <<'PY'
import json
import sys
from pathlib import Path


data = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)


checks = {
    "step7d2a_pass":
        data.get("step7d2a_pass") is True,

    "ready":
        data.get(
            "ready_for_step7d2_tamarin_model"
        ) is True,

    "state":
        data.get(
            "scientific_state"
        )
        ==
        "IMPLEMENTED_SYMBOLIC_LKH_SEMANTICS_FROZEN_FOR_FORMALIZATION",

    "byte_level_not_claimed":
        data.get(
            "byte_level_lkh_crypto_claim"
        ) is False,
}


for key, value in checks.items():
    print(
        f"{key:34s}",
        "PASS" if value else "FAIL",
    )


if not all(checks.values()):
    raise SystemExit(
        "STEP7D2-A prerequisite failed"
    )


print()
print("STEP7D2A_PREREQUISITE=PASS")
PY


# ==================================================================
# 2. Verify implemented semantics still unchanged
# ==================================================================

echo
echo "===== 2. IMPLEMENTATION FREEZE CHECK ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
  -c \
  "$PREV/implemented-semantics.sha256"

echo "IMPLEMENTED_SEMANTICS_UNCHANGED=PASS"


# ==================================================================
# 3. Generate semantic mapping from frozen probe
# ==================================================================

echo
echo "===== 3. GENERATE EXACT SEMANTIC MAPPING ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$PREV/lkh-semantic-probe.json" \
    "$MAPPING" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


probe = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

out = Path(sys.argv[2])


case = probe[
    "cases"
][
    "four_members_revoke_4_then_3"
]


steps = case["steps"]

if len(steps) != 2:
    raise SystemExit(
        "Expected exactly two sequential rekeys"
    )


step1 = steps[0]
step2 = steps[1]


def compact_update(update):
    return {
        "target_node":
            update["target"]["node_id"],

        "target_version":
            update["target"]["version"],

        "wrapper_node":
            update["wrapper"]["node_id"],

        "wrapper_version":
            update["wrapper"]["version"],

        "recipients":
            update["recipients"],
    }


observed1 = [
    compact_update(update)
    for update
    in step1["plan"]["updates"]
]

observed2 = [
    compact_update(update)
    for update
    in step2["plan"]["updates"]
]


expected1 = [
    {
        "target_node": 3,
        "target_version": 1,
        "wrapper_node": 6,
        "wrapper_version": 0,
        "recipients": [3],
    },
    {
        "target_node": 1,
        "target_version": 1,
        "wrapper_node": 2,
        "wrapper_version": 0,
        "recipients": [1, 2],
    },
    {
        "target_node": 1,
        "target_version": 1,
        "wrapper_node": 3,
        "wrapper_version": 1,
        "recipients": [3],
    },
]


expected2 = [
    {
        "target_node": 1,
        "target_version": 2,
        "wrapper_node": 2,
        "wrapper_version": 0,
        "recipients": [1, 2],
    },
]


checks = {
    "epoch1_revoked":
        step1["revoked_now"] == [4],

    "epoch2_revoked":
        step2["revoked_now"] == [3],

    "epoch1_root_version":
        step1["plan"]["root_key"]["version"]
        == 1,

    "epoch2_root_version":
        step2["plan"]["root_key"]["version"]
        == 2,

    "epoch1_updates_exact":
        observed1 == expected1,

    "epoch2_updates_exact":
        observed2 == expected2,

    "final_active":
        step2["after"]["active_member_ids"]
        == [1, 2],
}


for key, passed in checks.items():

    print(
        f"{key:34s}",
        "PASS"
        if passed
        else "FAIL",
    )


if not all(checks.values()):
    raise SystemExit(
        "Frozen LKH probe differs from expected reference instance"
    )


payload = {
    "schema_version":
        1,

    "source":
        (
            "STEP7D2A implemented "
            "LkhKeyTree semantic probe"
        ),

    "formal_instance":
        "FOUR_MEMBER_REVOKE_4_THEN_3",

    "tree": {
        "root":
            1,

        "parents": {
            "4": 2,
            "5": 2,
            "6": 3,
            "7": 3,
            "2": 1,
            "3": 1,
        },

        "member_leaves": {
            "1": 4,
            "2": 5,
            "3": 6,
            "4": 7,
        },
    },

    "epoch1": {
        "revoked":
            [4],

        "active":
            [1, 2, 3],

        "root_version":
            1,

        "updates":
            observed1,
    },

    "epoch2": {
        "revoked":
            [3],

        "active":
            [1, 2],

        "root_version":
            2,

        "updates":
            observed2,
    },

    "claim_boundary":
        (
            "Exact reference-instance model of "
            "implemented symbolic LKH plan semantics; "
            "not an arbitrary-N theorem."
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


print()
print(
    "EXACT_LKH_REFERENCE_MAPPING=PASS"
)
PY


# ==================================================================
# 4. Create Tamarin model
# ==================================================================

echo
echo "===== 4. CREATE TAMARIN MULTI-EPOCH MODEL ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - "$MODEL" <<'PY'
from pathlib import Path
import sys


path = Path(sys.argv[1])

model = r"""
theory RangerIoT_LKH_MultiEpoch_4Member

begin

builtins: symmetric-encryption


/********************************************************************
 * STEP 7D.2-B
 *
 * Exact reference instance derived from implemented LkhKeyTree:
 *
 * members 1,2,3,4
 *
 * tree:
 *
 *           n1
 *         /    \
 *       n2      n3
 *      /  \    /  \
 *    n4   n5 n6   n7
 *    m1   m2 m3   m4
 *
 * epoch e1:
 *   revoke m4
 *
 *   update n3/v1 under n6/v0 -> m3
 *   update n1/v1 under n2/v0 -> m1,m2
 *   update n1/v1 under n3/v1 -> m3
 *
 * epoch e2:
 *   revoke m3
 *
 *   update n1/v2 under n2/v0 -> m1,m2
 *
 * This is NOT a generic arbitrary-N LKH theorem.
 ********************************************************************/


/********************************************************************
 * SETUP
 ********************************************************************/

rule Setup:
  [
      Fr(~k4),
      Fr(~k5),
      Fr(~k6),
      Fr(~k7),
      Fr(~k2v0),
      Fr(~k3v0),
      Fr(~root0)
  ]
  --[
      Setup('gm'),

      EpochRoot(
          'e0',
          'v0',
          ~root0
      )
    ]->
  [
      !GroupContext(
          'gm',
          'm1',
          'm2',
          'm3',
          'm4'
      ),

      !Parent('n4','n2'),
      !Parent('n5','n2'),
      !Parent('n6','n3'),
      !Parent('n7','n3'),
      !Parent('n2','n1'),
      !Parent('n3','n1'),

      !MemberLeaf('m1','n4'),
      !MemberLeaf('m2','n5'),
      !MemberLeaf('m3','n6'),
      !MemberLeaf('m4','n7'),

      !M1Base(~k4,~k2v0,~root0),
      !M2Base(~k5,~k2v0,~root0),
      !M3Base(~k6,~k3v0,~root0),
      !M4Base(~k7,~k3v0,~root0),

      !OwnsKey('m1','n4','v0',~k4),
      !OwnsKey('m1','n2','v0',~k2v0),
      !OwnsKey('m1','n1','v0',~root0),

      !OwnsKey('m2','n5','v0',~k5),
      !OwnsKey('m2','n2','v0',~k2v0),
      !OwnsKey('m2','n1','v0',~root0),

      !OwnsKey('m3','n6','v0',~k6),
      !OwnsKey('m3','n3','v0',~k3v0),
      !OwnsKey('m3','n1','v0',~root0),

      !OwnsKey('m4','n7','v0',~k7),
      !OwnsKey('m4','n3','v0',~k3v0),
      !OwnsKey('m4','n1','v0',~root0),

      !EpochRootKey(
          'e0',
          'v0',
          ~root0
      ),

      Stage('s0')
  ]


/********************************************************************
 * EPOCH 1
 *
 * Implemented plan:
 *
 *   revoke m4
 *
 *   target n3/v1 wrapper n6/v0 recipients {m3}
 *   target n1/v1 wrapper n2/v0 recipients {m1,m2}
 *   target n1/v1 wrapper n3/v1 recipients {m3}
 ********************************************************************/

rule Start_Epoch1:
  [
      Stage('s0'),

      !M1Base(k4,k2v0,root0),
      !M3Base(k6,k3v0,root0),

      Fr(~k3v1),
      Fr(~root1)
  ]
  --[
      RekeyStarted('e1'),

      NextEpoch('e0','e1'),

      AuthorizedAt('m1','e1'),
      AuthorizedAt('m2','e1'),
      AuthorizedAt('m3','e1'),

      RevokedAt('m4','e1'),

      KeyVersion(
          'n3',
          'v1',
          'e1'
      ),

      KeyVersion(
          'n1',
          'v1',
          'e1'
      ),

      EpochRoot(
          'e1',
          'v1',
          ~root1
      ),

      SecretEpoch(
          'e1',
          'v1',
          ~root1
      ),

      LkhUpdate(
          'e1',
          'n3',
          'v1',
          'n6',
          'v0'
      ),

      LkhRecipient(
          'e1',
          'n3',
          'v1',
          'm3'
      ),

      LkhUpdate(
          'e1',
          'n1',
          'v1',
          'n2',
          'v0'
      ),

      LkhRecipient(
          'e1',
          'n1',
          'v1',
          'm1'
      ),

      LkhRecipient(
          'e1',
          'n1',
          'v1',
          'm2'
      ),

      LkhUpdate(
          'e1',
          'n1',
          'v1',
          'n3',
          'v1'
      ),

      LkhRecipient(
          'e1',
          'n1',
          'v1',
          'm3'
      )
    ]->
  [
      !AuthorizedEpoch('m1','e1'),
      !AuthorizedEpoch('m2','e1'),
      !AuthorizedEpoch('m3','e1'),

      !RevokedEpoch('m4','e1'),

      !KeyMaterial(
          'n3',
          'v1',
          'e1',
          ~k3v1
      ),

      !EpochRootKey(
          'e1',
          'v1',
          ~root1
      ),

      !EpochCipher(
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
          ~k3v1,
          ~root1
      ),

      Stage('s1'),

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


/********************************************************************
 * MEMBER 3 DERIVES THE UPDATED n3 KEY
 ********************************************************************/

rule M3_Derive_N3_V1:
  [
      !M3Base(k6,k3v0,root0),

      !KeyMaterial(
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
          'm3',
          'n3',
          'v1',
          'e1'
      )
    ]->
  [
      !M3BranchE1(k3v1),

      !OwnsKey(
          'm3',
          'n3',
          'v1',
          k3v1
      )
  ]


/********************************************************************
 * INITIAL ACCEPTANCE — EPOCH 1
 ********************************************************************/

rule Accept_E1_M1:
  [
      !AuthorizedEpoch('m1','e1'),
      !M1Base(k4,k2v0,root0),
      !EpochRootKey('e1','v1',root1),

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
          'm1',
          'e1',
          'v1',
          root1
      ),

      AcceptCipher(
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
          'm1',
          'e1',
          'v1',
          root1
      ),

      !OwnsKey(
          'm1',
          'n1',
          'v1',
          root1
      )
  ]


rule Accept_E1_M2:
  [
      !AuthorizedEpoch('m2','e1'),
      !M2Base(k5,k2v0,root0),
      !EpochRootKey('e1','v1',root1),

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
          'm2',
          'e1',
          'v1',
          root1
      ),

      AcceptCipher(
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
          'm2',
          'e1',
          'v1',
          root1
      ),

      !OwnsKey(
          'm2',
          'n1',
          'v1',
          root1
      )
  ]


rule Accept_E1_M3:
  [
      !AuthorizedEpoch('m3','e1'),
      !M3BranchE1(k3v1),
      !EpochRootKey('e1','v1',root1),

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
          'm3',
          'e1',
          'v1',
          root1
      ),

      AcceptCipher(
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
          'm3',
          'e1',
          'v1',
          root1
      ),

      !OwnsKey(
          'm3',
          'n1',
          'v1',
          root1
      )
  ]


/********************************************************************
 * SAME-EPOCH RECOVERY — EPOCH 1
 ********************************************************************/

rule Recovery_Request_E1_M2:
  [
      !AuthorizedEpoch('m2','e1'),

      !EpochCipher(
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
          'm2',
          'e1'
      )
    ]->
  [
      Recovering(
          'm2',
          'e1'
      ),

      Out(
          <
              'recovery-request',
              'm2',
              'e1'
          >
      )
  ]


rule Recovery_Response_E1_M1:
  [
      !AuthorizedEpoch('m1','e1'),

      !Accepted(
          'm1',
          'e1',
          'v1',
          root1
      ),

      !EpochCipher(
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
              'm2',
              'e1'
          >
      )
  ]
  --[
      RecoveryResponse(
          'm1',
          'm2',
          'e1'
      )
    ]->
  [
      !RecoveryResponseCipher(
          'e1',
          cipher
      ),

      Out(cipher)
  ]


rule Recovery_Accept_E1_M2:
  [
      Recovering(
          'm2',
          'e1'
      ),

      !AuthorizedEpoch('m2','e1'),

      !M2Base(k5,k2v0,root0),

      !EpochRootKey(
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
          'm2',
          'e1',
          'v1',
          root1
      ),

      RecoveryAccept(
          'm2',
          'e1'
      ),

      RecoveryAcceptCipher(
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
          'm2',
          'e1',
          'v1',
          root1
      ),

      !OwnsKey(
          'm2',
          'n1',
          'v1',
          root1
      )
  ]


/********************************************************************
 * EPOCH 2
 *
 * Implemented plan:
 *
 *   revoke m3
 *
 *   target n1/v2 wrapper n2/v0 recipients {m1,m2}
 ********************************************************************/

rule Start_Epoch2:
  [
      Stage('s1'),

      !M1Base(k4,k2v0,root0),

      Fr(~root2)
  ]
  --[
      RekeyStarted('e2'),

      NextEpoch('e1','e2'),

      AuthorizedAt('m1','e2'),
      AuthorizedAt('m2','e2'),

      RevokedAt('m3','e2'),

      KeyVersion(
          'n1',
          'v2',
          'e2'
      ),

      EpochRoot(
          'e2',
          'v2',
          ~root2
      ),

      SecretEpoch(
          'e2',
          'v2',
          ~root2
      ),

      LkhUpdate(
          'e2',
          'n1',
          'v2',
          'n2',
          'v0'
      ),

      LkhRecipient(
          'e2',
          'n1',
          'v2',
          'm1'
      ),

      LkhRecipient(
          'e2',
          'n1',
          'v2',
          'm2'
      )
    ]->
  [
      !AuthorizedEpoch('m1','e2'),
      !AuthorizedEpoch('m2','e2'),

      !RevokedEpoch('m3','e2'),

      !EpochRootKey(
          'e2',
          'v2',
          ~root2
      ),

      !EpochCipher(
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

      !ManagerEpoch2(~root2),

      Stage('s2'),

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


/********************************************************************
 * INITIAL ACCEPTANCE — EPOCH 2
 ********************************************************************/

rule Accept_E2_M1:
  [
      !AuthorizedEpoch('m1','e2'),
      !M1Base(k4,k2v0,root0),
      !EpochRootKey('e2','v2',root2),

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
          'm1',
          'e2',
          'v2',
          root2
      ),

      AcceptCipher(
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
          'm1',
          'e2',
          'v2',
          root2
      ),

      !OwnsKey(
          'm1',
          'n1',
          'v2',
          root2
      )
  ]


rule Accept_E2_M2:
  [
      !AuthorizedEpoch('m2','e2'),
      !M2Base(k5,k2v0,root0),
      !EpochRootKey('e2','v2',root2),

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
          'm2',
          'e2',
          'v2',
          root2
      ),

      AcceptCipher(
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
          'm2',
          'e2',
          'v2',
          root2
      ),

      !OwnsKey(
          'm2',
          'n1',
          'v2',
          root2
      )
  ]


/********************************************************************
 * SAME-EPOCH RECOVERY — EPOCH 2
 ********************************************************************/

rule Recovery_Request_E2_M2:
  [
      !AuthorizedEpoch('m2','e2'),

      !EpochCipher(
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
          'm2',
          'e2'
      )
    ]->
  [
      Recovering(
          'm2',
          'e2'
      ),

      Out(
          <
              'recovery-request',
              'm2',
              'e2'
          >
      )
  ]


rule Recovery_Response_E2_M1:
  [
      !AuthorizedEpoch('m1','e2'),

      !Accepted(
          'm1',
          'e2',
          'v2',
          root2
      ),

      !EpochCipher(
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
              'm2',
              'e2'
          >
      )
  ]
  --[
      RecoveryResponse(
          'm1',
          'm2',
          'e2'
      )
    ]->
  [
      !RecoveryResponseCipher(
          'e2',
          cipher
      ),

      Out(cipher)
  ]


rule Recovery_Accept_E2_M2:
  [
      Recovering(
          'm2',
          'e2'
      ),

      !AuthorizedEpoch('m2','e2'),

      !M2Base(k5,k2v0,root0),

      !EpochRootKey(
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
          'm2',
          'e2',
          'v2',
          root2
      ),

      RecoveryAccept(
          'm2',
          'e2'
      ),

      RecoveryAcceptCipher(
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
          'm2',
          'e2',
          'v2',
          root2
      ),

      !OwnsKey(
          'm2',
          'n1',
          'v2',
          root2
      )
  ]


/********************************************************************
 * REPLAY OF OLD MATERIAL
 ********************************************************************/

rule Replay_E1_Root_Cipher_At_E2:
  [
      !EpochRootKey(
          'e2',
          'v2',
          root2
      ),

      !EpochCipher(
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
          'e2',
          'v2',
          root2
      ),

      !RecoveryResponseCipher(
          'e1',
          oldcipher
      )
  ]
  --[
      ReplayOldRecoveryResponse(
          'e1',
          'e2',
          oldcipher
      )
    ]->
  [
      Out(oldcipher)
  ]


/********************************************************************
 * EXPLICIT COMPROMISE
 ********************************************************************/

rule Compromise_M1:
  [
      !M1Base(k4,k2v0,root0)
  ]
  --[
      CompromiseMember('m1')
    ]->
  [
      Out(k4),
      Out(k2v0),
      Out(root0)
  ]


rule Compromise_M2:
  [
      !M2Base(k5,k2v0,root0)
  ]
  --[
      CompromiseMember('m2')
    ]->
  [
      Out(k5),
      Out(k2v0),
      Out(root0)
  ]


rule Compromise_M3:
  [
      !M3Base(k6,k3v0,root0)
  ]
  --[
      CompromiseMember('m3')
    ]->
  [
      Out(k6),
      Out(k3v0),
      Out(root0)
  ]


rule Compromise_M4:
  [
      !M4Base(k7,k3v0,root0)
  ]
  --[
      CompromiseMember('m4')
    ]->
  [
      Out(k7),
      Out(k3v0),
      Out(root0)
  ]


rule Compromise_GM_E1:
  [
      !ManagerEpoch1(
          k3v1,
          root1
      )
  ]
  --[
      CompromiseManager('e1')
    ]->
  [
      Out(k3v1),
      Out(root1)
  ]


rule Compromise_GM_E2:
  [
      !ManagerEpoch2(root2)
  ]
  --[
      CompromiseManager('e2')
    ]->
  [
      Out(root2)
  ]


/********************************************************************
 * REVOKED OLD-KEY EXPOSURE
 *
 * These are deliberately NOT classified as compromise exceptions
 * for the new epoch.
 ********************************************************************/

rule Leak_M4_Old_Keys_After_E1:
  [
      !RevokedEpoch('m4','e1'),

      !M4Base(
          k7,
          k3v0,
          root0
      )
  ]
  --[
      OldKeyLeak(
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
      !RevokedEpoch('m3','e2'),

      !M3Base(
          k6,
          k3v0,
          root0
      ),

      !M3BranchE1(k3v1),

      !Accepted(
          'm3',
          'e1',
          'v1',
          root1
      )
  ]
  --[
      OldKeyLeak(
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
 * NON-VACUITY
 ********************************************************************/

lemma executable_first_lkh_rekey:
  exists-trace
  "
    Ex root #i.
      RekeyStarted('e1') @ i
    & EpochRoot('e1','v1',root) @ i
  "


lemma executable_second_lkh_rekey:
  exists-trace
  "
    Ex root1 root2 #i #j.
      EpochRoot('e1','v1',root1) @ i
    & EpochRoot('e2','v2',root2) @ j
    & i < j
  "


lemma executable_same_epoch_recovery_after_lkh_rekey:
  exists-trace
  "
    Ex #q #r #a.
      RecoveryRequest('m2','e1') @ q
    & RecoveryResponse('m1','m2','e1') @ r
    & RecoveryAccept('m2','e1') @ a
    & q < r
    & r < a
  "


lemma executable_old_cipher_replay:
  exists-trace
  "
    Ex c #i #r.
      RekeyStarted('e2') @ i
    & ReplayOldCipher('e1','e2',c) @ r
    & i < r
  "


/********************************************************************
 * MULTI-EPOCH ORDERING
 ********************************************************************/

lemma second_epoch_follows_first:
  "
    All #j.
      RekeyStarted('e2') @ j
      ==>
      (Ex #i.
         RekeyStarted('e1') @ i
       & NextEpoch('e1','e2') @ j
       & i < j)
  "


/********************************************************************
 * REVOCATION
 ********************************************************************/

lemma revoked_member_excluded_from_new_epoch:
  "
    All m e v root #r #a.
      RevokedAt(m,e) @ r
    & Accept(m,e,v,root) @ a
      ==> F
  "


/********************************************************************
 * LKH UPDATE ORIGIN
 ********************************************************************/

lemma survivor_acceptance_has_lkh_update_chain:
  "
    All m e v root #a.
      Accept(m,e,v,root) @ a
      ==>
      (Ex wrapper wrapperVersion #u.
         LkhUpdate(
             e,
             'n1',
             v,
             wrapper,
             wrapperVersion
         ) @ u
       & LkhRecipient(
             e,
             'n1',
             v,
             m
         ) @ u
       & u < a)
  "


lemma m3_acceptance_requires_branch_update:
  "
    All root #a.
      Accept('m3','e1','v1',root) @ a
      ==>
      (Ex #d.
         DerivedKey(
             'm3',
             'n3',
             'v1',
             'e1'
         ) @ d
       & d < a)
  "


lemma acceptance_matches_current_root_version:
  "
    All m e v root #a.
      Accept(m,e,v,root) @ a
      ==>
      (Ex #r.
         EpochRoot(e,v,root) @ r
       & r < a)
  "


/********************************************************************
 * REPLAY / FRESHNESS
 ********************************************************************/

lemma replay_old_capsule_cannot_accept_new_epoch:
  "
    All m c #r #a.
      ReplayOldCipher('e1','e2',c) @ r
    & AcceptCipher(m,'e2',c) @ a
      ==> F
  "


lemma replay_old_recovery_response_cannot_accept_new_epoch:
  "
    All m c #r #a.
      ReplayOldRecoveryResponse(
          'e1',
          'e2',
          c
      ) @ r
    & RecoveryAcceptCipher(
          m,
          'e2',
          c
      ) @ a
      ==> F
  "


lemma root_keys_fresh_across_epochs:
  "
    All root1 root2 #i #j.
      EpochRoot(
          'e1',
          'v1',
          root1
      ) @ i
    & EpochRoot(
          'e2',
          'v2',
          root2
      ) @ j
      ==>
      not (root1 = root2)
  "


/********************************************************************
 * SECRECY + COMPROMISE TIMING
 *
 * A compromise only explains adversarial root-key knowledge if:
 *
 *   - the compromised member was authorized in that epoch, or
 *   - that epoch's manager state was compromised,
 *
 * and the compromise occurred BEFORE K(root).
 ********************************************************************/

lemma new_epoch_key_secret_without_relevant_compromise:
  "
    All e v root #s #k.
      SecretEpoch(e,v,root) @ s
    & K(root) @ k
      ==>
      (
        (Ex m #a #c.
           AuthorizedAt(m,e) @ a
         & CompromiseMember(m) @ c
         & c < k)
        |
        (Ex #c.
           CompromiseManager(e) @ c
         & c < k)
      )
  "


lemma revoked_old_key_does_not_reveal_new_root_key:
  "
    All m e v root #l #s #k.
      OldKeyLeak(m,e) @ l
    & SecretEpoch(e,v,root) @ s
    & K(root) @ k
      ==>
      (
        (Ex survivor #a #c.
           AuthorizedAt(survivor,e) @ a
         & CompromiseMember(survivor) @ c
         & c < k)
        |
        (Ex #c.
           CompromiseManager(e) @ c
         & c < k)
      )
  "


/********************************************************************
 * RECOVERY AUTHORIZATION
 ********************************************************************/

lemma recovery_requester_authorized_in_same_epoch:
  "
    All requester e #r.
      RecoveryRequest(requester,e) @ r
      ==>
      (Ex #a.
         AuthorizedAt(requester,e) @ a
       & a < r)
  "


lemma recovery_helper_authorized_in_same_epoch:
  "
    All helper requester e #r.
      RecoveryResponse(
          helper,
          requester,
          e
      ) @ r
      ==>
      (Ex #a.
         AuthorizedAt(helper,e) @ a
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
    "STEP7D2B_MODEL_GENERATION=PASS"
)
PY


# ==================================================================
# 5. Static model contract
# ==================================================================

echo
echo "===== 5. STATIC MODEL CONTRACT ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$MODEL" \
    "$OUT/model-static-audit.json" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


model = Path(sys.argv[1])
out = Path(sys.argv[2])

text = model.read_text(
    encoding="utf-8"
)


lemma_names = re.findall(
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
    "theory":
        (
            "theory RangerIoT_LKH_MultiEpoch_4Member"
            in text
        ),

    "symmetric_encryption":
        (
            "builtins: symmetric-encryption"
            in text
        ),

    "two_epoch_rules":
        (
            "rule Start_Epoch1:"
            in text
            and
            "rule Start_Epoch2:"
            in text
        ),

    "exact_epoch1_update_n3_n6":
        (
            "'n3',\n"
            "          'v1',\n"
            "          'n6',\n"
            "          'v0'"
            in text
        ),

    "exact_epoch1_root_n2":
        (
            "'n1',\n"
            "          'v1',\n"
            "          'n2',\n"
            "          'v0'"
            in text
        ),

    "exact_epoch1_root_n3":
        (
            "'n1',\n"
            "          'v1',\n"
            "          'n3',\n"
            "          'v1'"
            in text
        ),

    "exact_epoch2_root_n2":
        (
            "'n1',\n"
            "          'v2',\n"
            "          'n2',\n"
            "          'v0'"
            in text
        ),

    "revoke_m4_then_m3":
        (
            "RevokedAt('m4','e1')"
            in text
            and
            "RevokedAt('m3','e2')"
            in text
        ),

    "replay_rules":
        (
            "ReplayOldCipher("
            in text
            and
            "ReplayOldRecoveryResponse("
            in text
        ),

    "old_key_leaks":
        (
            "OldKeyLeak("
            in text
        ),

    "explicit_compromise":
        (
            "CompromiseMember("
            in text
            and
            "CompromiseManager("
            in text
        ),

    "lemma_count_16":
        len(lemma_names) == 16,

    "exact_lemma_set":
        lemma_names == expected,

    "no_sorry":
        "sorry" not in text.lower(),

    "no_admit":
        "admit" not in text.lower(),
}


for key, value in checks.items():

    print(
        f"{key:38s}",
        "PASS"
        if value
        else "FAIL",
    )


payload = {
    "schema_version":
        1,

    "model":
        model.as_posix(),

    "lemma_count":
        len(lemma_names),

    "lemmas":
        lemma_names,

    "checks":
        checks,

    "pass":
        all(checks.values()),
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


if not all(checks.values()):
    raise SystemExit(
        "STEP7D2-B static model contract failed"
    )


print()
print(
    "STEP7D2B_STATIC_MODEL_CONTRACT=PASS"
)
PY


# ==================================================================
# 6. Hash model / mapping
# ==================================================================

echo
echo "===== 6. FORMAL INPUT HASHES ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
    "$MODEL" \
    "$MAPPING" \
  > "$OUT/formal-inputs.sha256"

cat "$OUT/formal-inputs.sha256"


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
        '$MODEL'
  " \
  > "$OUT/precompute.log" \
  2>&1

PRE_RC=$?

set -e

echo "PRECOMPUTE_RC=$PRE_RC"

if [ "$PRE_RC" -ne 0 ]; then

    echo "STEP7D2B_PRECOMPUTE=FAIL"

    cat "$OUT/precompute.log"

    exit "$PRE_RC"

fi


echo "STEP7D2B_PRECOMPUTE=PASS"


# ==================================================================
# 8. Isolated proof matrix
# ==================================================================

echo
echo "===== 8. ISOLATED PROOF MATRIX ====="

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
"new_epoch_key_secret_without_relevant_compromise|all-traces|360|DFS|s"
"revoked_old_key_does_not_reveal_new_root_key|all-traces|360|DFS|s"
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
            '$MODEL' \
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
# 9. Classify exact Tamarin results
# ==================================================================

echo
echo "===== 9. CLASSIFY FORMAL RESULTS ====="

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

            "log":
                log_path.as_posix(),
        }
    )


def names(classification):
    return [
        row["lemma"]
        for row in rows
        if (
            row["classification"]
            == classification
        )
    ]


verified = names("verified")
falsified = names("falsified")
timeouts = names("timeout")
incomplete = names("incomplete")

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
        "STEP7D2B_REFERENCE_INSTANCE_"
        "ALL_16_LEMMAS_VERIFIED"
    )

elif falsified:

    state = (
        "STEP7D2B_CONFIRMED_"
        "COUNTEREXAMPLE_AUDIT_REQUIRED"
    )

elif errors:

    state = (
        "STEP7D2B_EXECUTION_ANOMALY"
    )

elif timeouts:

    state = (
        "STEP7D2B_PARTIAL_PROOF_WITH_TIMEOUTS"
    )

elif incomplete:

    state = (
        "STEP7D2B_PARTIAL_INCOMPLETE"
    )

else:

    state = (
        "STEP7D2B_UNCLASSIFIED_RESULT"
    )


payload = {
    "schema_version":
        1,

    "step":
        "STEP7D2B_LKH_MULTI_EPOCH_TAMARIN",

    "model":
        (
            "formal/tamarin/"
            "ranger_lkh_multi_epoch_4member.spthy"
        ),

    "model_class":
        (
            "EXACT_IMPLEMENTED_SYMBOLIC_LKH_"
            "FOUR_MEMBER_MULTI_EPOCH_REFERENCE_INSTANCE"
        ),

    "arbitrary_n_theorem":
        False,

    "byte_level_lkh_crypto":
        False,

    "implementation_equivalence_proof":
        False,

    "expected_lemmas":
        16,

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

    "incomplete_lemmas":
        incomplete,

    "execution_anomaly_count":
        len(errors),

    "execution_anomalies":
        errors,

    "rows":
        rows,

    "all_16_verified":
        all_16,

    "scientific_state":
        state,

    "full_ranger_formally_verified":
        False,

    "next_if_all_verified":
        (
            "STEP7D2C_GENERALIZE_"
            "LKH_MULTI_EPOCH_STRUCTURE"
        ),

    "next_if_falsified":
        (
            "STEP7D2B_COUNTEREXAMPLE_AUDIT"
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
    f"STATE={state}"
)
PY


# ==================================================================
# 10. Full CI
# ==================================================================

echo
echo "===== 10. PROJECT CI ====="

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
# 11. Final evidence package
# ==================================================================

echo
echo "===== 11. EVIDENCE PACKAGE ====="

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

    MAN=/tmp/step7d2b.sha256
    TAR=/tmp/step7d2b.tar.gz

    rm -f \
      \"\$MAN\" \
      \"\$TAR\"

    find '$OUT' \
      -type f \
      ! -name 'evidence.sha256' \
      ! -name 'evidence-verify.log' \
      ! -name 'step7d2b-evidence.tar.gz' \
      ! -name 'step7d2b-evidence.tar.gz.sha256' \
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
      '$OUT/step7d2b-evidence.tar.gz'

    sha256sum \
      '$OUT/step7d2b-evidence.tar.gz' \
      > '$OUT/step7d2b-evidence.tar.gz.sha256'

    sha256sum \
      -c \
      '$OUT/step7d2b-evidence.tar.gz.sha256'
  "


echo
echo "===================================================================="
echo "STEP 7D.2-B COMPLETE"
echo
echo "MODEL:"
echo "  $MODEL"
echo
echo "RESULT:"
echo "  $SUMMARY"
echo
echo "IMPORTANT:"
echo "  This is a four-member exact reference instance."
echo "  It is NOT yet an arbitrary-N LKH theorem."
echo
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
