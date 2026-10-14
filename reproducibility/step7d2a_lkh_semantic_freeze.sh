#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"

STEP7D1="artifacts/article-evidence/31-step7d1-recovery-witness-portfolio"
OUT="artifacts/article-evidence/32-step7d2a-lkh-semantic-freeze"

LKH="src/ranger_iot/protocols/lkh.py"
GROUP="src/ranger_iot/group.py"
STATIC="src/ranger_iot/ranger/static_protocol.py"
RECOVERY="src/ranger_iot/ranger/recovery_protocol.py"

mkdir -p "$OUT"

echo "===================================================================="
echo "RANGER-IOT — STEP 7D.2-A"
echo "IMPLEMENTED LKH SEMANTIC FREEZE"
echo
echo "PURPOSE:"
echo "  derive STEP7D2 formal semantics from implemented code"
echo
echo "IMPORTANT:"
echo "  implemented LKH = SYMBOLIC KEY/VERSION + LOGICAL UPDATE PLAN"
echo "  NOT byte-level cryptographic implementation"
echo
echo "HOST = orchestration only"
echo "SCIENTIFIC EXECUTION = Docker only"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="


# ==================================================================
# 1. STEP7D1 closure prerequisite
# ==================================================================

echo
echo "===== 1. VERIFY STEP7D1 CLOSURE ====="

test -f "$STEP7D1/step7d1w-summary.json"

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$STEP7D1/step7d1w-summary.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


path = Path(sys.argv[1])

data = json.loads(
    path.read_text(
        encoding="utf-8"
    )
)


checks = {
    "verified_11":
        data.get("verified_count") == 11,

    "all_11":
        data.get("all_11_verified") is True,

    "state":
        data.get("scientific_state")
        == "STEP7D1_V2_ALL_11_LEMMAS_VERIFIED",

    "full_ranger_not_claimed":
        data.get("full_ranger_formally_verified") is False,

    "model_not_modified":
        data.get("model_modified") is False,

    "implementation_not_modified":
        data.get("implementation_modified") is False,
}


for key, value in checks.items():

    print(
        f"{key:34s}",
        "PASS" if value else "FAIL",
    )


if not all(checks.values()):
    raise SystemExit(
        "STEP7D1 closure prerequisite failed"
    )


print()
print("STEP7D1_FORMAL_ABSTRACTION_CLOSED=PASS")
PY


# ==================================================================
# 2. Source prerequisites
# ==================================================================

echo
echo "===== 2. SOURCE PREFLIGHT ====="

for path in \
  "$LKH" \
  "$GROUP" \
  "$STATIC" \
  "$RECOVERY"
do

    test -f "$path"

    echo "PASS: $path"

done


echo
echo "===== 3. HASH IMPLEMENTED SEMANTICS ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  sha256sum \
    "$LKH" \
    "$GROUP" \
    "$STATIC" \
    "$RECOVERY" \
  > "$OUT/implemented-semantics.sha256"

cat "$OUT/implemented-semantics.sha256"

echo "IMPLEMENTED_SEMANTICS_HASHED=PASS"


# ==================================================================
# 4. AST inventory + exact source extraction
# ==================================================================

echo
echo "===== 4. EXACT LKH AST INVENTORY ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$LKH" \
    "$OUT/lkh-ast-inventory.json" \
    "$OUT/lkh-rekey-exact-source.py.txt" <<'PY'
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


source_path = Path(sys.argv[1])
inventory_path = Path(sys.argv[2])
rekey_path = Path(sys.argv[3])


source = source_path.read_text(
    encoding="utf-8"
)

tree = ast.parse(source)


classes = {}
rekey_node = None


for node in tree.body:

    if not isinstance(
        node,
        ast.ClassDef,
    ):
        continue

    methods = {}

    for child in node.body:

        if isinstance(
            child,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):

            methods[
                child.name
            ] = {
                "lineno":
                    child.lineno,

                "end_lineno":
                    child.end_lineno,

                "args":
                    [
                        arg.arg
                        for arg
                        in child.args.args
                    ]
                    +
                    [
                        arg.arg
                        for arg
                        in child.args.kwonlyargs
                    ],
            }

            if (
                node.name == "LkhKeyTree"
                and
                child.name == "rekey"
            ):
                rekey_node = child


    classes[
        node.name
    ] = {
        "lineno":
            node.lineno,

        "end_lineno":
            node.end_lineno,

        "docstring":
            ast.get_docstring(node),

        "methods":
            methods,
    }


