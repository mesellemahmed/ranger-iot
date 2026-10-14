# Deterministic Topology Suite v1

STEP 4E.2 extends the baseline campaign infrastructure with four deterministic
connected topology families. The goal is to separate protocol behavior from the
special properties of a single line topology before any RANGER-specific
mechanism is introduced.

## Supported topologies

- `line`: the Group Manager is placed at one end of a chain.
- `star`: the Group Manager is the center and every member is one hop away.
- `balanced-tree`: nodes are assigned breadth-first to a deterministic binary tree rooted at the Group Manager.
- `grid`: nodes are assigned row-major to a near-square rectangular grid; the Group Manager occupies the first cell.

The Group Manager is always the topology root even when its numeric identifier
is not the smallest identifier. Remaining node identifiers are sorted to make
edge construction reproducible.

## Grid construction

For `V` total nodes, the grid width is `ceil(sqrt(V))`. Nodes are filled
row-major and only existing cells receive right/down edges. This also defines a
connected deterministic partial grid when `V` is not a perfect square.

## Campaign smoke matrix

`experiments/configs/step4e-topology-suite-smoke.yaml` executes:

- 3 protocols: SKDC, LKH-UNICAST, LKH-FLOOD;
- 4 topologies;
- 3 member counts: 4, 8, 16;
- 2 packet-loss rates: 0 and 0.1;
- 2 deterministic seeds: 11 and 29.

The matrix therefore contains 144 runs. This is an infrastructure smoke
campaign, not a statistically powered scientific experiment.

## Interpretation rule

Cost metrics must always be interpreted together with convergence. A protocol
that transmits fewer packets because a lossy path failed early has not become
more efficient. Incomplete runs must not be compared to complete runs on cost
alone.
