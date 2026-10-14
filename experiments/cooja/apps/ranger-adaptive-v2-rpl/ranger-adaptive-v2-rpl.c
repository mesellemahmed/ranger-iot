/*
 * RANGER-IoT — STEP 6C.1
 * Static 3-of-5 coded epoch reconstruction over validated multi-hop RPL.
 *
 * Node 1: RPL DAG root / Group Manager.
 * Nodes 2..7: authorized members.
 * Node 8: revoked member.
 *
 * This stage mirrors the simulator's ideal k-of-n abstraction: fragment
 * identity is transported and any three distinct fragments reconstruct the
 * epoch. No Reed-Solomon byte arithmetic, recovery, or adaptation is modeled.
 */

#include "contiki.h"

#include "net/ipv6/simple-udp.h"
#include "net/netstack.h"
#include "net/routing/routing.h"
#include "net/routing/rpl-lite/rpl-neighbor.h"
#include "net/linkaddr.h"

#include "sys/etimer.h"
#include "sys/log.h"
#include "sys/node-id.h"

#include <stdint.h>

#define LOG_MODULE "RANGER-ADAPTIVE-V2"
#define LOG_LEVEL LOG_LEVEL_INFO

#define RANGER_PORT 4243

#define RANGER_GM_ID 1
#define RANGER_FIRST_MEMBER_ID 2
#define RANGER_LAST_MEMBER_ID 8
#define RANGER_REVOKED_ID 8
#define RANGER_MEMBER_COUNT 7

#define MSG_REGISTER 1
#define MSG_CODED_FRAGMENT 2
#define MSG_REPORT 3
#define MSG_RECOVERY_REQUEST 4
#define MSG_RECOVERY_FRAGMENT 5
#define MSG_ADAPTIVE_NACK 7
#define MSG_RECOVERY_EPOCH_PRIME 6

#define STATUS_ACCEPT 1
#define STATUS_REJECT 2

#define RANGER_GROUP_ID 1

#ifndef RANGER_CODING_K
#define RANGER_CODING_K 3
#endif

#ifndef RANGER_CODING_N
#define RANGER_CODING_N 5
#endif

#ifndef RANGER_LOSS_BP
#define RANGER_LOSS_BP 0
#endif

#ifndef RANGER_LOSS_SEED
#define RANGER_LOSS_SEED 1
#endif

#ifndef RANGER_CAMPAIGN_MODE
#define RANGER_CAMPAIGN_MODE 0
#endif

#if RANGER_CODING_K < 1
#error "RANGER_CODING_K must be >= 1"
#endif

#if RANGER_CODING_N < RANGER_CODING_K
#error "RANGER_CODING_N must be >= RANGER_CODING_K"
#endif

#if RANGER_CODING_N > 8
#error "RANGER_CODING_N must be <= 8"
#endif

#if RANGER_LOSS_BP > 10000
#error "RANGER_LOSS_BP must be <= 10000"
#endif

#define REGISTER_INTERVAL (10 * CLOCK_SECOND)
#define FIRST_REGISTER_DELAY (8 * CLOCK_SECOND)
#define FRAGMENT_SPACING (CLOCK_SECOND)

#ifndef RANGER_RECOVERY_SMOKE
#define RANGER_RECOVERY_SMOKE 0
#endif

#ifndef RANGER_RECOVERY_CASCADE_SMOKE
#define RANGER_RECOVERY_CASCADE_SMOKE 0
#endif

#define RANGER_RECOVERY_REQUEST_BYTES 24
#define RANGER_RECOVERY_INITIAL_DELAY (40 * CLOCK_SECOND)
#define RANGER_RECOVERY_ROUND_GAP (8 * CLOCK_SECOND)
#define RANGER_RECOVERY_MAX_ROUNDS 2

#ifndef RANGER_ADAPTIVE_NACK_SMOKE
#define RANGER_ADAPTIVE_NACK_SMOKE 0
#endif

#define RANGER_ADAPTIVE_NACK_BYTES 16

/*
 * Initial k dissemination needs roughly 21 s
 * on the current 7-target / k=3 oracle.
 *
 * NACK starts after initial dissemination but
 * before the existing Recovery timer (~40 s).
 */
#define RANGER_ADAPTIVE_NACK_INITIAL_DELAY \
    (30 * CLOCK_SECOND)

#define RANGER_ADAPTIVE_NACK_ROUND_GAP \
    (20 * CLOCK_SECOND)

#define RANGER_ADAPTIVE_NACK_MAX_ROUNDS \
    (RANGER_CODING_N - RANGER_CODING_K)

#define RANGER_RECOVERY_EPOCH_PRIME_BYTES 6

/*
 * The control-plane prime is sent while the
 * post-bootstrap radio is still healthy.
 *
 * Five seconds are left for the routed control
 * messages to settle before RANGER_CODED_READY.
 */
#define RANGER_RECOVERY_EPOCH_PRIME_SETTLE     (5 * CLOCK_SECOND)

/*
 * Recovery starts only after the initial 3-of-5
 * dissemination has had time to drain.
 *
 * This mirrors the Python Recovery model, where
 * recovery rounds begin after the initial flood.
 */
#define RANGER_RECOVERY_PRIMED_DELAY     (48 * CLOCK_SECOND)

static struct simple_udp_connection udp_conn;

static uip_ipaddr_t member_addr[RANGER_LAST_MEMBER_ID + 1];
static uint8_t member_registered[RANGER_LAST_MEMBER_ID + 1];
static uint8_t report_seen[RANGER_LAST_MEMBER_ID + 1];

static uint8_t registered_count;
static uint8_t accepted_count;
static uint8_t rejected_count;
static uint8_t report_count;

static uint8_t rekey_scheduled;
static uint8_t next_rekey_target;
static uint8_t next_fragment_index;
static uint8_t update_received;
static uint8_t received_fragment_mask;
static uint8_t received_fragment_count;

static uint16_t pending_epoch;

static uint8_t recovery_epoch_primed;

static uint8_t recovery_arm_requested;
static uint8_t recovery_timer_armed;
static uint8_t recovery_round;

/*
 * Adaptive feedback state.
 */
static uip_ipaddr_t adaptive_parent_addr;
static uint8_t adaptive_parent_id;
static uint8_t adaptive_parent_valid;

static uint8_t adaptive_nack_round;
static uint8_t adaptive_nack_timer_armed;

/*
 * GM-side idempotence:
 * one released parity fragment per round_id.
 */
static uint16_t adaptive_released_round_mask;
static uint8_t final_result_printed;
#if RANGER_CAMPAIGN_MODE
static uint8_t campaign_result_printed;
#endif
static uint8_t planned_delivery_count[RANGER_LAST_MEMBER_ID + 1];
static uint16_t accepted_mask;
#if RANGER_CAMPAIGN_MODE
static uint16_t expected_reconstructed_mask;
#endif
static uint16_t current_epoch;

/*
 * One-hop Recovery peers learned while the
 * RPL topology is healthy.
 *
 * Recovery packets still traverse the normal
 * Contiki-NG radio/network stack and therefore
 * remain subject to the active UDGM conditions.
 */
