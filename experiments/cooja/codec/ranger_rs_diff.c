#include "ranger_rs_codec.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LINE_CAPACITY 32768u


typedef struct {
  uint8_t k;
  uint8_t n;

  const uint8_t *all_shards;

  size_t shard_size;

  const uint8_t *payload;
  size_t payload_len;

  uint8_t indices[
      RANGER_RS_MAX_K
  ];

  uint8_t *selected;
  uint8_t *decoded;

  unsigned long count;

  int failed;
} subset_context_t;


static int
hex_value(char value)
{
  if(value >= '0' && value <= '9') {
    return value - '0';
  }

  if(value >= 'a' && value <= 'f') {
    return value - 'a' + 10;
  }

  if(value >= 'A' && value <= 'F') {
    return value - 'A' + 10;
  }

  return -1;
}


static int
hex_decode(
    const char *text,
    uint8_t *output,
    size_t expected_len
)
{
  size_t index;

  if(
      text == NULL ||
      output == NULL ||
      strlen(text)
          != expected_len * 2u
  ) {
    return -1;
  }

  for(
      index = 0u;
      index < expected_len;
      index++
  ) {
    int high =
        hex_value(
            text[index * 2u]
        );

    int low =
        hex_value(
            text[index * 2u + 1u]
        );

    if(high < 0 || low < 0) {
      return -1;
    }

    output[index] =
        (uint8_t)(
            (high << 4)
            | low
        );
  }

  return 0;
}


static void
hex_write(
    FILE *stream,
    const uint8_t *data,
    size_t length
)
{
  static const char digits[] =
      "0123456789abcdef";

  size_t index;

  for(index = 0u; index < length; index++) {
    fputc(
        digits[
            data[index] >> 4
        ],
        stream
    );

    fputc(
        digits[
            data[index] & 0x0fu
        ],
        stream
    );
  }
}


static char *
next_field(char **cursor)
{
  char *start;
  char *separator;

  if(
      cursor == NULL ||
      *cursor == NULL
  ) {
    return NULL;
  }

  start = *cursor;

  separator =
      strchr(
          start,
          '\t'
      );

  if(separator == NULL) {
    *cursor = NULL;
  } else {
    *separator = '\0';
    *cursor = separator + 1;
  }

  return start;
}


static void
subset_recurse(
    subset_context_t *context,
    uint8_t depth,
    uint8_t start
)
{
  uint8_t candidate;

  if(context->failed) {
    return;
  }

  if(depth == context->k) {
    uint8_t selected_index;
    int rc;

    for(
        selected_index = 0u;
        selected_index < context->k;
        selected_index++
    ) {
      memcpy(
          context->selected
              + (size_t)selected_index
                * context->shard_size,

          context->all_shards
              + (size_t)context
                    ->indices[
                        selected_index
                    ]
                * context->shard_size,

          context->shard_size
      );
    }

    rc =
        ranger_rs_decode(
            context->k,
            context->n,
            context->indices,
            context->selected,
            context->shard_size,
            context->payload_len,
            context->decoded
        );

    context->count++;

    if(
        rc != 0 ||
        memcmp(
            context->decoded,
            context->payload,
            context->payload_len
        ) != 0
    ) {
      context->failed = 1;
    }

    return;
  }

  for(
      candidate = start;
      candidate
          <= (uint8_t)(
              context->n
              - (
                  context->k
                  - depth
              )
          );
      candidate++
  ) {
    context->indices[
        depth
    ] = candidate;

    subset_recurse(
        context,
        (uint8_t)(depth + 1u),
        (uint8_t)(candidate + 1u)
    );

    if(context->failed) {
      return;
    }
  }
}


static int
test_all_subsets(
    uint8_t k,
    uint8_t n,
    const uint8_t *all_shards,
    size_t shard_size,
    const uint8_t *payload,
    size_t payload_len,
    unsigned long *count_out
)
{
  subset_context_t context;

  memset(
      &context,
      0,
      sizeof(context)
  );

  context.k = k;
  context.n = n;
  context.all_shards = all_shards;
  context.shard_size = shard_size;
  context.payload = payload;
  context.payload_len = payload_len;

  context.selected =
      malloc(
          (size_t)k
          * shard_size
      );

  context.decoded =
      malloc(
          payload_len
      );

  if(
      context.selected == NULL ||
      context.decoded == NULL
  ) {
    free(context.selected);
    free(context.decoded);

    return -1;
  }

  subset_recurse(
      &context,
      0u,
      0u
  );

  *count_out =
      context.count;

  free(context.selected);
  free(context.decoded);

  return context.failed
      ? -2
      : 0;
}


