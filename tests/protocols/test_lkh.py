import pytest

from ranger_iot.protocols.lkh import LkhKeyRef, LkhKeyTree, LkhKeyUpdate


def test_lkh_tree_assigns_deterministic_leaf_paths() -> None:
    tree = LkhKeyTree({4, 1, 3, 2})

    assert tree.member_ids == (1, 2, 3, 4)
    assert tree.active_member_ids == (1, 2, 3, 4)
    assert tree.leaf_base == 4
    assert tree.leaf_node(1) == 4
    assert tree.leaf_node(4) == 7
    assert tree.member_key_path(1) == (4, 2, 1)
    assert tree.member_key_path(4) == (7, 3, 1)
    assert tree.members_under(2) == (1, 2)
    assert tree.members_under(3) == (3, 4)
    assert tree.root_key == LkhKeyRef(node_id=1, version=0)


def test_single_revocation_produces_classic_bottom_up_plan() -> None:
    tree = LkhKeyTree({1, 2, 3, 4})

    plan = tree.rekey({4})

    assert plan.revoked_members == (4,)
    assert plan.affected_nodes == (3, 1)
    assert plan.logical_ciphertexts == 3
    assert plan.root_key == LkhKeyRef(node_id=1, version=1)
    assert tree.active_member_ids == (1, 2, 3)

    assert plan.updates == (
        LkhKeyUpdate(
            target=LkhKeyRef(3, 1),
            wrapper=LkhKeyRef(6, 0),
            recipients=(3,),
        ),
        LkhKeyUpdate(
            target=LkhKeyRef(1, 1),
            wrapper=LkhKeyRef(2, 0),
            recipients=(1, 2),
        ),
        LkhKeyUpdate(
            target=LkhKeyRef(1, 1),
            wrapper=LkhKeyRef(3, 1),
            recipients=(3,),
        ),
    )
    assert all(4 not in update.recipients for update in plan.updates)


def test_batch_revocation_updates_both_affected_branches() -> None:
    tree = LkhKeyTree({1, 2, 3, 4})

    plan = tree.rekey({2, 4})

    assert plan.affected_nodes == (2, 3, 1)
    assert plan.logical_ciphertexts == 4
    assert tree.active_member_ids == (1, 3)
    assert plan.updates == (
        LkhKeyUpdate(LkhKeyRef(2, 1), LkhKeyRef(4, 0), (1,)),
        LkhKeyUpdate(LkhKeyRef(3, 1), LkhKeyRef(6, 0), (3,)),
        LkhKeyUpdate(LkhKeyRef(1, 1), LkhKeyRef(2, 1), (1,)),
        LkhKeyUpdate(LkhKeyRef(1, 1), LkhKeyRef(3, 1), (3,)),
    )


def test_periodic_rekey_rotates_only_root() -> None:
    tree = LkhKeyTree({1, 2, 3, 4})

    plan = tree.rekey(set())

    assert plan.revoked_members == ()
    assert plan.affected_nodes == (1,)
    assert plan.logical_ciphertexts == 2
    assert plan.root_key == LkhKeyRef(1, 1)
    assert plan.updates == (
        LkhKeyUpdate(LkhKeyRef(1, 1), LkhKeyRef(2, 0), (1, 2)),
        LkhKeyUpdate(LkhKeyRef(1, 1), LkhKeyRef(3, 0), (3, 4)),
    )


def test_sequential_revocation_prunes_empty_subtree() -> None:
    tree = LkhKeyTree({1, 2, 3, 4})

    first = tree.rekey({4})
    second = tree.rekey({3})

    assert first.root_key == LkhKeyRef(1, 1)
    assert second.affected_nodes == (1,)
    assert second.root_key == LkhKeyRef(1, 2)
    assert second.updates == (LkhKeyUpdate(LkhKeyRef(1, 2), LkhKeyRef(2, 0), (1, 2)),)
    assert tree.active_member_ids == (1, 2)


def test_non_power_of_two_tree_does_not_emit_empty_branch_updates() -> None:
    tree = LkhKeyTree({1, 2, 3, 4, 5})

    assert tree.leaf_base == 8
    plan = tree.rekey({5})

    assert plan.affected_nodes == (1,)
    assert plan.logical_ciphertexts == 1
    assert plan.updates[0].recipients == (1, 2, 3, 4)
    assert plan.updates[0].wrapper == LkhKeyRef(2, 0)


def test_lkh_validation_and_symbolic_key_guards() -> None:
    with pytest.raises(ValueError, match="at least two"):
        LkhKeyTree({1})
    with pytest.raises(ValueError, match="non-negative"):
        LkhKeyTree({-1, 2})
    with pytest.raises(ValueError, match="node_id"):
        LkhKeyRef(0, 0)
    with pytest.raises(ValueError, match="version"):
        LkhKeyRef(1, -1)
    with pytest.raises(ValueError, match="must not be empty"):
        LkhKeyUpdate(LkhKeyRef(1, 1), LkhKeyRef(2, 0), ())
    with pytest.raises(ValueError, match="unique"):
        LkhKeyUpdate(LkhKeyRef(1, 1), LkhKeyRef(2, 0), (1, 1))
    with pytest.raises(ValueError, match="non-negative"):
        LkhKeyUpdate(LkhKeyRef(1, 1), LkhKeyRef(2, 0), (-1,))

    tree = LkhKeyTree({1, 2})
    with pytest.raises(KeyError, match="unknown LKH member"):
        tree.leaf_node(9)
    with pytest.raises(KeyError, match="unknown LKH tree node"):
        tree.key_ref(99)
    with pytest.raises(KeyError, match="unknown LKH tree node"):
        tree.members_under(99)
    with pytest.raises(KeyError, match="unknown LKH member"):
        tree.rekey({9})


def test_lkh_rejects_repeated_and_total_revocation() -> None:
    tree = LkhKeyTree({1, 2, 3})
    tree.rekey({3})

    with pytest.raises(ValueError, match="already revoked"):
        tree.rekey({3})
    with pytest.raises(ValueError, match="revoke all"):
        tree.rekey({1, 2})


def test_active_only_membership_view_tracks_rekey_state() -> None:
    tree = LkhKeyTree({1, 2, 3, 4})
    tree.rekey({4})

    assert tree.members_under(3) == (3, 4)
    assert tree.members_under(3, active_only=True) == (3,)
