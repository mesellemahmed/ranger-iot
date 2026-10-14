# Wireless broadcast radio accounting

STEP 5E.0 separates receiver/link delivery attempts from sender-side radio
emissions.

Legacy metrics remain available for backward compatibility:

- `physical_transmissions`: receiver/link attempts
- `manager_transmissions`: manager receiver/link attempts
- `bytes_sent`: bytes multiplied by receiver/link attempts

New explicit metrics are:

- `link_attempts`
- `link_bytes_attempted`
- `radio_transmissions`
- `manager_radio_transmissions`
- `radio_bytes_sent`

For unicast, one link attempt equals one radio emission. For broadcast, one
radio emission may generate several receiver/link attempts. Loss remains
receiver-specific, so one broadcast can succeed at some neighbors and fail at
others.

This remains a deterministic graph-level wireless broadcast model. It does not
model CSMA/CA, collisions, interference, capture, duty cycling, RSSI/LQI, or
full IEEE 802.15.4 PHY/MAC timing.
