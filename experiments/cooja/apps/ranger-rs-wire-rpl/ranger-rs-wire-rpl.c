/*
 * RANGER-IoT — STEP 7C.3
 *
 * Real byte-level Reed-Solomon shards over multi-hop RPL.
 *
 * This is an isolated scientific validation application.
 * It does not replace the historical STEP 7A/7B applications.
 *
 * Node 1    : Group Manager / RPL root
 * Nodes 2-7 : authorized members
 * Node 8    : revoked member
 *
 * RS profile:
 *   GF(256), primitive polynomial 0x11D
 *   k = 3
 *   n = 5
 *   payload = 16 bytes
 *   shard   = 6 bytes
 */

#include "contiki.h"

#include "net/ipv6/simple-udp.h"
#include "net/netstack.h"
#include "net/routing/routing.h"

#include "sys/etimer.h"
#include "sys/log.h"
#include "sys/node-id.h"

#include "ranger_rs_codec.h"

#include <stdint.h>
#include <string.h>


#define LOG_MODULE "RANGER-RS"
#define LOG_LEVEL LOG_LEVEL_INFO


#ifndef RANGER_RS_WIRE_MODE
#define RANGER_RS_WIRE_MODE 0
#endif


#if RANGER_RS_WIRE_MODE != 0 && RANGER_RS_WIRE_MODE != 1
#error "RANGER_RS_WIRE_MODE must be 0 or 1"
#endif


#define RANGER_PORT 4243

#define RANGER_GM_ID 1
#define RANGER_FIRST_MEMBER_ID 2
#define RANGER_LAST_MEMBER_ID 8
#define RANGER_REVOKED_ID 8
#define RANGER_MEMBER_COUNT 7

#define RANGER_GROUP_ID 1

#define RANGER_RS_K 3
#define RANGER_RS_N 5

#define RANGER_PAYLOAD_BYTES 16
#define RANGER_SHARD_BYTES 6

#define RANGER_RS_HEADER_BYTES 12
#define RANGER_RS_PACKET_BYTES \
  (RANGER_RS_HEADER_BYTES + RANGER_SHARD_BYTES)

#define MSG_REGISTER 1
#define MSG_RS_FRAGMENT 2
#define MSG_REPORT 3
#define MSG_FINALIZE 4

#define STATUS_ACCEPT 1
#define STATUS_REJECT 2
#define STATUS_BELOW_K 3
#define STATUS_BAD 4

#define REGISTER_INTERVAL \
  (10 * CLOCK_SECOND)

#define FIRST_REGISTER_DELAY \
  (8 * CLOCK_SECOND)

#define FRAGMENT_SPACING \
  (CLOCK_SECOND)

#define FINALIZE_SETTLE \
  (5 * CLOCK_SECOND)

#define FINALIZE_SPACING \
  (CLOCK_SECOND)


static const uint8_t ranger_payload[
    RANGER_PAYLOAD_BYTES
] = {
    'R', 'A', 'N', 'G', 'E', 'R', '-', 'R',
    'S', '-', 'E', 'P', 'O', 'C', 'H', '1'
};


static struct simple_udp_connection udp_conn;


static uip_ipaddr_t member_addr[
    RANGER_LAST_MEMBER_ID + 1
];

static uint8_t member_registered[
    RANGER_LAST_MEMBER_ID + 1
];

static uint8_t report_seen[
    RANGER_LAST_MEMBER_ID + 1
];

static uint8_t report_fragment_mask[
    RANGER_LAST_MEMBER_ID + 1
];


static uint8_t registered_count;
static uint8_t accepted_count;
static uint8_t rejected_count;
static uint8_t below_k_count;
static uint8_t bad_count;
static uint8_t report_count;


static uint16_t accepted_mask;
static uint16_t rejected_mask;
static uint16_t below_k_mask;


static uint8_t rekey_scheduled;
static uint8_t final_result_printed;

static uint8_t next_target;
static uint8_t next_shard;
static uint8_t tx_phase;

static uint16_t current_epoch;


static uint8_t encoded_shards[
    RANGER_RS_N * RANGER_SHARD_BYTES
];


static uint8_t received_shards[
    RANGER_RS_N
][
    RANGER_SHARD_BYTES
];

static uint8_t received_fragment_mask;
static uint8_t received_fragment_count;

static uint16_t pending_epoch;

static uint8_t member_done;


