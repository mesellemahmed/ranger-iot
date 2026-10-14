from __future__ import annotations

import argparse
import csv
import hashlib
import json
from itertools import combinations
from math import comb
from pathlib import Path
from zlib import crc32

from ranger_iot.ranger.rs_codec import (
    ReedSolomonCodec,
    ReedSolomonFragment,
    ReedSolomonParameters,
)


EXPECTED_VECTOR_COUNT = 259
EXPECTED_SUBSET_COUNT = 2588


def _flatten_generator(
    codec: ReedSolomonCodec,
) -> bytes:
    return bytes(
        value
        for row
        in codec.generator_matrix
        for value
        in row
    )


def _primary_payload(
    length: int,
) -> bytes:
    return bytes(
        (
            length * 37
            + index * 19
            + index * index
        )
        % 256
        for index in range(length)
    )


def _generic_payload(
    length: int,
) -> bytes:
    return bytes(
        (
            index * 43
            + length
        )
        % 256
        for index in range(length)
    )


def generate_vectors(
    output: Path,
) -> None:
    rows: list[
        dict[str, str]
    ] = []

    primary_parameters = (
        ReedSolomonParameters(
            data_shards=3,
            total_shards=5,
        )
    )

    primary_codec = (
        ReedSolomonCodec(
            primary_parameters
        )
    )

    generator_hex = (
        _flatten_generator(
            primary_codec
        ).hex()
    )

    for length in range(
        1,
        257,
    ):
        payload = _primary_payload(
            length
        )

        fragments = (
            primary_codec.encode(
                payload
            )
        )

        rows.append({
            "vector_id":
                f"primary-3of5-len{length:03d}",

            "k":
                "3",

            "n":
                "5",

            "payload_hex":
                payload.hex(),

            "generator_hex":
                generator_hex,

            "expected_shards_hex":
                ",".join(
                    fragment.data.hex()
                    for fragment
                    in fragments
                ),
        })


    generic_profiles = [
        (
            "generic-2of3",
            2,
            3,
            41,
        ),
        (
            "generic-3of5",
            3,
            5,
            73,
        ),
        (
            "generic-4of6",
            4,
            6,
            97,
        ),
    ]


    for (
        vector_id,
        k,
        n,
        length,
    ) in generic_profiles:
        codec = ReedSolomonCodec(
            ReedSolomonParameters(
                data_shards=k,
                total_shards=n,
            )
        )

        payload = _generic_payload(
            length
        )

        fragments = codec.encode(
            payload
        )

        rows.append({
            "vector_id":
                vector_id,

            "k":
                str(k),

            "n":
                str(n),

            "payload_hex":
                payload.hex(),

            "generator_hex":
                _flatten_generator(
                    codec
                ).hex(),

            "expected_shards_hex":
                ",".join(
                    fragment.data.hex()
                    for fragment
                    in fragments
                ),
        })


    if len(rows) != EXPECTED_VECTOR_COUNT:
        raise RuntimeError(
            "unexpected vector count: "
            f"{len(rows)}"
        )


    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    with output.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "vector_id",
                "k",
                "n",
                "payload_hex",
                "generator_hex",
                "expected_shards_hex",
            ],
            delimiter="\t",
            lineterminator="\n",
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


    print(
        "VECTOR_GENERATION=PASS"
    )

    print(
        "vectors =",
        len(rows),
    )


