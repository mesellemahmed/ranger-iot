#!/usr/bin/env bash
set -euo pipefail

ROOT_COMPOSE="docker-compose.yml"

FORMAL_PREV="artifacts/article-evidence/37-step7d2b-temporal-security-contract"
STEP7D2A="artifacts/article-evidence/32-step7d2a-lkh-semantic-freeze"

OUT="artifacts/article-evidence/38-step7d2ca-structural-lkh-generalization"

LKH="src/ranger_iot/protocols/lkh.py"

mkdir -p "$OUT"

echo "===================================================================="
echo "RANGER-IOT — STEP 7D.2-C-A"
echo "EXHAUSTIVE STRUCTURAL LKH GENERALIZATION"
echo
echo "SCOPE:"
echo "  exact implemented LkhKeyTree"
echo "  N = 4,5,7,8,9,16,17,32,33,64"
echo "  all single revocations"
echo "  all ordered two-epoch revocation sequences"
echo "  all simultaneous two-member revocations"
echo "  individual revoked-state closure"
echo "  revoked-coalition closure"
echo "  historical-key-retention boundary"
echo
echo "IMPORTANT:"
echo "  finite exhaustive implementation-derived validation"
echo "  NOT an arbitrary-N theorem"
echo
echo "IMPLEMENTATION CHANGE = NONE"
echo "FORMAL MODEL CHANGE   = NONE"
echo "NO COMMIT / NO PUSH"
echo "===================================================================="


# ==================================================================
# 1. Formal prerequisite
# ==================================================================

echo
echo "===== 1. STEP7D2-B FORMAL CLOSURE PREREQUISITE ====="

test -f "$FORMAL_PREV/final-state.json"
test -f "$FORMAL_PREV/proof-matrix-temporal-security.json"

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$FORMAL_PREV/final-state.json" \
    "$FORMAL_PREV/proof-matrix-temporal-security.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


state = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

proof = json.loads(
    Path(sys.argv[2]).read_text(
        encoding="utf-8"
    )
)


checks = {
    "reference_instance_closed":
        state.get(
            "reference_instance_closed"
        )
        is True,

    "all_17_verified":
        state.get(
            "all_17_verified"
        )
        is True,

    "negative_control":
        state.get(
            "negative_control_pass"
        )
        is True,

    "boundary_demonstrated":
        state.get(
            "historical_key_exposure_boundary_demonstrated"
        )
        is True,

    "not_arbitrary_n":
        state.get(
            "arbitrary_n_generalization"
        )
        is False,

    "proof_verified_17":
        proof.get(
            "verified_count"
        )
        == 17,

    "proof_falsified_0":
        proof.get(
            "falsified_count"
        )
        == 0,

    "proof_timeout_0":
        proof.get(
            "timeout_count"
        )
        == 0,
}


for key, passed in checks.items():

    print(
        f"{key:38s}",
        "PASS"
        if passed
        else "FAIL",
    )


if not all(checks.values()):

    raise SystemExit(
        "STEP7D2-B formal prerequisite failed"
    )


print()
print(
    "STEP7D2B_FORMAL_REFERENCE_CLOSED=PASS"
)
PY


# ==================================================================
# 2. Implementation freeze
# ==================================================================

echo
echo "===== 2. IMPLEMENTATION FREEZE ====="

test -f "$STEP7D2A/implemented-semantics.sha256"

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
# 3. Run exhaustive structural audit
# ==================================================================

echo
echo "===== 3. EXHAUSTIVE IMPLEMENTED-LKH CLOSURE AUDIT ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$OUT/structural-cases.csv" \
    "$OUT/structural-summary.json" \
    "$OUT/structural-failures.json" <<'PY'
from __future__ import annotations

import csv
import json
import sys

from dataclasses import dataclass
from itertools import combinations, permutations
from pathlib import Path

from ranger_iot.protocols.lkh import LkhKeyTree


csv_path = Path(sys.argv[1])
summary_path = Path(sys.argv[2])
failure_path = Path(sys.argv[3])


GROUP_SIZES = [
    4,
    5,
    7,
    8,
    9,
    16,
    17,
    32,
    33,
    64,
]


KeyRef = tuple[int, int]


