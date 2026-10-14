/*
 * RANGER-IoT — STEP 6B.3
 * Scripted multi-hop RPL validation in Contiki-NG/Cooja.
 *
 * Node 1: RPL DAG root / Group Manager.
 * Nodes 2..7: authorized members.
 * Node 8: revoked member.
 *
 * Members first register with the root over RPL. Once all members are
 * registered, the GM unicasts epoch-1 updates to each member. Members return
 * reports to the GM over RPL. This validates end-to-end multi-hop transport
 * before coding, recovery, and adaptive redundancy are introduced.
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
#define MSG_EPOCH_UPDATE 2
#define MSG_REPORT 3

#define STATUS_ACCEPT 1
#define STATUS_REJECT 2

#define REGISTER_INTERVAL (10 * CLOCK_SECOND)
#define FIRST_REGISTER_DELAY (8 * CLOCK_SECOND)
#define REKEY_SPACING (2 * CLOCK_SECOND)

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
static uint8_t update_received;
static uint8_t final_result_printed;
static uint16_t current_epoch;

PROCESS(ranger_rpl_process, "RANGER multi-hop RPL core");
AUTOSTART_PROCESSES(&ranger_rpl_process);


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
handle_epoch_update(const uip_ipaddr_t *sender_addr,
                    const uint8_t *data,
                    uint16_t datalen)
{
  uint16_t epoch;
  uint8_t revoked_id;
  uint8_t status;

  if(node_id == RANGER_GM_ID || datalen != 5) {
    return;
  }

  epoch = ((uint16_t)data[2] << 8) | (uint16_t)data[3];
  revoked_id = data[4];

  if(update_received || epoch <= current_epoch) {
    return;
  }

  update_received = 1;

  if(node_id == revoked_id) {
    status = STATUS_REJECT;

    LOG_INFO(
        "RANGER_RPL_REJECT node=%u epoch=%u revoked=%u\n",
        node_id,
        epoch,
        revoked_id
    );
  } else {
    current_epoch = epoch;
    status = STATUS_ACCEPT;

    LOG_INFO(
        "RANGER_RPL_ACCEPT node=%u epoch=%u revoked=%u\n",
        node_id,
        epoch,
        revoked_id
    );
  }

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

  case MSG_EPOCH_UPDATE:
    handle_epoch_update(sender_addr, data, datalen);
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
  static uint8_t update[5];

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

        LOG_INFO(
            "RANGER_RPL_READY registered=%u/%u epoch=%u revoked=%u\n",
            registered_count,
            RANGER_MEMBER_COUNT,
            current_epoch,
            RANGER_REVOKED_ID
        );

        etimer_set(&rekey_timer, REKEY_SPACING);
      }

      if(ev == PROCESS_EVENT_TIMER &&
         data == &rekey_timer &&
         rekey_scheduled &&
         next_rekey_target <= RANGER_LAST_MEMBER_ID) {
        uint8_t target = next_rekey_target;

        update[0] = MSG_EPOCH_UPDATE;
        update[1] = RANGER_GM_ID;
        update[2] = (uint8_t)(current_epoch >> 8);
        update[3] = (uint8_t)(current_epoch & 0xff);
        update[4] = RANGER_REVOKED_ID;

        simple_udp_sendto(
            &udp_conn,
            update,
            sizeof(update),
            &member_addr[target]
        );

        LOG_INFO(
            "RANGER_RPL_REKEY_SENT target=%u epoch=%u revoked=%u\n",
            target,
            current_epoch,
            RANGER_REVOKED_ID
        );

        next_rekey_target++;

        if(next_rekey_target <= RANGER_LAST_MEMBER_ID) {
          etimer_reset_with_new_interval(&rekey_timer, REKEY_SPACING);
        } else {
          LOG_INFO(
              "RANGER_RPL_REKEY_ALL_SENT epoch=%u targets=%u\n",
              current_epoch,
              RANGER_MEMBER_COUNT
          );
        }
      }
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