def _load_tsv(
    path: Path,
) -> list[
    dict[str, str]
]:
    with path.open(
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(
            csv.DictReader(
                handle,
                delimiter="\t",
            )
        )


def validate(
    vectors_path: Path,
    c_results_path: Path,
    report_path: Path,
) -> None:
    vectors = _load_tsv(
        vectors_path
    )

    c_results = _load_tsv(
        c_results_path
    )


    expected_by_id = {
        row[
            "vector_id"
        ]:
        row
        for row
        in vectors
    }


    actual_by_id = {
        row[
            "vector_id"
        ]:
        row
        for row
        in c_results
    }


    if len(
        expected_by_id
    ) != EXPECTED_VECTOR_COUNT:
        raise RuntimeError(
            "unexpected vector cardinality"
        )


    if set(
        expected_by_id
    ) != set(
        actual_by_id
    ):
        raise RuntimeError(
            "C result vector IDs "
            "do not match Python vectors"
        )


    matrix_matches = 0
    shard_matches = 0

    c_on_c_subsets = 0
    c_on_python_subsets = 0

    python_on_c_subsets = 0

    expected_digest = hashlib.sha256()
    actual_digest = hashlib.sha256()


    for vector_id in sorted(
        expected_by_id
    ):
        expected = expected_by_id[
            vector_id
        ]

        actual = actual_by_id[
            vector_id
        ]


        k = int(
            expected[
                "k"
            ]
        )

        n = int(
            expected[
                "n"
            ]
        )

        payload = bytes.fromhex(
            expected[
                "payload_hex"
            ]
        )


        expected_generator = (
            expected[
                "generator_hex"
            ]
        )

        actual_generator = (
            actual[
                "actual_generator_hex"
            ]
        )


        if (
            actual[
                "matrix_match"
            ]
            != "1"

            or

            expected_generator
            != actual_generator
        ):
            raise RuntimeError(
                "generator mismatch "
                f"for {vector_id}"
            )


        matrix_matches += 1


        expected_shards_hex = (
            expected[
                "expected_shards_hex"
            ]
        )

        actual_shards_hex = (
            actual[
                "actual_shards_hex"
            ]
        )


        if (
            actual[
                "encode_match"
            ]
            != "1"

            or

            expected_shards_hex
            != actual_shards_hex
        ):
            raise RuntimeError(
                "byte-for-byte shard mismatch "
                f"for {vector_id}"
            )


        shard_matches += 1


        expected_digest.update(
            expected_shards_hex.encode(
                "ascii"
            )
        )

        actual_digest.update(
            actual_shards_hex.encode(
                "ascii"
            )
        )


        subset_count = comb(
            n,
            k,
        )


        current_c_on_c = int(
            actual[
                "c_decode_subset_count"
            ]
        )

        current_c_on_python = int(
            actual[
                "python_shard_decode_count"
            ]
        )


        if (
            actual[
                "c_decode_all_match"
            ]
            != "1"

            or

            current_c_on_c
            != subset_count
        ):
            raise RuntimeError(
                "C->C decode failure "
                f"for {vector_id}"
            )


        if (
            actual[
                "python_shard_decode_all_match"
            ]
            != "1"

            or

            current_c_on_python
            != subset_count
        ):
            raise RuntimeError(
                "Python shards -> C decoder "
                f"failure for {vector_id}"
            )


        c_on_c_subsets += (
            current_c_on_c
        )

        c_on_python_subsets += (
            current_c_on_python
        )


        #
        # Reverse differential direction:
        #
        # shards encoded by C are reconstructed
        # with the Python decoder.
        #

        actual_shards = [
            bytes.fromhex(
                item
            )
            for item
            in actual_shards_hex.split(
                ","
            )
        ]


        if len(
            actual_shards
        ) != n:
            raise RuntimeError(
                "invalid C shard count "
                f"for {vector_id}"
            )


        shard_size = len(
            actual_shards[
                0
            ]
        )


        checksum = (
            crc32(
                payload
            )
            & 0xFFFFFFFF
        )


        fragments = tuple(
            ReedSolomonFragment(
                index=index,
                data=data,
                original_length=len(
                    payload
                ),
                shard_size=shard_size,
                data_shards=k,
                total_shards=n,
                payload_crc32=checksum,
            )
            for index, data
            in enumerate(
                actual_shards
            )
        )


        python_codec = ReedSolomonCodec(
            ReedSolomonParameters(
                data_shards=k,
                total_shards=n,
            )
        )


        for subset in combinations(
            fragments,
            k,
        ):
            reconstructed = (
                python_codec.decode(
                    subset
                )
            )

            if reconstructed != payload:
                raise RuntimeError(
                    "C shards -> Python decoder "
                    f"failure for {vector_id} "
                    f"subset="
                    f"{[x.index for x in subset]}"
                )

            python_on_c_subsets += 1


    expected_hash = (
        expected_digest.hexdigest()
    )

    actual_hash = (
        actual_digest.hexdigest()
    )


    checks = {
        "vectors":
            len(
                vectors
            )
            == EXPECTED_VECTOR_COUNT,

        "matrix_matches":
            matrix_matches
            == EXPECTED_VECTOR_COUNT,

        "byte_exact_shard_matches":
            shard_matches
            == EXPECTED_VECTOR_COUNT,

        "c_decoder_on_c_shards":
            c_on_c_subsets
            == EXPECTED_SUBSET_COUNT,

        "c_decoder_on_python_shards":
            c_on_python_subsets
            == EXPECTED_SUBSET_COUNT,

        "python_decoder_on_c_shards":
            python_on_c_subsets
            == EXPECTED_SUBSET_COUNT,

        "aggregate_shard_digest":
            expected_hash
            == actual_hash,
    }


    for name, passed in checks.items():
        print(
            f"{name:34s}",
            "PASS"
            if passed
            else "FAIL",
        )


    passed = all(
        checks.values()
    )


    report = {
        "schema_version":
            1,

        "step":
            "STEP7C2_C_PYTHON_DIFFERENTIAL",

        "field":
            "GF(256)",

        "primitive_polynomial":
            "0x11D",

        "c_bounds": {
            "max_k":
                8,

            "max_n":
                16,
        },

        "primary_profile": {
            "k":
                3,

            "n":
                5,

            "payload_lengths":
                "1..256",
        },

        "generic_profiles": [
            "2-of-3",
            "3-of-5",
            "4-of-6",
        ],

        "vector_count":
            len(
                vectors
            ),

        "generator_matrix_matches":
            matrix_matches,

        "byte_exact_shard_vectors":
            shard_matches,

        "c_decoder_on_c_shards":
            c_on_c_subsets,

        "c_decoder_on_python_shards":
            c_on_python_subsets,

        "python_decoder_on_c_shards":
            python_on_c_subsets,

        "expected_subset_count_each_direction":
            EXPECTED_SUBSET_COUNT,

        "expected_shard_digest_sha256":
            expected_hash,

        "actual_c_shard_digest_sha256":
            actual_hash,

        "checks":
            checks,

        "step7c2_differential_pass":
            passed,

        "scientific_state": (
            "C_PYTHON_BYTE_LEVEL_CODEC_EQUIVALENCE_VALIDATED"
            if passed
            else
            "C_PYTHON_CODEC_DIFFERENTIAL_FAILED"
        ),

        "network_integration":
            False,

        "cooja_real_rs_validated":
            False,

        "next_step":
            "STEP7C3_COOJA_REAL_RS_WIRE_INTEGRATION",
    }


    report_path.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


    print()
    print(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
        )
    )


    if not passed:
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )


    generate = sub.add_parser(
        "generate"
    )

    generate.add_argument(
        "--output",
        required=True,
        type=Path,
    )


    validate_parser = sub.add_parser(
        "validate"
    )

    validate_parser.add_argument(
        "--vectors",
        required=True,
        type=Path,
    )

    validate_parser.add_argument(
        "--c-results",
        required=True,
        type=Path,
    )

    validate_parser.add_argument(
        "--report",
        required=True,
        type=Path,
    )


    args = parser.parse_args()


    if args.command == "generate":
        generate_vectors(
            args.output
        )

    elif args.command == "validate":
        validate(
            args.vectors,
            args.c_results,
            args.report,
        )

    else:
        raise AssertionError(
            args.command
        )


if __name__ == "__main__":
    main()