@dataclass(frozen=True)
class Update:
    target: KeyRef
    wrapper: KeyRef
    recipients: tuple[int, ...]


def ref_tuple(ref) -> KeyRef:
    return (
        int(ref.node_id),
        int(ref.version),
    )


def closure(
    initial: set[KeyRef],
    updates: list[Update],
) -> set[KeyRef]:
    known = set(initial)

    changed = True

    while changed:
        changed = False

        for update in updates:
            if (
                update.wrapper in known
                and
                update.target not in known
            ):
                known.add(
                    update.target
                )
                changed = True

    return known


def plan_updates(plan) -> list[Update]:
    return [
        Update(
            target=ref_tuple(
                update.target
            ),
            wrapper=ref_tuple(
                update.wrapper
            ),
            recipients=tuple(
                sorted(
                    int(member)
                    for member
                    in update.recipients
                )
            ),
        )
        for update
        in plan.updates
    ]


def initial_knowledge(
    tree: LkhKeyTree,
    members: list[int],
) -> dict[int, set[KeyRef]]:
    result = {}

    for member in members:
        path = tuple(
            int(node)
            for node
            in tree.member_key_path(
                member
            )
        )

        result[member] = {
            (
                node,
                0,
            )
            for node
            in path
        }

    return result


def audit_sequence(
    n: int,
    revocation_steps: list[set[int]],
    case_kind: str,
    case_id: str,
):
    members = list(
        range(
            1,
            n + 1,
        )
    )

    tree = LkhKeyTree(
        set(members)
    )

    knowledge = initial_knowledge(
        tree,
        members,
    )

    revoked_cumulative: set[int] = set()

    epoch_records = []

    failures = []

    historical_previous_root = None

    historical_second_revoked_retained_previous = None


    for epoch, revoke_now in enumerate(
        revocation_steps,
        start=1,
    ):
        active_before = set(
            tree.active_member_ids
        )

        revoke_now = set(
            revoke_now
        )


        if not revoke_now:
            failures.append(
                {
                    "type":
                        "EMPTY_REVOCATION_SET",

                    "epoch":
                        epoch,
                }
            )

            break


        if not revoke_now <= active_before:
            failures.append(
                {
                    "type":
                        "REVOKE_NON_ACTIVE_MEMBER",

                    "epoch":
                        epoch,

                    "revoked":
                        sorted(
                            revoke_now
                        ),

                    "active_before":
                        sorted(
                            active_before
                        ),
                }
            )

            break


        pre_knowledge = {
            member:
                set(keys)
            for member, keys
            in knowledge.items()
        }


        previous_root = (
            ref_tuple(
                tree.root_key
            )
        )


        plan = tree.rekey(
            revoke_now
        )


        active_after = set(
            tree.active_member_ids
        )


        expected_active = (
            active_before
            - revoke_now
        )


        revoked_cumulative |= (
            revoke_now
        )


        updates = plan_updates(
            plan
        )


        root = ref_tuple(
            plan.root_key
        )


        # ----------------------------------------------------------
        # Every participant sees every ciphertext.
        #
        # Cryptographic derivability is therefore determined only
        # by possession of wrapper keys, not by recipients metadata.
        # ----------------------------------------------------------

        for member in members:
            knowledge[
                member
            ] = closure(
                pre_knowledge[
                    member
                ],
                updates,
            )


        # ----------------------------------------------------------
        # Coalition closure.
        #
        # Union all knowledge held by every revoked member and then
        # close it again under all public ciphertexts.
        # ----------------------------------------------------------

        revoked_union: set[KeyRef] = set()

        for member in revoked_cumulative:
            revoked_union |= (
                knowledge[
                    member
                ]
            )


        revoked_coalition = closure(
            revoked_union,
            updates,
        )


        # ----------------------------------------------------------
        # Structural checks
        # ----------------------------------------------------------

        checks = {
            "active_set_exact":
                active_after
                == expected_active,

            "root_matches_tree":
                ref_tuple(
                    tree.root_key
                )
                == root,

            "root_version_matches_epoch":
                root[1]
                == epoch,

            "logical_ciphertexts_match_updates":
                int(
                    plan.logical_ciphertexts
                )
                == len(
                    updates
                ),

            "all_recipients_currently_authorized":
                all(
                    set(
                        update.recipients
                    )
                    <= active_after
                    for update
                    in updates
                ),

            "no_revoked_recipient":
                all(
                    not (
                        set(
                            update.recipients
                        )
                        &
                        revoked_cumulative
                    )
                    for update
                    in updates
                ),

            "all_survivors_derive_root":
                all(
                    root
                    in knowledge[
                        member
                    ]
                    for member
                    in active_after
                ),

            "no_revoked_member_derives_root":
                all(
                    root
                    not in knowledge[
                        member
                    ]
                    for member
                    in revoked_cumulative
                ),

            "revoked_coalition_cannot_derive_root":
                root
                not in revoked_coalition,

            "root_is_fresh":
                root
                != previous_root,
        }


        failed_checks = [
            name
            for name, passed
            in checks.items()
            if not passed
        ]


        if failed_checks:
            failures.append(
                {
                    "type":
                        "STRUCTURAL_SECURITY_FAILURE",

                    "epoch":
                        epoch,

                    "failed_checks":
                        failed_checks,

                    "revoked_now":
                        sorted(
                            revoke_now
                        ),

                    "revoked_cumulative":
                        sorted(
                            revoked_cumulative
                        ),

                    "active_after":
                        sorted(
                            active_after
                        ),

                    "root":
                        list(
                            root
                        ),

                    "previous_root":
                        list(
                            previous_root
                        ),

                    "updates":
                        [
                            {
                                "target":
                                    list(
                                        update.target
                                    ),

                                "wrapper":
                                    list(
                                        update.wrapper
                                    ),

                                "recipients":
                                    list(
                                        update.recipients
                                    ),
                            }
                            for update
                            in updates
                        ],
                }
            )


        if (
            epoch == 2
            and
            len(
                revoke_now
            )
            == 1
        ):
            second_revoked = next(
                iter(
                    revoke_now
                )
            )

            historical_second_revoked_retained_previous = (
                historical_previous_root
                is not None
                and
                historical_previous_root
                in pre_knowledge[
                    second_revoked
                ]
            )


        epoch_records.append(
            {
                "epoch":
                    epoch,

                "revoked_now":
                    sorted(
                        revoke_now
                    ),

                "revoked_cumulative":
                    sorted(
                        revoked_cumulative
                    ),

                "active_count":
                    len(
                        active_after
                    ),

                "root_node":
                    root[0],

                "root_version":
                    root[1],

                "logical_ciphertexts":
                    int(
                        plan.logical_ciphertexts
                    ),

                "update_count":
                    len(
                        updates
                    ),

                "revoked_coalition_key_count":
                    len(
                        revoked_coalition
                    ),

                "all_checks_pass":
                    all(
                        checks.values()
                    ),

                "checks":
                    checks,
            }
        )


        historical_previous_root = root


    return {
        "case_id":
            case_id,

        "case_kind":
            case_kind,

        "n":
            n,

        "steps":
            [
                sorted(
                    step
                )
                for step
                in revocation_steps
            ],

        "epoch_records":
            epoch_records,

        "historical_second_revoked_retained_previous_root":
            historical_second_revoked_retained_previous,

        "pass":
            not failures,

        "failures":
            failures,
    }