static uip_ipaddr_t
recovery_neighbor_addr[
    RANGER_LAST_MEMBER_ID + 1
];

static uint16_t recovery_neighbor_mask;


static void
ranger_log_neighbor_census(void)
{
  rpl_nbr_t *nbr;
  uint8_t count = 0;

  LOG_INFO(
      "RANGER_NEIGHBOR_SELF node=%u lladdr=",
      node_id
  );
  LOG_INFO_LLADDR(&linkaddr_node_addr);
  LOG_INFO_("\n");

  for(nbr = nbr_table_head(rpl_neighbors);
      nbr != NULL;
      nbr = nbr_table_next(rpl_neighbors, nbr)) {
    const linkaddr_t *lladdr =
        rpl_neighbor_get_lladdr(nbr);
    const uip_ipaddr_t *ipaddr =
        rpl_neighbor_get_ipaddr(nbr);

    LOG_INFO(
        "RANGER_NEIGHBOR_ENTRY node=%u lladdr=",
        node_id
    );
    LOG_INFO_LLADDR(lladdr);
    LOG_INFO_(" ip=");
    LOG_INFO_6ADDR(ipaddr);
    LOG_INFO_("\n");

    count++;
  }

  LOG_INFO(
      "RANGER_NEIGHBOR_SUMMARY node=%u count=%u\n",
      node_id,
      count
  );
}


PROCESS(ranger_rpl_process, "RANGER multi-hop RPL core");
AUTOSTART_PROCESSES(&ranger_rpl_process);


static uint32_t
ranger_loss_hash(uint8_t target, uint8_t fragment_index)
{
  uint32_t x = (uint32_t)RANGER_LOSS_SEED;

  x ^= (uint32_t)target * 0x9e37UL;
  x ^= (uint32_t)(fragment_index + 1u) * 0x85ebUL;

  x ^= x << 13;
  x ^= x >> 17;
  x ^= x << 5;

  return x;
}


static uint8_t
ranger_should_drop(uint8_t target, uint8_t fragment_index)
{
#if RANGER_ADAPTIVE_NACK_SMOKE
  /*
   * Controlled Adaptive oracle:
   * node 7 misses exactly initial fragment 2.
   *
   * With k=3, node 7 therefore remains at 2/3
   * until the first adaptive parity fragment.
   */
  if(target == 7 &&
     fragment_index == 2) {
    return 1;
  }
#endif

  return (ranger_loss_hash(target, fragment_index) % 10000UL)
         < (uint32_t)RANGER_LOSS_BP;
}



static uint8_t
ranger_recovery_smoke_should_drop(
    uint8_t target,
    uint8_t fragment_index)
{
#if RANGER_RECOVERY_CASCADE_SMOKE
  /*
   * Controlled two-round cascade:
   *
   * node 6 starts with fragments {0,1}
   * node 7 starts with fragments {0,1}
   *
   * Node 5 remains fully populated.
   * Node 8 remains revoked.
   */
  return
      (target == 6 ||
       target == 7) &&
      fragment_index >= 2;

#elif RANGER_RECOVERY_SMOKE
  /*
   * Controlled one-hop Recovery oracle:
   * node 4 receives only fragments {0,1}.
   */
  return target == 4 &&
         fragment_index >= 2;

#else
  (void)target;
  (void)fragment_index;
  return 0;
#endif
}


static clock_time_t
ranger_recovery_initial_delay(void)
{
#if RANGER_RECOVERY_CASCADE_SMOKE
  /*
   * Controlled causal ordering:
   *
   * node 7 round 1 occurs first while node 6
   * is still stale.
   *
   * node 6 then performs round 1 and is repaired
   * by node 5.
   *
   * node 7 subsequently performs round 2 and can
   * now be repaired by the newly recovered node 6.
   */
  if(node_id == 6) {
    return 47 * CLOCK_SECOND;
  }

  if(node_id == 7) {
    return 40 * CLOCK_SECOND;
  }
#endif

  return RANGER_RECOVERY_INITIAL_DELAY;
}


static clock_time_t
ranger_recovery_arm_delay(void)
{
  if(recovery_epoch_primed) {
    return
        RANGER_RECOVERY_PRIMED_DELAY;
  }

  return ranger_recovery_initial_delay();
}


static uint8_t
ranger_neighbor_id(rpl_nbr_t *nbr)
{
  const linkaddr_t *lladdr;

  if(nbr == NULL) {
    return 0;
  }

  lladdr =
      rpl_neighbor_get_lladdr(nbr);

  if(lladdr == NULL) {
    return 0;
  }

  /*
   * STEP 6D.1B proved the Cooja LLADDR mapping:
   * mote N ends with byte N.
   */
  return lladdr->u8[
      LINKADDR_SIZE - 1
  ];
}


static uint8_t
ranger_is_authorized_recovery_node(
    uint8_t id)
{
  return id == RANGER_GM_ID ||
         (
           id >= RANGER_FIRST_MEMBER_ID &&
           id < RANGER_REVOKED_ID
         );
}


static void
ranger_cache_recovery_neighbors(void)
{
  rpl_nbr_t *nbr;

  for(
      nbr = nbr_table_head(
          rpl_neighbors
      );
      nbr != NULL;
      nbr = nbr_table_next(
          rpl_neighbors,
          nbr
      )
  ) {
    uint8_t neighbor_id =
        ranger_neighbor_id(nbr);

    const uip_ipaddr_t *neighbor_addr;

    uint16_t neighbor_bit;

    if(
        neighbor_id == node_id ||
        !ranger_is_authorized_recovery_node(
            neighbor_id
        )
    ) {
      continue;
    }

    neighbor_addr =
        rpl_neighbor_get_ipaddr(nbr);

    if(neighbor_addr == NULL) {
      continue;
    }

    neighbor_bit =
        (uint16_t)(
            1u << neighbor_id
        );

    uip_ipaddr_copy(
        &recovery_neighbor_addr[
            neighbor_id
        ],
        neighbor_addr
    );

    if(
        (
          recovery_neighbor_mask &
          neighbor_bit
        ) == 0
    ) {
      recovery_neighbor_mask |=
          neighbor_bit;

      LOG_INFO(
          "RANGER_RECOVERY_CACHE_ADD "
          "node=%u neighbor=%u mask=%u\n",
          node_id,
          neighbor_id,
          recovery_neighbor_mask
      );
    }
  }
}


static uint8_t
ranger_recovery_cached_peer_matches(
    uint8_t peer_id,
    const uip_ipaddr_t *peer_addr)
{
  uint16_t peer_bit;

  if(
      peer_addr == NULL ||
      peer_id >
          RANGER_LAST_MEMBER_ID ||
      !ranger_is_authorized_recovery_node(
          peer_id
      )
  ) {
    return 0;
  }

  peer_bit =
      (uint16_t)(
          1u << peer_id
      );

  if(
      (
        recovery_neighbor_mask &
        peer_bit
      ) == 0
  ) {
    return 0;
  }

  return uip_ipaddr_cmp(
      &recovery_neighbor_addr[
          peer_id
      ],
      peer_addr
  );
}