PROCESS(
    ranger_rs_wire_process,
    "RANGER real RS wire validation"
);

AUTOSTART_PROCESSES(
    &ranger_rs_wire_process
);


#if RANGER_RS_WIRE_MODE == 0
static uint8_t
ranger_popcount(uint8_t value)
{
  uint8_t count = 0u;

  while(value != 0u) {
    count += (uint8_t)(
        value & 1u
    );

    value >>= 1;
  }

  return count;
}
#endif


static uint8_t
ranger_send_mask(uint8_t target)
{
#if RANGER_RS_WIRE_MODE == 0

  (void)target;

  return 0x1fu;

#else

  switch(target) {
  case 2:
    return 0x07u; /* {0,1,2} */

  case 3:
    return 0x0bu; /* {0,1,3} */

  case 4:
    return 0x13u; /* {0,1,4} */

  case 5:
    return 0x0du; /* {0,2,3} */

  case 6:
    return 0x1au; /* {1,3,4} */

  case 7:
    return 0x03u; /* only two shards */

  case 8:
    return 0x01u; /* revoked: one shard is sufficient */

  default:
    return 0u;
  }

#endif
}


#if RANGER_RS_WIRE_MODE == 1
static uint8_t
ranger_expected_report_mask(
    uint8_t member_id)
{
  if(member_id == RANGER_REVOKED_ID) {
    return 0u;
  }

#if RANGER_RS_WIRE_MODE == 0

  /*
   * Reconstruction happens immediately after
   * the first three distinct successfully
   * received shards. Their exact identities
   * are not assumed by the no-loss oracle.
   */
  return 0xffu;

#else

  return ranger_send_mask(
      member_id
  );

#endif
}
#endif


static void
ranger_send_register(void)
{
  static uip_ipaddr_t root_addr;

  uint8_t packet[2];


  if(
      !NETSTACK_ROUTING
          .node_is_reachable()
  ) {
    return;
  }


  if(
      !NETSTACK_ROUTING
          .get_root_ipaddr(
              &root_addr
          )
  ) {
    return;
  }


  packet[0] =
      MSG_REGISTER;

  packet[1] =
      (uint8_t)node_id;


  simple_udp_sendto(
      &udp_conn,
      packet,
      sizeof(packet),
      &root_addr
  );


  LOG_INFO(
      "RANGER_RS_WIRE_REGISTER_SENT "
      "node=%u\n",
      (unsigned int)node_id
  );
}


static void
ranger_send_report(
    const uip_ipaddr_t *root_addr,
    uint16_t epoch,
    uint8_t status,
    uint8_t fragment_mask)
{
  uint8_t packet[6];


  packet[0] =
      MSG_REPORT;

  packet[1] =
      (uint8_t)node_id;

  packet[2] =
      (uint8_t)(
          epoch >> 8
      );

  packet[3] =
      (uint8_t)(
          epoch & 0xffu
      );

  packet[4] =
      status;

  packet[5] =
      fragment_mask;


  simple_udp_sendto(
      &udp_conn,
      packet,
      sizeof(packet),
      root_addr
  );


  LOG_INFO(
      "RANGER_RS_WIRE_REPORT_SENT "
      "node=%u status=%u mask=%u "
      "mode=%u\n",
      (unsigned int)node_id,
      (unsigned int)status,
      (unsigned int)fragment_mask,
      (unsigned int)RANGER_RS_WIRE_MODE
  );
}


static void
ranger_handle_register(
    const uip_ipaddr_t *sender_addr,
    const uint8_t *data,
    uint16_t datalen)
{
  uint8_t member_id;


  if(
      node_id != RANGER_GM_ID ||
      datalen != 2u
  ) {
    return;
  }


  member_id =
      data[1];


  if(
      member_id
          < RANGER_FIRST_MEMBER_ID ||
      member_id
          > RANGER_LAST_MEMBER_ID
  ) {
    return;
  }


  if(
      !member_registered[
          member_id
      ]
  ) {
    member_registered[
        member_id
    ] = 1u;

    registered_count++;


    LOG_INFO(
        "RANGER_RS_WIRE_REGISTER "
        "node=%u registered=%u/%u "
        "mode=%u\n",
        (unsigned int)member_id,
        (unsigned int)registered_count,
        (unsigned int)RANGER_MEMBER_COUNT,
        (unsigned int)RANGER_RS_WIRE_MODE
    );
  }


  uip_ipaddr_copy(
      &member_addr[
          member_id
      ],
      sender_addr
  );


  if(
      registered_count
          == RANGER_MEMBER_COUNT &&
      !rekey_scheduled
  ) {
    process_poll(
        &ranger_rs_wire_process
    );
  }
}