required_classes = {
    "LkhKeyRef",
    "LkhKeyUpdate",
    "LkhRekeyPlan",
    "LkhKeyTree",
}


missing = sorted(
    required_classes
    - set(classes)
)


if missing:

    raise SystemExit(
        "Missing expected LKH classes: "
        + repr(missing)
    )


if rekey_node is None:

    raise SystemExit(
        "LkhKeyTree.rekey not found"
    )


lines = source.splitlines()


exact_rekey = "\n".join(
    lines[
        rekey_node.lineno - 1:
        rekey_node.end_lineno
    ]
)


rekey_path.write_text(
    exact_rekey
    + "\n",
    encoding="utf-8",
)


payload = {
    "schema_version":
        1,

    "source":
        source_path.as_posix(),

    "classes":
        classes,

    "required_classes_present":
        True,

    "rekey_method_present":
        True,

    "rekey_lineno":
        rekey_node.lineno,

    "rekey_end_lineno":
        rekey_node.end_lineno,

    "symbolic_key_version_model":
        (
            "symbolic key versions"
            in (
                classes[
                    "LkhKeyTree"
                ][
                    "docstring"
                ]
                or ""
            ).lower()
        ),

    "bottom_up_plan_documented":
        (
            "bottom-up"
            in (
                classes[
                    "LkhRekeyPlan"
                ][
                    "docstring"
                ]
                or ""
            ).lower()
        ),
}