cases = []


# ==================================================================
# Singles
# ==================================================================

for n in GROUP_SIZES:
    for revoked in range(
        1,
        n + 1,
    ):
        cases.append(
            audit_sequence(
                n=n,
                revocation_steps=[
                    {revoked},
                ],
                case_kind="single",
                case_id=(
                    f"n{n:03d}"
                    f"__single"
                    f"__r{revoked:03d}"
                ),
            )
        )


# ==================================================================
# Ordered sequential pairs
# ==================================================================

for n in GROUP_SIZES:
    members = range(
        1,
        n + 1,
    )

    for first, second in permutations(
        members,
        2,
    ):
        cases.append(
            audit_sequence(
                n=n,
                revocation_steps=[
                    {first},
                    {second},
                ],
                case_kind="sequential_pair",
                case_id=(
                    f"n{n:03d}"
                    f"__seq"
                    f"__r{first:03d}"
                    f"__r{second:03d}"
                ),
            )
        )


# ==================================================================
# Simultaneous pairs
# ==================================================================

for n in GROUP_SIZES:
    members = range(
        1,
        n + 1,
    )

    for first, second in combinations(
        members,
        2,
    ):
        cases.append(
            audit_sequence(
                n=n,
                revocation_steps=[
                    {
                        first,
                        second,
                    },
                ],
                case_kind="simultaneous_pair",
                case_id=(
                    f"n{n:03d}"
                    f"__sim"
                    f"__r{first:03d}"
                    f"__r{second:03d}"
                ),
            )
        )