static void
ranger_log_send(
    uint8_t target,
    uint8_t shard_index,
    const uint8_t *shard)
{
  LOG_INFO(
      "RANGER_RS_WIRE_SEND "
      "target=%u shard=%u "
      "packet_bytes=%u "
      "data=%02x%02x%02x%02x%02x%02x "
      "mode=%u\n",
      (unsigned int)target,
      (unsigned int)shard_index,
      (unsigned int)RANGER_RS_PACKET_BYTES,
      (unsigned int)shard[0],
      (unsigned int)shard[1],
      (unsigned int)shard[2],
      (unsigned int)shard[3],
      (unsigned int)shard[4],
      (unsigned int)shard[5],
      (unsigned int)RANGER_RS_WIRE_MODE
  );
}


static void
ranger_log_rx(
    uint8_t shard_index,
    const uint8_t *shard)
{
  LOG_INFO(
      "RANGER_RS_WIRE_RX "
      "node=%u shard=%u "
      "packet_bytes=%u "
      "data=%02x%02x%02x%02x%02x%02x "
      "mode=%u\n",
      (unsigned int)node_id,
      (unsigned int)shard_index,
      (unsigned int)RANGER_RS_PACKET_BYTES,
      (unsigned int)shard[0],
      (unsigned int)shard[1],
      (unsigned int)shard[2],
      (unsigned int)shard[3],
      (unsigned int)shard[4],
      (unsigned int)shard[5],
      (unsigned int)RANGER_RS_WIRE_MODE
  );
}


static void
ranger_handle_fragment(
    const uip_ipaddr_t *sender_addr,
    const uint8_t *data,
    uint16_t datalen)
{
  uint16_t epoch;

  uint8_t fragment_index;
  uint8_t fragment_bit;

  uint8_t indices[
      RANGER_RS_K
  ];

  uint8_t selected[
      RANGER_RS_K
      * RANGER_SHARD_BYTES
  ];

  uint8_t recovered[
      RANGER_PAYLOAD_BYTES
  ];

  uint8_t selected_count = 0u;
  uint8_t scan;

  int decode_rc;


  if(
      node_id == RANGER_GM_ID ||
      member_done ||
      datalen
          != RANGER_RS_PACKET_BYTES
  ) {
    return;
  }


  epoch =
      (
          (uint16_t)data[3]
          << 8
      )
      |
      (uint16_t)data[4];


  fragment_index =
      data[6];


  if(
      data[1] != RANGER_GM_ID ||
      data[2] != RANGER_GROUP_ID ||
      data[5] != RANGER_REVOKED_ID ||
      data[7] != RANGER_RS_K ||
      data[8] != RANGER_RS_N ||
      data[9] != RANGER_PAYLOAD_BYTES ||
      data[10] != RANGER_SHARD_BYTES ||
      data[11] != RANGER_RS_WIRE_MODE ||
      fragment_index >= RANGER_RS_N
  ) {
    return;
  }


  ranger_log_rx(
      fragment_index,
      &data[
          RANGER_RS_HEADER_BYTES
      ]
  );


  if(
      node_id == RANGER_REVOKED_ID
  ) {
    member_done = 1u;


    LOG_INFO(
        "RANGER_RS_WIRE_REJECT "
        "node=%u shard=%u "
        "mode=%u\n",
        (unsigned int)node_id,
        (unsigned int)fragment_index,
        (unsigned int)RANGER_RS_WIRE_MODE
    );


    ranger_send_report(
        sender_addr,
        epoch,
        STATUS_REJECT,
        0u
    );

    return;
  }


  if(pending_epoch == 0u) {
    pending_epoch = epoch;
  }


  if(
      epoch != pending_epoch
  ) {
    return;
  }


  fragment_bit =
      (uint8_t)(
          1u
          << fragment_index
      );


  if(
      (
          received_fragment_mask
          & fragment_bit
      )
      != 0u
  ) {
    return;
  }


  memcpy(
      received_shards[
          fragment_index
      ],
      &data[
          RANGER_RS_HEADER_BYTES
      ],
      RANGER_SHARD_BYTES
  );


  received_fragment_mask |=
      fragment_bit;

  received_fragment_count++;


  if(
      received_fragment_count
          < RANGER_RS_K
  ) {
    return;
  }


  for(
      scan = 0u;
      scan < RANGER_RS_N &&
      selected_count < RANGER_RS_K;
      scan++
  ) {
    if(
        (
            received_fragment_mask
            & (
                (uint8_t)(
                    1u << scan
                )
            )
        )
        == 0u
    ) {
      continue;
    }


    indices[
        selected_count
    ] = scan;


    memcpy(
        &selected[
            (size_t)selected_count
            * RANGER_SHARD_BYTES
        ],
        received_shards[
            scan
        ],
        RANGER_SHARD_BYTES
    );


    selected_count++;
  }


  decode_rc =
      ranger_rs_decode(
          RANGER_RS_K,
          RANGER_RS_N,
          indices,
          selected,
          RANGER_SHARD_BYTES,
          RANGER_PAYLOAD_BYTES,
          recovered
      );


  if(
      decode_rc != 0 ||
      memcmp(
          recovered,
          ranger_payload,
          RANGER_PAYLOAD_BYTES
      ) != 0
  ) {
    member_done = 1u;


    LOG_ERR(
        "RANGER_RS_WIRE_BAD "
        "node=%u rc=%d mask=%u "
        "mode=%u\n",
        (unsigned int)node_id,
        decode_rc,
        (unsigned int)received_fragment_mask,
        (unsigned int)RANGER_RS_WIRE_MODE
    );


    ranger_send_report(
        sender_addr,
        epoch,
        STATUS_BAD,
        received_fragment_mask
    );

    return;
  }


  member_done = 1u;
  current_epoch = epoch;


  LOG_INFO(
      "RANGER_RS_WIRE_RECONSTRUCT "
      "node=%u mode=%u mask=%u "
      "payload_match=1\n",
      (unsigned int)node_id,
      (unsigned int)RANGER_RS_WIRE_MODE,
      (unsigned int)received_fragment_mask
  );


  ranger_send_report(
      sender_addr,
      epoch,
      STATUS_ACCEPT,
      received_fragment_mask
  );
}