static void
ranger_cache_adaptive_parent(void)
{
  rpl_nbr_t *parent;

  uint8_t parent_id;

  const uip_ipaddr_t *parent_addr;

  if(node_id == RANGER_GM_ID ||
     node_id == RANGER_REVOKED_ID) {
    return;
  }

  parent =
      rpl_neighbor_select_best();

  if(parent == NULL) {
    return;
  }

  parent_id =
      ranger_neighbor_id(parent);

  parent_addr =
      rpl_neighbor_get_ipaddr(parent);

  if(
      parent_addr == NULL ||
      !ranger_is_authorized_recovery_node(
          parent_id
      ) ||
      parent_id == node_id
  ) {
    return;
  }

  uip_ipaddr_copy(
      &adaptive_parent_addr,
      parent_addr
  );

  if(
      !adaptive_parent_valid ||
      adaptive_parent_id != parent_id
  ) {
    adaptive_parent_id =
        parent_id;

    adaptive_parent_valid = 1;

    LOG_INFO(
        "RANGER_ADAPTIVE_PARENT "
        "node=%u parent=%u\n",
        node_id,
        adaptive_parent_id
    );
  }
}


static uint8_t
ranger_send_adaptive_nack(
    uint16_t epoch)
{
  uint8_t packet[
      RANGER_ADAPTIVE_NACK_BYTES
  ] = {0};

  uint8_t round_id;

  if(
      node_id == RANGER_GM_ID ||
      node_id == RANGER_REVOKED_ID ||
      update_received ||
      epoch == 0 ||
      received_fragment_count >=
          RANGER_CODING_K ||
      !adaptive_parent_valid ||
      adaptive_nack_round >=
          RANGER_ADAPTIVE_NACK_MAX_ROUNDS
  ) {
    return 0;
  }

  adaptive_nack_round++;

  round_id =
      adaptive_nack_round;

  packet[0] =
      MSG_ADAPTIVE_NACK;

  /*
   * Original stale requester.
   */
  packet[1] =
      (uint8_t)node_id;

  packet[2] =
      RANGER_GROUP_ID;

  packet[3] =
      (uint8_t)(epoch >> 8);

  packet[4] =
      (uint8_t)(epoch & 0xff);

  packet[5] =
      round_id;

  packet[6] =
      received_fragment_count;

  /*
   * Immediate hop sender.
   * Relays update this field before forwarding.
   */
  packet[7] =
      (uint8_t)node_id;

  simple_udp_sendto(
      &udp_conn,
      packet,
      sizeof(packet),
      &adaptive_parent_addr
  );

  LOG_INFO(
      "RANGER_ADAPTIVE_NACK_SOURCE "
      "requester=%u parent=%u "
      "round=%u epoch=%u unique=%u "
      "bytes=%u\n",
      node_id,
      adaptive_parent_id,
      round_id,
      epoch,
      received_fragment_count,
      (unsigned)sizeof(packet)
  );

  return 1;
}


static void
ranger_release_adaptive_parity(
    uint16_t epoch,
    uint8_t round_id,
    uint8_t requester_id)
{
  uint16_t round_bit;

  uint8_t fragment_index;

  uint8_t target;

  uint8_t packet[9] = {0};

  if(
      node_id != RANGER_GM_ID ||
      epoch != current_epoch ||
      round_id < 1 ||
      round_id >
          RANGER_ADAPTIVE_NACK_MAX_ROUNDS
  ) {
    return;
  }

  round_bit =
      (uint16_t)(
          1u << round_id
      );

  if(
      (
        adaptive_released_round_mask &
        round_bit
      ) != 0
  ) {
    LOG_INFO(
        "RANGER_ADAPTIVE_PARITY_ALREADY_RELEASED "
        "requester=%u round=%u epoch=%u\n",
        requester_id,
        round_id,
        epoch
    );

    return;
  }

  fragment_index =
      (uint8_t)(
          RANGER_CODING_K +
          round_id - 1
      );

  if(fragment_index >=
     RANGER_CODING_N) {
    return;
  }

  /*
   * Mark before transmissions:
   * concurrent/duplicate NACKs for the same
   * round cannot trigger a second parity.
   */
  adaptive_released_round_mask |=
      round_bit;

  LOG_INFO(
      "RANGER_ADAPTIVE_PARITY_RELEASE "
      "requester=%u round=%u epoch=%u "
      "fragment=%u\n",
      requester_id,
      round_id,
      epoch,
      fragment_index
  );

  packet[0] =
      MSG_CODED_FRAGMENT;

  packet[1] =
      RANGER_GM_ID;

  packet[2] =
      RANGER_GROUP_ID;

  packet[3] =
      (uint8_t)(epoch >> 8);

  packet[4] =
      (uint8_t)(epoch & 0xff);

  packet[5] =
      RANGER_REVOKED_ID;

  packet[6] =
      fragment_index;

  packet[7] =
      RANGER_CODING_K;

  packet[8] =
      RANGER_CODING_N;

  /*
   * Same dissemination abstraction as the
   * existing Cooja coded-fragment path:
   * one logical parity fragment is sent to
   * every registered target.
   */
  for(
      target = RANGER_FIRST_MEMBER_ID;
      target <= RANGER_LAST_MEMBER_ID;
      target++
  ) {
    simple_udp_sendto(
        &udp_conn,
        packet,
        sizeof(packet),
        &member_addr[target]
    );

    LOG_INFO(
        "RANGER_ADAPTIVE_PARITY_SEND "
        "target=%u requester=%u "
        "round=%u epoch=%u fragment=%u\n",
        target,
        requester_id,
        round_id,
        epoch,
        fragment_index
    );
  }
}


