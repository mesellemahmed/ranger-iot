/*
 * RANGER-IoT
 * STEP 6B.1 — Functional rekey core for Contiki-NG / Cooja
 *
 * Scientific purpose:
 *   Validate epoch transition and revocation semantics before adding
 *   multi-hop dissemination, coding, recovery, or cryptography.
 *
 * Topology:
 *   node 1 : Group Manager
 *   nodes 2-4 : authorized members
 *   node 5 : revoked member
 *
 * Expected outcome for epoch 1:
 *   nodes 2,3,4 -> ACCEPT
 *   node 5       -> REJECT
 *   node 1       -> RANGER_CORE_PASS
 */

#include "contiki.h"

#include "net/ipv6/simple-udp.h"
#include "net/ipv6/uip.h"

#include "sys/etimer.h"
#include "sys/log.h"
#include "sys/node-id.h"

#include <stdint.h>
#include <string.h>


#define LOG_MODULE "RANGER"
#define LOG_LEVEL LOG_LEVEL_INFO


#define RANGER_PORT 4242

#define RANGER_GM_ID 1
#define RANGER_REVOKED_ID 5

#define RANGER_FIRST_MEMBER_ID 2
#define RANGER_LAST_MEMBER_ID 5
#define RANGER_MEMBER_COUNT 4

#define RANGER_MSG_EPOCH_UPDATE 1
#define RANGER_MSG_REPORT 2

#define RANGER_STATUS_ACCEPT 1
#define RANGER_STATUS_REJECT 2


static struct simple_udp_connection udp_conn;

static uint16_t current_epoch = 0;

static uint8_t report_seen[6];
static uint8_t accepted_count = 0;
static uint8_t rejected_count = 0;
static uint8_t report_count = 0;
static uint8_t final_result_printed = 0;


PROCESS(
    ranger_core_process,
    "RANGER functional rekey core"
);

AUTOSTART_PROCESSES(
    &ranger_core_process
);


static void
send_report(
    const uip_ipaddr_t *gm_addr,
    uint16_t epoch,
    uint8_t status
)
{
  uint8_t packet[5];

  packet[0] = RANGER_MSG_REPORT;
  packet[1] = (uint8_t)node_id;
  packet[2] = (uint8_t)(epoch >> 8);
  packet[3] = (uint8_t)(epoch & 0xff);
  packet[4] = status;

  simple_udp_sendto(
      &udp_conn,
      packet,
      sizeof(packet),
      gm_addr
  );
}


static void
handle_epoch_update(
    const uip_ipaddr_t *sender_addr,
    const uint8_t *data,
    uint16_t datalen
)
{
  uint16_t epoch;
  uint8_t revoked_id;
  uint8_t status;

  if(datalen != 5) {
    LOG_WARN(
        "RANGER_INVALID_UPDATE node=%u len=%u\n",
        node_id,
        datalen
    );
    return;
  }

  epoch =
      ((uint16_t)data[2] << 8)
      | (uint16_t)data[3];

  revoked_id = data[4];

  if(node_id == RANGER_GM_ID) {
    return;
  }

  if(epoch <= current_epoch) {
    LOG_INFO(
        "RANGER_DUPLICATE node=%u epoch=%u\n",
        node_id,
        epoch
    );
    return;
  }

  if(node_id == revoked_id) {

    status = RANGER_STATUS_REJECT;

    LOG_INFO(
        "RANGER_REJECT "
        "node=%u epoch=%u revoked=%u\n",
        node_id,
        epoch,
        revoked_id
    );

  } else {

    current_epoch = epoch;
    status = RANGER_STATUS_ACCEPT;

    LOG_INFO(
        "RANGER_ACCEPT "
        "node=%u epoch=%u revoked=%u\n",
        node_id,
        epoch,
        revoked_id
    );
  }

  send_report(
      sender_addr,
      epoch,
      status
  );
}