static void
ranger_handle_finalize(
    const uip_ipaddr_t *sender_addr,
    const uint8_t *data,
    uint16_t datalen)
{
  uint16_t epoch;


  if(
      node_id == RANGER_GM_ID ||
      member_done ||
      datalen != 4u
  ) {
    return;
  }


  epoch =
      (
          (uint16_t)data[1]
          << 8
      )
      |
      (uint16_t)data[2];


  if(
      data[3]
          != RANGER_RS_WIRE_MODE
  ) {
    return;
  }


  if(
      node_id
          == RANGER_REVOKED_ID
  ) {
    member_done = 1u;


    LOG_ERR(
        "RANGER_RS_WIRE_BAD "
        "node=%u reason=revoked-no-shard "
        "mode=%u\n",
        (unsigned int)node_id,
        (unsigned int)RANGER_RS_WIRE_MODE
    );


    ranger_send_report(
        sender_addr,
        epoch,
        STATUS_BAD,
        0u
    );

    return;
  }


  member_done = 1u;


  LOG_INFO(
      "RANGER_RS_WIRE_BELOW_K "
      "node=%u unique=%u mask=%u "
      "mode=%u\n",
      (unsigned int)node_id,
      (unsigned int)received_fragment_count,
      (unsigned int)received_fragment_mask,
      (unsigned int)RANGER_RS_WIRE_MODE
  );


  ranger_send_report(
      sender_addr,
      epoch,
      STATUS_BELOW_K,
      received_fragment_mask
  );
}