static void
handle_adaptive_nack(
    const uip_ipaddr_t *sender_addr,
    const uint8_t *data,
    uint16_t datalen)
{
  uint8_t requester_id;

  uint8_t group_id;

  uint16_t epoch;

  uint8_t round_id;

  uint8_t unique_received;

  uint8_t hop_sender_id;

  uint8_t packet[
      RANGER_ADAPTIVE_NACK_BYTES
  ];

  uint8_t i;

  if(
      datalen !=
          RANGER_ADAPTIVE_NACK_BYTES
  ) {
    return;
  }

  requester_id =
      data[1];

  group_id =
      data[2];

  epoch =
      ((uint16_t)data[3] << 8) |
      (uint16_t)data[4];

  round_id =
      data[5];

  unique_received =
      data[6];

  hop_sender_id =
      data[7];

  if(
      group_id != RANGER_GROUP_ID ||
      epoch == 0 ||
      round_id < 1 ||
      round_id >
          RANGER_ADAPTIVE_NACK_MAX_ROUNDS ||
      requester_id <
          RANGER_FIRST_MEMBER_ID ||
      requester_id >=
          RANGER_REVOKED_ID ||
      unique_received >=
          RANGER_CODING_K
  ) {
    return;
  }

  /*
   * Every Adaptive control hop must come from
   * a peer learned as one-hop during the healthy
   * bootstrap.
   */
  if(
      !ranger_recovery_cached_peer_matches(
          hop_sender_id,
          sender_addr
      )
  ) {
    return;
  }

  if(node_id == RANGER_GM_ID) {

    if(epoch != current_epoch) {
      return;
    }

    LOG_INFO(
        "RANGER_ADAPTIVE_NACK_GM "
        "requester=%u via=%u "
        "round=%u epoch=%u unique=%u\n",
        requester_id,
        hop_sender_id,
        round_id,
        epoch,
        unique_received
    );

    ranger_release_adaptive_parity(
        epoch,
        round_id,
        requester_id
    );

    return;
  }

  if(
      node_id == RANGER_REVOKED_ID ||
      !adaptive_parent_valid
  ) {
    return;
  }

  /*
   * 6E.1D intentionally forwards every valid
   * NACK. Branch-local duplicate suppression
   * is the next V2 step.
   */
  for(
      i = 0;
      i < RANGER_ADAPTIVE_NACK_BYTES;
      i++
  ) {
    packet[i] = data[i];
  }

  packet[7] =
      (uint8_t)node_id;

  simple_udp_sendto(
      &udp_conn,
      packet,
      sizeof(packet),
      &adaptive_parent_addr
  );

  LOG_INFO(
      "RANGER_ADAPTIVE_NACK_FORWARD "
      "relay=%u requester=%u parent=%u "
      "round=%u epoch=%u\n",
      node_id,
      requester_id,
      adaptive_parent_id,
      round_id,
      epoch
  );
}



#if RANGER_CAMPAIGN_MODE
static uint16_t
ranger_expected_reconstructed_mask(void)
{
  uint16_t mask = 0;
  uint8_t member_id;

  for(member_id = RANGER_FIRST_MEMBER_ID;
      member_id < RANGER_REVOKED_ID;
      member_id++) {
    if(planned_delivery_count[member_id] >= RANGER_CODING_K) {
      mask |= (uint16_t)(1u << member_id);
    }
  }

  return mask;
}
#endif


static uint8_t
ranger_sender_is_root(
    const uip_ipaddr_t *sender_addr)
{
  static uip_ipaddr_t root_addr;

  if(sender_addr == NULL) {
    return 0;
  }

  if(
      !NETSTACK_ROUTING.get_root_ipaddr(
          &root_addr
      )
  ) {
    return 0;
  }

  return uip_ipaddr_cmp(
      &root_addr,
      sender_addr
  );
}


#if !RANGER_RECOVERY_SMOKE && !RANGER_RECOVERY_CASCADE_SMOKE
static void
ranger_send_recovery_epoch_prime(
    uint16_t epoch)
{
  uint8_t target;

  uint8_t packet[
      RANGER_RECOVERY_EPOCH_PRIME_BYTES
  ] = {0};

  packet[0] =
      MSG_RECOVERY_EPOCH_PRIME;

  packet[1] =
      RANGER_GM_ID;

  packet[2] =
      RANGER_GROUP_ID;

  packet[3] =
      (uint8_t)(epoch >> 8);

  packet[4] =
      (uint8_t)(epoch & 0xff);

  packet[5] =
      RANGER_REVOKED_ID;

  for(
      target = RANGER_FIRST_MEMBER_ID;
      target < RANGER_REVOKED_ID;
      target++
  ) {
    simple_udp_sendto(
        &udp_conn,
        packet,
        sizeof(packet),
        &member_addr[target]
    );

    LOG_INFO(
        "RANGER_RECOVERY_EPOCH_SEND "
        "target=%u epoch=%u bytes=%u\n",
        target,
        epoch,
        (unsigned)sizeof(packet)
    );
  }

  LOG_INFO(
      "RANGER_RECOVERY_EPOCH_ALL_SENT "
      "epoch=%u targets=%u bytes=%u\n",
      epoch,
      (unsigned)(
          RANGER_REVOKED_ID -
          RANGER_FIRST_MEMBER_ID
      ),
      (unsigned)(
          (
            RANGER_REVOKED_ID -
            RANGER_FIRST_MEMBER_ID
          ) *
          sizeof(packet)
      )
  );
}
#endif /* normal Recovery only */


static void
send_register(void)
{
  static uip_ipaddr_t root_addr;
  uint8_t packet[2];

  if(!NETSTACK_ROUTING.node_is_reachable()) {
    LOG_INFO("RANGER_RPL_WAIT node=%u reason=not-reachable\n", node_id);
    return;
  }

  if(!NETSTACK_ROUTING.get_root_ipaddr(&root_addr)) {
    LOG_INFO("RANGER_RPL_WAIT node=%u reason=no-root-address\n", node_id);
    return;
  }

  ranger_cache_recovery_neighbors();

  ranger_cache_adaptive_parent();

  packet[0] = MSG_REGISTER;
  packet[1] = (uint8_t)node_id;

  simple_udp_sendto(&udp_conn, packet, sizeof(packet), &root_addr);

  LOG_INFO("RANGER_RPL_REGISTER_SENT node=%u\n", node_id);
}


static void
send_report(const uip_ipaddr_t *root_addr, uint16_t epoch, uint8_t status)
{
  uint8_t packet[5];

  packet[0] = MSG_REPORT;
  packet[1] = (uint8_t)node_id;
  packet[2] = (uint8_t)(epoch >> 8);
  packet[3] = (uint8_t)(epoch & 0xff);
  packet[4] = status;

  simple_udp_sendto(&udp_conn, packet, sizeof(packet), root_addr);

  LOG_INFO(
      "RANGER_RPL_REPORT_SENT node=%u epoch=%u status=%u\n",
      node_id,
      epoch,
      status
  );
}



static void
ranger_send_report_to_root(
    uint16_t epoch,
    uint8_t status)
{
  static uip_ipaddr_t root_addr;

  if(!NETSTACK_ROUTING.get_root_ipaddr(
         &root_addr)) {
    LOG_WARN(
        "RANGER_RECOVERY_REPORT_SKIP "
        "node=%u reason=no-root epoch=%u\n",
        node_id,
        epoch
    );
    return;
  }

  send_report(
      &root_addr,
      epoch,
      status
  );
}