static void
handle_report(
    const uint8_t *data,
    uint16_t datalen
)
{
  uint8_t member_id;
  uint16_t epoch;
  uint8_t status;

  if(node_id != RANGER_GM_ID) {
    return;
  }

  if(datalen != 5) {
    return;
  }

  member_id = data[1];

  epoch =
      ((uint16_t)data[2] << 8)
      | (uint16_t)data[3];

  status = data[4];

  if(
      member_id < RANGER_FIRST_MEMBER_ID
      || member_id > RANGER_LAST_MEMBER_ID
  ) {
    return;
  }

  if(report_seen[member_id]) {
    return;
  }

  report_seen[member_id] = 1;
  report_count++;

  if(status == RANGER_STATUS_ACCEPT) {
    accepted_count++;
  }

  if(status == RANGER_STATUS_REJECT) {
    rejected_count++;
  }

  LOG_INFO(
      "RANGER_REPORT "
      "node=%u epoch=%u status=%u "
      "reports=%u/%u\n",
      member_id,
      epoch,
      status,
      report_count,
      RANGER_MEMBER_COUNT
  );

  if(
      report_count == RANGER_MEMBER_COUNT
      && !final_result_printed
  ) {

    final_result_printed = 1;

    if(
        accepted_count == 3
        && rejected_count == 1
    ) {

      LOG_INFO(
          "RANGER_CORE_PASS "
          "epoch=%u accepted=%u rejected=%u\n",
          epoch,
          accepted_count,
          rejected_count
      );

    } else {

      LOG_ERR(
          "RANGER_CORE_FAIL "
          "epoch=%u accepted=%u rejected=%u\n",
          epoch,
          accepted_count,
          rejected_count
      );
    }
  }
}


static void
udp_rx_callback(
    struct simple_udp_connection *c,
    const uip_ipaddr_t *sender_addr,
    uint16_t sender_port,
    const uip_ipaddr_t *receiver_addr,
    uint16_t receiver_port,
    const uint8_t *data,
    uint16_t datalen
)
{
  uint8_t message_type;

  (void)c;
  (void)sender_port;
  (void)receiver_addr;
  (void)receiver_port;

  if(datalen < 1) {
    return;
  }

  message_type = data[0];

  if(message_type == RANGER_MSG_EPOCH_UPDATE) {

    handle_epoch_update(
        sender_addr,
        data,
        datalen
    );

  } else if(
      message_type == RANGER_MSG_REPORT
  ) {

    handle_report(
        data,
        datalen
    );
  }
}


PROCESS_THREAD(
    ranger_core_process,
    ev,
    data
)
{
  static struct etimer timer;
  static uip_ipaddr_t multicast_addr;
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
      "RANGER_BOOT node=%u role=%s epoch=%u\n",
      node_id,
      node_id == RANGER_GM_ID
          ? "GM"
          : "MEMBER",
      current_epoch
  );

  if(node_id == RANGER_GM_ID) {

    /*
     * Give all Cooja motes time to boot before
     * the first rekey operation.
     */
    etimer_set(
        &timer,
        10 * CLOCK_SECOND
    );

    PROCESS_WAIT_EVENT_UNTIL(
        etimer_expired(&timer)
    );

    /*
     * IPv6 link-local all-nodes multicast:
     * ff02::1
     *
     * STEP 6B.1 intentionally keeps every mote
     * within one radio hop.
     */
    uip_ip6addr(
        &multicast_addr,
        0xff02,
        0,
        0,
        0,
        0,
        0,
        0,
        1
    );

    current_epoch = 1;

    update[0] = RANGER_MSG_EPOCH_UPDATE;
    update[1] = RANGER_GM_ID;
    update[2] = 0;
    update[3] = 1;
    update[4] = RANGER_REVOKED_ID;

    LOG_INFO(
        "RANGER_REKEY_START "
        "epoch=1 revoked=%u\n",
        RANGER_REVOKED_ID
    );

    simple_udp_sendto(
        &udp_conn,
        update,
        sizeof(update),
        &multicast_addr
    );

    LOG_INFO(
        "RANGER_REKEY_SENT "
        "epoch=1 revoked=%u\n",
        RANGER_REVOKED_ID
    );
  }

  PROCESS_END();
}
