#ifndef PROJECT_CONF_H_
#define PROJECT_CONF_H_

/*
 * STEP 6B.3 uses the default Contiki-NG CSMA + RPL-Lite stack.
 * Keep the route table explicitly large enough for this 8-node experiment.
 */
#define NETSTACK_MAX_ROUTE_ENTRIES 32

#endif /* PROJECT_CONF_H_ */