static void
ranger_finish_root(uint16_t epoch)
{
  uint8_t member_id;
  uint8_t masks_ok = 1u;

  uint16_t expected_accept_mask;
  uint16_t expected_below_mask;


#if RANGER_RS_WIRE_MODE == 0

  expected_accept_mask =
      0x00fcu;

  expected_below_mask =
      0x0000u;

#else

  expected_accept_mask =
      0x007cu;

  expected_below_mask =
      0x0080u;

#endif


  if(final_result_printed) {
    return;
  }


  final_result_printed = 1u;


  for(
      member_id =
          RANGER_FIRST_MEMBER_ID;
      member_id <
          RANGER_REVOKED_ID;
      member_id++
  ) {

#if RANGER_RS_WIRE_MODE == 0

    if(
        ranger_popcount(
            report_fragment_mask[
                member_id
            ]
        )
        != RANGER_RS_K
    ) {
      masks_ok = 0u;
    }

#else

    if(
        report_fragment_mask[
            member_id
        ]
        != ranger_expected_report_mask(
            member_id
        )
    ) {
      masks_ok = 0u;
    }

#endif

  }


  if(
      report_fragment_mask[
          RANGER_REVOKED_ID
      ]
      != 0u
  ) {
    masks_ok = 0u;
  }


  if(masks_ok) {
    LOG_INFO(
        "RANGER_RS_WIRE_MASK_PASS "
        "mode=%u\n",
        (unsigned int)RANGER_RS_WIRE_MODE
    );
  } else {
    LOG_ERR(
        "RANGER_RS_WIRE_MASK_FAIL "
        "mode=%u\n",
        (unsigned int)RANGER_RS_WIRE_MODE
    );
  }


  if(
      registered_count
          == RANGER_MEMBER_COUNT &&
      report_count
          == RANGER_MEMBER_COUNT &&
      accepted_mask
          == expected_accept_mask &&
      rejected_mask
          == 0x0100u &&
      below_k_mask
          == expected_below_mask &&
      bad_count == 0u &&
      masks_ok
  ) {
    LOG_INFO(
        "RANGER_RS_WIRE_CORE_PASS "
        "mode=%u epoch=%u "
        "registered=%u "
        "accepted=%u rejected=%u "
        "below=%u bad=%u reports=%u\n",
        (unsigned int)RANGER_RS_WIRE_MODE,
        (unsigned int)epoch,
        (unsigned int)registered_count,
        (unsigned int)accepted_count,
        (unsigned int)rejected_count,
        (unsigned int)below_k_count,
        (unsigned int)bad_count,
        (unsigned int)report_count
    );
  } else {
    LOG_ERR(
        "RANGER_RS_WIRE_CORE_FAIL "
        "mode=%u epoch=%u "
        "registered=%u "
        "accepted=%u rejected=%u "
        "below=%u bad=%u reports=%u "
        "accepted_mask=%u "
        "rejected_mask=%u "
        "below_mask=%u\n",
        (unsigned int)RANGER_RS_WIRE_MODE,
        (unsigned int)epoch,
        (unsigned int)registered_count,
        (unsigned int)accepted_count,
        (unsigned int)rejected_count,
        (unsigned int)below_k_count,
        (unsigned int)bad_count,
        (unsigned int)report_count,
        (unsigned int)accepted_mask,
        (unsigned int)rejected_mask,
        (unsigned int)below_k_mask
    );
  }
}


static void
ranger_handle_report(
    const uint8_t *data,
    uint16_t datalen)
{
  uint8_t member_id;
  uint16_t epoch;
  uint8_t status;


  if(
      node_id != RANGER_GM_ID ||
      datalen != 6u
  ) {
    return;
  }


  member_id =
      data[1];

  epoch =
      (
          (uint16_t)data[2]
          << 8
      )
      |
      (uint16_t)data[3];

  status =
      data[4];


  if(
      member_id
          < RANGER_FIRST_MEMBER_ID ||
      member_id
          > RANGER_LAST_MEMBER_ID ||
      report_seen[
          member_id
      ]
  ) {
    return;
  }


  report_seen[
      member_id
  ] = 1u;

  report_fragment_mask[
      member_id
  ] = data[5];

  report_count++;


  switch(status) {
  case STATUS_ACCEPT:

    accepted_count++;

    accepted_mask |=
        (uint16_t)(
            1u << member_id
        );

    break;


  case STATUS_REJECT:

    rejected_count++;

    rejected_mask |=
        (uint16_t)(
            1u << member_id
        );

    break;


  case STATUS_BELOW_K:

    below_k_count++;

    below_k_mask |=
        (uint16_t)(
            1u << member_id
        );

    break;


  default:

    bad_count++;

    break;
  }


  LOG_INFO(
      "RANGER_RS_WIRE_REPORT "
      "node=%u status=%u mask=%u "
      "reports=%u/%u mode=%u\n",
      (unsigned int)member_id,
      (unsigned int)status,
      (unsigned int)data[5],
      (unsigned int)report_count,
      (unsigned int)RANGER_MEMBER_COUNT,
      (unsigned int)RANGER_RS_WIRE_MODE
  );


  if(
      report_count
          == RANGER_MEMBER_COUNT
  ) {
    ranger_finish_root(
        epoch
    );
  }
}


