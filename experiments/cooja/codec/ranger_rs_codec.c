#include "ranger_rs_codec.h"

#include <string.h>

#define RANGER_RS_PRIMITIVE_POLYNOMIAL 0x11du


static uint8_t
gf_mul(uint8_t left, uint8_t right)
{
  uint8_t product = 0u;

  while(right != 0u) {
    uint16_t shifted;

    if((right & 1u) != 0u) {
      product ^= left;
    }

    shifted = (uint16_t)left << 1;

    if((shifted & 0x100u) != 0u) {
      shifted ^= RANGER_RS_PRIMITIVE_POLYNOMIAL;
    }

    left = (uint8_t)shifted;
    right >>= 1;
  }

  return product;
}


static uint8_t
gf_pow(uint8_t value, unsigned int exponent)
{
  uint8_t result = 1u;

  while(exponent != 0u) {
    if((exponent & 1u) != 0u) {
      result = gf_mul(result, value);
    }

    exponent >>= 1;

    if(exponent != 0u) {
      value = gf_mul(value, value);
    }
  }

  return result;
}


static uint8_t
gf_inv(uint8_t value)
{
  return gf_pow(value, 254u);
}


static int
matrix_inverse(
    const uint8_t *matrix,
    uint8_t size,
    uint8_t *inverse
)
{
  uint8_t augmented[
      RANGER_RS_MAX_K
  ][
      RANGER_RS_MAX_K * 2u
  ];

  uint8_t row;
  uint8_t column;

  if(
      matrix == NULL ||
      inverse == NULL ||
      size == 0u ||
      size > RANGER_RS_MAX_K
  ) {
    return -1;
  }

  memset(
      augmented,
      0,
      sizeof(augmented)
  );

  for(row = 0u; row < size; row++) {
    for(column = 0u; column < size; column++) {
      augmented[row][column] =
          matrix[
              (size_t)row * size
              + column
          ];

      augmented[row][size + column] =
          row == column
          ? 1u
          : 0u;
    }
  }

  for(column = 0u; column < size; column++) {
    uint8_t pivot = column;
    uint8_t pivot_inverse;
    uint8_t position;

    while(
        pivot < size &&
        augmented[pivot][column] == 0u
    ) {
      pivot++;
    }

    if(pivot == size) {
      return -2;
    }

    if(pivot != column) {
      uint8_t tmp[
          RANGER_RS_MAX_K * 2u
      ];

      memcpy(
          tmp,
          augmented[column],
          sizeof(tmp)
      );

      memcpy(
          augmented[column],
          augmented[pivot],
          sizeof(tmp)
      );

      memcpy(
          augmented[pivot],
          tmp,
          sizeof(tmp)
      );
    }

    pivot_inverse =
        gf_inv(
            augmented[column][column]
        );

    for(
        position = 0u;
        position < (uint8_t)(size * 2u);
        position++
    ) {
      augmented[column][position] =
          gf_mul(
              augmented[column][position],
              pivot_inverse
          );
    }

    for(row = 0u; row < size; row++) {
      uint8_t factor;

      if(row == column) {
        continue;
      }

      factor =
          augmented[row][column];

      if(factor == 0u) {
        continue;
      }

      for(
          position = 0u;
          position < (uint8_t)(size * 2u);
          position++
      ) {
        augmented[row][position] ^=
            gf_mul(
                factor,
                augmented[column][position]
            );
      }
    }
  }

  for(row = 0u; row < size; row++) {
    for(column = 0u; column < size; column++) {
      inverse[
          (size_t)row * size
          + column
      ] =
          augmented[
              row
          ][
              size + column
          ];
    }
  }

  return 0;
}


size_t
ranger_rs_shard_size(
    size_t payload_len,
    uint8_t k
)
{
  if(payload_len == 0u || k == 0u) {
    return 0u;
  }

  return (
      payload_len
      + (size_t)k
      - 1u
  ) / (size_t)k;
}


int
ranger_rs_build_generator(
    uint8_t k,
    uint8_t n,
    uint8_t *generator
)
{
  uint8_t vandermonde[
      RANGER_RS_MAX_N
      * RANGER_RS_MAX_K
  ];

  uint8_t first_square[
      RANGER_RS_MAX_K
      * RANGER_RS_MAX_K
  ];

  uint8_t transform[
      RANGER_RS_MAX_K
      * RANGER_RS_MAX_K
  ];

  uint8_t row;
  uint8_t column;
  int rc;

  if(
      generator == NULL ||
      k == 0u ||
      n < k ||
      k > RANGER_RS_MAX_K ||
      n > RANGER_RS_MAX_N
  ) {
    return -1;
  }

  for(row = 0u; row < n; row++) {
    for(column = 0u; column < k; column++) {
      vandermonde[
          (size_t)row * k
          + column
      ] =
          gf_pow(
              (uint8_t)(row + 1u),
              column
          );
    }
  }

  for(row = 0u; row < k; row++) {
    for(column = 0u; column < k; column++) {
      first_square[
          (size_t)row * k
          + column
      ] =
          vandermonde[
              (size_t)row * k
              + column
          ];
    }
  }

  rc = matrix_inverse(
      first_square,
      k,
      transform
  );

  if(rc != 0) {
    return rc;
  }

  for(row = 0u; row < n; row++) {
    uint8_t output_column;

    for(
        output_column = 0u;
        output_column < k;
        output_column++
    ) {
      uint8_t value = 0u;

      for(
          column = 0u;
          column < k;
          column++
      ) {
        value ^=
            gf_mul(
                vandermonde[
                    (size_t)row * k
                    + column
                ],
                transform[
                    (size_t)column * k
                    + output_column
                ]
            );
      }

      generator[
          (size_t)row * k
          + output_column
      ] = value;
    }
  }

  return 0;
}


