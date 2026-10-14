TIMEOUT(600000, log.log("RANGER_STATIC_CODED_ASSERT_TIMEOUT\n"); log.testFailed());

var registered = {};
var reconstructed = {};
var rejected = {};
var corePass = false;

while (true) {
  YIELD();

  var matchRegister =
    msg.match(/RANGER_RPL_REGISTER node=([0-9]+) registered=/);

  if (matchRegister) {
    registered[parseInt(matchRegister[1])] = true;
  }

  var matchReconstruct = msg.match(
    /RANGER_CODED_RECONSTRUCT node=([0-9]+) group=1 epoch=1 unique=3 k=3 n=5/
  );

  if (matchReconstruct) {
    reconstructed[parseInt(matchReconstruct[1])] = true;
  }

  var matchReject = msg.match(
    /RANGER_CODED_REJECT node=([0-9]+) group=1 epoch=1 fragment=4 revoked=8/
  );

  if (matchReject) {
    rejected[parseInt(matchReject[1])] = true;
  }

  if (msg.indexOf(
      "RANGER_STATIC_CODED_CORE_PASS epoch=1 registered=7 reconstructed=6 rejected=1 k=3 n=5"
  ) >= 0) {
    corePass = true;
  }

  var allRegistered =
    registered[2] && registered[3] && registered[4] &&
    registered[5] && registered[6] && registered[7] && registered[8];

  var allReconstructed =
    reconstructed[2] && reconstructed[3] && reconstructed[4] &&
    reconstructed[5] && reconstructed[6] && reconstructed[7];

  var revokedRejected = rejected[8];

  if (allRegistered &&
      allReconstructed &&
      revokedRejected &&
      corePass) {
    log.log(
      "RANGER_STATIC_CODED_ASSERT_PASS " +
      "registered=7 reconstructed=6 rejected=1 k=3 n=5\n"
    );
    log.testOK();
  }
}