static void
ranger_udp_rx(
    struct simple_udp_connection *connection,
    const uip_ipaddr_t *sender_addr,
    uint16_t sender_port,
    const uip_ipaddr_t *receiver_addr,
    uint16_t receiver_port,
    const uint8_t *data,
    uint16_t datalen)
{
  (void)connection;
  (void)sender_port;
  (void)receiver_addr;
  (void)receiver_port;


  if(datalen < 1u) {
    return;
  }


  switch(data[0]) {
  case MSG_REGISTER:

    ranger_handle_register(
        sender_addr,
        data,
        datalen
    );

    break;


  case MSG_RS_FRAGMENT:

    ranger_handle_fragment(
        sender_addr,
        data,
        datalen
    );

    break;


  case MSG_REPORT:

    ranger_handle_report(
        data,
        datalen
    );

    break;


  case MSG_FINALIZE:

    ranger_handle_finalize(
        sender_addr,
        data,
        datalen
    );

    break;


  default:
    break;
  }
}


static void
ranger_send_fragment(
    uint8_t target,
    uint8_t shard_index)
{
  uint8_t packet[
      RANGER_RS_PACKET_BYTES
  ];

  const uint8_t *shard =
      &encoded_shards[
          (size_t)shard_index
          * RANGER_SHARD_BYTES
      ];


  packet[0] =
      MSG_RS_FRAGMENT;

  packet[1] =
      RANGER_GM_ID;

  packet[2] =
      RANGER_GROUP_ID;

  packet[3] =
      (uint8_t)(
          current_epoch >> 8
      );

  packet[4] =
      (uint8_t)(
          current_epoch
          & 0xffu
      );

  packet[5] =
      RANGER_REVOKED_ID;

  packet[6] =
      shard_index;

  packet[7] =
      RANGER_RS_K;

  packet[8] =
      RANGER_RS_N;

  packet[9] =
      RANGER_PAYLOAD_BYTES;

  packet[10] =
      RANGER_SHARD_BYTES;

  packet[11] =
      RANGER_RS_WIRE_MODE;


  memcpy(
      &packet[
          RANGER_RS_HEADER_BYTES
      ],
      shard,
      RANGER_SHARD_BYTES
  );


  simple_udp_sendto(
      &udp_conn,
      packet,
      sizeof(packet),
      &member_addr[
          target
      ]
  );


  ranger_log_send(
      target,
      shard_index,
      shard
  );
}


static void
ranger_send_finalize(
    uint8_t target)
{
  uint8_t packet[4];


  packet[0] =
      MSG_FINALIZE;

  packet[1] =
      (uint8_t)(
          current_epoch >> 8
      );

  packet[2] =
      (uint8_t)(
          current_epoch
          & 0xffu
      );

  packet[3] =
      RANGER_RS_WIRE_MODE;


  simple_udp_sendto(
      &udp_conn,
      packet,
      sizeof(packet),
      &member_addr[
          target
      ]
  );


  LOG_INFO(
      "RANGER_RS_WIRE_FINALIZE "
      "target=%u mode=%u\n",
      (unsigned int)target,
      (unsigned int)RANGER_RS_WIRE_MODE
  );
}