static int
parse_expected_shards(
    const char *field,
    uint8_t n,
    size_t shard_size,
    uint8_t *output
)
{
  char *copy;
  char *token;

  uint8_t index = 0u;

  copy =
      malloc(
          strlen(field) + 1u
      );

  if(copy == NULL) {
    return -1;
  }

  strcpy(
      copy,
      field
  );

  token =
      strtok(
          copy,
          ","
      );

  while(token != NULL) {
    if(
        index >= n ||
        hex_decode(
            token,
            output
                + (size_t)index
                  * shard_size,
            shard_size
        ) != 0
    ) {
      free(copy);
      return -1;
    }

    index++;

    token =
        strtok(
            NULL,
            ","
        );
  }

  free(copy);

  return index == n
      ? 0
      : -1;
}


int
main(
    int argc,
    char **argv
)
{
  FILE *input;
  FILE *output;

  char line[
      LINE_CAPACITY
  ];

  unsigned long vector_count = 0u;

  int any_failure = 0;

  if(argc != 3) {
    fprintf(
        stderr,
        "usage: %s VECTORS.tsv RESULTS.tsv\n",
        argv[0]
    );

    return 2;
  }

  input =
      fopen(
          argv[1],
          "r"
      );

  if(input == NULL) {
    perror("vectors");
    return 2;
  }

  output =
      fopen(
          argv[2],
          "w"
      );

  if(output == NULL) {
    perror("results");

    fclose(input);

    return 2;
  }

  fprintf(
      output,
      "vector_id\t"
      "k\t"
      "n\t"
      "matrix_match\t"
      "encode_match\t"
      "c_decode_subset_count\t"
      "c_decode_all_match\t"
      "python_shard_decode_count\t"
      "python_shard_decode_all_match\t"
      "actual_generator_hex\t"
      "actual_shards_hex\n"
  );

  if(
      fgets(
          line,
          sizeof(line),
          input
      ) == NULL
  ) {
    fprintf(
        stderr,
        "empty vectors file\n"
    );

    fclose(input);
    fclose(output);

    return 2;
  }

  while(
      fgets(
          line,
          sizeof(line),
          input
      ) != NULL
  ) {
    char *cursor = line;

    char *vector_id;
    char *k_text;
    char *n_text;
    char *payload_hex;
    char *generator_hex;
    char *shards_hex;

    char *end;

    unsigned long parsed_k;
    unsigned long parsed_n;

    uint8_t k;
    uint8_t n;

    size_t payload_len;
    size_t shard_size;
    size_t generator_len;
    size_t shards_len;

    uint8_t *payload;
    uint8_t *expected_generator;
    uint8_t *actual_generator;
    uint8_t *expected_shards;
    uint8_t *actual_shards;

    unsigned long c_decode_count = 0u;

    unsigned long
        python_shard_decode_count = 0u;

    int matrix_match;
    int encode_match;

    int c_decode_ok;
    int python_shard_decode_ok;

    uint8_t shard_index;

    line[
        strcspn(
            line,
            "\r\n"
        )
    ] = '\0';

    if(line[0] == '\0') {
      continue;
    }

    vector_id =
        next_field(
            &cursor
        );

    k_text =
        next_field(
            &cursor
        );

    n_text =
        next_field(
            &cursor
        );

    payload_hex =
        next_field(
            &cursor
        );

    generator_hex =
        next_field(
            &cursor
        );

    shards_hex =
        next_field(
            &cursor
        );

    if(
        vector_id == NULL ||
        k_text == NULL ||
        n_text == NULL ||
        payload_hex == NULL ||
        generator_hex == NULL ||
        shards_hex == NULL ||
        cursor != NULL
    ) {
      fprintf(
          stderr,
          "malformed vector line %lu\n",
          vector_count + 2u
      );

      any_failure = 1;
      break;
    }

    parsed_k =
        strtoul(
            k_text,
            &end,
            10
        );

    if(
        *k_text == '\0' ||
        *end != '\0' ||
        parsed_k > RANGER_RS_MAX_K
    ) {
      fprintf(
          stderr,
          "invalid k for %s\n",
          vector_id
      );

      any_failure = 1;
      break;
    }

    parsed_n =
        strtoul(
            n_text,
            &end,
            10
        );

    if(
        *n_text == '\0' ||
        *end != '\0' ||
        parsed_n > RANGER_RS_MAX_N
    ) {
      fprintf(
          stderr,
          "invalid n for %s\n",
          vector_id
      );

      any_failure = 1;
      break;
    }

    k =
        (uint8_t)parsed_k;

    n =
        (uint8_t)parsed_n;

    if(
        k == 0u ||
        n < k ||
        (
            strlen(
                payload_hex
            )
            & 1u
        ) != 0u
    ) {
      fprintf(
          stderr,
          "invalid vector dimensions for %s\n",
          vector_id
      );

      any_failure = 1;
      break;
    }

    payload_len =
        strlen(
            payload_hex
        ) / 2u;

    shard_size =
        ranger_rs_shard_size(
            payload_len,
            k
        );

    generator_len =
        (size_t)n
        * k;

    shards_len =
        (size_t)n
        * shard_size;

    payload =
        malloc(
            payload_len
        );

    expected_generator =
        malloc(
            generator_len
        );

    actual_generator =
        malloc(
            generator_len
        );

    expected_shards =
        malloc(
            shards_len
        );

    actual_shards =
        malloc(
            shards_len
        );

    if(
        payload == NULL ||
        expected_generator == NULL ||
        actual_generator == NULL ||
        expected_shards == NULL ||
        actual_shards == NULL
    ) {
      fprintf(
          stderr,
          "allocation failure for %s\n",
          vector_id
      );

      free(payload);
      free(expected_generator);
      free(actual_generator);
      free(expected_shards);
      free(actual_shards);

      any_failure = 1;
      break;
    }

    if(
        hex_decode(
            payload_hex,
            payload,
            payload_len
        ) != 0 ||

        hex_decode(
            generator_hex,
            expected_generator,
            generator_len
        ) != 0 ||

        parse_expected_shards(
            shards_hex,
            n,
            shard_size,
            expected_shards
        ) != 0 ||

        ranger_rs_build_generator(
            k,
            n,
            actual_generator
        ) != 0 ||

        ranger_rs_encode(
            k,
            n,
            payload,
            payload_len,
            actual_shards,
            shard_size
        ) != 0
    ) {
      fprintf(
          stderr,
          "vector setup failure for %s\n",
          vector_id
      );

      free(payload);
      free(expected_generator);
      free(actual_generator);
      free(expected_shards);
      free(actual_shards);

      any_failure = 1;
      break;
    }

    matrix_match =
        memcmp(
            expected_generator,
            actual_generator,
            generator_len
        ) == 0;

    encode_match =
        memcmp(
            expected_shards,
            actual_shards,
            shards_len
        ) == 0;

    c_decode_ok =
        test_all_subsets(
            k,
            n,
            actual_shards,
            shard_size,
            payload,
            payload_len,
            &c_decode_count
        ) == 0;

    /*
     * Critical cross-language direction:
     *
     * C decoder consumes shards generated by
     * the Python implementation.
     */
    python_shard_decode_ok =
        test_all_subsets(
            k,
            n,
            expected_shards,
            shard_size,
            payload,
            payload_len,
            &python_shard_decode_count
        ) == 0;

    fprintf(
        output,
        "%s\t%u\t%u\t"
        "%d\t%d\t"
        "%lu\t%d\t"
        "%lu\t%d\t",
        vector_id,
        k,
        n,
        matrix_match,
        encode_match,
        c_decode_count,
        c_decode_ok,
        python_shard_decode_count,
        python_shard_decode_ok
    );

    hex_write(
        output,
        actual_generator,
        generator_len
    );

    fputc(
        '\t',
        output
    );

    for(
        shard_index = 0u;
        shard_index < n;
        shard_index++
    ) {
      if(shard_index != 0u) {
        fputc(
            ',',
            output
        );
      }

      hex_write(
          output,
          actual_shards
              + (size_t)shard_index
                * shard_size,
          shard_size
      );
    }

    fputc(
        '\n',
        output
    );

    if(
        !matrix_match ||
        !encode_match ||
        !c_decode_ok ||
        !python_shard_decode_ok
    ) {
      any_failure = 1;
    }

    vector_count++;

    free(payload);
    free(expected_generator);
    free(actual_generator);
    free(expected_shards);
    free(actual_shards);
  }

  fclose(input);
  fclose(output);

  fprintf(
      stderr,
      "vectors=%lu verdict=%s\n",
      vector_count,
      any_failure
          ? "FAIL"
          : "PASS"
  );

  return any_failure
      ? 1
      : 0;
}
