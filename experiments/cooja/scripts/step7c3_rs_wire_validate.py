from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path
from zlib import crc32

from ranger_iot.ranger.rs_codec import (
    ReedSolomonCodec,
    ReedSolomonFragment,
    ReedSolomonParameters,
)

PAYLOAD = b"RANGER-RS-EPOCH1"

PARAMETERS = ReedSolomonParameters(
    data_shards=3,
    total_shards=5,
)

CODEC = ReedSolomonCodec(PARAMETERS)

CANONICAL_FRAGMENTS = CODEC.encode(PAYLOAD)

CANONICAL = {fragment.index: fragment.data.hex() for fragment in CANONICAL_FRAGMENTS}


CONTROLLED_SEND_MASKS = {
    2: 0x07,
    3: 0x0B,
    4: 0x13,
    5: 0x0D,
    6: 0x1A,
    7: 0x03,
    8: 0x01,
}


CONTROLLED_RECONSTRUCTION_MASKS = {
    2: 0x07,
    3: 0x0B,
    4: 0x13,
    5: 0x0D,
    6: 0x1A,
}


def mask_indices(
    mask: int,
) -> set[int]:
    return {index for index in range(5) if (mask & (1 << index))}


def load_json(
    path: Path,
) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def make_fragment(
    *,
    index: int,
    data_hex: str,
) -> ReedSolomonFragment:
    data = bytes.fromhex(data_hex)

    return ReedSolomonFragment(
        index=index,
        data=data,
        original_length=len(PAYLOAD),
        shard_size=len(data),
        data_shards=3,
        total_shards=5,
        payload_crc32=(crc32(PAYLOAD) & 0xFFFFFFFF),
    )


def validate_common(
    evidence: dict[str, object],
    mode: int,
) -> tuple[
    dict[tuple[int, int], str],
    dict[tuple[int, int], str],
]:
    if evidence.get("schema_version") != 2:
        raise RuntimeError(f"mode {mode}: invalid schema")

    if evidence.get("mode") != mode:
        raise RuntimeError(f"mode {mode}: wrong mode")

    if evidence.get("success") is not True:
        raise RuntimeError(f"mode {mode}: Cooja observer did not pass")

    if evidence.get("registered_count") != 7:
        raise RuntimeError(f"mode {mode}: registration contract failed")

    if evidence.get("core_pass") is not True:
        raise RuntimeError(f"mode {mode}: firmware core did not pass")

    if evidence.get("mask_pass") is not True:
        raise RuntimeError(f"mode {mode}: firmware mask oracle did not pass")

    if evidence.get("rejected") is not True:
        raise RuntimeError(f"mode {mode}: revoked member was not rejected")

    sends: dict[
        tuple[int, int],
        str,
    ] = {}

    for event in evidence["sends"]:
        target = int(event["target"])

        shard = int(event["shard"])

        data = str(event["data"]).lower()

        if int(event["mode"]) != mode:
            raise RuntimeError("cross-mode SEND event")

        if int(event["emitter"]) != 1:
            raise RuntimeError("RS SEND not emitted by GM")

        if data != CANONICAL[shard]:
            raise RuntimeError(
                "C SEND bytes differ from "
                "Python canonical shard "
                f"mode={mode} "
                f"target={target} "
                f"shard={shard}"
            )

        key = (
            target,
            shard,
        )

        if key in sends:
            raise RuntimeError(f"duplicate SEND {key}")

        sends[key] = data

    receives: dict[
        tuple[int, int],
        str,
    ] = {}

    for event in evidence["receives"]:
        node = int(event["node"])

        shard = int(event["shard"])

        data = str(event["data"]).lower()

        if int(event["mode"]) != mode:
            raise RuntimeError("cross-mode RX event")

        if int(event["emitter"]) != node:
            raise RuntimeError("RX emitter/node mismatch")

        if data != CANONICAL[shard]:
            raise RuntimeError(
                "wire RX bytes differ from "
                "Python canonical shard "
                f"mode={mode} "
                f"node={node} "
                f"shard={shard}"
            )

        key = (
            node,
            shard,
        )

        if key in receives:
            raise RuntimeError(f"duplicate RX {key}")

        receives[key] = data

    return (
        sends,
        receives,
    )


def python_reconstruct_node(
    *,
    node: int,
    mask: int,
    receives: dict[
        tuple[int, int],
        str,
    ],
) -> None:
    fragments = []

    for shard in sorted(mask_indices(mask)):
        key = (
            node,
            shard,
        )

        if key not in receives:
            raise RuntimeError(
                "C reconstruction claims "
                "a shard that was not observed "
                f"at RX node={node} "
                f"shard={shard}"
            )

        fragments.append(
            make_fragment(
                index=shard,
                data_hex=receives[key],
            )
        )

    reconstructed = CODEC.decode(fragments)

    if reconstructed != PAYLOAD:
        raise RuntimeError(f"Python could not reproduce the Cooja reconstruction for node {node}")


