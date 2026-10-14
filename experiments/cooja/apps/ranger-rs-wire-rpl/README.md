# RANGER-IoT STEP 7C.3

Isolated byte-level Reed-Solomon wire-validation application.

This application does not replace the historical STEP 7A/7B Cooja
applications.

It validates:

- systematic GF(256), primitive polynomial 0x11D;
- k=3, n=5;
- 16-byte deterministic epoch payload;
- 6-byte RS shards;
- actual shard bytes carried in UDP/RPL packets;
- exact byte-level reconstruction;
- no-loss operation;
- deterministic controlled fragment omission;
- below-k non-reconstruction;
- revoked-member rejection.

`RANGER_RS_WIRE_MODE=0` is no-loss.

`RANGER_RS_WIRE_MODE=1` is deterministic application-level fragment
omission. It is not a radio-loss experiment.
