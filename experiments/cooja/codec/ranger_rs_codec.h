#ifndef RANGER_RS_CODEC_H
#define RANGER_RS_CODEC_H

#include <stddef.h>
#include <stdint.h>

/*
 * STEP 7C.2 bounded embedded implementation.
 *
 * The field is GF(256) with primitive polynomial 0x11D.
 *
 * Current implementation bounds are intentionally
 * conservative for constrained embedded targets.
 */
#define RANGER_RS_MAX_K 8u
#define RANGER_RS_MAX_N 16u

size_t ranger_rs_shard_size(
    size_t payload_len,
    uint8_t k
);

int ranger_rs_build_generator(
    uint8_t k,
    uint8_t n,
    uint8_t *generator
);

int ranger_rs_encode(
    uint8_t k,
    uint8_t n,
    const uint8_t *payload,
    size_t payload_len,
    uint8_t *shards,
    size_t shard_size
);

int ranger_rs_decode(
    uint8_t k,
    uint8_t n,
    const uint8_t *indices,
    const uint8_t *selected_shards,
    size_t shard_size,
    size_t original_len,
    uint8_t *payload_out
);

#endif