static void
ranger_start_recovery_round(
    uint16_t epoch)
{
  uint8_t neighbor_id;

  uint8_t packet[
      RANGER_RECOVERY_REQUEST_BYTES
  ] = {0};

  uint8_t needed;
  uint8_t request_count = 0;

  if(node_id == RANGER_GM_ID ||
     node_id == RANGER_REVOKED_ID ||
     update_received ||
     epoch == 0 ||
     received_fragment_count >=
         RANGER_CODING_K ||
     recovery_round >=
         RANGER_RECOVERY_MAX_ROUNDS) {
    return;
  }

  needed =
      RANGER_CODING_K -
      received_fragment_count;

  recovery_round++;

  packet[0] = MSG_RECOVERY_REQUEST;
  packet[1] = (uint8_t)node_id;
  packet[2] = RANGER_GROUP_ID;
  packet[3] =
      (uint8_t)(epoch >> 8);
  packet[4] =
      (uint8_t)(epoch & 0xff);
  packet[5] =
      received_fragment_mask;
  packet[6] = needed;

  for(
      neighbor_id = RANGER_GM_ID;
      neighbor_id < RANGER_REVOKED_ID;
      neighbor_id++
  ) {
    uint16_t neighbor_bit =
        (uint16_t)(
            1u << neighbor_id
        );

    if(
        (
          recovery_neighbor_mask &
          neighbor_bit
        ) == 0
    ) {
      continue;
    }

    simple_udp_sendto(
        &udp_conn,
        packet,
        sizeof(packet),
        &recovery_neighbor_addr[
            neighbor_id
        ]
    );

    request_count++;

    LOG_INFO(
        "RANGER_RECOVERY_REQUEST "
        "node=%u neighbor=%u round=%u "
        "epoch=%u mask=%u needed=%u "
        "bytes=%u\n",
        node_id,
        neighbor_id,
        recovery_round,
        epoch,
        received_fragment_mask,
        needed,
        (unsigned)sizeof(packet)
    );
  }

  LOG_INFO(
      "RANGER_RECOVERY_CACHE_USE "
      "node=%u round=%u mask=%u "
      "requests=%u\n",
      node_id,
      recovery_round,
      recovery_neighbor_mask,
      request_count
  );

  LOG_INFO(
      "RANGER_RECOVERY_ROUND "
      "node=%u round=%u epoch=%u "
      "requests=%u unique=%u/%u\n",
      node_id,
      recovery_round,
      epoch,
      request_count,
      received_fragment_count,
      RANGER_CODING_K
  );
}


static void
handle_recovery_epoch_prime(
    const uip_ipaddr_t *sender_addr,
    const uint8_t *data,
    uint16_t datalen)
{
  uint8_t sender_id;
  uint8_t group_id;
  uint16_t epoch;
  uint8_t revoked_id;

  if(
      node_id == RANGER_GM_ID ||
      node_id == RANGER_REVOKED_ID ||
      datalen !=
          RANGER_RECOVERY_EPOCH_PRIME_BYTES
  ) {
    return;
  }

  sender_id = data[1];
  group_id = data[2];

  epoch =
      ((uint16_t)data[3] << 8) |
      (uint16_t)data[4];

  revoked_id = data[5];

  if(
      sender_id != RANGER_GM_ID ||
      group_id != RANGER_GROUP_ID ||
      revoked_id != RANGER_REVOKED_ID ||
      epoch < current_epoch ||
      !ranger_sender_is_root(
          sender_addr
      )
  ) {
    return;
  }

  if(
      pending_epoch != 0 &&
      pending_epoch != epoch
  ) {
    return;
  }

  pending_epoch = epoch;
  recovery_epoch_primed = 1;

  LOG_INFO(
      "RANGER_RECOVERY_EPOCH "
      "node=%u epoch=%u unique=%u/%u\n",
      node_id,
      pending_epoch,
      received_fragment_count,
      RANGER_CODING_K
  );

  if(
      !update_received &&
      !recovery_arm_requested &&
      !recovery_timer_armed
  ) {
    recovery_arm_requested = 1;

    process_poll(
        &ranger_rpl_process
    );
  }
}


static void
handle_recovery_request(
    const uip_ipaddr_t *sender_addr,
    const uint8_t *data,
    uint16_t datalen)
{
  uint8_t requester_id;
  uint8_t group_id;
  uint16_t epoch;

  uint8_t requester_mask;
  uint8_t needed;
  uint8_t available_mask;
  uint8_t sent = 0;
  uint8_t fragment_index;

  uint8_t packet[9];

  if(datalen !=
     RANGER_RECOVERY_REQUEST_BYTES) {
    return;
  }

  requester_id = data[1];
  group_id = data[2];

  epoch =
      ((uint16_t)data[3] << 8) |
      (uint16_t)data[4];

  requester_mask = data[5];
  needed = data[6];

  if(group_id != RANGER_GROUP_ID ||
     epoch == 0 ||
     needed == 0 ||
     needed > RANGER_CODING_K ||
     !ranger_is_authorized_recovery_node(
         requester_id
     ) ||
     requester_id == RANGER_GM_ID ||
     node_id == RANGER_REVOKED_ID ||
     !ranger_is_authorized_recovery_node(
         (uint8_t)node_id
     )) {
    return;
  }

  /*
   * The requester must be present in the local
   * RPL-Lite one-hop table. This prevents an
   * arbitrary routed multi-hop node from using
   * the Recovery peer interface.
   */
  if(
      !ranger_recovery_cached_peer_matches(
          requester_id,
          sender_addr
      )
  ) {
    return;
  }

  if(node_id == RANGER_GM_ID) {
    if(current_epoch != epoch) {
      return;
    }

    available_mask =
        (uint8_t)(
            (1u << RANGER_CODING_N)
            - 1u
        );
  } else {
    if(pending_epoch != epoch &&
       current_epoch != epoch) {
      return;
    }

    available_mask =
        received_fragment_mask;
  }

  for(
      fragment_index = 0;
      fragment_index <
          RANGER_CODING_N &&
      sent < needed;
      fragment_index++
  ) {
    uint8_t bit =
        (uint8_t)(
            1u << fragment_index
        );

    if(
        (available_mask & bit) == 0 ||
        (requester_mask & bit) != 0
    ) {
      continue;
    }

    packet[0] =
        MSG_RECOVERY_FRAGMENT;

    packet[1] =
        (uint8_t)node_id;

    packet[2] =
        RANGER_GROUP_ID;

    packet[3] =
        (uint8_t)(epoch >> 8);

    packet[4] =
        (uint8_t)(epoch & 0xff);

    packet[5] =
        RANGER_REVOKED_ID;

    packet[6] =
        fragment_index;

    packet[7] =
        RANGER_CODING_K;

    packet[8] =
        RANGER_CODING_N;

    simple_udp_sendto(
        &udp_conn,
        packet,
        sizeof(packet),
        sender_addr
    );

    sent++;

    LOG_INFO(
        "RANGER_RECOVERY_FRAGMENT_SEND "
        "responder=%u requester=%u "
        "epoch=%u fragment=%u "
        "available_mask=%u\n",
        node_id,
        requester_id,
        epoch,
        fragment_index,
        available_mask
    );
  }
}