def validate_no_loss(
    evidence: dict[str, object],
) -> dict[str, object]:
    sends, receives = validate_common(
        evidence,
        0,
    )

    expected_sends = {
        (
            target,
            shard,
        )
        for target in range(
            2,
            9,
        )
        for shard in range(5)
    }

    if set(sends) != expected_sends:
        raise RuntimeError("no-loss SEND matrix mismatch")

    if len(receives) != 19:
        raise RuntimeError(f"no-loss RX cardinality mismatch: {len(receives)} != 19")

    reconstruct_masks = {
        int(node): int(mask) for node, mask in evidence["reconstruct_mask"].items()
    }

    if set(reconstruct_masks) != {
        2,
        3,
        4,
        5,
        6,
        7,
    }:
        raise RuntimeError("no-loss reconstructed-node set mismatch")

    for node, mask in reconstruct_masks.items():
        if mask.bit_count() != 3:
            raise RuntimeError(
                f"no-loss C reconstruction did not use exactly k=3 node={node} mask={mask}"
            )

        python_reconstruct_node(
            node=node,
            mask=mask,
            receives=receives,
        )

    if evidence.get("below_k") is not False:
        raise RuntimeError("unexpected below-k in no-loss")

    return {
        "send_count": len(sends),
        "receive_count": len(receives),
        "reconstruction_masks": reconstruct_masks,
        "c_reconstruction_count": len(reconstruct_masks),
        "python_reconstruction_count": len(reconstruct_masks),
        "revoked_rejected": True,
        "below_k": False,
        "canonical_send_bytes": True,
        "canonical_receive_bytes": True,
        "python_reconstruction_from_rx": True,
    }


def validate_controlled(
    evidence: dict[str, object],
) -> dict[str, object]:
    sends, receives = validate_common(
        evidence,
        1,
    )

    expected_pairs = {
        (
            node,
            shard,
        )
        for node, mask in CONTROLLED_SEND_MASKS.items()
        for shard in mask_indices(mask)
    }

    if set(sends) != expected_pairs:
        raise RuntimeError("controlled SEND matrix mismatch")

    if set(receives) != expected_pairs:
        raise RuntimeError("controlled RX matrix mismatch")

    reconstruct_masks = {
        int(node): int(mask) for node, mask in evidence["reconstruct_mask"].items()
    }

    if reconstruct_masks != CONTROLLED_RECONSTRUCTION_MASKS:
        raise RuntimeError(f"controlled reconstruction masks mismatch: {reconstruct_masks}")

    for node, mask in reconstruct_masks.items():
        python_reconstruct_node(
            node=node,
            mask=mask,
            receives=receives,
        )

    node7_fragments = [
        make_fragment(
            index=shard,
            data_hex=receives[
                (
                    7,
                    shard,
                )
            ],
        )
        for shard in sorted(mask_indices(CONTROLLED_SEND_MASKS[7]))
    ]

    below_k_rejected = False

    try:
        CODEC.decode(node7_fragments)

    except ValueError as exc:
        below_k_rejected = "insufficient distinct fragments" in str(exc)

    if not below_k_rejected:
        raise RuntimeError("Python decoder unexpectedly decoded node 7 with only 2 shards")

    if evidence.get("below_k") is not True:
        raise RuntimeError("C node 7 below-k marker missing")

    if evidence.get("below_mask") != 3:
        raise RuntimeError("C node 7 below-k mask mismatch")

    return {
        "send_count": len(sends),
        "receive_count": len(receives),
        "reconstruction_masks": reconstruct_masks,
        "c_reconstruction_count": len(reconstruct_masks),
        "python_reconstruction_count": len(reconstruct_masks),
        "revoked_rejected": True,
        "below_k_node": 7,
        "below_k_mask": 3,
        "python_below_k_rejected": True,
        "canonical_send_bytes": True,
        "canonical_receive_bytes": True,
        "python_reconstruction_from_rx": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode0-evidence",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--mode1-evidence",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--oracle",
        required=True,
        type=Path,
    )

    parser.add_argument(
        "--report",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    mode0 = load_json(args.mode0_evidence)

    mode1 = load_json(args.mode1_evidence)

    no_loss = validate_no_loss(mode0)

    controlled = validate_controlled(mode1)

    #
    # Additional codec-level arbitrary-subset
    # sanity check using the same payload.
    #
    all_subset_count = 0

    for subset in combinations(
        CANONICAL_FRAGMENTS,
        3,
    ):
        if CODEC.decode(subset) != PAYLOAD:
            raise RuntimeError("Python canonical arbitrary 3-of-5 subset failure")

        all_subset_count += 1

    oracle = {
        "schema_version": 2,
        "payload_ascii": PAYLOAD.decode("ascii"),
        "payload_hex": PAYLOAD.hex(),
        "payload_bytes": len(PAYLOAD),
        "field": "GF(256)",
        "primitive_polynomial": "0x11D",
        "k": 3,
        "n": 5,
        "shard_bytes": 6,
        "wire_packet_bytes": 18,
        "canonical_shards": {str(index): value for index, value in CANONICAL.items()},
        "all_python_3of5_subsets": all_subset_count,
    }

    args.oracle.write_text(
        json.dumps(
            oracle,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    report = {
        "schema_version": 2,
        "step": "STEP7C3_COOJA_REAL_RS_WIRE_INTEGRATION",
        "codec": {
            "field": "GF(256)",
            "primitive_polynomial": "0x11D",
            "systematic": True,
            "k": 3,
            "n": 5,
        },
        "payload": {
            "bytes": len(PAYLOAD),
            "hex": PAYLOAD.hex(),
        },
        "wire": {
            "shard_bytes": 6,
            "packet_bytes": 18,
        },
        "no_loss": no_loss,
        "controlled_fragment_omission": controlled,
        "all_python_3of5_subsets": all_subset_count,
        "controlled_omission_is_radio_loss": False,
        "historical_7a_7b_modified": False,
        "canonical_step7c2_codec_modified": False,
        "step7c3_pass": True,
        "scientific_state": "REAL_RS_BYTES_VALIDATED_ON_COOJA_RPL_WIRE",
        "next_step": "STEP7D_FORMAL_SECURITY_EXECUTABILITY_AUDIT",
    }

    args.report.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )

    print()
    print("STEP7C3_STRUCTURED_VALIDATION=PASS")


if __name__ == "__main__":
    main()