inventory_path.write_text(
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


print()
print(
    "LKH_AST_INVENTORY=PASS"
)
PY


# ==================================================================
# 5. Existing exact LKH tests
# ==================================================================

echo
echo "===== 5. EXISTING LKH TEST SUITE ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  bash -lc '
    set -euo pipefail

    cd /workspace

    TESTS=()

    for candidate in \
      tests/protocols/test_lkh.py \
      tests/protocols/test_lkh_flood.py \
      tests/protocols/test_lkh_transport.py
    do

        if [ -f "$candidate" ]; then
            TESTS+=("$candidate")
        fi

    done

    if [ "${#TESTS[@]}" -eq 0 ]; then
        echo "ERROR: no LKH tests found"
        exit 1
    fi

    printf "LKH_TEST_FILES:\n"

    printf "  %s\n" "${TESTS[@]}"

    python -m pytest \
      -q \
      "${TESTS[@]}"
  ' \
  2>&1 \
  | tee "$OUT/lkh-tests.log"


LKH_TEST_RC=${PIPESTATUS[0]}

echo "LKH_TEST_RC=$LKH_TEST_RC"

if [ "$LKH_TEST_RC" -ne 0 ]; then
    exit "$LKH_TEST_RC"
fi

echo "IMPLEMENTED_LKH_TESTS=PASS"


# ==================================================================
# 6. Deterministic semantic probe
# ==================================================================

echo
echo "===== 6. EXECUTE IMPLEMENTED LKH SEMANTICS ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$OUT/lkh-semantic-probe.json" <<'PY'
from __future__ import annotations

import json
import sys

from dataclasses import (
    asdict,
    fields,
    is_dataclass,
)

from pathlib import Path

from ranger_iot.protocols.lkh import (
    LkhKeyTree,
)


out = Path(sys.argv[1])


def normalize(value):
    if is_dataclass(value):
        return normalize(
            asdict(value)
        )

    if isinstance(value, dict):
        return {
            str(key):
                normalize(item)
            for key, item
            in sorted(
                value.items(),
                key=lambda pair:
                    str(pair[0]),
            )
        }

    if isinstance(
        value,
        (
            list,
            tuple,
        ),
    ):
        return [
            normalize(item)
            for item in value
        ]

    if isinstance(value, set):
        return sorted(
            normalize(item)
            for item in value
        )

    return value


def update_schema(plan):
    updates = getattr(
        plan,
        "updates",
        (),
    )

    if not updates:
        return []

    first = updates[0]

    if is_dataclass(first):
        return [
            field.name
            for field
            in fields(first)
        ]

    return sorted(
        vars(first)
    )


def snapshot(tree: LkhKeyTree):
    members = list(
        tree.member_ids
    )

    active = list(
        tree.active_member_ids
    )

    return {
        "member_ids":
            members,

        "active_member_ids":
            active,

        "leaf_base":
            tree.leaf_base,

        "root_key":
            normalize(
                tree.root_key
            ),

        "leaf_nodes": {
            str(member):
                tree.leaf_node(
                    member
                )
            for member in members
        },

        "member_key_paths": {
            str(member):
                list(
                    tree.member_key_path(
                        member
                    )
                )
            for member in members
        },
    }


def plan_snapshot(plan):
    data = normalize(plan)

    data[
        "logical_ciphertexts"
    ] = getattr(
        plan,
        "logical_ciphertexts",
        None,
    )

    data[
        "update_schema"
    ] = update_schema(
        plan
    )

    return data


def sequential_case(
    members,
    revocations,
):
    tree = LkhKeyTree(
        set(members)
    )

    result = {
        "initial":
            snapshot(tree),

        "steps":
            [],
    }

    previously_revoked = set()

    for number, revoked in enumerate(
        revocations,
        start=1,
    ):

        revoked = set(revoked)

        before = snapshot(tree)

        plan = tree.rekey(
            revoked
        )

        previously_revoked |= revoked

        after = snapshot(tree)

        active_expected = sorted(
            set(members)
            - previously_revoked
        )

        if (
            after[
                "active_member_ids"
            ]
            != active_expected
        ):
            raise AssertionError(
                (
                    "Active-member evolution mismatch: "
                    f"expected={active_expected} "
                    f"actual="
                    f"{after['active_member_ids']}"
                )
            )

        result[
            "steps"
        ].append(
            {
                "step":
                    number,

                "revoked_now":
                    sorted(revoked),

                "revoked_cumulative":
                    sorted(
                        previously_revoked
                    ),

                "before":
                    before,

                "plan":
                    plan_snapshot(
                        plan
                    ),

                "after":
                    after,
            }
        )

    return result


cases = {
    "four_members_revoke_4_then_3":
        sequential_case(
            [1, 2, 3, 4],
            [
                {4},
                {3},
            ],
        ),

    "four_members_revoke_2_and_4":
        sequential_case(
            [1, 2, 3, 4],
            [
                {2, 4},
            ],
        ),

    "four_members_no_revocation":
        sequential_case(
            [1, 2, 3, 4],
            [
                set(),
            ],
        ),

    "five_members_revoke_5":
        sequential_case(
            [1, 2, 3, 4, 5],
            [
                {5},
            ],
        ),
}


payload = {
    "schema_version":
        1,

    "execution":
        "inside Docker ranger image",

    "semantics":
        "implemented LkhKeyTree",

    "cases":
        cases,
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


print()
print(
    "IMPLEMENTED_LKH_SEMANTIC_PROBE=PASS"
)
PY


# ==================================================================
# 7. Analyze concrete implementation semantics
# ==================================================================

echo
echo "===== 7. DERIVE IMPLEMENTATION FACTS ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$OUT/lkh-ast-inventory.json" \
    "$OUT/lkh-semantic-probe.json" \
    "$LKH" \
    "$STATIC" \
    "$OUT/lkh-derived-semantics.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


ast_path = Path(sys.argv[1])
probe_path = Path(sys.argv[2])
lkh_path = Path(sys.argv[3])
static_path = Path(sys.argv[4])
out_path = Path(sys.argv[5])


inventory = json.loads(
    ast_path.read_text(
        encoding="utf-8"
    )
)

probe = json.loads(
    probe_path.read_text(
        encoding="utf-8"
    )
)

lkh_source = lkh_path.read_text(
    encoding="utf-8"
)

static_source = static_path.read_text(
    encoding="utf-8"
)


seq = probe[
    "cases"
][
    "four_members_revoke_4_then_3"
]


versions = [
    step[
        "after"
    ][
        "root_key"
    ][
        "version"
    ]
    for step
    in seq[
        "steps"
    ]
]


logical_counts = [
    step[
        "plan"
    ][
        "logical_ciphertexts"
    ]
    for step
    in seq[
        "steps"
    ]
]


update_schemas = sorted(
    {
        tuple(
            step[
                "plan"
            ][
                "update_schema"
            ]
        )
        for case
        in probe[
            "cases"
        ].values()
        for step
        in case[
            "steps"
        ]
        if step[
            "plan"
        ][
            "update_schema"
        ]
    }
)


facts = {
    "schema_version":
        1,

    "scope_name":
        "IMPLEMENTED_SYMBOLIC_LKH_PLAN_SEMANTICS",

    "not_claimed":
        [
            (
                "byte-level LKH encryption "
                "implementation"
            ),
            (
                "computational cryptographic "
                "security proof"
            ),
            (
                "equivalence between Tamarin "
                "and Python implementation"
            ),
        ],

    "code_facts": {
        "symbolic_key_versions":
            inventory[
                "symbolic_key_version_model"
            ],

        "bottom_up_rekey_plan":
            inventory[
                "bottom_up_plan_documented"
            ],

        "has_LkhKeyRef":
            "class LkhKeyRef"
            in lkh_source,

        "has_LkhKeyUpdate":
            "class LkhKeyUpdate"
            in lkh_source,

        "has_LkhRekeyPlan":
            "class LkhRekeyPlan"
            in lkh_source,

        "has_rekey_method":
            "def rekey("
            in lkh_source,

        "ranger_consumes_tree_rekey":
            (
                "plan = self._tree.rekey("
                in static_source
            ),

        "ranger_checks_epoch_root_version":
            (
                "epoch != plan.root_key.version"
                in static_source
            ),

        "ranger_targets_current_authorized_members":
            (
                "targets = self._group.authorized_member_ids"
                in static_source
            ),
    },

    "observed_execution": {
        "sequential_root_versions":
            versions,

        "sequential_logical_ciphertexts":
            logical_counts,

        "observed_update_schemas":
            [
                list(schema)
                for schema
                in update_schemas
            ],

        "sequential_revocation_case":
            "4 then 3",

        "final_active_members":
            seq[
                "steps"
            ][-1][
                "after"
            ][
                "active_member_ids"
            ],
    },
}


checks = {
    "symbolic_versions":
        facts[
            "code_facts"
        ][
            "symbolic_key_versions"
        ],

    "bottom_up":
        facts[
            "code_facts"
        ][
            "bottom_up_rekey_plan"
        ],

    "key_ref":
        facts[
            "code_facts"
        ][
            "has_LkhKeyRef"
        ],

    "key_update":
        facts[
            "code_facts"
        ][
            "has_LkhKeyUpdate"
        ],

    "rekey_plan":
        facts[
            "code_facts"
        ][
            "has_LkhRekeyPlan"
        ],

    "rekey_method":
        facts[
            "code_facts"
        ][
            "has_rekey_method"
        ],

    "ranger_consumes_lkh":
        facts[
            "code_facts"
        ][
            "ranger_consumes_tree_rekey"
        ],

    "epoch_alignment_check":
        facts[
            "code_facts"
        ][
            "ranger_checks_epoch_root_version"
        ],

    "authorized_targets":
        facts[
            "code_facts"
        ][
            "ranger_targets_current_authorized_members"
        ],
}


facts[
    "semantic_contract_pass"
] = all(
    checks.values()
)


out_path.write_text(
    json.dumps(
        facts,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


for key, value in checks.items():

    print(
        f"{key:34s}",
        "PASS"
        if value
        else "FAIL",
    )


print()
print(
    "ROOT_VERSIONS="
    + repr(versions)
)

print(
    "LOGICAL_CIPHERTEXT_COUNTS="
    + repr(logical_counts)
)

print(
    "UPDATE_SCHEMAS="
    + repr(update_schemas)
)


if not all(
    checks.values()
):
    raise SystemExit(
        "Implemented-LKH semantic contract failed"
    )


print()
print(
    "IMPLEMENTED_LKH_SEMANTIC_CONTRACT=PASS"
)
PY


# ==================================================================
# 8. Generate exact 7D2 formalization blueprint
# ==================================================================

echo
echo "===== 8. GENERATE STEP7D2 FORMALIZATION BLUEPRINT ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$OUT/lkh-derived-semantics.json" \
    "$OUT/step7d2-formalization-blueprint.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


semantics_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])


semantics = json.loads(
    semantics_path.read_text(
        encoding="utf-8"
    )
)


if not semantics.get(
    "semantic_contract_pass"
):

    raise SystemExit(
        "Cannot produce formalization blueprint "
        "from failed semantic contract"
    )


payload = {
    "schema_version":
        1,

    "step":
        "STEP7D2_FORMALIZATION_BLUEPRINT",

    "source_semantics":
        "IMPLEMENTED_SYMBOLIC_LKH_PLAN_SEMANTICS",

    "formal_model_target":
        (
            "EXACT_IMPLEMENTED_SYMBOLIC_LKH_"
            "MULTI_EPOCH_ABSTRACTION"
        ),

    "explicit_scope": [
        (
            "balanced LKH tree structure "
            "used by LkhKeyTree"
        ),
        (
            "LkhKeyRef node/version state"
        ),
        (
            "LkhKeyUpdate target/wrapper "
            "logical ciphertext relation"
        ),
        (
            "deterministic bottom-up "
            "rekey-plan evolution"
        ),
        (
            "active-member removal"
        ),
        (
            "root-key version / RANGER "
            "epoch alignment"
        ),
        (
            "at least two sequential epochs"
        ),
        (
            "same-epoch recovery binding"
        ),
        (
            "old-capsule replay into a "
            "newer epoch"
        ),
        (
            "explicit compromise timing"
        ),
    ],

    "explicit_non_scope": [
        (
            "byte-level implementation of "
            "LKH encryption"
        ),
        (
            "Reed-Solomon algebra"
        ),
        (
            "wireless packet loss/liveness"
        ),
        (
            "computational cryptography"
        ),
        (
            "automatic implementation "
            "equivalence theorem"
        ),
    ],

    "required_state_relations": [
        "MemberLeaf(member,leaf)",
        "Parent(child,parent)",
        "OwnsKey(member,node,version)",
        "Active(member,epoch)",
        "Revoked(member,epoch)",
        "KeyVersion(node,version,epoch)",
        "LkhUpdate(target,newVersion,wrapper,wrapperVersion,epoch)",
        "EpochRoot(epoch,rootVersion,groupKey)",
        "NextEpoch(epoch1,epoch2)",
        "Accepted(member,epoch)",
        "CompromiseMember(member,time)",
        "CompromiseManager(manager,time)",
    ],

    "minimum_nonvacuity_lemmas": [
        "executable_first_lkh_rekey",
        "executable_second_lkh_rekey",
        "executable_same_epoch_recovery_after_lkh_rekey",
    ],

    "security_lemmas": [
        "revoked_member_excluded_from_new_epoch",
        "survivor_acceptance_has_lkh_update_chain",
        "acceptance_matches_current_root_version",
        "replay_old_capsule_cannot_accept_new_epoch",
        "replay_old_recovery_response_cannot_accept_new_epoch",
        "revoked_old_key_does_not_reveal_new_root_key",
        "new_epoch_key_secret_without_relevant_compromise",
        "post_knowledge_compromise_does_not_explain_prior_knowledge",
        "recovery_requester_authorized_in_same_epoch",
        "recovery_helper_authorized_in_same_epoch",
    ],

    "multi_epoch_minimum":
        2,

    "counterexample_policy":
        (
            "Any falsified lemma must be preserved "
            "and audited before model modification."
        ),

    "proof_policy": {
        "docker_only":
            True,

        "network_during_proof":
            "none",

        "tamarin_version":
            "1.12.0",

        "separate_lemma_proofs":
            True,

        "exists_trace_portfolio":
            [
                "BFS",
                "DFS",
                "SEQDFS",
                "heuristic C",
            ],
    },

    "claim_if_future_passes":
        (
            "The formal model captures the implemented "
            "symbolic LKH key-version/update-plan semantics "
            "across sequential epochs and satisfies the "
            "specified authorization, replay, freshness, "
            "and compromise-timing properties under its "
            "explicit symbolic assumptions."
        ),

    "forbidden_claims": [
        (
            "RANGER-IoT is fully formally verified."
        ),
        (
            "The deployed cryptographic LKH "
            "implementation is byte-for-byte verified."
        ),
        (
            "Tamarin is formally equivalent to "
            "the Python/C/Cooja implementation."
        ),
        (
            "Formal safety proves lossy-network liveness."
        ),
    ],
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


print(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
)


print()
print(
    "STEP7D2_FORMALIZATION_BLUEPRINT=PASS"
)
PY


# ==================================================================
# 9. Full project CI
# ==================================================================

echo
echo "===== 9. PROJECT CI ====="

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
# 10. Final readiness classification
# ==================================================================

echo
echo "===== 10. STEP7D2-A READINESS ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$OUT/lkh-derived-semantics.json" \
    "$OUT/step7d2-formalization-blueprint.json" \
    "$OUT/step7d2a-readiness.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


semantics = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

blueprint = json.loads(
    Path(sys.argv[2]).read_text(
        encoding="utf-8"
    )
)

out = Path(sys.argv[3])


ready = (
    semantics.get(
        "semantic_contract_pass"
    )
    is True
    and
    blueprint.get(
        "multi_epoch_minimum"
    )
    == 2
)


payload = {
    "schema_version":
        1,

    "step":
        "STEP7D2A_IMPLEMENTED_LKH_SEMANTIC_FREEZE",

    "scientific_state":
        (
            "IMPLEMENTED_SYMBOLIC_LKH_"
            "SEMANTICS_FROZEN_FOR_FORMALIZATION"
            if ready
            else
            "STEP7D2A_NOT_READY"
        ),

    "step7d1_closed":
        True,

    "step7d2a_pass":
        ready,

    "implemented_lkh_scope":
        (
            "symbolic key/version and "
            "logical update-plan semantics"
        ),

    "byte_level_lkh_crypto_claim":
        False,

    "ready_for_step7d2_tamarin_model":
        ready,

    "next_step":
        (
            "STEP7D2B_BUILD_MULTI_EPOCH_"
            "IMPLEMENTED_LKH_TAMARIN_MODEL"
            if ready
            else
            "STEP7D2A_REVIEW_FAILURE"
        ),

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
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
)


if not ready:
    raise SystemExit(1)
PY


# ==================================================================
# 11. Evidence package
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

    MAN=/tmp/step7d2a.sha256
    TAR=/tmp/step7d2a.tar.gz

    rm -f \
      \"\$MAN\" \
      \"\$TAR\"

    find '$OUT' \
      -type f \
      ! -name 'evidence.sha256' \
      ! -name 'evidence-verify.log' \
      ! -name 'step7d2a-evidence.tar.gz' \
      ! -name 'step7d2a-evidence.tar.gz.sha256' \
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
      '$LKH' \
      '$GROUP' \
      '$STATIC' \
      '$RECOVERY'

    tar \
      -tzf \
      \"\$TAR\" \
      >/dev/null

    cp \
      \"\$TAR\" \
      '$OUT/step7d2a-evidence.tar.gz'

    sha256sum \
      '$OUT/step7d2a-evidence.tar.gz' \
      > '$OUT/step7d2a-evidence.tar.gz.sha256'

    sha256sum \
      -c \
      '$OUT/step7d2a-evidence.tar.gz.sha256'
  "


echo
echo "===================================================================="
echo "STEP 7D.2-A COMPLETE"
echo
echo "READINESS:"
echo "  $OUT/step7d2a-readiness.json"
echo
echo "BLUEPRINT:"
echo "  $OUT/step7d2-formalization-blueprint.json"
echo
echo "SEMANTIC PROBE:"
echo "  $OUT/lkh-semantic-probe.json"
echo
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