static void
handle_recovery_fragment(
    const uip_ipaddr_t *sender_addr,
    const uint8_t *data,
    uint16_t datalen)
{
  uint8_t responder_id;
  uint8_t group_id;
  uint16_t epoch;
  uint8_t revoked_id;
  uint8_t fragment_index;
  uint8_t data_fragments;
  uint8_t total_fragments;
  uint8_t fragment_bit;

  if(node_id == RANGER_GM_ID ||
     node_id == RANGER_REVOKED_ID ||
     datalen != 9) {
    return;
  }

  responder_id = data[1];
  group_id = data[2];

  epoch =
      ((uint16_t)data[3] << 8) |
      (uint16_t)data[4];

  revoked_id = data[5];
  fragment_index = data[6];
  data_fragments = data[7];
  total_fragments = data[8];

  if(
      !ranger_is_authorized_recovery_node(
          responder_id
      ) ||
      responder_id ==
          RANGER_REVOKED_ID ||
      group_id != RANGER_GROUP_ID ||
      revoked_id !=
          RANGER_REVOKED_ID ||
      data_fragments !=
          RANGER_CODING_K ||
      total_fragments !=
          RANGER_CODING_N ||
      fragment_index >=
          RANGER_CODING_N ||
      update_received
  ) {
    return;
  }

  if(
      !ranger_recovery_cached_peer_matches(
          responder_id,
          sender_addr
      )
  ) {
    return;
  }

  if(pending_epoch == 0) {
    pending_epoch = epoch;
  }

  if(epoch != pending_epoch ||
     epoch < current_epoch) {
    return;
  }

  fragment_bit =
      (uint8_t)(
          1u << fragment_index
      );

  if(
      (received_fragment_mask &
       fragment_bit) != 0
  ) {
    return;
  }

  received_fragment_mask |=
      fragment_bit;

  received_fragment_count++;

  LOG_INFO(
      "RANGER_RECOVERY_FRAGMENT "
      "node=%u responder=%u epoch=%u "
      "fragment=%u unique=%u/%u\n",
      node_id,
      responder_id,
      epoch,
      fragment_index,
      received_fragment_count,
      RANGER_CODING_K
  );

  if(
      received_fragment_count <
      RANGER_CODING_K
  ) {
    return;
  }

  update_received = 1;
  current_epoch = epoch;

  LOG_INFO(
      "RANGER_RECOVERY_RECONSTRUCT "
      "node=%u epoch=%u unique=%u "
      "k=%u n=%u round=%u\n",
      node_id,
      epoch,
      received_fragment_count,
      RANGER_CODING_K,
      RANGER_CODING_N,
      recovery_round
  );

  ranger_send_report_to_root(
      epoch,
      STATUS_ACCEPT
  );
}


static void
handle_register(const uip_ipaddr_t *sender_addr,
                const uint8_t *data,
                uint16_t datalen)
{
  uint8_t member_id;

  if(node_id != RANGER_GM_ID || datalen != 2) {
    return;
  }

  member_id = data[1];

  if(member_id < RANGER_FIRST_MEMBER_ID ||
     member_id > RANGER_LAST_MEMBER_ID) {
    return;
  }

  if(!member_registered[member_id]) {
    member_registered[member_id] = 1;
    uip_ipaddr_copy(&member_addr[member_id], sender_addr);
    registered_count++;

    LOG_INFO(
        "RANGER_RPL_REGISTER node=%u registered=%u/%u\n",
        member_id,
        registered_count,
        RANGER_MEMBER_COUNT
    );

    if(registered_count == RANGER_MEMBER_COUNT) {
      process_poll(&ranger_rpl_process);
    }
  } else {
    /* Refresh the address in case the route/address representation changed. */
    uip_ipaddr_copy(&member_addr[member_id], sender_addr);
  }
}


static void
handle_coded_fragment(const uip_ipaddr_t *sender_addr,
                      const uint8_t *data,
                      uint16_t datalen)
{
  uint8_t group_id;
  uint16_t epoch;
  uint8_t revoked_id;
  uint8_t fragment_index;
  uint8_t data_fragments;
  uint8_t total_fragments;
  uint8_t fragment_bit;
  uint8_t status;

  if(node_id == RANGER_GM_ID || datalen != 9) {
    return;
  }

  group_id = data[2];
  epoch = ((uint16_t)data[3] << 8) | (uint16_t)data[4];
  revoked_id = data[5];
  fragment_index = data[6];
  data_fragments = data[7];
  total_fragments = data[8];

  if(group_id != RANGER_GROUP_ID ||
     data_fragments != RANGER_CODING_K ||
     total_fragments != RANGER_CODING_N ||
     fragment_index >= RANGER_CODING_N) {
    return;
  }

  if(node_id == revoked_id) {
    if(update_received || fragment_index != (RANGER_CODING_N - 1)) {
      return;
    }

    update_received = 1;
    status = STATUS_REJECT;

    LOG_INFO(
        "RANGER_CODED_REJECT node=%u group=%u epoch=%u fragment=%u revoked=%u\n",
        node_id,
        group_id,
        epoch,
        fragment_index,
        revoked_id
    );

    LOG_INFO(
        "RANGER_RPL_REJECT node=%u epoch=%u revoked=%u\n",
        node_id,
        epoch,
        revoked_id
    );

    send_report(sender_addr, epoch, status);
    return;
  }

  if(pending_epoch == 0) {
    pending_epoch = epoch;
  }

  if(epoch != pending_epoch ||
     epoch < current_epoch) {
    return;
  }

  if(!recovery_arm_requested &&
     !recovery_timer_armed) {
    recovery_arm_requested = 1;
    process_poll(
        &ranger_rpl_process
    );
  }

  fragment_bit =
      (uint8_t)(1u << fragment_index);

  if((received_fragment_mask & fragment_bit) != 0) {
    LOG_INFO(
        "RANGER_CODED_DUPLICATE node=%u group=%u epoch=%u fragment=%u unique=%u\n",
        node_id,
        group_id,
        epoch,
        fragment_index,
        received_fragment_count
    );
    return;
  }

  received_fragment_mask |= fragment_bit;
  received_fragment_count++;

  LOG_INFO(
      "RANGER_CODED_FRAGMENT node=%u group=%u epoch=%u fragment=%u unique=%u/%u\n",
      node_id,
      group_id,
      epoch,
      fragment_index,
      received_fragment_count,
      RANGER_CODING_K
  );

  /*
   * A member that already reconstructed continues
   * caching distinct same-epoch fragments. This
   * mirrors FragmentAccumulator in the Python model.
   */
  if(update_received) {
    return;
  }

  if(received_fragment_count <
     RANGER_CODING_K) {
    return;
  }

  update_received = 1;
  current_epoch = epoch;
  status = STATUS_ACCEPT;

  LOG_INFO(
      "RANGER_CODED_RECONSTRUCT node=%u group=%u epoch=%u unique=%u k=%u n=%u\n",
      node_id,
      group_id,
      epoch,
      received_fragment_count,
      RANGER_CODING_K,
      RANGER_CODING_N
  );

  LOG_INFO(
      "RANGER_RPL_ACCEPT node=%u epoch=%u revoked=%u\n",
      node_id,
      epoch,
      revoked_id
  );

  send_report(sender_addr, epoch, status);
}


