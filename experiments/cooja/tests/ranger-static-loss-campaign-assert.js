TIMEOUT(600000, log.log("RANGER_LOSS_ASSERT_TIMEOUT\\n"); log.testFailed());

var registered = {};
var reconstructedMask = 0;
var revokedReconstructed = false;

while (true) {
  YIELD();

  var reg =
    msg.match(/RANGER_RPL_REGISTER node=([0-9]+) registered=/);

  if (reg) {
    registered[parseInt(reg[1])] = true;
  }

  var rec =
    msg.match(/RANGER_CODED_RECONSTRUCT node=([0-9]+).*epoch=1/);

  if (rec) {
    var node = parseInt(rec[1]);

    if (node === 8) {
      revokedReconstructed = true;
    } else if (node >= 2 && node <= 7) {
      reconstructedMask |= (1 << node);
    }
  }

  var done = msg.match(
    /RANGER_LOSS_DONE expected_mask=([0-9]+) actual_mask=([0-9]+) reconstructed=([0-9]+) reports=([0-9]+) rejected=([0-9]+) k=([0-9]+) n=([0-9]+) loss_bp=([0-9]+) seed=([0-9]+)/
  );

  if (done) {
    var expectedMask = parseInt(done[1]);
    var actualMask = parseInt(done[2]);
    var reconstructedCount = parseInt(done[3]);
    var k = parseInt(done[6]);
    var n = parseInt(done[7]);
    var lossBp = parseInt(done[8]);

    var allRegistered =
      registered[2] &&
      registered[3] &&
      registered[4] &&
      registered[5] &&
      registered[6] &&
      registered[7] &&
      registered[8];

    var validProfile =
      k === 3 &&
      n >= 3 &&
      n <= 5 &&
      lossBp >= 0 &&
      lossBp <= 10000;

    var observedCount = 0;

    for (var nodeId = 2; nodeId <= 7; nodeId++) {
      if ((reconstructedMask & (1 << nodeId)) !== 0) {
        observedCount++;
      }
    }

    var valid =
      allRegistered &&
      validProfile &&
      !revokedReconstructed &&
      expectedMask === actualMask &&
      actualMask === reconstructedMask &&
      reconstructedCount === observedCount;

    if (valid) {
      log.log(
        "RANGER_LOSS_ASSERT_PASS expected_mask=" +
        expectedMask +
        " actual_mask=" +
        actualMask +
        " reconstructed=" +
        reconstructedCount +
        "\n"
      );
      log.testOK();
    } else {
      log.log(
        "RANGER_LOSS_ASSERT_FAIL expected_mask=" +
        expectedMask +
        " actual_mask=" +
        actualMask +
        " observed_mask=" +
        reconstructedMask +
        "\n"
      );
      log.testFailed();
    }
  }
}