# ==================================================================
# Aggregate
# ==================================================================

failures = [
    case
    for case
    in cases
    if not case[
        "pass"
    ]
]


single_cases = [
    case
    for case
    in cases
    if case[
        "case_kind"
    ]
    == "single"
]


sequential_cases = [
    case
    for case
    in cases
    if case[
        "case_kind"
    ]
    == "sequential_pair"
]


simultaneous_cases = [
    case
    for case
    in cases
    if case[
        "case_kind"
    ]
    == "simultaneous_pair"
]


historical_boundary_cases = [
    case
    for case
    in sequential_cases
    if case[
        "historical_second_revoked_retained_previous_root"
    ]
    is True
]


total_epochs = sum(
    len(
        case[
            "epoch_records"
        ]
    )
    for case
    in cases
)


rows = []


for case in cases:
    for epoch_record in case[
        "epoch_records"
    ]:
        rows.append(
            {
                "case_id":
                    case[
                        "case_id"
                    ],

                "case_kind":
                    case[
                        "case_kind"
                    ],

                "n":
                    case[
                        "n"
                    ],

                "epoch":
                    epoch_record[
                        "epoch"
                    ],

                "revoked_now":
                    ",".join(
                        str(value)
                        for value
                        in epoch_record[
                            "revoked_now"
                        ]
                    ),

                "revoked_cumulative":
                    ",".join(
                        str(value)
                        for value
                        in epoch_record[
                            "revoked_cumulative"
                        ]
                    ),

                "active_count":
                    epoch_record[
                        "active_count"
                    ],

                "root_node":
                    epoch_record[
                        "root_node"
                    ],

                "root_version":
                    epoch_record[
                        "root_version"
                    ],

                "logical_ciphertexts":
                    epoch_record[
                        "logical_ciphertexts"
                    ],

                "update_count":
                    epoch_record[
                        "update_count"
                    ],

                "revoked_coalition_key_count":
                    epoch_record[
                        "revoked_coalition_key_count"
                    ],

                "all_checks_pass":
                    epoch_record[
                        "all_checks_pass"
                    ],
            }
        )


with csv_path.open(
    "w",
    encoding="utf-8",
    newline="",
) as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=list(
            rows[0]
        ),
    )

    writer.writeheader()

    writer.writerows(
        rows
    )