static void
handle_report(const uint8_t *data, uint16_t datalen)
{
  uint8_t member_id;
  uint16_t epoch;
  uint8_t status;

  if(node_id != RANGER_GM_ID || datalen != 5) {
    return;
  }

  member_id = data[1];
  epoch = ((uint16_t)data[2] << 8) | (uint16_t)data[3];
  status = data[4];

  if(member_id < RANGER_FIRST_MEMBER_ID ||
     member_id > RANGER_LAST_MEMBER_ID ||
     report_seen[member_id]) {
    return;
  }

  report_seen[member_id] = 1;
  report_count++;

  if(status == STATUS_ACCEPT) {
    accepted_count++;
    accepted_mask |= (uint16_t)(1u << member_id);
  } else if(status == STATUS_REJECT) {
    rejected_count++;
  }

  LOG_INFO(
      "RANGER_RPL_REPORT node=%u epoch=%u status=%u reports=%u/%u\n",
      member_id,
      epoch,
      status,
      report_count,
      RANGER_MEMBER_COUNT
  );

  if(report_count == RANGER_MEMBER_COUNT && !final_result_printed) {
    final_result_printed = 1;

    if(registered_count == RANGER_MEMBER_COUNT &&
       accepted_count == 6 &&
       rejected_count == 1) {
      LOG_INFO(
          "RANGER_STATIC_CODED_CORE_PASS epoch=%u registered=%u reconstructed=%u rejected=%u k=%u n=%u\n",
          epoch,
          registered_count,
          accepted_count,
          rejected_count,
          RANGER_CODING_K,
          RANGER_CODING_N
      );

      LOG_INFO(
          "RANGER_RPL_CORE_PASS epoch=%u registered=%u accepted=%u rejected=%u\n",
          epoch,
          registered_count,
          accepted_count,
          rejected_count
      );
    } else {
      LOG_ERR(
          "RANGER_RPL_CORE_FAIL epoch=%u registered=%u accepted=%u rejected=%u\n",
          epoch,
          registered_count,
          accepted_count,
          rejected_count
      );
    }
  }
}


static void
udp_rx_callback(struct simple_udp_connection *c,
                const uip_ipaddr_t *sender_addr,
                uint16_t sender_port,
                const uip_ipaddr_t *receiver_addr,
                uint16_t receiver_port,
                const uint8_t *data,
                uint16_t datalen)
{
  (void)c;
  (void)sender_port;
  (void)receiver_addr;
  (void)receiver_port;

  if(datalen < 1) {
    return;
  }

  switch(data[0]) {
  case MSG_REGISTER:
    handle_register(sender_addr, data, datalen);
    break;

  case MSG_CODED_FRAGMENT:
    handle_coded_fragment(sender_addr, data, datalen);
    break;

  case MSG_REPORT:
    handle_report(data, datalen);
    break;

  case MSG_RECOVERY_EPOCH_PRIME:
    handle_recovery_epoch_prime(
        sender_addr,
        data,
        datalen
    );
    break;

  case MSG_RECOVERY_REQUEST:
    handle_recovery_request(
        sender_addr,
        data,
        datalen
    );
    break;

  case MSG_RECOVERY_FRAGMENT:
    handle_recovery_fragment(
        sender_addr,
        data,
        datalen
    );
    break;

  case MSG_ADAPTIVE_NACK:
    handle_adaptive_nack(
        sender_addr,
        data,
        datalen
    );
    break;

  default:
    break;
  }
}


