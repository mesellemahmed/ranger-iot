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

#include "sys/etimer.h"
#include "sys/log.h"
#include "sys/node-id.h"

#include <stdint.h>

#define LOG_MODULE "RANGER-RPL"
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
  return (ranger_loss_hash(target, fragment_index) % 10000UL)
         < (uint32_t)RANGER_LOSS_BP;
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

  if(update_received || epoch < current_epoch) {
    return;
  }

  fragment_bit = (uint8_t)(1u << fragment_index);

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

  if(received_fragment_count < RANGER_CODING_K) {
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

  default:
    break;
  }
}


PROCESS_THREAD(ranger_rpl_process, ev, data)
{
  static struct etimer register_timer;
  static struct etimer rekey_timer;
#if RANGER_CAMPAIGN_MODE
  static struct etimer result_timer;
#endif
  static uint8_t update[9];

  PROCESS_BEGIN();

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

    if(node_id == RANGER_GM_ID) {
      if(ev == PROCESS_EVENT_POLL &&
         registered_count == RANGER_MEMBER_COUNT &&
         !rekey_scheduled) {
        rekey_scheduled = 1;
        current_epoch = 1;
        next_rekey_target = RANGER_FIRST_MEMBER_ID;
        next_fragment_index = 0;

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

        etimer_set(&rekey_timer, FRAGMENT_SPACING);
      }

      if(ev == PROCESS_EVENT_TIMER &&
         data == &rekey_timer &&
         rekey_scheduled &&
         next_rekey_target <= RANGER_LAST_MEMBER_ID) {
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

        if(ranger_should_drop(target, next_fragment_index)) {
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

        if(next_fragment_index >= RANGER_CODING_N) {
          next_fragment_index = 0;
          next_rekey_target++;
        }

        if(next_rekey_target <= RANGER_LAST_MEMBER_ID) {
          etimer_reset_with_new_interval(&rekey_timer, FRAGMENT_SPACING);
        } else {
          LOG_INFO(
              "RANGER_CODED_ALL_SENT group=%u epoch=%u targets=%u k=%u n=%u\n",
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
      if(ev == PROCESS_EVENT_TIMER && data == &register_timer) {
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
