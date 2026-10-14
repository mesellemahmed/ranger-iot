import pytest

from ranger_iot.group import GroupState
from ranger_iot.rekey import RekeySession


def test_group_tracks_revocation_and_monotonic_epochs() -> None:
    group = GroupState(group_id=7, manager_id=0, member_ids={1, 2, 3})

    assert group.member_ids == (1, 2, 3)
    assert group.authorized_member_ids == (1, 2, 3)
    assert group.current_epoch == 0

    group.revoke(2)
    assert group.revoked_member_ids == (2,)
    assert group.authorized_member_ids == (1, 3)

    assert group.advance_epoch() == 1
    assert group.accept_epoch(1, 1)
    assert not group.accept_epoch(1, 1)
    assert not group.accept_epoch(2, 1)
    assert group.member_epoch(1) == 1
    assert group.member_epoch(2) == 0
    assert group.convergence_fraction() == 0.5


def test_group_validation() -> None:
    with pytest.raises(ValueError, match="at least one"):
        GroupState(group_id=0, manager_id=0, member_ids=set())
    with pytest.raises(ValueError, match="manager"):
        GroupState(group_id=0, manager_id=0, member_ids={0, 1})

    group = GroupState(group_id=0, manager_id=0, member_ids={1})
    with pytest.raises(KeyError, match="unknown group member"):
        group.revoke(9)
    with pytest.raises(ValueError, match="already revoked"):
        group.revoke(1)
        group.revoke(1)


def test_rekey_session_computes_quantile_times() -> None:
    session = RekeySession(epoch=1, started_at_us=100, targets=(1, 2, 3, 4))

    assert session.record_acceptance(1, 110)
    assert session.record_acceptance(2, 120)
    assert session.record_acceptance(3, 130)
    assert not session.record_acceptance(3, 140)
    assert session.time_to_fraction_us(0.50) == 20
    assert session.time_to_fraction_us(0.95) is None

    assert session.record_acceptance(4, 180)
    summary = session.summary()
    assert summary.t50_us == 20
    assert summary.t95_us == 80
    assert summary.t100_us == 80
    assert summary.completed


def test_group_rejects_invalid_identity_and_epoch_inputs() -> None:
    with pytest.raises(ValueError, match="group_id"):
        GroupState(group_id=-1, manager_id=0, member_ids={1})
    with pytest.raises(ValueError, match="manager_id"):
        GroupState(group_id=0, manager_id=-1, member_ids={1})
    with pytest.raises(ValueError, match="initial_epoch"):
        GroupState(group_id=0, manager_id=0, member_ids={1}, initial_epoch=-1)
    with pytest.raises(ValueError, match="member identifiers"):
        GroupState(group_id=0, manager_id=0, member_ids={-1})

    group = GroupState(group_id=0, manager_id=0, member_ids={1})
    with pytest.raises(ValueError, match="newer"):
        group.accept_epoch(1, 1)


def test_group_with_all_members_revoked_is_vacuously_converged() -> None:
    group = GroupState(group_id=0, manager_id=0, member_ids={1})
    group.revoke(1)
    group.advance_epoch()

    assert group.convergence_fraction() == 1.0


def test_member_state_validation() -> None:
    from ranger_iot.group import MemberState

    with pytest.raises(ValueError, match="node_id"):
        MemberState(node_id=-1)
    with pytest.raises(ValueError, match="current_epoch"):
        MemberState(node_id=1, current_epoch=-1)


def test_rekey_session_validation_and_empty_targets() -> None:
    with pytest.raises(ValueError, match="epoch"):
        RekeySession(epoch=-1, started_at_us=0, targets=(1,))
    with pytest.raises(ValueError, match="started_at_us"):
        RekeySession(epoch=1, started_at_us=-1, targets=(1,))
    with pytest.raises(ValueError, match="unique"):
        RekeySession(epoch=1, started_at_us=0, targets=(1, 1))
    with pytest.raises(ValueError, match="identifiers"):
        RekeySession(epoch=1, started_at_us=0, targets=(-1,))

    empty = RekeySession(epoch=1, started_at_us=10, targets=())
    assert empty.completed
    assert empty.convergence_fraction == 1.0
    assert empty.time_to_fraction_us(1.0) == 0

    session = RekeySession(epoch=1, started_at_us=10, targets=(1,))
    with pytest.raises(ValueError, match="not a target"):
        session.record_acceptance(2, 11)
    with pytest.raises(ValueError, match="precede"):
        session.record_acceptance(1, 9)
    with pytest.raises(ValueError, match="fraction"):
        session.time_to_fraction_us(0.0)