PROCESS_THREAD(ranger_rpl_process, ev, data)
{
  static struct etimer register_timer;
  static struct etimer rekey_timer;
  #if !RANGER_RECOVERY_SMOKE && !RANGER_RECOVERY_CASCADE_SMOKE
  static struct etimer recovery_epoch_prime_timer;
  #endif /* normal Recovery only */
  static struct etimer recovery_timer;
  static struct etimer adaptive_nack_timer;
  static struct etimer neighbor_census_timer;
  static uint8_t neighbor_census_printed;
#if RANGER_CAMPAIGN_MODE
  static struct etimer result_timer;
#endif
  static uint8_t update[9];

  PROCESS_BEGIN();

  etimer_set(
      &neighbor_census_timer,
      180 * CLOCK_SECOND
  );

  simple_udp_register(
      &udp_conn,
      RANGER_PORT,
      NULL,
      RANGER_PORT,
      udp_rx_callback
  );

  LOG_INFO(
      "RANGER_RPL_BOOT node=%u role=%s epoch=%u\n",
      node_id,
      node_id == RANGER_GM_ID ? "GM" : "MEMBER",
      current_epoch
  );

  if(node_id == RANGER_GM_ID) {
    NETSTACK_ROUTING.root_start();

    LOG_INFO("RANGER_RPL_ROOT_START node=%u\n", node_id);
  } else {
    etimer_set(&register_timer, FIRST_REGISTER_DELAY);
  }

  while(1) {
    PROCESS_YIELD();

    if(ev == PROCESS_EVENT_TIMER &&
       data == &neighbor_census_timer &&
       !neighbor_census_printed) {
      neighbor_census_printed = 1;
      ranger_log_neighbor_census();
    }

    if(node_id == RANGER_GM_ID) {
      if(ev == PROCESS_EVENT_POLL &&
         registered_count == RANGER_MEMBER_COUNT &&
         !rekey_scheduled) {
        rekey_scheduled = 1;
        current_epoch = 1;
        next_rekey_target =
            RANGER_FIRST_MEMBER_ID;
        next_fragment_index = 0;

        ranger_cache_recovery_neighbors();

#if RANGER_RECOVERY_SMOKE || \
    RANGER_RECOVERY_CASCADE_SMOKE

        LOG_INFO(
            "RANGER_CODED_READY registered=%u/%u group=%u epoch=%u revoked=%u k=%u n=%u\n",
            registered_count,
            RANGER_MEMBER_COUNT,
            RANGER_GROUP_ID,
            current_epoch,
            RANGER_REVOKED_ID,
            RANGER_CODING_K,
            RANGER_CODING_N
        );

        LOG_INFO(
            "RANGER_RPL_READY registered=%u/%u epoch=%u revoked=%u\n",
            registered_count,
            RANGER_MEMBER_COUNT,
            current_epoch,
            RANGER_REVOKED_ID
        );

        etimer_set(
            &rekey_timer,
            FRAGMENT_SPACING
        );

#else

        ranger_send_recovery_epoch_prime(
            current_epoch
        );

        etimer_set(
            &recovery_epoch_prime_timer,
            RANGER_RECOVERY_EPOCH_PRIME_SETTLE
        );

#endif
      }


#if !RANGER_RECOVERY_SMOKE && \
    !RANGER_RECOVERY_CASCADE_SMOKE

      if(
          ev == PROCESS_EVENT_TIMER &&
          data ==
              &recovery_epoch_prime_timer &&
          rekey_scheduled
      ) {
        LOG_INFO(
            "RANGER_CODED_READY registered=%u/%u group=%u epoch=%u revoked=%u k=%u n=%u\n",
            registered_count,
            RANGER_MEMBER_COUNT,
            RANGER_GROUP_ID,
            current_epoch,
            RANGER_REVOKED_ID,
            RANGER_CODING_K,
            RANGER_CODING_N
        );

        LOG_INFO(
            "RANGER_RPL_READY registered=%u/%u epoch=%u revoked=%u\n",
            registered_count,
            RANGER_MEMBER_COUNT,
            current_epoch,
            RANGER_REVOKED_ID
        );

        etimer_set(
            &rekey_timer,
            FRAGMENT_SPACING
        );
      }

#endif

      if(ev == PROCESS_EVENT_TIMER &&
         data == &rekey_timer &&
         rekey_scheduled &&
         next_rekey_target < RANGER_REVOKED_ID) {
        uint8_t target = next_rekey_target;

        update[0] = MSG_CODED_FRAGMENT;
        update[1] = RANGER_GM_ID;
        update[2] = RANGER_GROUP_ID;
        update[3] = (uint8_t)(current_epoch >> 8);
        update[4] = (uint8_t)(current_epoch & 0xff);
        update[5] = RANGER_REVOKED_ID;
        update[6] = next_fragment_index;
        update[7] = RANGER_CODING_K;
        update[8] = RANGER_CODING_N;

        if(ranger_recovery_smoke_should_drop(
               target,
               next_fragment_index)) {
          LOG_INFO(
              "RANGER_RECOVERY_SMOKE_DROP "
              "target=%u epoch=%u fragment=%u\n",
              target,
              current_epoch,
              next_fragment_index
          );
        } else if(ranger_should_drop(
                      target,
                      next_fragment_index)) {
          LOG_INFO(
              "RANGER_CODED_DROP target=%u group=%u epoch=%u fragment=%u "
              "k=%u n=%u loss_bp=%u seed=%lu\n",
              target,
              RANGER_GROUP_ID,
              current_epoch,
              next_fragment_index,
              RANGER_CODING_K,
              RANGER_CODING_N,
              RANGER_LOSS_BP,
              (unsigned long)RANGER_LOSS_SEED
          );
        } else {
          planned_delivery_count[target]++;

          simple_udp_sendto(
              &udp_conn,
              update,
              sizeof(update),
              &member_addr[target]
          );

          LOG_INFO(
              "RANGER_CODED_SEND target=%u group=%u epoch=%u fragment=%u "
              "k=%u n=%u loss_bp=%u seed=%lu\n",
              target,
              RANGER_GROUP_ID,
              current_epoch,
              next_fragment_index,
              RANGER_CODING_K,
              RANGER_CODING_N,
              RANGER_LOSS_BP,
              (unsigned long)RANGER_LOSS_SEED
          );
        }

        next_fragment_index++;

        if(next_fragment_index >= RANGER_CODING_K) {
          next_fragment_index = 0;
          next_rekey_target++;
        }

        if(next_rekey_target < RANGER_REVOKED_ID) {
          etimer_reset_with_new_interval(&rekey_timer, FRAGMENT_SPACING);
        } else {
          LOG_INFO(
              "RANGER_ADAPTIVE_INITIAL_ALL_SENT group=%u epoch=%u targets=%u k=%u n=%u\n",
              RANGER_GROUP_ID,
              current_epoch,
              RANGER_MEMBER_COUNT,
              RANGER_CODING_K,
              RANGER_CODING_N
          );

          LOG_INFO(
              "RANGER_RPL_REKEY_ALL_SENT epoch=%u targets=%u\n",
              current_epoch,
              RANGER_MEMBER_COUNT
          );

#if RANGER_CAMPAIGN_MODE
          expected_reconstructed_mask =
              ranger_expected_reconstructed_mask();

          etimer_set(&result_timer, 30 * CLOCK_SECOND);
#endif
        }
      }

#if RANGER_CAMPAIGN_MODE
      if(ev == PROCESS_EVENT_TIMER &&
         data == &result_timer &&
         !campaign_result_printed) {
        campaign_result_printed = 1;

        LOG_INFO(
            "RANGER_LOSS_DONE expected_mask=%u actual_mask=%u "
            "reconstructed=%u reports=%u rejected=%u "
            "k=%u n=%u loss_bp=%u seed=%lu\n",
            expected_reconstructed_mask,
            accepted_mask,
            accepted_count,
            report_count,
            rejected_count,
            RANGER_CODING_K,
            RANGER_CODING_N,
            RANGER_LOSS_BP,
            (unsigned long)RANGER_LOSS_SEED
        );
      }
#endif
    } else {
      if(ev == PROCESS_EVENT_POLL &&
         recovery_arm_requested &&
         !adaptive_nack_timer_armed &&
         node_id !=
             RANGER_REVOKED_ID) {

        adaptive_nack_timer_armed = 1;

        etimer_set(
            &adaptive_nack_timer,
            RANGER_ADAPTIVE_NACK_INITIAL_DELAY
        );

        LOG_INFO(
            "RANGER_ADAPTIVE_NACK_ARM "
            "node=%u epoch=%u unique=%u/%u\n",
            node_id,
            pending_epoch,
            received_fragment_count,
            RANGER_CODING_K
        );
      }


      if(ev == PROCESS_EVENT_POLL &&
         recovery_arm_requested &&
         !recovery_timer_armed &&
         node_id !=
             RANGER_REVOKED_ID) {

        recovery_timer_armed = 1;

        etimer_set(
            &recovery_timer,
            ranger_recovery_arm_delay()
        );

        LOG_INFO(
            "RANGER_RECOVERY_ARM "
            "node=%u epoch=%u unique=%u/%u\n",
            node_id,
            pending_epoch,
            received_fragment_count,
            RANGER_CODING_K
        );
      }

      if(ev == PROCESS_EVENT_TIMER &&
         data == &adaptive_nack_timer &&
         adaptive_nack_timer_armed) {

        if(
            !update_received &&
            pending_epoch != 0 &&
            received_fragment_count <
                RANGER_CODING_K &&
            adaptive_nack_round <
                RANGER_ADAPTIVE_NACK_MAX_ROUNDS
        ) {
          uint8_t sent =
              ranger_send_adaptive_nack(
                  pending_epoch
              );

          if(
              sent &&
              !update_received &&
              adaptive_nack_round <
                  RANGER_ADAPTIVE_NACK_MAX_ROUNDS
          ) {
            etimer_set(
                &adaptive_nack_timer,
                RANGER_ADAPTIVE_NACK_ROUND_GAP
            );
          }
        }
      }


      if(ev == PROCESS_EVENT_TIMER &&
         data == &recovery_timer &&
         recovery_timer_armed) {

        if(!update_received &&
           pending_epoch != 0 &&
           recovery_round <
               RANGER_RECOVERY_MAX_ROUNDS) {

          ranger_start_recovery_round(
              pending_epoch
          );

          if(!update_received &&
             recovery_round <
                 RANGER_RECOVERY_MAX_ROUNDS) {

            etimer_set(
                &recovery_timer,
                RANGER_RECOVERY_ROUND_GAP
            );
          }
        }
      }

      if(ev == PROCESS_EVENT_TIMER &&
         data == &register_timer) {
        if(!update_received) {
          send_register();
          etimer_reset_with_new_interval(
              &register_timer,
              REGISTER_INTERVAL
          );
        }
      }
    }
  }

  PROCESS_END();
}