failure_path.write_text(
    json.dumps(
        failures,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


expected_single = sum(
    GROUP_SIZES
)


expected_sequential = sum(
    n * (
        n - 1
    )
    for n
    in GROUP_SIZES
)


expected_simultaneous = sum(
    (
        n
        * (
            n - 1
        )
        // 2
    )
    for n
    in GROUP_SIZES
)


checks = {
    "single_case_count":
        len(
            single_cases
        )
        == expected_single,

    "sequential_case_count":
        len(
            sequential_cases
        )
        == expected_sequential,

    "simultaneous_case_count":
        len(
            simultaneous_cases
        )
        == expected_simultaneous,

    "zero_failures":
        len(
            failures
        )
        == 0,

    "all_second_revoked_members_retained_previous_root":
        len(
            historical_boundary_cases
        )
        ==
        len(
            sequential_cases
        ),
}


summary = {
    "schema_version":
        1,

    "step":
        (
            "STEP7D2CA_STRUCTURAL_"
            "LKH_GENERALIZATION"
        ),

    "group_sizes":
        GROUP_SIZES,

    "case_classes": [
        "single",
        "sequential_pair",
        "simultaneous_pair",
    ],

    "single_cases":
        len(
            single_cases
        ),

    "sequential_pair_cases":
        len(
            sequential_cases
        ),

    "simultaneous_pair_cases":
        len(
            simultaneous_cases
        ),

    "total_cases":
        len(
            cases
        ),

    "total_rekey_epochs":
        total_epochs,

    "failure_count":
        len(
            failures
        ),

    "historical_boundary_cases":
        len(
            historical_boundary_cases
        ),

    "checks":
        checks,

    "security_invariants": [
        (
            "authorized survivors derive "
            "the new root"
        ),
        (
            "no currently or previously "
            "revoked member derives "
            "the new root"
        ),
        (
            "the coalition of all revoked "
            "members does not derive "
            "the new root"
        ),
        (
            "published LKH update recipients "
            "exclude revoked members"
        ),
        (
            "root version follows rekey epoch"
        ),
        (
            "historical roots remain known "
            "to members that legitimately "
            "held them before later revocation"
        ),
    ],

    "method":
        (
            "finite exhaustive symbolic-key "
            "closure over exact LkhKeyTree "
            "update plans"
        ),

    "arbitrary_n_theorem":
        False,

    "formal_tamarin_generalization":
        False,

    "implementation_modified":
        False,

    "scientific_state":
        (
            "FINITE_STRUCTURAL_GENERALIZATION_PASS"
            if all(
                checks.values()
            )
            else
            "FINITE_STRUCTURAL_GENERALIZATION_FAILURE"
        ),
}


summary_path.write_text(
    json.dumps(
        summary,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


print("=" * 78)
print("RANGER-IOT — STRUCTURAL LKH GENERALIZATION")
print("=" * 78)

print(
    f"GROUP_SIZES={GROUP_SIZES}"
)

print(
    f"SINGLE_CASES={len(single_cases)}"
)

print(
    "SEQUENTIAL_PAIR_CASES="
    f"{len(sequential_cases)}"
)

print(
    "SIMULTANEOUS_PAIR_CASES="
    f"{len(simultaneous_cases)}"
)

print(
    f"TOTAL_CASES={len(cases)}"
)

print(
    f"TOTAL_REKEY_EPOCHS={total_epochs}"
)

print(
    f"FAILURES={len(failures)}"
)

print(
    "HISTORICAL_BOUNDARY_CASES="
    f"{len(historical_boundary_cases)}"
)


print()
for key, passed in checks.items():
    print(
        f"{key:58s}",
        "PASS"
        if passed
        else "FAIL",
    )


print()
print(
    "STATE="
    + summary[
        "scientific_state"
    ]
)


if failures:

    print()
    print(
        "FIRST_FAILURE="
        + json.dumps(
            failures[0],
            sort_keys=True,
        )
    )

    raise SystemExit(20)


if not all(
    checks.values()
):

    raise SystemExit(21)
PY


# ==================================================================
# 4. Independent summary audit
# ==================================================================

echo
echo "===== 4. INDEPENDENT STRUCTURAL RESULT AUDIT ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$OUT/structural-summary.json" \
    "$OUT/structural-cases.csv" <<'PY'
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


summary = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)


with Path(
    sys.argv[2]
).open(
    encoding="utf-8",
    newline="",
) as handle:
    rows = list(
        csv.DictReader(
            handle
        )
    )


checks = {
    "state_pass":
        summary.get(
            "scientific_state"
        )
        ==
        "FINITE_STRUCTURAL_GENERALIZATION_PASS",

    "zero_failures":
        summary.get(
            "failure_count"
        )
        == 0,

    "csv_epoch_rows":
        len(
            rows
        )
        ==
        summary.get(
            "total_rekey_epochs"
        ),

    "all_csv_pass":
        all(
            row[
                "all_checks_pass"
            ]
            == "True"
            for row
            in rows
        ),

    "not_arbitrary_n_claim":
        summary.get(
            "arbitrary_n_theorem"
        )
        is False,

    "implementation_unchanged":
        summary.get(
            "implementation_modified"
        )
        is False,
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
        "Independent structural audit failed"
    )


print()
print(
    "STRUCTURAL_GENERALIZATION_AUDIT=PASS"
)
PY


# ==================================================================
# 5. Frozen source check
# ==================================================================

echo
echo "===== 5. POST-AUDIT IMPLEMENTATION FREEZE ====="

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
# 6. CI
# ==================================================================

echo
echo "===== 6. PROJECT CI ====="

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
# 7. Final classification
# ==================================================================

echo
echo "===== 7. FINAL STEP7D2C-A CLASSIFICATION ====="

docker compose \
  -f "$ROOT_COMPOSE" \
  run \
  --rm \
  -T \
  --no-deps \
  ranger \
  python - \
    "$FORMAL_PREV/final-state.json" \
    "$OUT/structural-summary.json" \
    "$OUT/final-state.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


formal = json.loads(
    Path(sys.argv[1]).read_text(
        encoding="utf-8"
    )
)

structural = json.loads(
    Path(sys.argv[2]).read_text(
        encoding="utf-8"
    )
)


closed = (
    formal.get(
        "reference_instance_closed"
    )
    is True
    and
    structural.get(
        "scientific_state"
    )
    ==
    "FINITE_STRUCTURAL_GENERALIZATION_PASS"
    and
    structural.get(
        "failure_count"
    )
    == 0
)


payload = {
    "schema_version":
        1,

    "step":
        "STEP7D2CA",

    "formal_reference_instance_closed":
        formal.get(
            "reference_instance_closed"
        ),

    "formal_17_of_17":
        formal.get(
            "all_17_verified"
        ),

    "formal_negative_control":
        formal.get(
            "negative_control_pass"
        ),

    "structural_generalization_pass":
        structural.get(
            "scientific_state"
        )
        ==
        "FINITE_STRUCTURAL_GENERALIZATION_PASS",

    "structural_case_count":
        structural.get(
            "total_cases"
        ),

    "structural_rekey_epoch_count":
        structural.get(
            "total_rekey_epochs"
        ),

    "structural_failure_count":
        structural.get(
            "failure_count"
        ),

    "group_sizes":
        structural.get(
            "group_sizes"
        ),

    "revoked_coalition_checked":
        True,

    "arbitrary_n_theorem":
        False,

    "full_ranger_formally_verified":
        False,

    "step7d2ca_closed":
        closed,

    "scientific_state":
        (
            "STEP7D2CA_FINITE_STRUCTURAL_GENERALIZATION_CLOSED"
            if closed
            else
            "STEP7D2CA_NOT_CLOSED"
        ),

    "next_step":
        (
            "STEP7D2CB_REAL_RS_COMPARATIVE_BRIDGE"
            if closed
            else
            "STEP7D2CA_FAILURE_AUDIT"
        ),
}


Path(
    sys.argv[3]
).write_text(
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
    raise SystemExit(30)
PY


# ==================================================================
# 8. Evidence package
# ==================================================================

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

    MAN=/tmp/step7d2ca.sha256
    TAR=/tmp/step7d2ca.tar.gz

    rm -f \
      \"\$MAN\" \
      \"\$TAR\"

    find '$OUT' \
      -type f \
      ! -name 'evidence.sha256' \
      ! -name 'evidence-verify.log' \
      ! -name 'step7d2ca-evidence.tar.gz' \
      ! -name 'step7d2ca-evidence.tar.gz.sha256' \
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
      '$LKH'

    tar \
      -tzf \
      \"\$TAR\" \
      >/dev/null

    cp \
      \"\$TAR\" \
      '$OUT/step7d2ca-evidence.tar.gz'

    sha256sum \
      '$OUT/step7d2ca-evidence.tar.gz' \
      > '$OUT/step7d2ca-evidence.tar.gz.sha256'

    sha256sum \
      -c \
      '$OUT/step7d2ca-evidence.tar.gz.sha256'
  "


echo
echo "===================================================================="
echo "STEP 7D.2-C-A COMPLETE"
echo
echo "SUMMARY:"
echo "  $OUT/structural-summary.json"
echo
echo "FINAL STATE:"
echo "  $OUT/final-state.json"
echo
echo "FAILURES:"
echo "  $OUT/structural-failures.json"
echo
echo "NEXT:"
echo "  STEP7D2-C-B REAL-RS COMPARATIVE BRIDGE"
echo
echo "NO COMMIT"
echo "NO PUSH"
echo "===================================================================="