PROCESS_THREAD(
    ranger_rs_wire_process,
    ev,
    data)
{
  static struct etimer register_timer;
  static struct etimer tx_timer;


  PROCESS_BEGIN();


  simple_udp_register(
      &udp_conn,
      RANGER_PORT,
      NULL,
      RANGER_PORT,
      ranger_udp_rx
  );


  LOG_INFO(
      "RANGER_RS_WIRE_BOOT "
      "node=%u role=%s mode=%u\n",
      (unsigned int)node_id,
      node_id == RANGER_GM_ID
          ? "GM"
          : "MEMBER",
      (unsigned int)RANGER_RS_WIRE_MODE
  );


  LOG_INFO(
      "RANGER_RS_WIRE_MODE "
      "mode=%u payload=%u shard=%u "
      "packet=%u k=%u n=%u\n",
      (unsigned int)RANGER_RS_WIRE_MODE,
      (unsigned int)RANGER_PAYLOAD_BYTES,
      (unsigned int)RANGER_SHARD_BYTES,
      (unsigned int)RANGER_RS_PACKET_BYTES,
      (unsigned int)RANGER_RS_K,
      (unsigned int)RANGER_RS_N
  );


  if(node_id == RANGER_GM_ID) {

    NETSTACK_ROUTING
        .root_start();


    LOG_INFO(
        "RANGER_RS_WIRE_ROOT_START "
        "node=%u\n",
        (unsigned int)node_id
    );

  } else {

    etimer_set(
        &register_timer,
        FIRST_REGISTER_DELAY
    );
  }


  while(1) {

    PROCESS_YIELD();


    if(node_id == RANGER_GM_ID) {

      if(
          ev == PROCESS_EVENT_POLL &&
          registered_count
              == RANGER_MEMBER_COUNT &&
          !rekey_scheduled
      ) {
        int encode_rc;


        rekey_scheduled = 1u;

        current_epoch = 1u;

        next_target =
            RANGER_FIRST_MEMBER_ID;

        next_shard = 0u;

        tx_phase = 1u;


        encode_rc =
            ranger_rs_encode(
                RANGER_RS_K,
                RANGER_RS_N,
                ranger_payload,
                RANGER_PAYLOAD_BYTES,
                encoded_shards,
                RANGER_SHARD_BYTES
            );


        if(encode_rc != 0) {

          LOG_ERR(
              "RANGER_RS_WIRE_ENCODE_FAIL "
              "rc=%d mode=%u\n",
              encode_rc,
              (unsigned int)RANGER_RS_WIRE_MODE
          );

        } else {

          LOG_INFO(
              "RANGER_RS_WIRE_ENCODE_PASS "
              "mode=%u k=%u n=%u\n",
              (unsigned int)RANGER_RS_WIRE_MODE,
              (unsigned int)RANGER_RS_K,
              (unsigned int)RANGER_RS_N
          );


          etimer_set(
              &tx_timer,
              FRAGMENT_SPACING
          );
        }
      }


      if(
          ev == PROCESS_EVENT_TIMER &&
          data == &tx_timer &&
          tx_phase == 1u
      ) {
        uint8_t send_mask =
            ranger_send_mask(
                next_target
            );


        if(
            (
                send_mask
                & (
                    (uint8_t)(
                        1u << next_shard
                    )
                )
            )
            != 0u
        ) {

          ranger_send_fragment(
              next_target,
              next_shard
          );

        } else {

          LOG_INFO(
              "RANGER_RS_WIRE_DROP "
              "target=%u shard=%u "
              "mode=%u\n",
              (unsigned int)next_target,
              (unsigned int)next_shard,
              (unsigned int)RANGER_RS_WIRE_MODE
          );
        }


        next_shard++;


        if(
            next_shard
                >= RANGER_RS_N
        ) {
          next_shard = 0u;
          next_target++;
        }


        if(
            next_target
                <= RANGER_LAST_MEMBER_ID
        ) {

          etimer_reset_with_new_interval(
              &tx_timer,
              FRAGMENT_SPACING
          );

        } else {

          tx_phase = 2u;

          next_target =
              RANGER_FIRST_MEMBER_ID;


          LOG_INFO(
              "RANGER_RS_WIRE_ALL_SHARDS_SENT "
              "mode=%u\n",
              (unsigned int)RANGER_RS_WIRE_MODE
          );


          etimer_set(
              &tx_timer,
              FINALIZE_SETTLE
          );
        }
      }


      if(
          ev == PROCESS_EVENT_TIMER &&
          data == &tx_timer &&
          tx_phase == 2u
      ) {

        ranger_send_finalize(
            next_target
        );


        next_target++;


        if(
            next_target
                <= RANGER_LAST_MEMBER_ID
        ) {

          etimer_reset_with_new_interval(
              &tx_timer,
              FINALIZE_SPACING
          );

        } else {

          tx_phase = 3u;


          LOG_INFO(
              "RANGER_RS_WIRE_ALL_FINALIZED "
              "mode=%u\n",
              (unsigned int)RANGER_RS_WIRE_MODE
          );
        }
      }

    } else {

      if(
          ev == PROCESS_EVENT_TIMER &&
          data == &register_timer &&
          !member_done
      ) {

        ranger_send_register();


        etimer_reset_with_new_interval(
            &register_timer,
            REGISTER_INTERVAL
        );
      }
    }
  }


  PROCESS_END();
}