int
ranger_rs_encode(
    uint8_t k,
    uint8_t n,
    const uint8_t *payload,
    size_t payload_len,
    uint8_t *shards,
    size_t shard_size
)
{
  uint8_t generator[
      RANGER_RS_MAX_N
      * RANGER_RS_MAX_K
  ];

  uint8_t shard_index;
  int rc;

  if(
      payload == NULL ||
      shards == NULL ||
      payload_len == 0u ||
      shard_size
          != ranger_rs_shard_size(
              payload_len,
              k
          )
  ) {
    return -1;
  }

  rc = ranger_rs_build_generator(
      k,
      n,
      generator
  );

  if(rc != 0) {
    return rc;
  }

  for(
      shard_index = 0u;
      shard_index < n;
      shard_index++
  ) {
    size_t byte_index;

    for(
        byte_index = 0u;
        byte_index < shard_size;
        byte_index++
    ) {
      uint8_t value = 0u;
      uint8_t data_index;

      for(
          data_index = 0u;
          data_index < k;
          data_index++
      ) {
        size_t payload_index =
            (size_t)data_index
            * shard_size
            + byte_index;

        uint8_t input_byte =
            payload_index < payload_len
            ? payload[payload_index]
            : 0u;

        value ^=
            gf_mul(
                generator[
                    (size_t)shard_index
                    * k
                    + data_index
                ],
                input_byte
            );
      }

      shards[
          (size_t)shard_index
          * shard_size
          + byte_index
      ] = value;
    }
  }

  return 0;
}


int
ranger_rs_decode(
    uint8_t k,
    uint8_t n,
    const uint8_t *indices,
    const uint8_t *selected_shards,
    size_t shard_size,
    size_t original_len,
    uint8_t *payload_out
)
{
  uint8_t generator[
      RANGER_RS_MAX_N
      * RANGER_RS_MAX_K
  ];

  uint8_t selected_matrix[
      RANGER_RS_MAX_K
      * RANGER_RS_MAX_K
  ];

  uint8_t inverse[
      RANGER_RS_MAX_K
      * RANGER_RS_MAX_K
  ];

  uint8_t row;
  int rc;

  if(
      indices == NULL ||
      selected_shards == NULL ||
      payload_out == NULL ||
      k == 0u ||
      n < k ||
      k > RANGER_RS_MAX_K ||
      n > RANGER_RS_MAX_N ||
      shard_size == 0u ||
      original_len == 0u ||
      original_len
          > (size_t)k * shard_size
  ) {
    return -1;
  }

  for(row = 0u; row < k; row++) {
    uint8_t other;

    if(indices[row] >= n) {
      return -1;
    }

    for(other = 0u; other < row; other++) {
      if(indices[row] == indices[other]) {
        return -1;
      }
    }
  }

  rc = ranger_rs_build_generator(
      k,
      n,
      generator
  );

  if(rc != 0) {
    return rc;
  }

  for(row = 0u; row < k; row++) {
    uint8_t column;

    for(column = 0u; column < k; column++) {
      selected_matrix[
          (size_t)row * k
          + column
      ] =
          generator[
              (size_t)indices[row]
              * k
              + column
          ];
    }
  }

  rc = matrix_inverse(
      selected_matrix,
      k,
      inverse
  );

  if(rc != 0) {
    return rc;
  }

  memset(
      payload_out,
      0,
      original_len
  );

  for(row = 0u; row < k; row++) {
    size_t byte_index;

    for(
        byte_index = 0u;
        byte_index < shard_size;
        byte_index++
    ) {
      size_t payload_index =
          (size_t)row
          * shard_size
          + byte_index;

      uint8_t value = 0u;
      uint8_t selected_index;

      if(payload_index >= original_len) {
        continue;
      }

      for(
          selected_index = 0u;
          selected_index < k;
          selected_index++
      ) {
        value ^=
            gf_mul(
                inverse[
                    (size_t)row
                    * k
                    + selected_index
                ],
                selected_shards[
                    (size_t)selected_index
                    * shard_size
                    + byte_index
                ]
            );
      }

      payload_out[
          payload_index
      ] = value;
    }
  }

  return 0;
}
